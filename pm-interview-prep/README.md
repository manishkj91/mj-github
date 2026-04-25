# PM Behavioral Interview Prep Tool

An agentic prep tool for **behavioral rounds in Product Manager interviews at top companies**. The candidate uploads a resume; three coordinated AI agents take it from there:

1. **Resume Scanner Agent** — extracts roles, projects, scope, and metrics from the resume and proposes a tailored question plan grounded in what the candidate has actually done.
2. **Interview Agent** — asks the questions one at a time in a realistic interviewer voice, with up to two follow-up probes per question.
3. **Evaluation Agent** — scores each answer against a STAR + impact rubric, points out what worked and what to fix, and rewrites a stronger version of the candidate's *own* story.

This repository currently contains the **product spec only**. No code yet — the next step is M0 in the implementation plan.

## Documents

- [`docs/PRD.md`](docs/PRD.md) — Product Requirements Document (problem, users, journey, agent architecture, success metrics, risks, v1 cut-list).
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — Engineering plan (architecture, data model, agent contracts, milestones M0–M5, evals, cost budget, security).

## Status

- v0.1 spec — drafted 2026-04-25.
- Next milestone: **M0 — Foundations** (monorepo scaffolding, CI, hello-world agent endpoint).
