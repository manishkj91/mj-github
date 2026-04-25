"""Build the configured LLM client."""

from __future__ import annotations

from ..config import get_settings
from .base import LLMClient
from .mock import MockClient


def build_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "gemini":
        from .gemini import GeminiClient

        if not settings.gemini_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                "Add it to your .env or export it in the shell."
            )
        return GeminiClient(
            api_key=settings.gemini_api_key,
            strong_model=settings.gemini_strong_model,
            cheap_model=settings.gemini_cheap_model,
            rpm=settings.gemini_rpm,
        )
    return MockClient()
