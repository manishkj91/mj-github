"""LLM client abstraction.

All agents call `LLMClient.complete_json(...)` which guarantees a
schema-validated Pydantic object back. Two providers are bundled:

* ``GeminiClient`` — Google Generative AI (free-tier friendly).
* ``MockClient``  — deterministic, offline, used in tests and local dev.
"""

from __future__ import annotations

from .base import LLMClient, ModelTier
from .factory import build_client
from .mock import MockClient

__all__ = ["LLMClient", "ModelTier", "MockClient", "build_client"]
