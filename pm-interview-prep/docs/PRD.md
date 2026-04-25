# PRD: PM Behavioral Interview Prep Tool

**Owner:** Manish Jain
**Status:** Draft v0.1
**Last updated:** 2026-04-25
**Doc type:** Product Requirements Document

---

## 1. Overview

### 1.1 Problem
Behavioral interviews are the highest-variance, lowest-feedback portion of Product Manager loops at top tech companies (FAANG, Stripe, Airbnb, OpenAI, etc.). Candidates struggle with three things:

1. **Question anticipation:** They don't know which behavioral themes interviewers will mine from their resume (e.g., "stakeholder conflict," "ambiguous metric," "shipping under deadline pressure").
2. **Answer structure:** They default to chronology instead of frameworks like STAR / SCQA / CARL, and bury the impact.
3. **Feedback loop:** Mock interviews with peers are scarce, expensive, and inconsistent. Self-recording lacks rubric-based critique.

### 1.2 Solution (one-liner)
An agentic web app where a candidate uploads their resume and gets a tailored, multi-turn behavioral interview simulation, followed by a rubric-based evaluation of every answer — built on three coordinated AI agents.

### 1.3 Why now
- LLMs are now reliable enough to produce structured rubric scoring with calibrated examples.
- Candidate prep market (Exponent, IGotAnOffer, Hello PM) still relies on static question banks and human coaches; agentic personalization is a wedge.
- Solo-built sandbox project that demonstrates end-to-end AI agent orchestration — directly aligned with the builder-PM positioning in the profile README.

---

## 2. Goals & Non-Goals

### 2.1 Goals (v1)
- G1. A candidate can go from "uploaded PDF resume" to "first practice question" in under 60 seconds.
- G2. Generated questions are grounded in the candidate's resume (cite specific roles, projects, metrics) — not generic.
- G3. Each evaluation returns: (a) a STAR-completeness score, (b) what worked, (c) specific revision suggestions, (d) a model "stronger answer" rewrite.
- G4. Session is resumable — a candidate can return and continue prepping across days.
- G5. Ship a working v1 that the author can demo on `manishkj.tech` and on a public GitHub repo.

### 2.2 Non-Goals (v1)
- Not solving product-sense, estimation, technical, or system-design rounds.
- No live audio/video — text-first in v1 (voice is v2).
- No multi-user accounts with billing in v1; single-user-per-session is fine.
- No company-specific question scraping (e.g., scraping Glassdoor); we use a curated taxonomy instead.
- No human-in-the-loop coaching marketplace.

---

## 3. Target Users

### 3.1 Primary persona — "Mid-level PM Mira"
- 4–8 years experience, currently at a mid-sized SaaS company.
- Interviewing for Senior PM / Group PM roles at FAANG, Stripe, Linear, Notion.
- Has 3–5 strong stories but recycles them poorly across question types.
- Pain: doesn't know which stories map to which question; overruns on context, underdelivers on impact.

### 3.2 Secondary persona — "APM-track Arjun"
- 0–3 years experience, transitioning into PM from engineering or consulting.
- Resume is thin on PM-specific impact; needs help reframing past work as PM stories.
- Pain: doesn't know what behavioral themes top companies even ask about.

### 3.3 Anti-persona
- Senior Director / VP candidates — their loops are exec-style and don't fit STAR. Out of scope.

---

## 4. User Journey (v1)

```
[Landing] -> [Upload Resume] -> [Resume Scan + Question Plan]
   -> [Interview Session: Q&A loop] -> [Per-Answer Evaluation]
   -> [Session Summary + Story Bank] -> [Resume / Export]
```

