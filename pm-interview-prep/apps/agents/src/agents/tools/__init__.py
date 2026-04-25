"""Tools agents can call.

These are plain Python functions, not LLM calls. They produce deterministic,
auditable outputs that the agents can either use directly (Scanner) or feed
into their prompts as grounding (Evaluation, Interview).
"""

from .pdf_parse import load_resume_text
from .pii import redact_pii
from .question_bank import question_bank_lookup
from .taxonomy import competency_taxonomy_lookup

__all__ = [
    "load_resume_text",
    "redact_pii",
    "competency_taxonomy_lookup",
    "question_bank_lookup",
]
