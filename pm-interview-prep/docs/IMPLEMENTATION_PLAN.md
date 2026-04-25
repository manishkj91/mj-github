# Implementation Plan: PM Behavioral Interview Prep Tool

**Companion to:** `PRD.md`
**Status:** Draft v0.1
**Last updated:** 2026-04-25

This plan translates the PRD into a concrete, sequenced build. It is organized around milestones (M0–M5), each with deliverables, acceptance criteria, and the technical decisions required.

---

## 1. Architecture Overview

### 1.1 High-level diagram (text)

```
                ┌─────────────────────┐
                │        Web UI       │  Next.js (App Router) + Tailwind
                │  (upload, chat, UI) │
                └──────────┬──────────┘
                           │  HTTP / Server Actions
                           ▼
                ┌─────────────────────┐
                │     API Layer       │  FastAPI (Python) or Next API routes
                │  /session, /scan,   │
                │  /interview, /eval  │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │    Orchestrator     │  Python service (LangGraph or custom FSM)
                │  - state machine    │
                │  - tool registry    │
                │  - retries / cost   │
                └──┬─────────┬────────┘
                   │         │
        ┌──────────┘         └───────────┐
        ▼                                ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Resume Scanner │  │ Interview      │  │ Evaluation     │
│ Agent          │  │ Agent          │  │ Agent          │
└──────┬─────────┘  └──────┬─────────┘  └──────┬─────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌────────────────────────────────────────────────────────┐
│                     Tool Layer                         │
│  pdf_parse · entity_extract · taxonomy_lookup ·        │
│  question_bank · score_rubric · exemplar_retrieve      │
└──────┬─────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Storage: Postgres (sessions) · Object store (resumes)  │
│ Vector store: pgvector (taxonomy + exemplars)          │
└────────────────────────────────────────────────────────┘
```

### 1.2 Key design choices
- **Single repo, two apps:** `apps/web` (Next.js UI) and `apps/agents` (Python FastAPI + agents). Shared `packages/contracts` for typed schemas.
- **Stateful orchestrator, stateless agents.** Each agent is a pure `(input, tools) -> structured_output`. The orchestrator owns session memory.
- **Structured outputs everywhere.** Every agent returns Pydantic-validated JSON; no free-form prose at agent boundaries.
- **Two-tier model strategy.** Cheap, fast model (e.g., Haiku-class) for the Interview Agent's routine probes; stronger model (e.g., Sonnet-class) for Scanner and Evaluation. Configurable via env.
- **Deterministic plan, stochastic conversation.** Question plan is generated once and persisted; the interview loop reads from it. Re-rolls re-run only the affected slot.

---

## 2. Tech Stack (proposed)

| Layer            | Choice                                  | Why |
|------------------|-----------------------------------------|-----|
| Frontend         | Next.js 14 (App Router) + Tailwind + shadcn/ui | Fast, modern, easy to deploy on Vercel. |
| Backend / agents | Python 3.11 + FastAPI                   | Best ecosystem for LLM tooling; matches author's stack. |
| Agent framework  | LangGraph (preferred) or custom FSM     | Native state machine + checkpointing fits orchestrator pattern. |
| LLM provider     | Anthropic Claude (primary), OpenAI as fallback | Strong structured output + tool use. Both abstracted behind a `LLMClient` interface. |
| PDF/DOCX parse   | `pypdf`, `python-docx`, `unstructured`  | Reliable, no vendor lock. |
| Storage          | Postgres (Neon/Supabase) + pgvector     | Single DB for session + embeddings. |
| Object storage   | S3-compatible (Cloudflare R2)           | Cheap, simple. |
| Auth             | None in v1; magic link in v1.1          | Defer complexity. |
| Observability    | OpenTelemetry → Langfuse / Logfire      | Per-agent traces, token cost. |
| Hosting          | Vercel (web) + Fly.io / Render (agents) | Author's prior tooling. |

