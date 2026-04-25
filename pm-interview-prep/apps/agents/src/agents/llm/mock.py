"""Deterministic mock LLM client.

The mock examines the requested ``schema`` and returns a hand-crafted, but
realistic-looking response for each known agent contract. This lets us:

* Run the full session CLI offline.
* Write fast unit tests that don't hit the network.
* Verify the orchestrator state machine in CI.

For any unrecognised schema the mock falls back to ``schema.model_construct``
with sensible defaults derived from the schema fields.
"""

from __future__ import annotations

import hashlib
import re
from typing import TypeVar

from pydantic import BaseModel

from ..contracts import (
    CandidateProfile,
    Competency,
    CompetencyHeatmapEntry,
    EvaluationOutput,
    InterviewTurnOutput,
    Metric,
    QuestionPlanItem,
    ResumeCitation,
    ResumeScanOutput,
    Role,
    RubricScores,
    SessionSummary,
)
from .base import LLMClient, ModelTier

T = TypeVar("T", bound=BaseModel)


# Canonical themes the mock scanner will distribute questions across. Mirrors
# the taxonomy used in `tools/taxonomy.py`.
_DEFAULT_THEMES = [
    "leadership",
    "stakeholder_conflict",
    "ambiguity",
    "failure",
    "prioritization",
    "data_driven_decision",
    "customer_obsession",
    "influence_without_authority",
]


