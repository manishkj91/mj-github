"""Lightweight PII redaction.

Strips obvious PII (email, phone, URLs containing usernames) from resume text
before it ever leaves the process for logging or LLM tracing. This is NOT a
substitute for a hardened DLP pipeline; it is a pragmatic first line of
defence appropriate for a sandbox project.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_URL = re.compile(r"https?://\S+|www\.\S+")
_LINKEDIN = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)


def redact_pii(text: str) -> str:
    out = _EMAIL.sub("[EMAIL]", text)
    out = _LINKEDIN.sub("[LINKEDIN]", out)
    out = _URL.sub("[URL]", out)
    out = _PHONE.sub("[PHONE]", out)
    return out
