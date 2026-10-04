"""Phase 3: Explainable Editorial Quality Scoring.

Produces a 0-100 overall score with individually exposed components so the desk
can see WHY a draft scored as it did. The score is an editorial-workflow signal,
NOT a guarantee of truth; human review remains mandatory.

Components:
- evidence_coverage (25%): share of cluster articles actually used as provenance
- factual_support   (25%): inverse of fact-guard findings per 100 generated words
- attribution       (15%): explicit source attribution present in copy
- completeness      (10%): required sections present for the artifact type
- clarity           (10%): sentence-length / paragraph heuristics
- headline_quality  (10%): length + clickbait/superlative penalty checks
- risk_level        (5%):  scaled severity of remaining risk flags

Overall = weighted average minus a hard penalty when CONFLICTING_SOURCES or
UNSUPPORTED_CLAIM flags remain unresolved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import RiskFlag
from app.services.editorial.context import ResearchContext
from app.services.editorial.fact_guard import GuardReport

WEIGHTS = {
    "evidence_coverage": 0.25,
    "factual_support": 0.25,
    "attribution": 0.15,
    "completeness": 0.10,
    "clarity": 0.10,
    "headline_quality": 0.10,
    "risk_level": 0.05,
}

HARD_PENALTY_FLAGS = {RiskFlag.CONFLICTING_SOURCES.value: 8, RiskFlag.UNSUPPORTED_CLAIM.value: 10}

CLICKBAIT_TERMS = (
    "you won't believe",
    "shocking",
    "mind-blowing",
    "insane",
    "unbelievable",
    "must-see",
    "gone wild",
    "explosive",
    "secret",
)
SUPERLATIVE_TERMS = ("best ever", "greatest ever", "worst ever", "historic", "unprecedented", "record-breaking")

REQUIRED_SECTIONS = {
    "article": ["headline", "dek", "body"],
    "summary": ["summary", "key_facts"],
    "social": ["caption", "call_to_action"],
    "headlines": ["headline", "alternate_headlines"],
}


@dataclass
class QualityAssessment:
    components: dict[str, int] = field(default_factory=dict)
    overall: int = 0
    confidence: int = 0
    explanation: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "components": self.components,
            "weights": WEIGHTS,
            "overall": self.overall,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "disclaimer": "Quality score supports editorial triage; it is not a guarantee of truth.",
        }


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w])


def score_evidence_coverage(context: ResearchContext, used_article_ids: set[int]) -> tuple[int, str]:
    total = context.story.get("article_count", len(context.articles)) or len(context.articles)
    if total <= 0:
        return 0, "No articles in evidence set."
    ratio = len(used_article_ids & {a["id"] for a in context.articles}) / max(total, len(context.articles))
    return round(min(1.0, ratio) * 100), f"{len(used_article_ids)} of {total} cluster articles used."


def score_factual_support(guard_report: GuardReport, word_count: int) -> tuple[int, str]:
    if word_count <= 0:
        return 0, "No generated text to evaluate."
    density = len(guard_report.findings) / max(word_count / 100.0, 0.5)
    score = int(max(0.0, 100.0 - density * 25.0))
    return score, f"{len(guard_report.findings)} guard finding(s) across {word_count} words."


def score_attribution(copy: str, context: ResearchContext) -> tuple[int, str]:
    lowered = copy.lower()
    pubs = [p for p in context.provenance.get("publishers", [])]
    mentioned = sum(1 for p in pubs if p.lower() in lowered)
    marker_words = ("according to", "said", "reported", "reports", "via")
    has_marker = any(m in lowered for m in marker_words)
    if not pubs:
        return 0, "No publishers in evidence."
    base = min(100, int(mentioned / max(len(pubs), 1) * 100))
    if has_marker and base >= 50:
        base = min(100, base + 15)
    return base, f"{mentioned}/{len(pubs)} publishers credited in copy" + (", attribution language present" if has_marker else "")


def score_completeness(payload: dict[str, Any], generation_type: str) -> tuple[int, str]:
    required = REQUIRED_SECTIONS.get(generation_type.lower(), [])
    if not required:
        return 100, "No structural requirements."
    present = [k for k in required if str(payload.get(k, "")).strip()]
    return round(len(present) / len(required) * 100), f"Sections present: {present or 'none'}."


def score_clarity(text: str) -> tuple[int, str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return 0, "No sentences to evaluate."
    lengths = [len(s.split()) for s in sentences]
    avg = sum(lengths) / len(lengths)
    too_long = sum(1 for ln in lengths if ln > 34)
    score = 100 - max(0, int((avg - 22) * 3)) - too_long * 6
    return int(max(0, min(100, score))), f"Average sentence length {avg:.1f} words; {too_long} overly long."


def score_headline_quality(headline: str) -> tuple[int, str]:
    if not headline.strip():
        return 0, "No headline."
    score = 100
    notes: list[str] = []
    words = len(headline.split())
    if words < 3:
        score -= 25
        notes.append("too short")
    elif words > 14:
        score -= 20
        notes.append("too long")
    lowered = headline.lower()
    hits = [t for t in CLICKBAIT_TERMS if t in lowered]
    if hits:
        score -= 30
        notes.append(f"clickbait terms {hits}")
    sups = [t for t in SUPERLATIVE_TERMS if t in lowered]
    if sups:
        score -= 20
        notes.append(f"unsupported superlatives {sups}")
    if lowered.endswith("?") and not any(c.isalnum() for c in headline[:-1]):
        score -= 15
        notes.append("empty teaser question")
    return int(max(0, min(100, score))), "; ".join(notes) or "within editorial style bounds"


def score_risk_level(guard_report: GuardReport) -> tuple[int, str]:
    """Score where 100 = no residual risk and lower scores mean higher risk."""
    weights = {
        RiskFlag.UNSUPPORTED_CLAIM.value: 30,
        RiskFlag.UNSUPPORTED_ENTITY.value: 25,
        RiskFlag.UNSUPPORTED_NUMBER.value: 25,
        RiskFlag.UNSUPPORTED_DATE.value: 25,
        RiskFlag.UNSUPPORTED_QUOTE.value: 30,
        RiskFlag.UNSUPPORTED_URL.value: 25,
        RiskFlag.MISSING_ATTRIBUTION.value: 15,
        RiskFlag.LOW_EVIDENCE.value: 10,
        RiskFlag.CONFLICTING_SOURCES.value: 20,
    }
    penalty = sum(weights.get(f.flag, 10) for f in guard_report.findings)
    return int(max(0, 100 - penalty)), f"{len(guard_report.findings)} active risk finding(s)."


def assess_quality(
    *,
    context: ResearchContext,
    payload: dict[str, Any],
    copy_text: str,
    guard_report: GuardReport,
    generation_type: str,
    used_article_ids: set[int] | None = None,
    headline: str | None = None,
) -> QualityAssessment:
    used = used_article_ids if used_article_ids is not None else {a["id"] for a in context.articles}
    components: dict[str, int] = {}
    explanation: list[str] = []

    for name, (value, note) in {
        "evidence_coverage": score_evidence_coverage(context, used),
        "factual_support": score_factual_support(guard_report, _word_count(copy_text)),
        "attribution": score_attribution(copy_text, context),
        "completeness": score_completeness(payload, generation_type),
        "clarity": score_clarity(copy_text),
        "headline_quality": score_headline_quality(headline if headline is not None else str(payload.get("headline", ""))),
        "risk_level": score_risk_level(guard_report),
    }.items():
        components[name] = value
        explanation.append(f"{name}: {note}")

    overall = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    flags = set(guard_report.flags)
    penalty = sum(p for flag, p in HARD_PENALTY_FLAGS.items() if flag in flags)
    if penalty:
        overall -= penalty
        explanation.append(f"Hard penalty -{penalty} applied for unresolved flags {sorted(flags)}.")
    overall_int = int(max(0, min(100, round(overall))))

    # Confidence: corroboration-weighted trust that the evidence itself is strong.
    confidence = int(max(0, min(100, round(components["factual_support"] * 0.5 + context.intelligence.get("corroboration", 0) * 0.5))))

    return QualityAssessment(components=components, overall=overall_int, confidence=confidence, explanation=explanation)
