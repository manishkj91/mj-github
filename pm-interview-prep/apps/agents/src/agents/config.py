"""Environment-driven configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["gemini", "mock"] = "mock"

    gemini_api_key: str | None = None
    gemini_strong_model: str = "gemini-2.5-pro"
    gemini_cheap_model: str = "gemini-2.5-flash"

    max_followups_per_question: int = Field(default=2, ge=0, le=3)
    max_questions_per_session: int = Field(default=5, ge=1, le=12)
    max_answer_chars: int = Field(default=4000, ge=200)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_for_tests() -> None:
    """Allow test fixtures to force a re-read of env vars."""
    global _settings
    _settings = None
