# How It Works — PM Behavioral Interview Prep Tool

> **High-level engineering design.** A single-file walkthrough of how the system fits together, what each agent owns, and the principles behind the design.

**Last updated:** 2026-04-25
**Companion to:** [`README.md`](./README.md), [`docs/PRD.md`](./docs/PRD.md), [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md)

---

## 1. The big picture

```text
   ┌─────────────────────┐
   │   Browser (you)     │
   │   Next.js 14 UI     │   apps/web/
   └──────────┬──────────┘
              │  HTTPS · JSON
              ▼
   ┌─────────────────────┐
   │   FastAPI server    │   apps/agents/src/agents/server/
   │   - HTTP endpoints  │
   │   - Session store   │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │    Orchestrator     │   apps/agents/src/agents/orchestrator/
   │  (state machine)    │
   │  INTAKE → SCANNED → │
   │  IN_INTERVIEW →     │
   │  COMPLETE           │
   └──┬──────┬──────┬────┘
      │      │      │
      ▼      ▼      ▼
   ┌────┐ ┌────┐ ┌────┐
   │ S  │ │ I  │ │ E  │   The 3 (+1) agents
   │can │ │nt  │ │val │   apps/agents/src/agents/agents/
   │ner │ │vw  │ │uat │
   └─┬──┘ └─┬──┘ └─┬──┘
     │      │      │
     ▼      ▼      ▼
   ┌─────────────────────┐
   │     LLM Client      │   apps/agents/src/agents/llm/
   │  (Gemini | Mock)    │   Provider-agnostic interface
   └─────────────────────┘

   Tools (deterministic, no LLM):
     • pdf_parse    • redact_pii
     • taxonomy_lookup    • question_bank
```

Five layers, each with a single job. Anything *can* be swapped without rewriting the others — that's the design's most important property.

---

## 2. The four agents

There are actually **four** agents, not three. The PRD called out three — Scanner, Interviewer, Evaluator — and we added a small fourth (Summary) once it became obvious the end-of-session report needed its own LLM call. Each one is a pure function:

```text
(input, tools) → structured Pydantic output
```

### 2.1 Resume Scanner Agent

| | |
|---|---|
| **Location** | `apps/agents/src/agents/agents/scanner.py` |
| **Prompt** | `apps/agents/prompts/scanner.system.md` |
| **Owns the flow** | "Reading the resume → drafting a question plan." |

**Input:** raw resume text + target company tier + seniority.

**Output (Pydantic-validated):** `ResumeScanOutput` containing:
- `candidate_profile` — extracted roles, metrics, scope, domains.
- `inferred_competencies` — themes the resume shows evidence for, ranked by confidence.
- `gap_areas` — themes the resume *doesn't* cover but the company tier expects.
- `question_plan` — 5–8 tailored questions, each with a verbatim citation from the resume.

**Hardest design constraint:** every non-gap question must cite a verbatim resume span. The agent's output is post-processed in code: any question whose `resume_citation.span` doesn't appear *as-is* in the resume gets dropped. If fewer than 3 grounded questions survive, we raise — we'd rather fail loudly than ship hallucinated questions.

This is the **#1 risk from the PRD** ("hallucinated resume facts in questions"), enforced not by trusting the model but by checking its work.

### 2.2 Interview Agent

| | |
|---|---|
| **Location** | `apps/agents/src/agents/agents/interviewer.py` |
| **Prompt** | `apps/agents/prompts/interview.system.md` |
| **Owns the flow** | "Asking the next thing the candidate hears." |

**Input:** the current question + transcript so far + interviewer's running notes + follow-up count.

