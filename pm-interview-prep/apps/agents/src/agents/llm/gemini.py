"""Google Gemini provider (uses the modern ``google-genai`` SDK).

We pass the Pydantic model directly as ``response_schema`` and ask the SDK to
parse it back into the same model via ``response.parsed``. This is the most
reliable path on the new SDK.

If ``response.parsed`` is ``None`` (model returned malformed JSON) we fall
back to a permissive prompt-only mode that asks the model to "return JSON
matching this exact schema" and validates manually.

Includes a simple per-process token-bucket to respect the Gemini free-tier
RPM limits (default: 10 req/min) so a multi-turn session doesn't 429 itself
into oblivion.
"""

from __future__ import annotations

import json
import threading
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import LLMClient, ModelTier


class _Throttle:
    """Naive per-model RPM throttle. Sleeps the calling thread when needed."""

    def __init__(self, rpm: int) -> None:
        self.min_interval = 60.0 / max(1, rpm)
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, model: str) -> None:
        with self._lock:
            now = time.monotonic()
            last = self._last.get(model, 0.0)
            wait = self.min_interval - (now - last)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._last[model] = now

T = TypeVar("T", bound=BaseModel)


class GeminiClient(LLMClient):
    def __init__(
        self,
        *,
        api_key: str,
        strong_model: str,
        cheap_model: str,
        rpm: int = 10,
    ) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._strong_model = strong_model
        self._cheap_model = cheap_model
        self._throttle = _Throttle(rpm=rpm)

    def _model_name(self, tier: ModelTier) -> str:
        return self._strong_model if tier == "strong" else self._cheap_model

    @retry(
        retry=retry_if_exception_type((ValidationError, json.JSONDecodeError, ValueError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        tier: ModelTier = "strong",
        temperature: float = 0.4,
        max_output_tokens: int = 2048,
    ) -> T:
        from google.genai import types

        # Disable "thinking" so all output tokens go to the response, not to
        # an invisible reasoning trace (which silently truncates JSON on
        # 2.5-flash / 2.5-flash-lite when budgets are tight).
        thinking_config = None
        try:
            thinking_config = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            thinking_config = None

        model_name = self._model_name(tier)
        self._throttle.wait(model_name)

        # Path 1: native Pydantic schema (best when supported).
        try:
            kwargs: dict = dict(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
                response_schema=schema,
            )
            if thinking_config is not None:
                kwargs["thinking_config"] = thinking_config
            config = types.GenerateContentConfig(**kwargs)
            resp = self._client.models.generate_content(
                model=model_name,
                contents=user,
                config=config,
            )
            parsed = getattr(resp, "parsed", None)
            if isinstance(parsed, schema):
                return parsed
            text = (resp.text or "").strip()
            if text:
                _ensure_complete(resp, text)
                return schema.model_validate(json.loads(_strip_code_fences(text)))
        except (TypeError, ValueError) as e:
            if isinstance(e, ValueError) and "truncated" in str(e).lower():
                raise
            # Schemas with anyOf / unions can be rejected by response_schema —
            # fall through to schema-as-text mode.

        # Path 2: schema-as-text in the prompt.
        kwargs2: dict = dict(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        )
        if thinking_config is not None:
            kwargs2["thinking_config"] = thinking_config
        config = types.GenerateContentConfig(**kwargs2)
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        augmented_user = (
            f"{user}\n\n"
            "You MUST return ONLY a JSON object that matches this schema. "
            "No prose, no markdown fences, no comments.\n\n"
            f"JSON Schema:\n{schema_json}"
        )
        resp = self._client.models.generate_content(
            model=model_name,
            contents=augmented_user,
            config=config,
        )
        text = (resp.text or "").strip()
        if not text:
            raise ValueError("Gemini returned empty content.")
        _ensure_complete(resp, text)
        return schema.model_validate(json.loads(_strip_code_fences(text)))


def _ensure_complete(resp, text: str) -> None:
    """Surface a clear error when Gemini truncated the JSON output."""
    finish = None
    try:
        finish = resp.candidates[0].finish_reason
    except Exception:
        pass
    if finish is not None and str(finish).upper().endswith("MAX_TOKENS"):
        raise ValueError(
            f"Gemini truncated output (finish_reason=MAX_TOKENS, len={len(text)}). "
            "Increase max_output_tokens or shrink the schema."
        )


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()
