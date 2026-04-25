"""Session Summary Agent."""

from __future__ import annotations

import json

from ..contracts import EvaluationOutput, QuestionPlanItem, SessionSummary
from ..llm import LLMClient
from ._prompts import load_prompt


def build_summary(
    client: LLMClient,
    *,
    questions: list[QuestionPlanItem],
    evaluations: dict[str, EvaluationOutput],
) -> SessionSummary:
    payload = []
    for q in questions:
        ev = evaluations.get(q.id)
        if ev is None:
            continue
        payload.append(
            {
                "question_id": q.id,
                "theme": q.theme,
                "question_text": q.question_text,
                "rubric_scores": ev.rubric_scores.model_dump(),
                "what_worked": ev.what_worked,
                "what_to_improve": ev.what_to_improve,
            }
        )
    user = (
        "Per-question evaluations follow. Build a session summary as defined "
        "by the schema.\n\n"
        + json.dumps(payload, indent=2)
    )
    return client.complete_json(
        system=load_prompt("summary.system.md"),
        user=user,
        schema=SessionSummary,
        tier="strong",
        temperature=0.3,
        max_output_tokens=1500,
    )
