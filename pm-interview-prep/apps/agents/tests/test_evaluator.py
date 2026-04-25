from agents.agents import evaluate_answer
from agents.contracts import (
    EvaluationInput,
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
        resume_citation=ResumeCitation(span="Stripe", role_index=0),
        is_gap_probe=False,
        expected_story_hook="Stripe Connect onboarding redesign.",
    )


def test_strong_answer_scores_higher_than_weak():
    weak = [
        Turn(role="interviewer", content="..."),
        Turn(role="candidate", content="I led a team. It was hard."),
    ]
    strong = [
        Turn(role="interviewer", content="..."),
        Turn(
            role="candidate",
            content=(
                "At Stripe, KYC activation had stalled at 38% for two quarters. I owned the "
                "redesign with a team of 4 engineers, ran a 5-day discovery sprint, found 60% "
                "of drop-off on one step, shipped a redesigned step behind a 50/50 experiment, "
                "and lifted activation to 51% in 6 weeks — a 13pp lift. I held the line on "
                "scope when sales pushed for an unrelated SSO project."
            ),
        ),
    ]
    weak_eval = evaluate_answer(
        MockClient(),
        EvaluationInput(
            question=_q(),
            transcript=weak,
            interviewer_notes={},
            target_seniority=Seniority.SENIOR,
        ),
    )
    strong_eval = evaluate_answer(
        MockClient(),
        EvaluationInput(
            question=_q(),
            transcript=strong,
            interviewer_notes={},
            target_seniority=Seniority.SENIOR,
        ),
    )
    assert strong_eval.rubric_scores.average > weak_eval.rubric_scores.average


def test_evaluation_has_required_fields():
    transcript = [
        Turn(role="interviewer", content="..."),
        Turn(role="candidate", content="I shipped a thing and it worked."),
    ]
    ev = evaluate_answer(
        MockClient(),
        EvaluationInput(
            question=_q(),
            transcript=transcript,
            interviewer_notes={},
            target_seniority=Seniority.PM,
        ),
    )
    assert ev.what_worked
    assert ev.what_to_improve
    assert ev.model_answer
    assert ev.revision_task
    for s in ev.rubric_scores.model_dump().values():
        assert 1 <= s <= 5
