from agents.agents import next_interviewer_turn
from agents.contracts import (
    InterviewTurnInput,
    QuestionPlanItem,
    ResumeCitation,
    Seniority,
    Turn,
)
from agents.llm import MockClient


def _q() -> QuestionPlanItem:
    return QuestionPlanItem(
        id="q1",
        theme="leadership",
        question_text="Tell me about a time you led a team through disagreement.",
        why_this_question="Probes leadership.",
        resume_citation=ResumeCitation(span="Senior Product Manager, Stripe", role_index=0),
        is_gap_probe=False,
        expected_story_hook="Stripe Connect onboarding redesign.",
    )


def test_first_turn_asks_the_question() -> None:
    out = next_interviewer_turn(
        MockClient(),
        InterviewTurnInput(
            current_question=_q(),
            transcript_so_far=[],
            interviewer_notes={},
            followup_count=0,
            target_seniority=Seniority.SENIOR,
        ),
    )
    assert out.next_action == "ask_question"
    assert out.utterance


def test_thin_answer_triggers_followup() -> None:
    transcript = [
        Turn(role="interviewer", content="Tell me about leadership."),
        Turn(role="candidate", content="I led a team. It went well."),
    ]
    out = next_interviewer_turn(
        MockClient(),
        InterviewTurnInput(
            current_question=_q(),
            transcript_so_far=transcript,
            interviewer_notes={},
            followup_count=0,
            target_seniority=Seniority.SENIOR,
        ),
    )
    assert out.next_action == "ask_followup"
    assert out.followup_count == 1


def test_strong_answer_moves_on() -> None:
    strong = (
        "At Stripe, our merchant KYC activation had stalled at 38% for two quarters. "
        "I led a 5-day discovery sprint that surfaced a single 60%-drop-off step. We "
        "shipped a redesigned step behind a 50/50 experiment, lifting activation to 51% "
        "in 6 weeks — a 13pp lift. I held the line on scope when sales pushed for SSO."
    )
    transcript = [
        Turn(role="interviewer", content="Tell me about leadership."),
        Turn(role="candidate", content=strong),
    ]
    out = next_interviewer_turn(
        MockClient(),
        InterviewTurnInput(
            current_question=_q(),
            transcript_so_far=transcript,
            interviewer_notes={},
            followup_count=0,
            target_seniority=Seniority.SENIOR,
        ),
    )
    assert out.next_action == "move_on"


def test_followup_cap_enforced() -> None:
    transcript = [
        Turn(role="interviewer", content="Tell me about leadership."),
        Turn(role="candidate", content="short."),
        Turn(role="interviewer", content="Quantify it?"),
        Turn(role="candidate", content="still short."),
    ]
    out = next_interviewer_turn(
        MockClient(),
        InterviewTurnInput(
            current_question=_q(),
            transcript_so_far=transcript,
            interviewer_notes={},
            followup_count=2,
            target_seniority=Seniority.SENIOR,
        ),
    )
    assert out.next_action == "move_on"
