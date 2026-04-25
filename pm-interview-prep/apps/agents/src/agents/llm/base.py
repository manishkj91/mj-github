"""Abstract LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypeVar

from pydantic import BaseModel

ModelTier = Literal["strong", "cheap"]

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Provider-agnostic client.

    Agents only ever call ``complete_json`` so we can guarantee structured
    output regardless of provider.
    """

    @abstractmethod
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
        """Return a Pydantic-validated object of ``schema``."""
        ...