### 4.1 Step-by-step
1. **Landing.** User picks target company tier (e.g., "FAANG", "Growth-stage", "AI-native") and seniority (APM / PM / Senior / GPM).
2. **Upload.** PDF or DOCX resume drag-and-drop. Optional paste-text fallback.
3. **Scan.** Resume Scanner Agent extracts roles, projects, metrics, scope, and inferred competencies, then proposes a question plan: ~8–12 questions across behavioral themes (leadership, conflict, ambiguity, failure, prioritization, influence without authority, data-driven decision, customer obsession, ethical dilemma).
4. **Plan review.** User sees the plan, can deselect themes, can re-roll a question, can set session length (e.g., "20 min / 5 questions").
5. **Interview loop.** Interview Agent asks one question at a time, in conversational tone, with optional follow-up probes ("What was the metric?" "Who pushed back?"). User types answer (later: dictates).
6. **Evaluate.** Evaluation Agent scores each answer against a STAR + impact rubric and returns structured feedback inline before the next question.
7. **Summary.** End-of-session report: heatmap of strengths/weaknesses, a "story bank" of the user's best raw answers, a list of revision tasks.
8. **Export.** Markdown / PDF download. Stored locally in browser + optional save to backend.

---

## 5. Agent Architecture (Functional Spec)

Three cooperating agents plus a thin orchestrator. All agents are LLM-backed with tool use; state is shared via a session store.

### 5.1 Resume Scanner Agent
- **Input:** Raw resume text (post-PDF/DOCX parse), target company tier, seniority.
- **Tools:** `pdf_parse`, `extract_entities`, `competency_taxonomy_lookup`, `question_bank_lookup`.
- **Output (structured JSON):**
  - `candidate_profile`: roles, tenure, domains, scope (team size, budget, users impacted), notable metrics.
  - `inferred_competencies`: ranked list with evidence snippets cited from resume.
  - `gap_areas`: themes the resume *doesn't* show evidence for (these become stretch questions).
  - `question_plan`: ordered list of `{theme, question_text, why_this_question, expected_story_hook}`.
- **Quality bar:** Every question must reference at least one concrete artifact from the resume (project name, metric, company) OR be explicitly flagged as a "gap probe."

### 5.2 Interview Agent
- **Input:** `question_plan`, current `session_state`, last user answer.
- **Tools:** `ask_followup`, `clarify`, `move_on`, `note_observation`.
- **Behavior:**
  - Asks one question at a time in a warm, professional interviewer voice (calibrated to target company tier — e.g., Amazon-style Bar Raiser vs. Google-style collaborative).
  - Issues at most 2 follow-up probes per question if the answer is missing Situation, Task, Action, Result, or quantified Impact.
  - Never evaluates inline. Never reveals the rubric.
  - Maintains a running `interviewer_notes` object the Evaluation Agent can read.
- **Stop condition:** Question count reached OR user types `/end`.

### 5.3 Evaluation Agent
- **Input:** Question, full answer transcript (incl. follow-ups), `interviewer_notes`, target seniority.
- **Tools:** `score_rubric`, `retrieve_exemplar_answer`, `rewrite_stronger_version`.
- **Output (per question):**
  - Rubric scores (1–5) on: Structure (STAR), Specificity, Ownership, Impact/Quantification, Reflection/Learning, Communication.
  - `what_worked`: 2–3 bullets, each citing a quote from the user's answer.
  - `what_to_improve`: 2–3 bullets, concrete and actionable.
  - `model_answer`: a rewritten version of the user's *own* story (not a generic template), kept to ~250 words, in STAR.
  - `revision_task`: a single, specific homework prompt (e.g., "Re-tell this story in 90 seconds, leading with the metric.").
- **End-of-session output:**
  - Competency heatmap.
  - Top 3 stories to keep, top 3 to retire/rework.
  - Suggested "story bank" structure.

### 5.4 Orchestrator
- Owns: session state, agent routing, tool registry, persistence, retries.
- Implements a simple state machine: `INTAKE -> SCAN -> PLAN_REVIEW -> INTERVIEW(qN) -> EVALUATE(qN) -> ... -> SUMMARY`.

---

## 6. Functional Requirements

