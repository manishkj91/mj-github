import json
from pathlib import Path

from agents.contracts import CompanyTier, Seniority, SessionStatus
from agents.llm import MockClient
from agents.orchestrator import Orchestrator, new_session
from agents.orchestrator.session import InterviewerSay


def test_full_session_runs_end_to_end(fixtures_dir: Path) -> None:
    resume = (fixtures_dir / "resume_alex.txt").read_text()
    answers = json.loads((fixtures_dir / "answers_alex.json").read_text())

    state = new_session(resume, tier=CompanyTier.FAANG, seniority=Seniority.SENIOR)

    orch = Orchestrator(MockClient())

    def provider(say: InterviewerSay) -> str:
        return answers.get(say.question.id, "I don't have a great example here.")

    orch.scan(state)
    assert state.scan is not None and state.scan.question_plan
    orch.run_interview(state, provider)
    orch.evaluate_all(state)
    orch.summarize(state)

    assert state.status == SessionStatus.COMPLETE
    assert state.summary is not None
    assert state.summary.competency_heatmap
    assert state.summary.top_recommendations

    answered = [q for q in state.scan.question_plan if q.id in state.transcripts]
    assert len(answered) >= 1
    for q in answered:
        assert q.id in state.evaluations