---

## 3. Data Model (v1)

```text
session
  id (uuid, pk)
  created_at
  target_company_tier         enum(faang, growth, ai_native, other)
  target_seniority            enum(apm, pm, senior, gpm)
  status                      enum(intake, scanned, in_interview, complete)
  resume_object_key
  redacted_resume_text

candidate_profile             (1:1 with session)
  session_id (fk)
  roles_json                  -- [{company, title, start, end, scope}]
  metrics_json
  inferred_competencies_json

question_plan_item
  id, session_id (fk)
  ord                         -- order in plan
  theme                       -- e.g., "stakeholder_conflict"
  question_text
  why_this_question
  resume_citation_span        -- verbatim resume substring
  status                      enum(pending, asked, answered, rerolled)

turn
  id, session_id (fk), question_plan_item_id (fk)
  role                        enum(interviewer, candidate)
  content_text
  meta_json                   -- e.g., probe_type, tokens
  created_at

evaluation
  id, session_id (fk), question_plan_item_id (fk)
  rubric_scores_json          -- {structure: 4, specificity: 3, ...}
  what_worked_json
  what_to_improve_json
  model_answer_text
  revision_task_text
  cost_cents
  created_at

session_summary               (1:1 with session)
  session_id (fk)
  competency_heatmap_json
  story_bank_json
  top_recommendations_json
```

---

## 4. Agent Contracts (interfaces)

All inputs/outputs are JSON schemas, validated by Pydantic on the Python side and by Zod on the TS side (both generated from `packages/contracts`).

### 4.1 Resume Scanner

```python
class ResumeScanInput(BaseModel):
    resume_text: str
    target_company_tier: Literal["faang", "growth", "ai_native", "other"]
    target_seniority: Literal["apm", "pm", "senior", "gpm"]

class ResumeCitation(BaseModel):
    span: str           # verbatim substring from resume
    role_index: int     # which role it came from

class QuestionPlanItem(BaseModel):
    theme: str
    question_text: str
    why_this_question: str
    resume_citation: ResumeCitation | None  # None only if explicitly a "gap probe"
    expected_story_hook: str

class ResumeScanOutput(BaseModel):
    candidate_profile: CandidateProfile
    inferred_competencies: list[Competency]
    gap_areas: list[str]
    question_plan: list[QuestionPlanItem]  # length 8–12
```

### 4.2 Interview Agent

```python
class InterviewTurnInput(BaseModel):
    session_id: str
    current_question: QuestionPlanItem
    transcript_so_far: list[Turn]
    interviewer_notes: dict

class InterviewTurnOutput(BaseModel):
    next_action: Literal["ask_question", "ask_followup", "move_on"]
    utterance: str
    updated_notes: dict
    followup_count: int
```

### 4.3 Evaluation Agent

```python
class EvaluationInput(BaseModel):
    question: QuestionPlanItem
    transcript: list[Turn]
    interviewer_notes: dict
    target_seniority: str

class RubricScores(BaseModel):
    structure: int          # 1–5
    specificity: int
    ownership: int
    impact: int
    reflection: int
    communication: int

class EvaluationOutput(BaseModel):
    rubric_scores: RubricScores
    what_worked: list[str]
    what_to_improve: list[str]
    model_answer: str       # ≤ 250 words, STAR
    revision_task: str
```

---

## 5. Tools (callable by agents)

| Tool | Used by | Purpose |
|------|---------|---------|
| `pdf_parse(file_bytes)` | Scanner | Extract text + section structure. |
| `redact_pii(text)` | Scanner | Strip emails, phone, address before storage/logging. |
| `extract_entities(text)` | Scanner | Roles, dates, companies, metrics. |
| `competency_taxonomy_lookup(tier, seniority)` | Scanner | Returns the canonical theme list to cover. |
| `question_bank_lookup(theme, tier)` | Scanner | Pull seed phrasings/exemplars for a theme. |
| `score_rubric(answer, theme, seniority)` | Evaluation | Returns per-dimension scores with reasoning. |
| `retrieve_exemplar_answer(theme, seniority)` | Evaluation | Pull a calibrated strong answer for tone. |
| `rewrite_stronger_version(transcript)` | Evaluation | Produce the STAR rewrite of the user's own story. |