| ID  | Requirement | Priority |
|-----|-------------|----------|
| F1  | Upload PDF and DOCX resumes up to 5 MB | P0 |
| F2  | Paste plain-text resume as fallback | P0 |
| F3  | Generate question plan within 20 seconds of upload | P0 |
| F4  | Display each question with target competency tag | P0 |
| F5  | Multi-turn answer with at least one follow-up probe | P0 |
| F6  | Per-answer evaluation rendered inline before next question | P0 |
| F7  | End-of-session summary with heatmap + revision tasks | P0 |
| F8  | Export session as Markdown | P1 |
| F9  | Resume an in-progress session via session ID | P1 |
| F10 | Voice answer (speech-to-text) | P2 |
| F11 | Company-tier-specific interviewer voice tuning | P1 |
| F12 | "Re-roll" a question the user doesn't want | P1 |
| F13 | Redact PII from stored resumes | P0 |
| F14 | Rate-limit per IP / per session to control LLM cost | P0 |

---

## 7. Non-Functional Requirements

- **Latency:** First question shown ≤ 25s after upload; per-question evaluation ≤ 15s.
- **Cost:** ≤ $0.30 in LLM cost per full session (~5 questions). Use a smaller model for follow-up probes, larger model for evaluation.
- **Privacy:** Resumes stored encrypted at rest; default 30-day TTL; user can delete on demand. No training on user data.
- **Reliability:** Agent retries on tool/LLM failure with exponential backoff; session never silently loses an answer.
- **Observability:** Structured logs per agent call (prompt, tokens, latency, cost), traceable by session ID.

---

## 8. Success Metrics

### 8.1 North-star
- **% of sessions completed end-to-end** (upload → ≥5 questions → summary). Target v1: 50%.

### 8.2 Supporting metrics
- Median time to first question.
- Median rubric score lift between question 1 and question 5 (does the user actually improve in-session?).
- Self-reported usefulness (1-click thumbs at end). Target: ≥70% positive.
- Cost per completed session.
- Returning-user rate within 7 days.

### 8.3 Counter-metrics
- Rate of "question doesn't match my resume" flags.
- Rate of evaluation flagged as "wrong" or "harsh."

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hallucinated resume facts in questions | High | High | Force agent to cite a verbatim resume span for every question; reject questions without a citation. |
| Generic, non-tailored questions | Med | High | Eval set of 20 sample resumes; regression-test question specificity score. |
| Evaluation feels harsh / wrong | Med | High | Calibrate rubric on 50 hand-graded answers; show rubric transparently; let user contest. |
| Cost blowout on long answers | Med | Med | Token caps per turn; summarize prior turns into rolling context. |
| PII leakage | Low | High | Server-side PII redaction before logging; encrypted store; TTL. |
| Single-author scope creep | High | Med | Strict v1 cut-list (Section 11); voice and accounts deferred. |

---

## 10. Open Questions

- Should the Interview Agent persona be a single neutral interviewer, or selectable (e.g., "Amazon Bar Raiser", "Google PM", "Stripe hiring manager")? Leaning selectable in v1.1.
- Do we offer a "show me a strong answer first" mode for absolute beginners, or strictly evaluate-after-attempt? Leaning evaluate-after only, to avoid anchoring.
- How opinionated should the rubric be on quantified impact for APM-level candidates whose resumes lack metrics?
- Local-only (browser + own API key) vs. hosted (managed backend) for the first public release?

---

## 11. v1 Cut-List (what we're explicitly NOT building)

- Accounts, billing, teams.
- Voice in/out.
- Mobile app (responsive web only).
- Company-specific question scraping.
- Multi-language (English only).
- Analytics dashboard for the user beyond the session summary.

---

## 12. Release Plan

- **v0.1 (internal):** Single-user CLI that runs the three agents end-to-end on a pasted resume. Validates agent contracts.
- **v0.2 (closed alpha):** Web UI (Next.js), upload, session, evaluation. Shared with 5–10 PM friends.
- **v1.0 (public):** Hosted demo, README + Loom, posted from `manishkj.tech` and LinkedIn.
- **v1.1:** Interviewer persona selection, re-roll, Markdown export.
- **v2.0:** Voice mode, accounts, story bank persistence across sessions.
