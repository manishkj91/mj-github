"""Resume Scanner Agent.

Reads a resume + target (tier, seniority) and produces a tailored question
plan. Every non-gap question is verified to cite a verbatim resume span; if
the LLM hallucinates a citation, we drop the question rather than let it
through.
"""

from __future__ import annotations

import json

from ..contracts import (
    QuestionPlanItem,
    ResumeScanInput,
    ResumeScanOutput,
)
from ..llm import LLMClient
from ..tools import competency_taxonomy_lookup, question_bank_lookup, redact_pii
from ._prompts import load_prompt


def scan_resume(client: LLMClient, payload: ResumeScanInput) -> ResumeScanOutput:
    redacted = redact_pii(payload.resume_text)
    themes = competency_taxonomy_lookup(payload.target_company_tier, payload.target_seniority)
    seeds = {t: question_bank_lookup(t, payload.target_company_tier) for t in themes}

    user = (
        f"Target company tier: {payload.target_company_tier.value}\n"
        f"Target seniority: {payload.target_seniority.value}\n\n"
        f"Canonical themes to cover (P0 first):\n"
        + "\n".join(f"- {t}" for t in themes)
        + "\n\nSeed phrasings (for tone, not verbatim copy):\n"
        + json.dumps(seeds, indent=2)
        + "\n\n<resume>\n"
        + redacted
        + "\n</resume>"
    )

    raw = client.complete_json(
        system=load_prompt("scanner.system.md"),
        user=user,
        schema=ResumeScanOutput,
        tier="strong",
        temperature=0.4,
        max_output_tokens=8192,
    )

    return _enforce_grounding(raw, redacted)


def _enforce_grounding(scan: ResumeScanOutput, resume_text: str) -> ResumeScanOutput:
    """Drop questions whose citation is not actually in the resume.

    Hallucinated resume facts are the #1 risk in the PRD, so we hard-enforce
    here rather than trusting the model.
    """
    haystack = resume_text.lower()
    kept: list[QuestionPlanItem] = []
    for q in scan.question_plan:
        if q.is_gap_probe and q.resume_citation is None:
            kept.append(q)
            continue
        if q.resume_citation is not None and q.resume_citation.span.lower() in haystack:
            kept.append(q)
        # else: silently drop. The orchestrator can choose to re-roll.

    if len(kept) < 3:
        # The model gave us almost nothing usable. Surface the failure so the
        # caller can decide whether to retry, fall back, or abort.
        raise ValueError(
            "Resume Scanner returned fewer than 3 grounded questions. "
            f"Got {len(kept)} of {len(scan.question_plan)}."
        )

    return scan.model_copy(update={"question_plan": kept})
