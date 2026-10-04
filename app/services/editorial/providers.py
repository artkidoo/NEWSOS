"""Phase 3: AI Provider Abstraction for the Editorial Desk.

The application is never hard-coded to one AI provider. Providers implement
`EditorialAIProvider` and are registered in a factory keyed by name.

Providers:
- TestEditorialProvider ("test"): deterministic, offline, explicitly identifiable
  (every output carries `is_demo: true`). Used for development and the full test
  suite so no paid external AI API is ever required by tests.
- OpenAIEditorialProvider ("openai"): real chat-completions provider configured
  exclusively through environment variables. It NEVER fabricates success; on any
  transport/HTTP error it raises a normalized AIPermanentError/AITimeoutError.

Secrets policy: API keys are only read from settings, never logged, never stored
in generation records, and never returned from any API response.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("newsroom.editorial.ai")


class AIProviderError(Exception):
    """Normalized base error for all AI provider failures."""

    error_code = "AI_PROVIDER_ERROR"

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AIConfigError(AIProviderError):
    """Provider selected but required configuration missing."""

    error_code = "AI_CONFIG_MISSING"


class AITimeoutError(AIProviderError):
    """Provider request exceeded the configured timeout."""

    error_code = "AI_TIMEOUT"


class AIRateLimitError(AIProviderError):
    """Provider rate-limited the request (retryable)."""

    error_code = "AI_RATE_LIMIT"


class AIPermanentError(AIProviderError):
    """Non-retryable-at-transport-level provider failure (retried per policy)."""

    error_code = "AI_PERMANENT_ERROR"


class AIInvalidResponseError(AIProviderError):
    """Provider returned content that could not be parsed into the schema."""

    error_code = "AI_INVALID_RESPONSE"


RETRYABLE_ERRORS = (AITimeoutError, AIRateLimitError, AIPermanentError)


@dataclass
class GenerationRequest:
    """A single editorial generation request against a provider."""

    system_prompt: str
    user_prompt: str
    schema_name: str
    max_output_tokens: int = 1200
    temperature: float | None = None


@dataclass
class GenerationResult:
    """Normalized provider response envelope."""

    provider: str
    model: str
    structured: dict[str, Any]
    raw_text: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    is_demo: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class EditorialAIProvider(ABC):
    """Abstract editorial AI provider.

    Concrete providers must expose name/model, honor timeout + retry policy,
    produce structured outputs, and normalize every error into an
    AIProviderError subclass.
    """

    name: str = "abstract"
    is_demo: bool = False

    def __init__(self, *, timeout: float = 30.0, max_retries: int = 2, temperature: float = 0.2):
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.temperature = temperature

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier used in audit records."""

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a normalized result for the request."""

    def generate_structured(self, request: GenerationRequest) -> GenerationResult:
        """Generate output conforming to the named editorial schema."""
        result = self.generate(request)
        if not isinstance(result.structured, dict) or not result.structured:
            raise AIInvalidResponseError("Provider returned no structured output.")
        return validate_result(request.schema_name, result)

    def call_with_retry(self, request: GenerationRequest) -> GenerationResult:
        """Execute generate_structured with the configured retry policy.

        Retries only retryable normalized errors; configuration and invalid
        response errors surface immediately. Raises the last error when all
        attempts fail — provider errors are never swallowed.
        """
        attempts = self.max_retries + 1
        last_error: AIProviderError | None = None
        for attempt in range(1, attempts + 1):
            try:
                started = time.monotonic()
                result = self.generate_structured(request)
                if not result.latency_ms:
                    result.latency_ms = int((time.monotonic() - started) * 1000)
                return result
            except RETRYABLE_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "generation attempt failed",
                    extra={"attempt": attempt, "attempts": attempts, "error_code": exc.error_code},
                )
                if attempt < attempts:
                    time.sleep(min(0.05 * attempt, 0.25))
        assert last_error is not None
        raise last_error


# ---------------------------------------------------------------------------
# Structured output schemas (deterministic validation of provider payloads)
# ---------------------------------------------------------------------------

EDITORIAL_SCHEMAS: dict[str, dict[str, Any]] = {
    "headline_result": {
        "required": ["headline", "alternate_headlines", "reasoning_summary", "risk_flags"],
        "types": {
            "headline": str,
            "alternate_headlines": list,
            "reasoning_summary": str,
            "risk_flags": list,
        },
    },
    "summary_result": {
        "required": ["summary", "key_facts", "risk_flags"],
        "types": {"summary": str, "key_facts": list, "risk_flags": list},
    },
    "article_result": {
        "required": ["headline", "dek", "body", "key_facts", "uncertainties", "risk_flags"],
        "types": {
            "headline": str,
            "dek": str,
            "body": str,
            "key_facts": list,
            "uncertainties": list,
            "risk_flags": list,
        },
    },
    "social_result": {
        "required": ["caption", "headline", "call_to_action", "hashtags", "risk_flags"],
        "types": {
            "caption": str,
            "headline": str,
            "call_to_action": str,
            "hashtags": list,
            "risk_flags": list,
        },
    },
}


def validate_structured_payload(schema_name: str, payload: Any) -> dict[str, Any]:
    """Validate a provider payload against a named editorial schema."""
    spec = EDITORIAL_SCHEMAS.get(schema_name)
    if spec is None:
        raise AIInvalidResponseError(f"Unknown editorial schema '{schema_name}'.")
    if not isinstance(payload, dict):
        raise AIInvalidResponseError(f"Structured output must be an object, got {type(payload).__name__}.")
    for key in spec["required"]:
        if key not in payload:
            raise AIInvalidResponseError(f"Structured output missing required field '{key}' for {schema_name}.")
        expected = spec["types"][key]
        if not isinstance(payload[key], expected):
            raise AIInvalidResponseError(
                f"Field '{key}' expected {expected.__name__}, got {type(payload[key]).__name__}."
            )
    return payload


def validate_result(schema_name: str, result: GenerationResult) -> GenerationResult:
    """Ensure a GenerationResult's structured payload matches its schema."""
    result.structured = validate_structured_payload(schema_name, result.structured)
    return result


