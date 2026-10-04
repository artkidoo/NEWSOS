"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings and environment variables."""

    APP_NAME: str = "NEWSROOM OS"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./newsroom.db"
    LOG_LEVEL: str = "INFO"
    REQUEST_TIMEOUT_SECONDS: int = 15
    MAX_RETRIES: int = 3

    class Config:
        env_file = ".env"
        extra = "ignore"


def get_settings() -> Settings:
    """Returns application settings instance."""
    return Settings()
