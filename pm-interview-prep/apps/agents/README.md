# `apps/agents` — PM Interview Prep agents (Python)

Backend service that hosts the three cooperating agents: **Resume Scanner**, **Interview**, and **Evaluation**, plus the orchestrator that runs the session state machine.

## Quickstart

```bash
cd apps/agents
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../../.env.example ../../.env  # then add your GEMINI_API_KEY
```

### Run with the mock LLM (no API key needed)

```bash
LLM_PROVIDER=mock pm-scan --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior
LLM_PROVIDER=mock pm-session --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior \
    --answers tests/fixtures/answers_alex.json --out /tmp/session.json
```

### Run with Gemini (requires `GEMINI_API_KEY`)

```bash
LLM_PROVIDER=gemini pm-session --resume tests/fixtures/resume_alex.txt --tier faang --seniority senior
```

## Layout

```
src/agents/
  agents/         # Scanner, Interview, Evaluation agents
  llm/            # LLMClient abstraction (Gemini, Mock)
  tools/          # pdf_parse, redact_pii, taxonomy, question_bank, exemplars
  orchestrator/   # session state machine
  cli/            # Typer CLIs (pm-scan, pm-session)
  contracts.py    # Pydantic schemas for all agent I/O
  config.py       # env-driven settings
prompts/          # versioned system / user prompts (markdown)
tests/            # pytest, with fixture resumes
```

## Tests

```bash
pytest                  # all tests, uses mock LLM
ruff check src tests    # lint
mypy src                # types
```
