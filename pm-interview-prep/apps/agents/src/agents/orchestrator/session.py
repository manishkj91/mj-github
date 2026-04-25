"""Session orchestrator.

Owns the state machine:

    INTAKE -> SCANNED -> IN_INTERVIEW(qN) -> ... -> COMPLETE

Pure-Python; no I/O beyond what the answer-provider does. Decoupling answer
input behind the ``AnswerProvider`` callable lets the same orchestrator drive
the CLI today and an HTTP/WebSocket transport tomorrow.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from ..agents import (
    build_summary,
    evaluate_answer,
    next_interviewer_turn,
    scan_resume,
)
from ..config import get_settings
from ..contracts import (
    CompanyTier,
    EvaluationInput,
    InterviewTurnInput,
    QuestionPlanItem,
    ResumeScanInput,
    Seniority,
    SessionState,
    SessionStatus,
    Turn,
)
from ..llm import LLMClient


@dataclass
class InterviewerSay:
    """The orchestrator emits these so the transport (CLI/web) can render."""

    question: QuestionPlanItem
    utterance: str
    is_followup: bool


# An AnswerProvider takes the latest interviewer utterance and returns the
# candidate's answer. Sync for now.
AnswerProvider = Callable[[InterviewerSay], str]


def new_session(
    resume_text: str,
    tier: CompanyTier,
    seniority: Seniority,
) -> SessionState:
    return SessionState(
        session_id=uuid.uuid4().hex[:12],
        target_company_tier=tier,
        target_seniority=seniority,
        resume_text=resume_text,
    )


class Orchestrator:
    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._settings = get_settings()

    # -- public API -----------------------------------------------------------

    def scan(self, state: SessionState) -> SessionState:
        if state.status != SessionStatus.INTAKE:
            return state
        scan = scan_resume(
            self._client,
            ResumeScanInput(
                resume_text=state.resume_text,
                target_company_tier=state.target_company_tier,
                target_seniority=state.target_seniority,
            ),
        )
        state.scan = scan
        state.status = SessionStatus.SCANNED
        return state

    def run_interview(
        self,
        state: SessionState,
        get_answer: AnswerProvider,
        *,
        max_questions: int | None = None,
    ) -> SessionState:
        if state.scan is None:
            raise RuntimeError("Cannot run interview before scan.")
        if state.status not in (SessionStatus.SCANNED, SessionStatus.IN_INTERVIEW):
            return state
        state.status = SessionStatus.IN_INTERVIEW

        max_q = max_questions or self._settings.max_questions_per_session
        questions = state.scan.question_plan[:max_q]

        for question in questions:
            self._run_one_question(state, question, get_answer)

        return state

    def evaluate_all(self, state: SessionState) -> SessionState:
        if state.scan is None:
            raise RuntimeError("Cannot evaluate before scan.")
        for question in state.scan.question_plan:
            transcript = state.transcripts.get(question.id)
            if not transcript or question.id in state.evaluations:
                continue
            ev = evaluate_answer(
                self._client,
                EvaluationInput(
                    question=question,
                    transcript=transcript,
                    interviewer_notes={},
                    target_seniority=state.target_seniority,
                ),
            )
            state.evaluations[question.id] = ev
        return state

    def summarize(self, state: SessionState) -> SessionState:
        if state.scan is None:
            return state
        if not state.evaluations:
            return state
        state.summary = build_summary(
            self._client,
            questions=state.scan.question_plan,
            evaluations=state.evaluations,
        )
        state.status = SessionStatus.COMPLETE
        return state

    def run_full_session(
        self, state: SessionState, get_answer: AnswerProvider
    ) -> SessionState:
        self.scan(state)
        self.run_interview(state, get_answer)
        self.evaluate_all(state)
        self.summarize(state)
        return state

    # -- internals ------------------------------------------------------------

    def _run_one_question(
        self,
        state: SessionState,
        question: QuestionPlanItem,
        get_answer: AnswerProvider,
    ) -> None:
        transcript: list[Turn] = []
        notes: dict = {}
        followup_count = 0
        max_followups = self._settings.max_followups_per_question

        # Initial ask.
        ask = next_interviewer_turn(
            self._client,
            InterviewTurnInput(
                current_question=question,
                transcript_so_far=transcript,
                interviewer_notes=notes,
                followup_count=followup_count,
                target_seniority=state.target_seniority,
            ),
        )
        transcript.append(Turn(role="interviewer", content=ask.utterance))
        notes = ask.updated_notes

        candidate_answer = get_answer(
            InterviewerSay(question=question, utterance=ask.utterance, is_followup=False)
        )
        candidate_answer = candidate_answer[: self._settings.max_answer_chars]
        transcript.append(Turn(role="candidate", content=candidate_answer))

        # Follow-up loop.
        while followup_count < max_followups:
            turn = next_interviewer_turn(
                self._client,
                InterviewTurnInput(
                    current_question=question,
                    transcript_so_far=transcript,
                    interviewer_notes=notes,
                    followup_count=followup_count,
                    target_seniority=state.target_seniority,
                ),
            )
            notes = turn.updated_notes
            if turn.next_action != "ask_followup":
                break
            transcript.append(Turn(role="interviewer", content=turn.utterance))
            followup_count = turn.followup_count
            answer = get_answer(
                InterviewerSay(question=question, utterance=turn.utterance, is_followup=True)
            )
            answer = answer[: self._settings.max_answer_chars]
            transcript.append(Turn(role="candidate", content=answer))

        state.transcripts[question.id] = transcript


def cli_answer_provider(prompt_fn: Callable[[str], str] | None = None) -> AnswerProvider:
    """Default CLI answer provider — prints the question and reads stdin."""

    fn = prompt_fn or _default_prompt

    def provider(say: InterviewerSay) -> str:
        marker = "↪ Follow-up" if say.is_followup else f"Question [{say.question.theme}]"
        print(f"\n{marker}: {say.utterance}\n")
        return fn("Your answer (end with a blank line):\n")

    return provider


def _default_prompt(label: str) -> str:
    print(label, end="")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()