Tools are plain Python functions registered with the agent framework. None of them call external paid APIs except the LLM tools.

---

## 6. Prompts (where to find them)

A separate `prompts/` directory at the root of the agents app:

```
apps/agents/prompts/
  scanner.system.md
  scanner.user.md
  interview.system.md
  interview.followup.user.md
  evaluation.system.md
  evaluation.rubric.md           # the canonical rubric the eval agent reads
  exemplars/                     # 30+ hand-curated strong/weak answers
```

Each prompt file is versioned (`v1`, `v2`...) and referenced by version in code so we can A/B without redeploying.

---

## 7. Milestones

### M0 — Foundations (scaffolding only)
**Deliverables:**
- Monorepo set up (`apps/web`, `apps/agents`, `packages/contracts`).
- Lint, format, typecheck, and a single CI workflow green.
- `.env.example`, secrets policy, and a `make dev` that boots web + API.
- Hello-world agent endpoint that round-trips a string through Claude.

**Acceptance:** `make dev` runs locally; CI passes on a noop PR.

---

### M1 — Resume Scanner Agent (CLI-first)
**Deliverables:**
- `pdf_parse`, `redact_pii`, `extract_entities` tools.
- Scanner agent producing valid `ResumeScanOutput` for 10 fixture resumes.
- A pytest suite asserting: every non-gap question has a citation that exists verbatim in the resume.
- A CLI: `python -m agents.scan path/to/resume.pdf --tier faang --seniority senior`.

**Acceptance:** ≥9/10 fixtures produce a usable plan (manual review). Citation check passes 100%.

---

### M2 — Interview + Evaluation Agents (CLI loop)
**Deliverables:**
- Interview agent with one-question-at-a-time loop and ≤2 follow-ups.
- Evaluation agent producing valid `EvaluationOutput` with calibrated scoring.
- An end-to-end CLI: `python -m agents.session run path/to/resume.pdf` that runs the full state machine and prints a Markdown summary.
- Eval set: 50 hand-graded (question, answer) pairs; report mean absolute error per rubric dimension vs. human grader. Target MAE ≤ 1.0.

**Acceptance:** A live demo against author's own resume produces tailored questions, sensible follow-ups, and rubric scores within target MAE.

---

### M3 — Web UI (closed alpha)
**Deliverables:**
- Upload page, plan-review page, chat-style interview page, summary page.
- Server actions or REST endpoints wired to the agents service.
- Session persistence in Postgres; resume-by-link.
- Basic styling polished enough to share.

**Acceptance:** 5 alpha users complete a full session; ≥3 say it's useful; cost per session ≤ $0.30 average.

---

### M4 — Hardening & Public v1
**Deliverables:**
- Rate limiting, abuse protection, PII redaction verified, TTL on stored resumes.
- Observability: per-session trace view (Langfuse) for the author.
- README, screenshots, Loom demo, deploy to Vercel + Fly.
- "How it works" page explaining the agent architecture (great recruiting artifact).

**Acceptance:** Public link live; passes a self-led security review checklist; author can debug any session from logs alone.

---

### M5 — v1.1 polish (post-launch)
**Deliverables:**
- Interviewer persona selection (Amazon / Google / Stripe / generic).
- Re-roll a question.
- Markdown export of session.
- Question-quality "thumbs" feedback flowing into a review queue.

**Acceptance:** First 25 public sessions reviewed; rubric calibration updated; one prompt iteration shipped based on real feedback.

---

## 8. Sequencing & Dependencies

