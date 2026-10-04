"""Phase 3: Deterministic Fact/Claim Guard.

A guardrail — not a truth oracle. Validates generated editorial text against the
supplied research context and emits risk flags when generated material contains:

- unsupported named entities (people/organizations/locations/brands/...)
- unsupported numbers/statistics
- unsupported dates
- unsupported quotations
- unsupported URLs
- missing attribution / low evidence
- conflicting sources (preserved, never silently resolved)

The guard never modifies content; it only annotates it with RiskFlag values and
per-instance details so downstream quality scoring and human review can act.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import RiskFlag
from app.services.editorial.context import ResearchContext, _extract_dates, _extract_numbers

ATTRIBUTION_MARKERS = (
    "according to",
    "said",
    "says",
    "reported",
    "reports",
    "reporting",
    "told",
    "announced",
    "confirmed",
    "stated",
    "via ",
    "from ",
)

QUOTED_SENTENCE_HINTS = ("expert", "analyst", "official", "spokesperson", "witness", "source")

# Deterministic boilerplate the demo/test provider composes around evidence.
# These are editorial-desk system phrases, not factual assertions about the
# world, so the guard treats them as supported vocabulary. Real providers do
# not emit them; genuine unsupported claims are still flagged.
DEMO_BOILERPLATE_TERMS = {
    "headlines", "read", "story", "coverage", "updates", "developments",
    "trending", "emerging", "rising", "peak", "cooling", "stale",
}


@dataclass
class GuardFinding:
    flag: str
    detail: str
    snippet: str = ""


@dataclass
class GuardReport:
    findings: list[GuardFinding] = field(default_factory=list)

    @property
    def flags(self) -> list[str]:
        seen: list[str] = []
        for f in self.findings:
            if f.flag not in seen:
                seen.append(f.flag)
        return seen

    @property
    def has_risk(self) -> bool:
        return bool(self.findings)


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", name.lower()).strip()


def _evidence_corpus(context: ResearchContext) -> str:
    parts: list[str] = []
    for art in context.articles:
        parts.extend([art.get("title", ""), art.get("excerpt", ""), art.get("publisher", "")])
    for ent in context.entities:
        parts.extend([ent.get("name", ""), ent.get("normalized_name", "")])
    parts.append(context.story.get("cluster_title", ""))
    return normalize_name(" ".join(parts))


def _find_capitalized_candidates(text: str) -> list[str]:
    """Heuristic proper-noun extraction: leading-capital sequences WITHIN a line.

    Scanning line-by-line prevents multi-line joins from producing phantom
    cross-line 'entities' (e.g. the last words of one paragraph fusing with the
    first words of the next).
    """
    candidates: list[str] = []
    for line in text.splitlines():
        candidates.extend(
            re.findall(
                r"\b([A-Z][a-zA-Z'’\.]+(?:\s+(?:of|the|and|for|de|van|von)?\s*[A-Z][a-zA-Z'’\.]+){0,3})\b",
                line,
            )
        )
    stop_words = {
        "the", "a", "an", "this", "that", "these", "those", "and", "or", "but", "if",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december",
    }
    out: list[str] = []
    for cand in candidates:
        norm = normalize_name(cand)
        if not norm or norm in stop_words:
            continue
        # Single common words capitalized at sentence start are weak signals; keep
        # them only if multi-word (stronger proper-noun evidence).
        words = norm.split()
        if len(words) == 1 and (norm in DEMO_BOILERPLATE_TERMS or not cand[0].isupper()):
            # Single-word demo boilerplate ("Headlines", "Read") and ALL-CAPS
            # lifecycle tokens ("TRENDING") are system vocabulary, not claims.
            continue
        out.append(cand)
    return out


class FactClaimGuard:
    """Deterministic validation of generated copy against the research context."""

    def __init__(self, context: ResearchContext):
        self.context = context
        self.corpus = _evidence_corpus(context)
        self.evidence_text = "\n".join(
            [a.get("title", "") + " " + a.get("excerpt", "") for a in context.articles]
        )
        self.supported_numbers = set(_extract_numbers(self.evidence_text)) | {
            n for art in context.articles for n in art.get("numbers", [])
        }
        self.supported_dates = set(_extract_dates(self.evidence_text)) | {
            d for art in context.articles for d in art.get("dates", [])
        }
        self.supported_urls = set(context.provenance.get("urls", {}).values())
        self.entity_names = {normalize_name(e["name"]) for e in context.entities}
        self.publisher_names = {normalize_name(p) for p in context.provenance.get("publishers", [])}

    # -- individual checks -------------------------------------------------

    def check_entities(self, text: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        seen: set[str] = set()
        for cand in _find_capitalized_candidates(text):
            norm = normalize_name(cand)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            if norm in self.corpus:
                continue
            # Also accept any supported entity/publisher contained in/containing candidate.
            if any(norm in tok or tok in norm for tok in self.entity_names | self.publisher_names):
                continue
            findings.append(
                GuardFinding(RiskFlag.UNSUPPORTED_ENTITY.value, f"Named entity '{cand}' not present in evidence.", cand)
            )
        return findings

    def check_numbers(self, text: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        for num in _extract_numbers(text):
            if num in self.supported_numbers:
                continue
            bare = num.rstrip("%").replace(",", "")
            if bare and all(bare in s or s in bare for s in (n.rstrip('%').replace(',', '') for n in self.supported_numbers) if s):
                continue
            findings.append(
                GuardFinding(RiskFlag.UNSUPPORTED_NUMBER.value, f"Number/statistic '{num}' not found in evidence.", num)
            )
        return findings

    def check_dates(self, text: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        for date in _extract_dates(text):
            if date in self.supported_dates:
                continue
            findings.append(
                GuardFinding(RiskFlag.UNSUPPORTED_DATE.value, f"Date '{date}' not found in evidence.", date)
            )
        return findings

    def check_quotes(self, text: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        for quote in re.findall(r"[\"“']([^\"”']{15,})[\"”']", text):
            if normalize_name(quote) in self.corpus:
                continue
            findings.append(
                GuardFinding(
                    RiskFlag.UNSUPPORTED_QUOTE.value,
                    "Quotation does not appear verbatim in source evidence.",
                    quote[:80],
                )
            )
        return findings

    def check_urls(self, text: str) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        for url in re.findall(r"https?://[^\s\"'<>)\]]+", text):
            if url in self.supported_urls:
                continue
            findings.append(GuardFinding(RiskFlag.UNSUPPORTED_URL.value, f"URL '{url}' is not a known source URL.", url))
        return findings

    def check_attribution(self, text: str) -> list[GuardFinding]:
        lowered = text.lower()
        has_marker = any(marker in lowered for marker in ATTRIBUTION_MARKERS)
        has_publisher = any(pub in lowered for pub in self.publisher_names if pub)
        if not has_marker and not has_publisher:
            return [
                GuardFinding(
                    RiskFlag.MISSING_ATTRIBUTION.value,
                    "Generated copy contains no explicit attribution to a source publisher.",
                )
            ]
        return []

    def check_evidence_strength(self) -> list[GuardFinding]:
        findings: list[GuardFinding] = []
        if len(self.context.articles) < 2:
            findings.append(
                GuardFinding(
                    RiskFlag.LOW_EVIDENCE.value,
                    f"Only {len(self.context.articles)} article(s) in evidence set; corroboration is weak.",
                )
            )
        for conflict in self.context.conflicts:
            findings.append(
                GuardFinding(
                    RiskFlag.CONFLICTING_SOURCES.value,
                    conflict.get("detail", "Sources disagree on key facts."),
                    ", ".join(str(a) for a in conflict.get("article_ids", [])),
                )
            )
        return findings

    # -- orchestration ------------------------------------------------------

    def run(self, *texts: str) -> GuardReport:
        combined = "\n".join(t for t in texts if t)
        report = GuardReport()
        report.findings.extend(self.check_evidence_strength())
        report.findings.extend(self.check_entities(combined))
        report.findings.extend(self.check_numbers(combined))
        report.findings.extend(self.check_dates(combined))
        report.findings.extend(self.check_quotes(combined))
        report.findings.extend(self.check_urls(combined))
        report.findings.extend(self.check_attribution(combined))
        return report


def claims_supported(text: str, context: ResearchContext) -> bool:
    """Convenience predicate used by tests/integrations: True if guard finds no risk."""
    guard = FactClaimGuard(context)
    return not guard.run(text).has_risk
