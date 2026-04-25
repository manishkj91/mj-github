# PM Behavioral Interview Prep Tool

An agentic prep tool for **behavioral rounds in Product Manager interviews at top companies**. The candidate uploads a resume; three coordinated AI agents take it from there:

1. **Resume Scanner Agent** — extracts roles, projects, scope, and metrics from the resume and proposes a tailored question plan grounded in what the candidate has actually done.
2. **Interview Agent** — asks the questions one at a time in a realistic interviewer voice, with up to two follow-up probes per question.
3. **Evaluation Agent** — scores each answer against a STAR + impact rubric, points out what worked and what to fix, and rewrites a stronger version of the candidate's *own* story.

## Status — M0 → M2 done (CLI loop ✅)

- v0.1 spec — drafted 2026-04-25.
- **M0 — Foundations** complete: monorepo scaffolding, CI workflow, `LLMClient` abstraction with **Gemini** and **Mock** providers.
- **M1 — Resume Scanner Agent** complete: structured-output Pydantic contracts, PII redaction, taxonomy + question-bank tools, hard citation enforcement (hallucinated questions are dropped, not surfaced).
- **M2 — Interview + Evaluation Agents + Orchestrator** complete: state-machine orchestrator drives `INTAKE → SCANNED → IN_INTERVIEW → COMPLETE`. Two CLIs: `pm-scan` (scan-only) and `pm-session` (full loop).
- 13 / 13 tests passing on the mock provider; CI runs on every push to `pm-interview-prep/**`.

## Quickstart (no API key)

```bash
cd pm-interview-prep/apps/agents
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

LLM_PROVIDER=mock pm-scan --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior
LLM_PROVIDER=mock pm-session --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior \
    --answers tests/fixtures/answers_alex.json --out /tmp/session.json
```

## Quickstart (with Gemini)

```bash
cp .env.example .env  # then paste your GEMINI_API_KEY
export $(grep -v '^#' .env | xargs)
LLM_PROVIDER=gemini pm-session --resume path/to/your_resume.pdf --tier faang --seniority senior
```

## Documents

- [`docs/PRD.md`](docs/PRD.md) — Product Requirements Document (problem, users, journey, agent architecture, success metrics, risks, v1 cut-list).
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — Engineering plan (architecture, data model, agent contracts, milestones M0–M5, evals, cost budget, security).
- [`apps/agents/README.md`](apps/agents/README.md) — How to run and develop the agents service.

## Next

- **M3 — Web UI** (Next.js): upload page, chat-style interview, summary page.
- Calibration set of 50 hand-graded answers for the Evaluation Agent (target MAE ≤ 1.0 vs. human grader).
- Interactive smoke test against Gemini once the API key is wired in.