# ---------------------------------------------------------------------------
# Deterministic evidence-grounded synthesis helpers (used by demo provider)
# ---------------------------------------------------------------------------


def _evidence_lines(context: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for art in context.get("articles", []):
        excerpt = (art.get("excerpt") or art.get("content") or "").strip()
        first_sentence = excerpt.split(". ")[0].rstrip(".") if excerpt else art.get("title", "")
        lines.append(first_sentence.strip())
    return [ln for ln in lines if ln]


def _trim(sentence: str, limit: int = 160) -> str:
    cleaned = sentence.strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 3].rsplit(" ", 1)[0] + "..."
    return cleaned


def build_demo_structured(schema_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """Deterministically synthesize a schema-valid editorial payload from evidence.

    The demo provider composes sentences ONLY from supplied article text; it does
    not invent entities, numbers, dates, quotes, or URLs.
    """
    articles = context.get("articles", [])
    story = context.get("story", {})
    title = story.get("cluster_title") or (articles[0]["title"] if articles else "Untitled story")
    lines = _evidence_lines(context)
    publishers = sorted({a.get("publisher", "unknown publisher") for a in articles})
    attribution = ", ".join(publishers[:3]) if publishers else "no sources"
    fact = lines[0] if lines else title

    if schema_name == "headline_result":
        candidates = [title]
        if len(lines) > 1:
            candidates.append(_trim(lines[1], 110))
        candidates.append(_trim(f"{title}: what {attribution} report", 110))
        return {
            "headline": title,
            "alternate_headlines": candidates[:5],
            "reasoning_summary": f"Headlines composed strictly from cluster evidence attributed to {attribution}.",
            "risk_flags": [],
        }
    if schema_name == "summary_result":
        key_facts = [_trim(ln) for ln in lines[:4]]
        summary = " ".join(key_facts[:2]) if key_facts else title
        return {"summary": summary, "key_facts": key_facts, "risk_flags": []}
    if schema_name == "article_result":
        body_paragraphs = [
            fact,
            " ".join(lines[1:3]) if len(lines) > 1 else "",
            f"Reporting from {attribution} describes these developments.",
            " ".join(lines[3:5]) if len(lines) > 3 else "",
            (
                f"This story was first tracked at {story.get('first_seen', 'an unknown time')} "
                f"and is currently marked {story.get('state', 'EMERGING')}."
            ),
        ]
        body = "\n\n".join(p for p in body_paragraphs if p)
        dek = _trim(lines[1]) if len(lines) > 1 else _trim(fact)
        return {
            "headline": title,
            "dek": dek,
            "body": body,
            "key_facts": [_trim(ln) for ln in lines[:5]],
            "uncertainties": (
                []
                if len(articles) >= 2
                else ["Story is reported by a single source; details remain unconfirmed."]
            ),
            "risk_flags": [],
        }
    if schema_name == "social_result":
        caption = _trim(f"{fact} (via {attribution})", 280)
        tag_words = [w.strip('.,;:!?"\'()').lower() for w in title.split()]
        hashtags = [f"#{w}" for w in tag_words if len(w) > 4][:3]
        return {
            "caption": caption,
            "headline": title,
            "call_to_action": "Read the full story coverage for updates.",
            "hashtags": hashtags,
            "risk_flags": [],
        }
    raise AIInvalidResponseError(f"Demo provider has no builder for schema '{schema_name}'.")


# ---------------------------------------------------------------------------
# Test / demo provider
# ---------------------------------------------------------------------------


class TestEditorialProvider(EditorialAIProvider):
    """Explicitly-identifiable offline provider for development and tests.

    Deterministic: identical context + schema => identical output. Every result
    is flagged is_demo=True and its raw text is prefixed so demo material can
    never masquerade as production output.
    """

    name = "test"
    is_demo = True

    def __init__(self, settings: Settings | None = None, **kwargs: Any):
        cfg = settings or get_settings()
        super().__init__(
            timeout=float(kwargs.get("timeout", cfg.AI_TIMEOUT)),
            max_retries=int(kwargs.get("max_retries", cfg.AI_MAX_RETRIES)),
            temperature=float(kwargs.get("temperature", cfg.AI_TEMPERATURE)),
        )
        self._model = str(kwargs.get("model", "newsroom-editorial-test-v1"))
        # Deterministic failure hooks for exercising error/timeout/retry paths.
        self.fail_times: int = int(kwargs.get("fail_times", 0))
        self.fail_error: type[AIProviderError] = kwargs.get("fail_error", AIPermanentError)
        self.simulated_latency_ms: int = int(kwargs.get("simulated_latency_ms", 0))
        self.context_provider: Callable[[], dict[str, Any]] | None = kwargs.get("context_provider")

    @property
    def model(self) -> str:
        return self._model

    def set_context(self, context: dict[str, Any]) -> None:
        """Attach the research context the deterministic outputs are built from."""
        self.context_provider = lambda: context

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if self.simulated_latency_ms:
            time.sleep(self.simulated_latency_ms / 1000.0)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.fail_error("Test provider forced failure.")
        context = self.context_provider() if self.context_provider else {}
        payload = build_demo_structured(request.schema_name, context)
        raw = "[DEMO-AI] " + json.dumps(payload, sort_keys=True)[:4000]
        return GenerationResult(
            provider=self.name,
            model=self.model,
            structured=payload,
            raw_text=raw,
            input_tokens=len(request.user_prompt) // 4,
            output_tokens=len(raw) // 4,
            latency_ms=self.simulated_latency_ms,
            is_demo=True,
            metadata={"demo": True, "schema": request.schema_name},
        )


# Alias so callers can use either name; "demo" is equally explicit.
DemoEditorialProvider = TestEditorialProvider


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (real API; env-configured only)
# ---------------------------------------------------------------------------

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIEditorialProvider(EditorialAIProvider):
    """OpenAI chat-completions provider configured via environment variables.

    Never fabricates successful responses: transport errors, HTTP errors, and
    malformed JSON all raise normalized AIProviderError subclasses.
    """

    name = "openai"
    is_demo = False

    def __init__(self, settings: Settings | None = None, **kwargs: Any):
        cfg = settings or get_settings()
        super().__init__(
            timeout=float(kwargs.get("timeout", cfg.AI_TIMEOUT)),
            max_retries=int(kwargs.get("max_retries", cfg.AI_MAX_RETRIES)),
            temperature=float(kwargs.get("temperature", cfg.AI_TEMPERATURE)),
        )
        self.api_key = (cfg.AI_API_KEY or "").strip()
        if not self.api_key:
            raise AIConfigError("AI_API_KEY is required when AI_PROVIDER=openai.")
        self._model = (cfg.AI_MODEL or "").strip() or OPENAI_DEFAULT_MODEL
        self.base_url = (cfg.AI_BASE_URL or "https://api.openai.com/v1").rstrip("/")

    @property
    def model(self) -> str:
        return self._model

    def generate(self, request: GenerationRequest) -> GenerationResult:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "temperature": request.temperature if request.temperature is not None else self.temperature,
            "max_tokens": request.max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        started = time.monotonic()
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"OpenAI request timed out after {self.timeout}s.") from exc
        except httpx.HTTPError as exc:
            raise AIPermanentError(f"OpenAI transport error: {type(exc).__name__}") from exc

        if resp.status_code == 429:
            raise AIRateLimitError("OpenAI rate limit exceeded.", status_code=429)
        if resp.status_code >= 400:
            # Never echo request contents or credentials; status + short reason only.
            raise AIPermanentError(f"OpenAI HTTP error {resp.status_code}.", status_code=resp.status_code)

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIInvalidResponseError("OpenAI response malformed.") from exc

        try:
            payload = json.loads(content)
        except ValueError as exc:
            raise AIInvalidResponseError("OpenAI returned non-JSON content.") from exc

        payload = validate_structured_payload(request.schema_name, payload)
        latency_ms = int((time.monotonic() - started) * 1000)
        return GenerationResult(
            provider=self.name,
            model=self.model,
            structured=payload,
            raw_text=content[:8000],
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            is_demo=False,
        )


PROVIDER_REGISTRY: dict[str, type[EditorialAIProvider]] = {
    "test": TestEditorialProvider,
    "demo": TestEditorialProvider,
    "openai": OpenAIEditorialProvider,
}


def register_provider(name: str, provider_cls: type[EditorialAIProvider]) -> None:
    """Extension hook so future providers can be added without touching callers."""
    PROVIDER_REGISTRY[name.lower()] = provider_cls


def create_provider(settings: Settings | None = None, **overrides: Any) -> EditorialAIProvider:
    """Instantiate the configured provider.

    Raises AIConfigError for unknown providers or missing real-provider config.
    """
    cfg = settings or get_settings()
    provider_name = (cfg.AI_PROVIDER or "").strip().lower()
    if provider_name not in PROVIDER_REGISTRY:
        raise AIConfigError(
            f"Unknown AI_PROVIDER '{cfg.AI_PROVIDER}'. Available: {sorted(PROVIDER_REGISTRY)}"
        )
    cls = PROVIDER_REGISTRY[provider_name]
    kwargs = dict(overrides)
    if provider_name not in ("test", "demo"):
        cfg.validate_ai_config()
    return cls(settings=cfg, **kwargs)  # type: ignore[call-arg]