**Output:** `InterviewTurnOutput` with:
- `next_action` — one of `ask_question`, `ask_followup`, `move_on`.
- `utterance` — what the interviewer says (≤60 words; that's prompt-enforced).
- `updated_notes` — short observations the agent leaves itself for the next turn.
- `followup_count` — incremented when it probes.

**Behavioral contract** baked into the prompt:

- One thing at a time. Either ask, follow up once, or move on.
- Never evaluates inline. Never tells the candidate what it's "looking for."
- Caps at **2 follow-ups per question**, then must move on.
- Probes are STAR-shaped: ask the smallest probe that fills the largest gap (Situation, Task, Action, Result, or quantified Impact).

The cap is enforced **twice** — once in the prompt and once in the orchestrator (`if followup_count >= max_followups: move_on`). Defence in depth.

> This is the only agent that runs on the **cheap model tier** (Gemini Flash-Lite by default), because it's called many times per session and each call is small.

### 2.3 Evaluation Agent

| | |
|---|---|
| **Location** | `apps/agents/src/agents/agents/evaluator.py` |
| **Prompt** | `apps/agents/prompts/evaluation.system.md` |
| **Owns the flow** | "Scoring one answer." |

**Input:** one question + the full multi-turn transcript for that question + interviewer notes + target seniority.

**Output:** `EvaluationOutput` with:
- `rubric_scores` — six 1–5 scores: structure, specificity, ownership, impact, reflection, communication.
- `what_worked` — 2–3 bullets, each citing a phrase from the candidate's answer.
- `what_to_improve` — 2–3 actionable bullets.
- `model_answer` — a STAR rewrite of the candidate's *own* story, ≤250 words.
- `revision_task` — a single concrete homework prompt.

**Calibration constraint:** every bullet must reference a phrase from the candidate's actual answer, and the model rewrite must use the candidate's own characters/projects (not a generic template). The rubric is dynamic to seniority — a 4 for an APM might be a 2 for a GPM.

> Runs on the **strong model tier** (Gemini Flash by default) because rubric calibration is where quality matters most.

### 2.4 Summary Agent

| | |
|---|---|
| **Location** | `apps/agents/src/agents/agents/summary.py` |
| **Prompt** | `apps/agents/prompts/summary.system.md` |
| **Owns the flow** | "End-of-session report." |

**Input:** all questions + all per-question evaluations.

**Output:** `SessionSummary` with:
- `competency_heatmap` — average rubric score per theme.
- `keep_stories` — 1–3 stories worth bringing into a real interview as-is.
- `rework_stories` — 1–3 stories that need work.
- `top_recommendations` — 3 prioritized coaching actions for next session.

A single LLM call at the very end, on the strong tier.

---

## 3. The orchestrator — who decides which agent runs

**Location:** `apps/agents/src/agents/orchestrator/session.py`

The orchestrator is the **only** thing that knows about session state. The agents don't even know they're in a session — they're stateless functions. The orchestrator owns:

- The **state machine:** `INTAKE → SCANNED → IN_INTERVIEW → COMPLETE`
- **Routing:** which agent to call next.
- **Transcripts:** the per-question history of who said what.
- **Progress:** which question we're on, how many follow-ups happened, what the interviewer noted.

It exposes two parallel APIs that share the same internals:

| API style | Used by | Methods |
|---|---|---|
| Callback-based (push) | CLI (`pm-session`) | `run_full_session(state, get_answer_callback)` |
| Turn-by-turn (pull) | HTTP server | `scan(state)`, `select_questions(...)`, `begin_question(state)`, `submit_answer(state, text)`, `skip_question(state)`, `evaluate_all(state)`, `summarize(state)` |

The HTTP API exists because in an HTTP world each request is independent — the server can't "wait" for the user to type. So instead of one long-running call, the orchestrator exposes "give me the next thing to say" and "here's the candidate's answer; what's next?" as separate methods.

---

## 4. The flow, end to end

Here's what happens when you click **Start session** in the browser, traced through every layer:

```text
 1. Browser  ──POST /api/sessions {resume_text, tier, seniority}──>  FastAPI
 2. FastAPI  ──new_session()──>  Orchestrator
 3.    new SessionState{status: INTAKE} stored in SessionStore
 4. ←─ {session_id}

 5. Browser navigates to /sessions/{id}/scanning, fires:
 6. Browser  ──POST /api/sessions/{id}/scan──>  FastAPI
 7. FastAPI  ──orch.scan(state)──>  Orchestrator
 8. Orchestrator  ──scan_resume()──>  RESUME SCANNER AGENT
 9.    Scanner Agent → tools.redact_pii(resume) → tools.taxonomy_lookup() → LLM call
10.   Scanner returns ResumeScanOutput
11. Orchestrator runs grounding check: drop questions whose citations
    aren't verbatim in the resume.
12. State.status = SCANNED, store updated.
13. ←─ full SessionState back to browser

14. Browser shows /sessions/{id}/plan. User picks 5 questions, clicks Start interview.
15. Browser  ──POST /api/sessions/{id}/select──>  FastAPI
16. Orchestrator records selected_question_ids, status = IN_INTERVIEW.

17. Browser navigates to /sessions/{id}/interview, fires:
18. Browser  ──POST /api/sessions/{id}/turn/begin──>  FastAPI
19. Orchestrator  ──begin_question(state)──>  INTERVIEW AGENT
20.   Interview Agent → LLM call (cheap tier) → "Tell me about a time..."
21. ←─ TurnResponse{kind: interviewer_utterance, ...}
22. Browser renders chat bubble.

23. User types answer, clicks Send.
24. Browser  ──POST /api/sessions/{id}/turn/answer {answer}──>  FastAPI
25. Orchestrator  ──submit_answer(state, text)──>
26.   Append candidate turn to transcript.
27.   Call INTERVIEW AGENT again with updated transcript.
28.   Agent decides: ask_followup OR move_on.
29.   If followup: ←─ TurnResponse{kind: interviewer_utterance, is_followup: true}
30.   If move_on:  ←─ TurnResponse{kind: question_finished, next_question_id: ...}
31. Browser either shows next bubble (back to step 23) or starts next question (step 18).

32. After last question, browser shows "See my evaluation":
33. Browser  ──POST /api/sessions/{id}/finish──>  FastAPI
34. Orchestrator:
35.   For each answered question:
36.     EVALUATION AGENT → LLM call (strong tier) → rubric + rewrite
37.   Then SUMMARY AGENT → LLM call (strong tier) → heatmap + recommendations
38. State.status = COMPLETE.
39. ←─ full SessionState with summary.
40. Browser navigates to /sessions/{id}/summary and renders the report.
```

> If you flip to the CLI (`pm-session`), steps 5–40 happen in one Python process with `input()` instead of HTTP — but the agents and orchestrator are **literally the same code.**

---

## 5. The LLM Client abstraction — why it matters

**Location:** `apps/agents/src/agents/llm/`

Every agent talks to an `LLMClient` interface with one method:

```python
complete_json(system: str, user: str, schema: type[T], tier: ModelTier) -> T
```

Two implementations live behind that interface:

- **`GeminiClient`** — uses the modern `google-genai` SDK, native Pydantic `response_schema`, free-tier rate-limit throttle, "thinking" tokens disabled for predictable JSON.
- **`MockClient`** — deterministic, offline, examines the requested schema and returns a realistic response. This is what makes the entire test suite, the CLI, and your demo work without an API key.

Adding **OpenAI / Anthropic / OpenRouter** is one new file in this directory. Nothing else changes — not the agents, not the orchestrator, not the prompts. That's the win from putting structured outputs at every boundary.

The factory (`build_client()`) reads `LLM_PROVIDER` from env and returns the right one. Tests force `mock` via a pytest fixture; the CLI and server just respect what's in `.env`.

---

## 6. Why this shape

Three principles drove the design.

### Principle 1 — Stateless agents, stateful orchestrator

Each agent is a pure function. The orchestrator owns memory. This means I can:

- Test each agent in isolation with a mock LLM.
- Run the same orchestrator in a CLI, an HTTP server, or eventually a WebSocket / Slack bot transport — without touching agent code.
- Reason about a session by reading one Pydantic object (`SessionState`) instead of chasing global variables.

### Principle 2 — Structured outputs at every boundary

There is **no free-form prose** between any two layers. Every agent input and output is a Pydantic schema. This is the difference between *"agentic system"* and *"spaghetti of LLM calls"*:

- Type-checked at the function boundary.
- Validated on parse — if the LLM returns malformed JSON we retry with backoff.
- Easy to log, test, and replay.

### Principle 3 — Defence in depth on quality

LLMs lie. The system assumes that and checks their work in code wherever it can:

- **Scanner:** verbatim citation check, drops bad questions, raises on too few good ones.
- **Interviewer:** follow-up cap enforced both in prompt and in orchestrator.
- **Evaluator:** rubric enforced via `Field(ge=1, le=5)` Pydantic constraint.
- **Tools** (PII redaction, taxonomy lookup, question bank seeds): deterministic Python, not LLM calls — cheaper, faster, and auditable.

---

## 7. What's *not* an agent (deliberately)

Things that look like they could be agents but aren't, because deterministic code is better:

| Job | Implementation | Why not an agent |
|---|---|---|
| PDF / DOCX parsing | `pypdf`, `python-docx` | LLMs are bad at this and it costs tokens. |
| PII redaction | regex on email / phone / URL | Predictable, auditable, runs before any LLM call. |
| Choosing which themes to cover | `taxonomy.py` lookup table | A switch statement is faster, cheaper, and more honest. |
| Verbatim citation check | substring match in Python | The whole point is to not trust the model. |
| Rate limiting | per-process token bucket | Belongs in the network layer, not in a prompt. |

> **Rule of thumb:** if a deterministic Python function can do the job, it should. Agents are reserved for tasks that genuinely require judgment under ambiguity — interpreting a resume, framing a question, scoring a story.

---

## 8. The whole system on one page

| Layer | Lives at | What it does | What it doesn't do |
|---|---|---|---|
| **Web UI** | `apps/web/` | Render pages, take input, call backend | Hold session state; call LLMs |
| **HTTP server** | `agents/server/` | Translate HTTP ↔ orchestrator calls; CORS; multipart uploads | Decide flow; call LLMs directly |
| **Orchestrator** | `agents/orchestrator/` | State machine; route to agents; persist state | Talk to LLM; understand questions |
| **Agents (×4)** | `agents/agents/` | One LLM call each, with structured I/O | Track state; enforce safety |
| **Tools** | `agents/tools/` | Deterministic helpers (parse, redact, lookup) | Call LLMs |
| **LLM client** | `agents/llm/` | Provider-agnostic structured-output interface | Know about agents or sessions |
| **Session store** | `agents/server/store.py` | Hold `SessionState` between requests | Persist to disk (yet — that's M4) |

What I'm most proud of architecturally is that **none of these layers know about the layer above them.** The agents don't know an orchestrator exists. The orchestrator doesn't know if it's being driven by a CLI or HTTP. The HTTP server doesn't know what model is behind the LLM client. That's why the same code fits a CLI, an HTTP server, and (eventually) a Slack bot.

---

## See also

- [`README.md`](./README.md) — quickstart and project overview
- [`docs/PRD.md`](./docs/PRD.md) — Product Requirements Document
- [`docs/IMPLEMENTATION_PLAN.md`](./docs/IMPLEMENTATION_PLAN.md) — engineering plan, milestones, evals
- [`apps/agents/README.md`](./apps/agents/README.md) — backend setup and CLI usage
- [`apps/web/README.md`](./apps/web/README.md) — frontend setup
