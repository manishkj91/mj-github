"""Interview Agent."""

from __future__ import annotations

import json

from ..config import get_settings
from ..contracts import InterviewTurnInput, InterviewTurnOutput
from ..llm import LLMClient
from ._prompts import load_prompt


def next_interviewer_turn(
    client: LLMClient, payload: InterviewTurnInput
) -> InterviewTurnOutput:
    settings = get_settings()
    transcript_blob = "\n".join(
        f"<{t.role}>{t.content}</{t.role}>" for t in payload.transcript_so_far
    )
    user = (
        f"target_seniority: {payload.target_seniority.value}\n"
        f"followup_count: {payload.followup_count} (max {settings.max_followups_per_question})\n"
        f"interviewer_notes: {json.dumps(payload.interviewer_notes)}\n\n"
        f"current_question:\n"
        f"  theme: {payload.current_question.theme}\n"
        f"  question_text: {payload.current_question.question_text}\n"
        f"  expected_story_hook: {payload.current_question.expected_story_hook}\n\n"
        f"transcript_so_far:\n{transcript_blob or '(none)'}"
    )
    out = client.complete_json(
        system=load_prompt("interview.system.md"),
        user=user,
        schema=InterviewTurnOutput,
        tier="cheap",
        temperature=0.5,
        max_output_tokens=400,
    )
    if (
        out.next_action == "ask_followup"
        and out.followup_count > settings.max_followups_per_question
    ):
        return out.model_copy(update={"next_action": "move_on", "utterance": ""})
    return out
