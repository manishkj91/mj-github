"""Google Gemini provider.

Uses ``google-generativeai`` with JSON-mode + a schema string in the prompt.
We do NOT rely on Gemini's experimental ``response_schema`` because it varies
across SDK versions; we instead force ``response_mime_type=application/json``
and validate with Pydantic, retrying once on parse failure.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import LLMClient, ModelTier

T = TypeVar("T", bound=BaseModel)


class GeminiClient(LLMClient):
    def __init__(self, *, api_key: str, strong_model: str, cheap_model: str) -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self._strong_model = strong_model
        self._cheap_model = cheap_model

    def _model_name(self, tier: ModelTier) -> str:
        return self._strong_model if tier == "strong" else self._cheap_model

    @retry(
        retry=retry_if_exception_type((ValidationError, json.JSONDecodeError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
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
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_system = (
            f"{system.strip()}\n\n"
            "You MUST respond with a single valid JSON object matching the schema "
            "below. Do not include markdown fences, comments, or any prose outside "
            "of the JSON.\n\n"
            f"JSON Schema:\n{schema_json}"
        )

        model = self._genai.GenerativeModel(
            model_name=self._model_name(tier),
            system_instruction=full_system,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "response_mime_type": "application/json",
            },
        )
        resp = model.generate_content(user)
        text = (resp.text or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            text = _strip_code_fences(text)
            data = json.loads(text)
        return schema.model_validate(data)


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()
