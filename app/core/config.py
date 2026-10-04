"""Configuration management using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing for a real AI provider."""


class Settings(BaseSettings):
    """Application settings and environment variables."""

    APP_NAME: str = "NEWSROOM OS"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./newsroom.db"
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT_SECONDS: int = 15
    MAX_RETRIES: int = 3

    # ---- Phase 3: AI Editorial Desk configuration ----
    # Provider selection. "test" / "demo" are explicitly-identifiable local
    # providers that require no external API key. Real providers (e.g. "openai")
    # must be configured via environment variables; nothing is committed.
    AI_PROVIDER: str = "test"
    AI_MODEL: str = ""
    AI_API_KEY: str = ""  # never logged, never persisted to DB
    AI_BASE_URL: str = ""
    AI_TIMEOUT: int = 30
    AI_MAX_RETRIES: int = 2
    AI_TEMPERATURE: float = 0.2
    EDITORIAL_PROMPT_VERSION: str = "v1"

    # Bounded evidence limits (never send an entire database to the model).
    EDITORIAL_MAX_ARTICLES: int = 8
    EDITORIAL_MAX_CONTENT_CHARS: int = 1200
    EDITORIAL_MAX_CONTEXT_CHARS: int = 12000

    class Config:
        env_file = ".env"
        extra = "ignore"

    def validate_ai_config(self) -> None:
        """Fail clearly at startup if a real provider is selected but misconfigured.

        Test/demo providers intentionally require no API key so the whole
        application can be developed and tested without a paid AI API.
        """
        provider = (self.AI_PROVIDER or "").strip().lower()
        if provider in TEST_PROVIDERS:
            return
        if not provider:
            raise ConfigurationError("AI_PROVIDER is not configured. Set AI_PROVIDER (e.g. 'test' or 'openai').")
        missing = []
        if not (self.AI_API_KEY or "").strip():
            missing.append("AI_API_KEY")
        if not (self.AI_MODEL or "").strip():
            missing.append("AI_MODEL")
        if missing:
            raise ConfigurationError(
                f"AI provider '{provider}' requires configuration but missing: {', '.join(missing)}. "
                "Set them via environment variables (see .env.example)."
            )


# Providers that run locally without external credentials.
TEST_PROVIDERS = {"test", "demo"}


@lru_cache
def get_settings() -> Settings:
    """Returns application settings instance (cached)."""
    return Settings()