```
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5
          │       │
          └──► Eval set (parallel)
                  │
                  └──► Rubric calibration (feeds M2 acceptance)
```

The eval set (50 graded answers) is the long-pole item; start curating during M1 in parallel, not after.

---

## 9. Evaluation & Quality Strategy

This is an LLM product — quality cannot be left to vibes. Three layers of evals:

1. **Scanner regression suite (fast, runs in CI).**
   - 10 fixture resumes → each produces a plan.
   - Assertions: schema valid, ≥1 question per required theme, every citation appears verbatim.

2. **Interview agent behavioral suite (run nightly).**
   - Scripted candidate replies (under-specified, over-specified, off-topic).
   - Assertions: at most 2 follow-ups, never evaluates inline, never invents resume facts.

3. **Evaluation calibration set (run on every prompt change).**
   - 50 hand-graded answers across themes and seniorities.
   - Metric: MAE vs. human on each rubric dimension; target ≤ 1.0; alert if drift > 0.3.

A `/evals` directory at repo root holds fixtures, scripts, and the calibration set. A `make evals` target runs all three.

---

## 10. Cost & Latency Budget

| Stage                | Model tier   | Max tokens (in/out) | Target latency | Target cost |
|----------------------|--------------|---------------------|----------------|-------------|
| Resume scan          | Strong       | 8k / 2k             | ≤ 20s          | ~$0.06      |
| Interview turn (Q)   | Cheap        | 2k / 0.4k           | ≤ 4s           | ~$0.01      |
| Interview followup   | Cheap        | 3k / 0.3k           | ≤ 4s           | ~$0.01      |
| Evaluation per Q     | Strong       | 4k / 1.5k           | ≤ 12s          | ~$0.04      |
| Session summary      | Strong       | 6k / 1.5k           | ≤ 15s          | ~$0.05      |
| **Total / session**  |              |                     | ≤ 90s LLM-time | **~$0.27**  |

Mitigations if over budget: rolling-summary of transcript instead of full replay; cap answer length to 350 words; downshift evaluation to medium tier for non-final questions.

---

## 11. Security & Privacy

- Resumes stored encrypted at rest (object store SSE) and never logged in raw form.
- PII redaction (`redact_pii` tool) runs **before** any text is sent to the LLM provider for logging/analytics tracing.
- LLM provider configured with zero-retention / no-training where available.
- Default 30-day TTL on resumes and sessions; user-triggered "delete my data" endpoint in v1.
- No third-party analytics with PII. First-party event counts only.
- Threat model checklist tracked in `docs/SECURITY.md` (created in M4).

---

## 12. Risks (engineering-specific) & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM provider outage | `LLMClient` abstraction with Anthropic primary, OpenAI fallback, queued retry. |
| Prompt regressions on update | All prompt changes gated by passing the eval suite in CI. |
| PDF parsing failures on weird layouts | Fall back to `unstructured` then to user paste-text. |
| Long answers blow context window | Rolling summarization of older turns; hard cap on answer tokens. |
| Cost spikes from a single user | Per-session token budget enforced in orchestrator; hard stop with friendly message. |
| Single-developer bus factor | Architecture intentionally boring (FastAPI + Postgres + Next.js); no exotic infra. |

---

## 13. Out of Scope for v1 (engineering view)

- Real-time voice (WebRTC, Whisper streaming).
- Multi-tenant org / team accounts.
- Fine-tuning a model on user data.
- Mobile apps.
- A/B framework for prompts beyond manual versioning.
- Payments.

---

## 14. Definition of Done (v1)

- A stranger can land on the public URL, upload a resume, complete a 5-question session, get a useful summary, and export it — without the author touching anything.
- The author can open a Langfuse trace for any session and explain every agent decision.
- Cost per session is under budget across the last 50 sessions.
- The README explains the agent architecture clearly enough that a hiring manager skimming it for 3 minutes "gets it."
