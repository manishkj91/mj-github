"""Pydantic schemas defining the contracts between agents.

Every agent boundary is a strict, validated JSON object. No free-form prose
crosses an agent boundary; the orchestrator always sees structured data.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class CompanyTier(StrEnum):
    FAANG = "faang"
    GROWTH = "growth"
    AI_NATIVE = "ai_native"
    OTHER = "other"


class Seniority(StrEnum):
    APM = "apm"
    PM = "pm"
    SENIOR = "senior"
    GPM = "gpm"


class Role(BaseModel):
    company: str
    title: str
    start: str | None = None
    end: str | None = None
    scope: str | None = None  # e.g. "team of 6, $4M ARR product"


class Metric(BaseModel):
    description: str
    value: str  # keep raw, e.g. "+38% activation"
    role_index: int


class Competency(BaseModel):
    name: str  # e.g. "stakeholder_conflict"
    confidence: Literal["low", "medium", "high"]
    evidence: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    roles: list[Role]
    metrics: list[Metric] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class ResumeCitation(BaseModel):
    span: str  # verbatim substring from the resume
    role_index: int


class QuestionPlanItem(BaseModel):
    id: str  # short slug, unique within a session
    theme: str  # canonical theme key, e.g. "stakeholder_conflict"
    question_text: str
    why_this_question: str
    resume_citation: ResumeCitation | None = (
        None  # None ONLY when explicitly flagged as a gap probe
    )
    is_gap_probe: bool = False
    expected_story_hook: str


class ResumeScanInput(BaseModel):
    resume_text: str
    target_company_tier: CompanyTier
    target_seniority: Seniority


class ResumeScanOutput(BaseModel):
    candidate_profile: CandidateProfile
    inferred_competencies: list[Competency]
    gap_areas: list[str] = Field(default_factory=list)
    question_plan: list[QuestionPlanItem] = Field(min_length=5, max_length=12)


# ---------- Interview Agent ---------------------------------------------------

TurnRole = Literal["interviewer", "candidate"]


class Turn(BaseModel):
    role: TurnRole
    content: str
    meta: dict = Field(default_factory=dict)


InterviewAction = Literal["ask_question", "ask_followup", "move_on"]


class InterviewTurnInput(BaseModel):
    current_question: QuestionPlanItem
    transcript_so_far: list[Turn] = Field(default_factory=list)
    interviewer_notes: dict = Field(default_factory=dict)
    followup_count: int = 0
    target_seniority: Seniority


class InterviewTurnOutput(BaseModel):
    next_action: InterviewAction
    utterance: str  # what the interviewer says next ("" when moving on)
    updated_notes: dict = Field(default_factory=dict)
    followup_count: int = 0


# ---------- Evaluation Agent --------------------------------------------------


class RubricScores(BaseModel):
    structure: int = Field(ge=1, le=5)
    specificity: int = Field(ge=1, le=5)
    ownership: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    reflection: int = Field(ge=1, le=5)
    communication: int = Field(ge=1, le=5)

    @property
    def average(self) -> float:
        return (
            self.structure
            + self.specificity
            + self.ownership
            + self.impact
            + self.reflection
            + self.communication
        ) / 6


class EvaluationInput(BaseModel):
    question: QuestionPlanItem
    transcript: list[Turn]
    interviewer_notes: dict = Field(default_factory=dict)
    target_seniority: Seniority


class EvaluationOutput(BaseModel):
    rubric_scores: RubricScores
    what_worked: list[str] = Field(min_length=1, max_length=4)
    what_to_improve: list[str] = Field(min_length=1, max_length=4)
    model_answer: str  # rewritten in STAR, ~250 words
    revision_task: str


# ---------- Session summary ---------------------------------------------------


class CompetencyHeatmapEntry(BaseModel):
    theme: str
    score: float  # 1.0 - 5.0


class SessionSummary(BaseModel):
    competency_heatmap: list[CompetencyHeatmapEntry]
    keep_stories: list[str]
    rework_stories: list[str]
    top_recommendations: list[str]


# ---------- Session state -----------------------------------------------------


class SessionStatus(StrEnum):
    INTAKE = "intake"
    SCANNED = "scanned"
    IN_INTERVIEW = "in_interview"
    COMPLETE = "complete"


class QuestionProgress(BaseModel):
    """Per-question progress for the HTTP/turn-by-turn flow."""

    question_id: str
    followup_count: int = 0
    interviewer_notes: dict = Field(default_factory=dict)
    awaiting_answer_to: str | None = None  # the last interviewer utterance
    finished: bool = False


class SessionState(BaseModel):
    session_id: str
    status: SessionStatus = SessionStatus.INTAKE
    target_company_tier: CompanyTier
    target_seniority: Seniority
    resume_text: str
    scan: ResumeScanOutput | None = None
    transcripts: dict[str, list[Turn]] = Field(default_factory=dict)
    evaluations: dict[str, EvaluationOutput] = Field(default_factory=dict)
    summary: SessionSummary | None = None
    progress: dict[str, QuestionProgress] = Field(default_factory=dict)
    selected_question_ids: list[str] = Field(default_factory=list)
    current_question_index: int = 0
