"""Tiny prompt loader.

Reads markdown prompt files from ``apps/agents/prompts/``. Versioning is
handled simply by filename for now (e.g. ``scanner.system.md`` ->
``scanner.system.v2.md`` when we want to A/B).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
