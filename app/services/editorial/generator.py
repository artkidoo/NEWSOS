"""Phase 3: Editorial Generation Engine.

Orchestrates the full generation lifecycle:

  story cluster -> deterministic research context -> provider call (retry policy)
  -> fact/claim guard -> quality scoring -> persisted draft + provenance
  -> immutable generation audit record

Idempotency: a successful generation for an identical
(cluster, generation_type, provider, model, prompt_version, context_hash)
returns the existing draft instead of re-calling the provider — unless an
explicit regeneration is requested, which ALWAYS creates a new generation
record and never overwrites historical evidence.

This engine generates editorial material ONLY. It never publishes, schedules,
or approves anything; every artifact lands in a review-required state.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.editorial import EditorialDraft, EditorialDraftSource, EditorialGeneration
from app.models.enums import DraftStatus, DraftType, GenerationType, RiskFlag
from app.services.editorial.context import ResearchContext, ResearchContextEngine
from app.services.editorial.fact_guard import FactClaimGuard
from app.services.editorial.providers import (
    AIProviderError,
    EditorialAIProvider,
    GenerationRequest,
    create_provider,
)
from app.services.editorial.quality import QualityAssessment, assess_quality

logger = get_logger("newsroom.editorial.generation")

DEFAULT_HEADLINE_CANDIDATES = 5

SYSTEM_PROMPT_TEMPLATE = (
    "You are the NEWSROOM OS AI Editorial Desk. You synthesize editorial copy ONLY from the "
    "supplied research context. Never fabricate facts, quotations, sources, statistics, people, "
    "organizations, events, locations, or dates. Never imply an unverified claim is confirmed. "
    "Never manufacture corroboration or treat trending score as truth. When evidence conflicts, "
    "preserve the conflict with attribution or explicit uncertainty. Respond ONLY with JSON "
    "matching the requested schema."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GenerationError(Exception):
    """Surface-level generation failure carrying a normalized error code."""

    def __init__(self, message: str, error_code: str = "GENERATION_FAILED", status_hint: int = 502):
        super().__init__(message)
        self.error_code = error_code
        self.status_hint = status_hint


class StoryNotFoundError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class EditorialGenerationService:
    """Application service wrapping the Phase 3 generation lifecycle."""

    def __init__(
        self,
        db: Session,
        provider: EditorialAIProvider | None = None,
        *,
        prompt_version: str | None = None,
        max_headline_candidates: int = DEFAULT_HEADLINE_CANDIDATES,
    ):
        self.db = db
        self.settings = get_settings()
        self.provider = provider if provider is not None else create_provider(self.settings)
        self.prompt_version = prompt_version or self.settings.EDITORIAL_PROMPT_VERSION
        self.max_headline_candidates = max_headline_candidates
        self.context_engine = ResearchContextEngine(db)

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    def generate_headlines(self, story_id: int, *, force: bool = False) -> dict[str, Any]:
        return self._generate(story_id, GenerationType.HEADLINES, "headline_result", force=force)

    def generate_summary(self, story_id: int, *, force: bool = False) -> dict[str, Any]:
        return self._generate(story_id, GenerationType.SUMMARY, "summary_result", force=force)

    def generate_article(self, story_id: int, *, force: bool = False) -> dict[str, Any]:
        return self._generate(story_id, GenerationType.ARTICLE, "article_result", force=force)

    def generate_social(self, story_id: int, *, force: bool = False) -> dict[str, Any]:
        return self._generate(story_id, GenerationType.SOCIAL, "social_result", force=force)

    def generate_package(self, story_id: int, *, force: bool = False) -> dict[str, Any]:
        """One high-level operation producing the complete editorial package.

        Package = 5 headline candidates + summary + article draft + social copy +
        key facts + uncertainties + risk flags + source list + quality breakdown.
        Persisted as one PACKAGE draft whose payload references its own traceable
        generation record and provenance rows.
        """
        context = self._build_context(story_id)
        existing = self._find_idempotent_draft(context, GenerationType.PACKAGE)
        if existing is not None and not force:
            logger.info(
                "generation idempotent hit",
                extra={"story_id": story_id, "type": GenerationType.PACKAGE.value, "draft_id": existing.id},
            )
            return self._package_response(existing, context, reused=True)

        sections: dict[str, Any] = {}
        all_findings: list[dict[str, Any]] = []
        uncertainties: list[str] = []
        key_facts: list[str] = []
        started_total = time.monotonic()

        for gen_type, schema in (
            (GenerationType.HEADLINES, "headline_result"),
            (GenerationType.SUMMARY, "summary_result"),
            (GenerationType.ARTICLE, "article_result"),
            (GenerationType.SOCIAL, "social_result"),
        ):
            outcome = self._run_generation(context, gen_type, schema, persist=False)
            payload = outcome["payload"]
            sections[gen_type.value.lower()] = payload
            all_findings.extend(outcome["guard"].get("findings", []))
            key_facts.extend(payload.get("key_facts", []))
            uncertainties.extend(payload.get("uncertainties", []))

        # Deduplicate while preserving order.
        key_facts = list(dict.fromkeys(key_facts))
        uncertainties = list(dict.fromkeys(uncertainties))

        headline_payload = sections[GenerationType.HEADLINES.value.lower()]
        candidate_list = [headline_payload.get("headline", "")] + list(headline_payload.get("alternate_headlines", []))
        candidate_list = [c for c in candidate_list if c][: self.max_headline_candidates]
        sections["headline_candidates"] = candidate_list

        combined_copy = "\n".join(
            [
                headline_payload.get("headline", ""),
                sections[GenerationType.SUMMARY.value.lower()].get("summary", ""),
                sections[GenerationType.ARTICLE.value.lower()].get("body", ""),
                sections[GenerationType.SOCIAL.value.lower()].get("caption", ""),
            ]
        )

        # Deterministic package-level guard + quality assessment.
        guard_report = FactClaimGuard(context).run(combined_copy)
        merged_flags = sorted({f["flag"] for f in all_findings} | set(guard_report.flags))
        if context.conflicts and RiskFlag.CONFLICTING_SOURCES.value not in merged_flags:
            merged_flags.append(RiskFlag.CONFLICTING_SOURCES.value)

        package_payload = {
            "headline_candidates": candidate_list,
            "summary": sections[GenerationType.SUMMARY.value.lower()],
            "article": sections[GenerationType.ARTICLE.value.lower()],
            "social": sections[GenerationType.SOCIAL.value.lower()],
            "key_facts": key_facts,
            "uncertainties": uncertainties,
            "risk_flags": merged_flags,
            "sources": self._source_list(context),
            "conflicts": context.conflicts,
        }

        quality = assess_quality(
            context=context,
            payload={"headline": candidate_list[0] if candidate_list else "", **package_payload["summary"]},
            copy_text=combined_copy,
            guard_report=guard_report,
            generation_type="PACKAGE",
        )
        package_payload["quality_breakdown"] = quality.as_dict()

        latency_ms = int((time.monotonic() - started_total) * 1000)
        generation = self._record_generation(
            context,
            GenerationType.PACKAGE,
            success=True,
            raw=json.dumps({"sections": "persisted per section", "package": True})[:4000],
            latency_ms=latency_ms,
            output_hash=_sha256(json.dumps(package_payload, sort_keys=True, default=str)),
        )
        draft = self._persist_draft(
            context,
            generation,
            draft_type=DraftType.ARTICLE,
            title=candidate_list[0] if candidate_list else context.story["cluster_title"],
            body=package_payload["article"].get("body", ""),
            dek=package_payload["article"].get("dek", ""),
            summary=package_payload["summary"].get("summary", ""),
            payload=package_payload,
            quality=quality,
            risk_flags=merged_flags,
            target_platform="editorial-package",
        )
        self.db.commit()
        self.db.refresh(draft)
        logger.info(
            "generation completed",
            extra={"story_id": story_id, "type": "PACKAGE", "draft_id": draft.id, "latency_ms": latency_ms},
        )
        return self._package_response(draft, context, reused=False)

    def regenerate_draft(self, draft_id: int) -> dict[str, Any]:
        """Explicit regeneration: always creates a NEW generation record.

        The superseded draft is marked REGENERATE and retained as history —
        historical generation evidence is never overwritten or deleted.
        """
        old_draft = self.db.get(EditorialDraft, draft_id)
        if old_draft is None:
            raise DraftNotFoundError(f"Editorial draft {draft_id} not found.")
        gen_type = GenerationType(self._draft_generation_type(old_draft))
        result = self._generate(old_draft.story_cluster_id, gen_type, self._schema_for(gen_type), force=True)
        old_draft.status = DraftStatus.REGENERATE.value
        old_draft.updated_at = _utcnow()
        self.db.commit()
        result["regenerated_from_draft_id"] = draft_id
        return result

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def _generate(self, story_id: int, gen_type: GenerationType, schema_name: str, *, force: bool) -> dict[str, Any]:
        context = self._build_context(story_id)
        existing = self._find_idempotent_draft(context, gen_type)
        if existing is not None and not force:
            logger.info(
                "generation idempotent hit",
                extra={"story_id": story_id, "type": gen_type.value, "draft_id": existing.id},
            )
            return self._draft_response(existing, context, reused=True)

        outcome = self._run_generation(context, gen_type, schema_name, persist=True)
        return outcome["response"]

    def _build_context(self, story_id: int) -> ResearchContext:
        try:
            context = self.context_engine.build(story_id)
        except LookupError as exc:
            raise StoryNotFoundError(str(exc)) from exc
        logger.info(
            "research context constructed",
            extra={
                "story_id": story_id,
                "context_hash": context.context_hash[:12],
                "articles": len(context.articles),
                "conflicts": len(context.conflicts),
            },
        )
        return context

    def _run_generation(
        self, context: ResearchContext, gen_type: GenerationType, schema_name: str, *, persist: bool
    ) -> dict[str, Any]:
        request = GenerationRequest(
            system_prompt=SYSTEM_PROMPT_TEMPLATE,
            user_prompt=self._user_prompt(context, gen_type),
            schema_name=schema_name,
        )
        logger.info(
            "generation requested",
            extra={
                "story_id": context.story["cluster_id"],
                "type": gen_type.value,
                "provider": self.provider.name,
                "model": self.provider.model,
            },
        )
        started = time.monotonic()
        try:
            result = self.provider.call_with_retry(request)
        except AIProviderError as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            self._record_generation(
                context, gen_type, success=False, raw="", latency_ms=latency_ms, error_code=exc.error_code
            )
            self.db.commit()
            logger.error(
                "generation failed",
                extra={"story_id": context.story["cluster_id"], "type": gen_type.value, "error_code": exc.error_code},
            )
            raise GenerationError(f"AI generation failed: {exc.message}", exc.error_code) from exc

        payload = result.structured
        guard_report = FactClaimGuard(context).run(*_texts_of(payload))
        flags = list(guard_report.flags)
        if context.conflicts and RiskFlag.CONFLICTING_SOURCES.value not in flags:
            flags.append(RiskFlag.CONFLICTING_SOURCES.value)

        quality = assess_quality(
            context=context,
            payload=payload,
            copy_text="\n".join(_texts_of(payload)),
            guard_report=guard_report,
            generation_type=gen_type.value,
        )

        draft_type = _draft_type_for(gen_type)
        status = _status_for(flags, quality.overall)

        generation = None
        draft = None
        if persist:
            generation = self._record_generation(
                context,
                gen_type,
                success=True,
                raw=result.raw_text,
                latency_ms=result.latency_ms or int((time.monotonic() - started) * 1000),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                output_hash=_sha256(json.dumps(payload, sort_keys=True, default=str)),
            )
            draft = self._persist_draft(
                context,
                generation,
                draft_type=draft_type,
                title=payload.get("headline") or context.story["cluster_title"],
                body=payload.get("body", ""),
                dek=payload.get("dek", ""),
                summary=payload.get("summary") or payload.get("caption", ""),
                payload=payload,
                quality=quality,
                risk_flags=flags,
                target_platform=payload.get("platform", _platform_for(draft_type)),
                status=status,
            )
            self.db.commit()
            self.db.refresh(draft)
            logger.info(
                "validation completed",
                extra={
                    "story_id": context.story["cluster_id"],
                    "type": gen_type.value,
                    "risk_flags": flags,
                    "quality_overall": quality.overall,
                    "draft_id": draft.id,
                },
            )

        guard_payload = {
            "flags": flags,
            "findings": [{"flag": f.flag, "detail": f.detail, "snippet": f.snippet} for f in guard_report.findings],
        }
        response = (
            self._draft_response(draft, context, reused=False) if persist and draft is not None else {}
        )
        return {
            "payload": payload,
            "guard": guard_payload,
            "quality": quality,
            "draft": draft,
            "response": response,
        }

    def _user_prompt(self, context: ResearchContext, gen_type: GenerationType) -> str:
        bounded = context.canonical_json()[: self.settings.EDITORIAL_MAX_CONTEXT_CHARS]
        instructions = {
            GenerationType.HEADLINES: (
                f"Produce exactly {self.max_headline_candidates} headline candidates (headline + alternate_headlines)."
            ),
            GenerationType.SUMMARY: "Produce a summary plus key_facts grounded strictly in the evidence.",
            GenerationType.ARTICLE: "Produce headline, dek, body, key_facts, uncertainties.",
            GenerationType.SOCIAL: "Produce caption, headline, call_to_action, hashtags.",
            GenerationType.PACKAGE: "Produce the complete editorial package.",
        }[gen_type]
        return f"{instructions}\n\nRESEARCH CONTEXT (authoritative evidence set; you may not add sources):\n{bounded}"

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _find_idempotent_draft(self, context: ResearchContext, gen_type: GenerationType) -> EditorialDraft | None:
        """Return an existing draft for identical generation parameters, if any."""
        prior = (
            self.db.query(EditorialGeneration)
            .filter(
                EditorialGeneration.story_cluster_id == context.story["cluster_id"],
                EditorialGeneration.generation_type == gen_type.value,
                EditorialGeneration.provider == self.provider.name,
                EditorialGeneration.model == self.provider.model,
                EditorialGeneration.prompt_version == self.prompt_version,
                EditorialGeneration.input_context_hash == context.context_hash,
                EditorialGeneration.success == 1,
            )
            .order_by(EditorialGeneration.created_at.desc())
            .first()
        )
        if prior is None:
            return None
        return (
            self.db.query(EditorialDraft)
            .filter(EditorialDraft.generation_id == prior.id)
            .order_by(EditorialDraft.created_at.desc())
            .first()
        )

    def _record_generation(
        self,
        context: ResearchContext,
        gen_type: GenerationType,
        *,
        success: bool,
        raw: str,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        output_hash: str | None = None,
        error_code: str | None = None,
    ) -> EditorialGeneration:
        record = EditorialGeneration(
            story_cluster_id=context.story["cluster_id"],
            provider=self.provider.name,
            model=self.provider.model,
            prompt_version=self.prompt_version,
            generation_type=gen_type.value,
            input_context_hash=context.context_hash,
            output_hash=output_hash,
            raw_response=raw[:8000] if raw else None,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=1 if success else 0,
            error_code=error_code,
            created_at=_utcnow(),
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _persist_draft(
        self,
        context: ResearchContext,
        generation: EditorialGeneration,
        *,
        draft_type: DraftType,
        title: str,
        body: str,
        dek: str,
        summary: str,
        payload: dict[str, Any],
        quality: QualityAssessment,
        risk_flags: list[str],
        target_platform: str,
        status: str | None = None,
    ) -> EditorialDraft:
        draft = EditorialDraft(
            story_cluster_id=context.story["cluster_id"],
            draft_type=draft_type.value,
            status=status or DraftStatus.GENERATED.value,
            title=title[:512],
            body=body,
            summary=summary,
            dek=dek,
            editorial_angle="evidence-synthesis",
            tone="neutral-editorial",
            target_platform=target_platform,
            language="en",
            payload_json=json.dumps(payload, sort_keys=True, default=str),
            quality_score=quality.overall,
            confidence_score=quality.confidence,
            quality_breakdown_json=json.dumps(quality.as_dict(), sort_keys=True, default=str),
            risk_flags_json=json.dumps(risk_flags),
            generation_id=generation.id,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            generated_at=_utcnow(),
        )
        self.db.add(draft)
        self.db.flush()

        # Provenance: every evidence article used becomes an immutable link row.
        for idx, art in enumerate(context.articles):
            self.db.add(
                EditorialDraftSource(
                    draft_id=draft.id,
                    article_id=art["id"],
                    source_id=art["source_id"],
                    relevance=round(art.get("similarity_score", 1.0) * 100),
                    citation_role="primary" if idx == 0 else "evidence",
                    created_at=_utcnow(),
                )
            )
        return draft

    # ------------------------------------------------------------------
    # Response shaping
    # ------------------------------------------------------------------

    def _source_list(self, context: ResearchContext) -> list[dict[str, Any]]:
        return [
            {
                "article_id": a["id"],
                "title": a["title"],
                "publisher": a["publisher"],
                "source_id": a["source_id"],
                "canonical_url": a["canonical_url"],
                "published_at": a["published_at"],
            }
            for a in context.articles
        ]

    def _draft_response(self, draft: EditorialDraft, context: ResearchContext, *, reused: bool) -> dict[str, Any]:
        payload = json.loads(draft.payload_json or "{}")
        return {
            "draft_id": draft.id,
            "story_id": draft.story_cluster_id,
            "generation_id": draft.generation_id,
            "generation_type": _generation_type_for_draft(draft),
            "draft_type": draft.draft_type,
            "status": draft.status,
            "reused_existing_generation": reused,
            "is_demo_output": self.provider.is_demo,
            "requires_human_review": True,
            "payload": payload,
            "quality_breakdown": json.loads(draft.quality_breakdown_json or "{}"),
            "risk_flags": json.loads(draft.risk_flags_json or "[]"),
            "sources": self._source_list(context),
            "conflicts": context.conflicts,
            "generated_at": draft.generated_at.isoformat(),
        }

    def _package_response(self, draft: EditorialDraft, context: ResearchContext, *, reused: bool) -> dict[str, Any]:
        payload = json.loads(draft.payload_json or "{}")
        return {
            "draft_id": draft.id,
            "story_id": draft.story_cluster_id,
            "generation_id": draft.generation_id,
            "generation_type": GenerationType.PACKAGE.value,
            "draft_type": draft.draft_type,
            "status": draft.status,
            "reused_existing_generation": reused,
            "is_demo_output": self.provider.is_demo,
            "requires_human_review": True,
            "package": payload,
            "quality_breakdown": json.loads(draft.quality_breakdown_json or "{}"),
            "risk_flags": json.loads(draft.risk_flags_json or "[]"),
            "sources": payload.get("sources", self._source_list(context)),
            "conflicts": payload.get("conflicts", context.conflicts),
            "generated_at": draft.generated_at.isoformat(),
        }

    @staticmethod
    def _schema_for(gen_type: GenerationType) -> str:
        return _schema_for_static(gen_type)

    @staticmethod
    def _draft_generation_type(draft: EditorialDraft) -> GenerationType:
        return _generation_type_for_draft(draft)


def _schema_for_static(gen_type: GenerationType) -> str:
    return {
        GenerationType.HEADLINES: "headline_result",
        GenerationType.SUMMARY: "summary_result",
        GenerationType.ARTICLE: "article_result",
        GenerationType.SOCIAL: "social_result",
        GenerationType.PACKAGE: "article_result",
    }[gen_type]


def _draft_type_for(gen_type: GenerationType) -> DraftType:
    return {
        GenerationType.HEADLINES: DraftType.NEWS_UPDATE,
        GenerationType.SUMMARY: DraftType.EXPLAINER,
        GenerationType.ARTICLE: DraftType.ARTICLE,
        GenerationType.SOCIAL: DraftType.SOCIAL_POST,
        GenerationType.PACKAGE: DraftType.ARTICLE,
    }[gen_type]


def _platform_for(draft_type: DraftType) -> str:
    return {
        DraftType.SOCIAL_POST: "facebook",
        DraftType.SHORT_CAPTION: "instagram",
        DraftType.BREAKING: "web-breaking",
    }.get(draft_type, "web")


def _generation_type_for_draft(draft: EditorialDraft) -> str:
    if draft.target_platform == "editorial-package":
        return GenerationType.PACKAGE.value
    mapping = {
        DraftType.NEWS_UPDATE.value: GenerationType.HEADLINES.value,
        DraftType.EXPLAINER.value: GenerationType.SUMMARY.value,
        DraftType.ARTICLE.value: GenerationType.ARTICLE.value,
        DraftType.SOCIAL_POST.value: GenerationType.SOCIAL.value,
    }
    return mapping.get(draft.draft_type, GenerationType.ARTICLE.value)


def _texts_of(payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in ("headline", "dek", "body", "summary", "caption", "reasoning_summary"):
        value = payload.get(key)
        if isinstance(value, str):
            texts.append(value)
    for key in ("alternate_headlines", "key_facts", "uncertainties", "hashtags", "call_to_action"):
        value = payload.get(key)
        if isinstance(value, list):
            texts.extend(str(v) for v in value)
        elif isinstance(value, str):
            texts.append(value)
    return texts


def _status_for(flags: list[str], quality_overall: int) -> str:
    """Phase 3 statuses only — no approval/publish states exist yet."""
    serious = {
        RiskFlag.UNSUPPORTED_CLAIM.value,
        RiskFlag.UNSUPPORTED_ENTITY.value,
        RiskFlag.UNSUPPORTED_NUMBER.value,
        RiskFlag.UNSUPPORTED_DATE.value,
        RiskFlag.UNSUPPORTED_QUOTE.value,
        RiskFlag.CONFLICTING_SOURCES.value,
    }
    if serious.intersection(flags) or quality_overall < 55:
        return DraftStatus.REGENERATE.value
    if flags:
        return DraftStatus.NEEDS_REVIEW.value
    return DraftStatus.GENERATED.value
