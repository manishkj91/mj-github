// Mirrors apps/agents/src/agents/contracts.py. Kept hand-written and small to
// avoid a code-generation step in v1; the agents service is the source of truth.

export type CompanyTier = "faang" | "growth" | "ai_native" | "other";
export type Seniority = "apm" | "pm" | "senior" | "gpm";
export type SessionStatus = "intake" | "scanned" | "in_interview" | "complete";

export interface ResumeCitation {
  span: string;
  role_index: number;
}

export interface QuestionPlanItem {
  id: string;
  theme: string;
  question_text: string;
  why_this_question: string;
  resume_citation: ResumeCitation | null;
  is_gap_probe: boolean;
  expected_story_hook: string;
}

export interface Role {
  company: string;
  title: string;
  start: string | null;
  end: string | null;
  scope: string | null;
}

export interface Metric {
  description: string;
  value: string;
  role_index: number;
}

export interface Competency {
  name: string;
  confidence: "low" | "medium" | "high";
  evidence: string[];
}

export interface CandidateProfile {
  roles: Role[];
  metrics: Metric[];
  domains: string[];
}

export interface ResumeScanOutput {
  candidate_profile: CandidateProfile;
  inferred_competencies: Competency[];
  gap_areas: string[];
  question_plan: QuestionPlanItem[];
}

export interface RubricScores {
  structure: number;
  specificity: number;
  ownership: number;
  impact: number;
  reflection: number;
  communication: number;
}

export interface EvaluationOutput {
  rubric_scores: RubricScores;
  what_worked: string[];
  what_to_improve: string[];
  model_answer: string;
  revision_task: string;
}

export interface CompetencyHeatmapEntry {
  theme: string;
  score: number;
}

export interface SessionSummary {
  competency_heatmap: CompetencyHeatmapEntry[];
  keep_stories: string[];
  rework_stories: string[];
  top_recommendations: string[];
}

export interface Turn {
  role: "interviewer" | "candidate";
  content: string;
  meta: Record<string, unknown>;
}

export interface SessionState {
  session_id: string;
  status: SessionStatus;
  target_company_tier: CompanyTier;
  target_seniority: Seniority;
  resume_text: string;
  scan: ResumeScanOutput | null;
  transcripts: Record<string, Turn[]>;
  evaluations: Record<string, EvaluationOutput>;
  summary: SessionSummary | null;
  selected_question_ids: string[];
  current_question_index: number;
}

export type TurnKind =
  | "interviewer_utterance"
  | "question_finished"
  | "session_complete";

export interface TurnResponse {
  kind: TurnKind;
  question_id: string;
  question_theme: string;
  utterance: string;
  is_followup: boolean;
  next_question_id: string | null;
}
