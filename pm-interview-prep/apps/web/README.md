# `apps/web` — Next.js UI

Thin client over the FastAPI agents service in `apps/agents`. Built with
Next.js 14 (App Router), TypeScript, and Tailwind. No state library —
everything lives in the backend, the UI just renders it.

## Quickstart

In one terminal, start the backend (mock provider; no API key needed):

```bash
cd ../agents
source ../../.venv/bin/activate
LLM_PROVIDER=mock pm-server
# → listening on http://127.0.0.1:8000
```

In another terminal, start the UI:

```bash
cd apps/web
npm install
npm run dev
# → http://localhost:3000
```

Open http://localhost:3000, paste / upload a resume, and walk through the flow.

## Pages

- `/` — landing + upload form
- `/sessions/[id]/scanning` — auto-runs the scan
- `/sessions/[id]/plan` — review + select questions
- `/sessions/[id]/interview` — chat-style interview surface
- `/sessions/[id]/summary` — competency heatmap, per-question feedback, model
  rewrites, top recommendations

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Backend URL |

Set in `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Quality

```bash
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm run build      # production build
```