class MockClient(LLMClient):
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        tier: ModelTier = "strong",
        temperature: float = 0.4,
        max_output_tokens: int = 2048,
    ) -> T:
        if schema is ResumeScanOutput:
            return self._mock_scan(user)  # type: ignore[return-value]
        if schema is InterviewTurnOutput:
            return self._mock_interview(user)  # type: ignore[return-value]
        if schema is EvaluationOutput:
            return self._mock_evaluation(user)  # type: ignore[return-value]
        if schema is SessionSummary:
            return self._mock_summary(user)  # type: ignore[return-value]
        raise NotImplementedError(
            f"MockClient has no canned response for schema {schema.__name__}"
        )

    # ---- per-schema canned responses ---------------------------------------

    def _mock_scan(self, user: str) -> ResumeScanOutput:
        resume_text = _extract_resume(user)
        roles = _extract_roles(resume_text)
        metrics = _extract_metrics(resume_text, roles)

        if not roles:
            roles = [Role(company="Unknown Co.", title="Product Manager")]

        # Seed competencies — high confidence for the first two themes,
        # medium for the next, and so on.
        competencies = [
            Competency(
                name=theme,
                confidence="high" if i < 2 else "medium" if i < 4 else "low",
                evidence=[roles[0].title + " @ " + roles[0].company],
            )
            for i, theme in enumerate(_DEFAULT_THEMES[:6])
        ]

        question_plan: list[QuestionPlanItem] = []
        for i, theme in enumerate(_DEFAULT_THEMES[:6]):
            role = roles[i % len(roles)]
            citation_span = _pick_citation(resume_text, role)
            question_plan.append(
                QuestionPlanItem(
                    id=f"q{i + 1}",
                    theme=theme,
                    question_text=_question_for_theme(theme, role),
                    why_this_question=(
                        f"Probes {theme.replace('_', ' ')} via the candidate's work as "
                        f"{role.title} at {role.company}."
                    ),
                    resume_citation=ResumeCitation(span=citation_span, role_index=i % len(roles))
                    if citation_span
                    else None,
                    is_gap_probe=citation_span is None,
                    expected_story_hook=(
                        f"Story about {theme.replace('_', ' ')} at {role.company}."
                    ),
                )
            )

        return ResumeScanOutput(
            candidate_profile=CandidateProfile(
                roles=roles,
                metrics=metrics,
                domains=_guess_domains(resume_text),
            ),
            inferred_competencies=competencies,
            gap_areas=[t for t in _DEFAULT_THEMES[6:] if True],
            question_plan=question_plan,
        )

    def _mock_interview(self, user: str) -> InterviewTurnOutput:
        # Heuristic: if the user prompt mentions "followup_count: 0" and the
        # last candidate turn looks short, ask a follow-up. Otherwise move on.
        followup_count = _extract_int(user, "followup_count", default=0)
        last_answer = _extract_last_candidate_answer(user)
        question_text = _extract_field(user, "question_text") or "Tell me about a time you led."

        if not last_answer:
            return InterviewTurnOutput(
                next_action="ask_question",
                utterance=question_text,
                updated_notes={"opened": True},
                followup_count=0,
            )
        if followup_count < 1 and _looks_thin(last_answer):
            return InterviewTurnOutput(
                next_action="ask_followup",
                utterance="Could you quantify the impact, and tell me who pushed back the most?",
                updated_notes={"asked_for_metric": True},
                followup_count=followup_count + 1,
            )
        return InterviewTurnOutput(
            next_action="move_on",
            utterance="",
            updated_notes={"complete": True},
            followup_count=followup_count,
        )

    def _mock_evaluation(self, user: str) -> EvaluationOutput:
        last_answer = _extract_last_candidate_answer(user) or ""
        seed = int(hashlib.md5(last_answer.encode("utf-8")).hexdigest(), 16)
        # Score 2-4 deterministically based on length; longer + more numbers = higher.
        length_bonus = min(2, len(last_answer) // 400)
        digit_bonus = 1 if re.search(r"\d", last_answer) else 0
        base = 2 + length_bonus + digit_bonus
        scores = RubricScores(
            structure=min(5, base + (seed % 2)),
            specificity=min(5, base + ((seed >> 1) % 2)),
            ownership=min(5, base),
            impact=min(5, base + digit_bonus),
            reflection=min(5, base),
            communication=min(5, base + 1),
        )
        return EvaluationOutput(
            rubric_scores=scores,
            what_worked=[
                "You opened with a clear situation and named the stakeholders involved.",
                "You owned the decision rather than crediting the team generically.",
            ],
            what_to_improve=[
                "Lead with the metric — say the result in the first 15 seconds.",
                "Cut the context by half; spend the recovered time on the action you took.",
            ],
            model_answer=(
                "**Situation.** At [Company], our activation rate had stalled at 38% for two "
                "quarters. **Task.** I owned a goal of lifting activation by 10pp in one quarter "
                "with a team of three engineers and one designer. **Action.** I ran a five-day "
                "discovery sprint, identified that 60% of drop-off happened on a single onboarding "
                "step, shipped a redesigned step behind a 50/50 experiment, and held the line on "
                "scope when sales pushed for a parallel SSO project. **Result.** Activation rose "
                "from 38% to 51% in six weeks, a +13pp lift, and we replicated the pattern across "
                "two adjacent funnels."
            ),
            revision_task=(
                "Re-tell this story in 90 seconds with the metric in the first sentence, "
                "and replace one paragraph of context with one specific user quote."
            ),
        )

    def _mock_summary(self, user: str) -> SessionSummary:
        return SessionSummary(
            competency_heatmap=[
                CompetencyHeatmapEntry(theme=t, score=3.5) for t in _DEFAULT_THEMES[:6]
            ],
            keep_stories=[
                "Activation lift story — strong metric, clear ownership.",
                "Failure / sunset story — honest reflection.",
            ],
            rework_stories=[
                "Stakeholder conflict story — needs a clearer 'I' vs 'we' boundary.",
            ],
            top_recommendations=[
                "Lead every answer with the headline metric.",
                "Practice cutting your situation paragraph by 50%.",
                "Add one customer quote to each customer-obsession story.",
            ],
        )


# ---- tiny extractors used by the mock ---------------------------------------


def _extract_resume(user: str) -> str:
    """The scanner prompt embeds the raw resume between markers."""
    m = re.search(r"<resume>(.*?)</resume>", user, re.DOTALL)
    return m.group(1).strip() if m else user


def _extract_roles(resume_text: str) -> list[Role]:
    roles: list[Role] = []
    # Naive heuristic: lines like "Title @ Company" or "Title, Company"
    for line in resume_text.splitlines():
        line = line.strip(" \t-•*")
        if not line:
            continue
        m = re.match(
            r"(?P<title>(Senior |Lead |Principal |Group |Associate )?(Product Manager|Engineer|Designer|Analyst))[\s,@\-|]+(?P<company>[A-Z][\w&\.\- ]{2,40})",
            line,
        )
        if m:
            roles.append(Role(title=m.group("title").strip(), company=m.group("company").strip()))
        if len(roles) >= 5:
            break
    return roles


def _extract_metrics(resume_text: str, roles: list[Role]) -> list[Metric]:
    metrics: list[Metric] = []
    for line in resume_text.splitlines():
        m = re.search(r"([+\-]?\d+\.?\d*\s?(?:%|pp|x|M|K|bps))", line)
        if m:
            metrics.append(
                Metric(
                    description=line.strip(" \t-•*")[:120],
                    value=m.group(1),
                    role_index=0,
                )
            )
        if len(metrics) >= 6:
            break
    return metrics


def _pick_citation(resume_text: str, role: Role) -> str | None:
    for line in resume_text.splitlines():
        if role.company.lower() in line.lower() or role.title.lower() in line.lower():
            return line.strip(" \t-•*")[:140]
    # Fall back to the first non-empty line, then None for "gap probe".
    for line in resume_text.splitlines():
        s = line.strip(" \t-•*")
        if len(s) > 20:
            return s[:140]
    return None


def _question_for_theme(theme: str, role: Role) -> str:
    bank = {
        "leadership": (
            f"Tell me about a time at {role.company} when you had to lead a team through a "
            "decision the team initially disagreed with."
        ),
        "stakeholder_conflict": (
            f"Walk me through a stakeholder conflict you navigated as {role.title}. What was at "
            "stake and how did you resolve it?"
        ),
        "ambiguity": (
            "Describe a project where the goal or success metric was ambiguous when you started. "
            "How did you frame it?"
        ),
        "failure": (
            f"Tell me about a launch or initiative at {role.company} that did not meet "
            "expectations. What did you learn?"
        ),
        "prioritization": (
            "Give me an example of a hard prioritization call you made. What did you say no to?"
        ),
        "data_driven_decision": (
            "Tell me about a decision you made primarily from data. Walk me through the analysis "
            "and the trade-off you accepted."
        ),
        "customer_obsession": (
            "Describe a time you advocated for the customer when it was unpopular internally."
        ),
        "influence_without_authority": (
            "Tell me about a time you got engineering or design to change direction without "
            "having formal authority over them."
        ),
    }
    return bank.get(theme, f"Tell me about a time you demonstrated {theme.replace('_', ' ')}.")


def _guess_domains(resume_text: str) -> list[str]:
    domains: list[str] = []
    text = resume_text.lower()
    for keyword, domain in [
        ("payments", "payments"),
        ("growth", "growth"),
        ("ml", "ai/ml"),
        ("ai", "ai/ml"),
        ("marketplace", "marketplace"),
        ("b2b", "b2b saas"),
        ("consumer", "consumer"),
        ("infra", "infrastructure"),
    ]:
        if keyword in text and domain not in domains:
            domains.append(domain)
    return domains[:4]


def _extract_int(user: str, key: str, default: int) -> int:
    m = re.search(rf"{key}\s*[:=]\s*(\d+)", user)
    return int(m.group(1)) if m else default


def _extract_field(user: str, key: str) -> str | None:
    m = re.search(rf"{key}\s*[:=]\s*(.+)", user)
    return m.group(1).strip() if m else None


def _extract_last_candidate_answer(user: str) -> str | None:
    matches = re.findall(r"<candidate>(.*?)</candidate>", user, re.DOTALL)
    return matches[-1].strip() if matches else None


def _looks_thin(answer: str) -> bool:
    if len(answer) < 220:
        return True
    if not re.search(r"\d", answer):
        return True
    return False
