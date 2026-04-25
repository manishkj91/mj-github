"""Evaluation Agent."""

from __future__ import annotations

from ..contracts import EvaluationInput, EvaluationOutput
from ..llm import LLMClient
from ._prompts import load_prompt


def evaluate_answer(client: LLMClient, payload: EvaluationInput) -> EvaluationOutput:
    transcript_blob = "\n".join(
        f"<{t.role}>{t.content}</{t.role}>" for t in payload.transcript
    )
    user = (
        f"target_seniority: {payload.target_seniority.value}\n"
        f"question_theme: {payload.question.theme}\n"
        f"question_text: {payload.question.question_text}\n"
        f"why_this_question: {payload.question.why_this_question}\n\n"
        f"transcript:\n{transcript_blob}"
    )
    return client.complete_json(
        system=load_prompt("evaluation.system.md"),
        user=user,
        schema=EvaluationOutput,
        tier="strong",
        temperature=0.3,
        max_output_tokens=1500,
    )
