# PM Behavioral Interview Prep Tool

An agentic prep tool for **behavioral rounds in Product Manager interviews at top companies**. The candidate uploads a resume; three coordinated AI agents take it from there:

1. **Resume Scanner Agent** — extracts roles, projects, scope, and metrics from the resume and proposes a tailored question plan grounded in what the candidate has actually done.
2. **Interview Agent** — asks the questions one at a time in a realistic interviewer voice, with up to two follow-up probes per question.
3. **Evaluation Agent** — scores each answer against a STAR + impact rubric, points out what worked and what to fix, and rewrites a stronger version of the candidate's *own* story.

## Status — M0 → M3 done (web UI ✅)

- v0.1 spec — drafted 2026-04-25.
- **M0** — monorepo scaffolding, CI, `LLMClient` abstraction (Gemini + Mock).
- **M1** — Resume Scanner Agent with hard-enforced verbatim citations.
- **M2** — Interview + Evaluation Agents + state-machine orchestrator + two CLIs.
- **M3** — FastAPI HTTP service + Next.js 14 web UI (upload, plan, chat-style interview, summary). 18 backend tests + clean Next.js build.

## Two-app layout

```
pm-interview-prep/
├── apps/
│   ├── agents/   # Python: agents + FastAPI HTTP server
│   └── web/      # Next.js 14 + Tailwind UI
└── docs/         # PRD + Implementation plan
```

## Quickstart (no API key)

Backend:

```bash
cd apps/agents
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
LLM_PROVIDER=mock pm-server      # http://127.0.0.1:8000
```

Frontend (in another terminal):

```bash
cd apps/web
npm install
npm run dev                       # http://localhost:3000
```

Open `http://localhost:3000`, paste / upload a resume, walk through the flow.

## Quickstart (with Gemini)

```bash
# In apps/agents/
cp ../../.env.example ../../.env   # then paste GEMINI_API_KEY
LLM_PROVIDER=gemini pm-server
```

The frontend doesn't need to change — it just talks to the same backend.

## CLIs (still supported)

```bash
LLM_PROVIDER=mock pm-scan --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior
LLM_PROVIDER=mock pm-session --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior \
    --answers tests/fixtures/answers_alex.json --out /tmp/session.json
```

## Documents

- [`docs/PRD.md`](docs/PRD.md) — PRD.
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — Engineering plan.
- [`apps/agents/README.md`](apps/agents/README.md) — Backend service.
- [`apps/web/README.md`](apps/web/README.md) — Web UI.

## Next

- Eval calibration set of 50 hand-graded answers (target MAE ≤ 1.0 vs. human grader).
- Persistence (Postgres) so sessions survive a backend restart.
- Deploy: Vercel (web) + Fly.io / Render (agents).
