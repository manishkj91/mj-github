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
    QuestionProgress,
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


@dataclass
class TurnResult:
    """Returned by ``begin_question``/``submit_answer`` for HTTP transports.

    Either ``utterance`` is set (the candidate must answer next) OR
    ``question_finished`` is True (move to the next question or summarize).
    """

    question: QuestionPlanItem
    utterance: str
    is_followup: bool
    question_finished: bool
    next_question_id: str | None
    session_complete: bool


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

    # -- HTTP-friendly turn-by-turn API --------------------------------------

    def select_questions(
        self, state: SessionState, question_ids: list[str] | None = None
    ) -> SessionState:
        """Pick which questions to actually run. Defaults to the first N from the plan."""
        if state.scan is None:
            raise RuntimeError("Cannot select questions before scan.")
        if question_ids is None:
            ids = [q.id for q in state.scan.question_plan][
                : self._settings.max_questions_per_session
            ]
        else:
            valid = {q.id for q in state.scan.question_plan}
            ids = [qid for qid in question_ids if qid in valid][
                : self._settings.max_questions_per_session
            ]
        state.selected_question_ids = ids
        state.current_question_index = 0
        if state.status == SessionStatus.SCANNED:
            state.status = SessionStatus.IN_INTERVIEW
        return state

    def begin_question(self, state: SessionState) -> TurnResult:
        """Ask the current question. Caller renders the utterance and waits for an answer."""
        question = self._current_question(state)
        if question is None:
            return self._terminal_turn(state)

        progress = state.progress.get(question.id) or QuestionProgress(question_id=question.id)
        transcript = state.transcripts.setdefault(question.id, [])

        ask = next_interviewer_turn(
            self._client,
            InterviewTurnInput(
                current_question=question,
                transcript_so_far=transcript,
                interviewer_notes=progress.interviewer_notes,
                followup_count=progress.followup_count,
                target_seniority=state.target_seniority,
            ),
        )
        transcript.append(Turn(role="interviewer", content=ask.utterance))
        progress.interviewer_notes = ask.updated_notes
        progress.awaiting_answer_to = ask.utterance
        state.progress[question.id] = progress

        return TurnResult(
            question=question,
            utterance=ask.utterance,
            is_followup=False,
            question_finished=False,
            next_question_id=None,
            session_complete=False,
        )

    def submit_answer(self, state: SessionState, answer_text: str) -> TurnResult:
        """Record the candidate's answer and decide what comes next.

        Either:
        * a follow-up question is returned (``is_followup=True``), OR
        * the question is marked finished and the next question id is returned.
        """
        question = self._current_question(state)
        if question is None:
            return self._terminal_turn(state)

        progress = state.progress.setdefault(
            question.id, QuestionProgress(question_id=question.id)
        )
        transcript = state.transcripts.setdefault(question.id, [])

        clipped = (answer_text or "").strip()[: self._settings.max_answer_chars]
        transcript.append(Turn(role="candidate", content=clipped))
        progress.awaiting_answer_to = None

        if progress.followup_count >= self._settings.max_followups_per_question:
            return self._finish_question(state, question, progress)

        decision = next_interviewer_turn(
            self._client,
            InterviewTurnInput(
                current_question=question,
                transcript_so_far=transcript,
                interviewer_notes=progress.interviewer_notes,
                followup_count=progress.followup_count,
                target_seniority=state.target_seniority,
            ),
        )
        progress.interviewer_notes = decision.updated_notes

        if decision.next_action != "ask_followup" or not decision.utterance.strip():
            return self._finish_question(state, question, progress)

        transcript.append(Turn(role="interviewer", content=decision.utterance))
        progress.followup_count = decision.followup_count
        progress.awaiting_answer_to = decision.utterance

        return TurnResult(
            question=question,
            utterance=decision.utterance,
            is_followup=True,
            question_finished=False,
            next_question_id=None,
            session_complete=False,
        )

    def skip_question(self, state: SessionState) -> TurnResult:
        """Mark current question as finished without further follow-ups."""
        question = self._current_question(state)
        if question is None:
            return self._terminal_turn(state)
        progress = state.progress.setdefault(
            question.id, QuestionProgress(question_id=question.id)
        )
        return self._finish_question(state, question, progress)

    def _finish_question(
        self,
        state: SessionState,
        question: QuestionPlanItem,
        progress: QuestionProgress,
    ) -> TurnResult:
        progress.finished = True
        progress.awaiting_answer_to = None
        state.progress[question.id] = progress
        state.current_question_index += 1
        next_q = self._current_question(state)
        return TurnResult(
            question=question,
            utterance="",
            is_followup=False,
            question_finished=True,
            next_question_id=next_q.id if next_q else None,
            session_complete=next_q is None,
        )

    def _current_question(self, state: SessionState) -> QuestionPlanItem | None:
        if state.scan is None or not state.selected_question_ids:
            return None
        if state.current_question_index >= len(state.selected_question_ids):
            return None
        target_id = state.selected_question_ids[state.current_question_index]
        for q in state.scan.question_plan:
            if q.id == target_id:
                return q
        return None

    def _terminal_turn(self, state: SessionState) -> TurnResult:
        # Best-effort placeholder when the caller asks for "next" but we're done.
        last_q = (
            state.scan.question_plan[-1]
            if state.scan and state.scan.question_plan
            else None
        )
        if last_q is None:
            raise RuntimeError("No questions in plan; cannot produce a terminal turn.")
        return TurnResult(
            question=last_q,
            utterance="",
            is_followup=False,
            question_finished=True,
            next_question_id=None,
            session_complete=True,
        )

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
