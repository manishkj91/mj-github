"""FastAPI app exposing the orchestrator over HTTP.

Endpoints (all JSON unless noted):

* ``POST /api/sessions`` — create a session from resume text + targets.
* ``POST /api/sessions/{id}/upload`` — alt: multipart upload of a PDF/DOCX/TXT.
* ``POST /api/sessions/{id}/scan`` — run the Resume Scanner Agent.
* ``POST /api/sessions/{id}/select`` — pick which question ids to interview on.
* ``GET  /api/sessions/{id}`` — full state snapshot (for resuming a session).
* ``POST /api/sessions/{id}/turn/begin`` — ask the current question.
* ``POST /api/sessions/{id}/turn/answer`` — submit candidate's answer; returns
  the next interviewer move (a follow-up, or "question finished").
* ``POST /api/sessions/{id}/turn/skip`` — skip remaining follow-ups for the
  current question.
* ``POST /api/sessions/{id}/finish`` — evaluate all answered questions and
  build the session summary.

The Next.js UI in ``apps/web`` is a thin client over this surface.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..contracts import (
    CompanyTier,
    Seniority,
    SessionState,
    SessionStatus,
)
from ..llm import LLMClient, build_client
from ..orchestrator import Orchestrator, new_session
from ..tools import load_resume_text
from .store import SessionStore

# ---- request / response models ---------------------------------------------


class CreateSessionRequest(BaseModel):
    resume_text: str = Field(min_length=20)
    target_company_tier: CompanyTier = CompanyTier.FAANG
    target_seniority: Seniority = Seniority.SENIOR


class SelectQuestionsRequest(BaseModel):
    question_ids: list[str] | None = None


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


class TurnResponse(BaseModel):
    kind: Literal["interviewer_utterance", "question_finished", "session_complete"]
    question_id: str
    question_theme: str
    utterance: str = ""
    is_followup: bool = False
    next_question_id: str | None = None


# ---- app factory ------------------------------------------------------------


def create_app(
    *,
    client: LLMClient | None = None,
    store: SessionStore | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Build a FastAPI app. Allows DI for tests (e.g. inject MockClient)."""

    app = FastAPI(title="PM Interview Prep — Agents", version="0.1.0")

    # Lazily build the LLM client so importing this module doesn't require
    # any env vars to be set (handy in tests and tooling).
    _client_singleton: dict[str, LLMClient | None] = {"value": client}

    def get_client() -> LLMClient:
        if _client_singleton["value"] is None:
            _client_singleton["value"] = build_client()
        return _client_singleton["value"]  # type: ignore[return-value]

    _store = store or SessionStore()

    if cors_origins is None:
        cors_origins = (
            os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
            if os.getenv("CORS_ORIGINS") is not None
            else ["http://localhost:3000"]
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    def get_session(session_id: str) -> SessionState:
        state = _store.get(session_id)
        if state is None:
            raise HTTPException(404, f"session {session_id} not found")
        return state

    def get_orchestrator(client: LLMClient = Depends(get_client)) -> Orchestrator:
        return Orchestrator(client)

    # ---- endpoints ----------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/api/sessions", status_code=201)
    def create_session(req: CreateSessionRequest) -> dict:
        state = new_session(
            req.resume_text, tier=req.target_company_tier, seniority=req.target_seniority
        )
        _store.put(state)
        return {"session_id": state.session_id, "status": state.status.value}

    @app.post("/api/sessions/{session_id}/upload", status_code=201)
    async def upload_resume(
        session_id: str,
        file: UploadFile = File(...),
        target_company_tier: CompanyTier = Form(CompanyTier.FAANG),
        target_seniority: Seniority = Form(Seniority.SENIOR),
    ) -> dict:
        suffix = Path(file.filename or "").suffix.lower() or ".txt"
        if suffix not in {".pdf", ".docx", ".txt", ".md"}:
            raise HTTPException(400, f"Unsupported file type: {suffix}")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        try:
            text = load_resume_text(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
        if len(text) < 50:
            raise HTTPException(400, "Could not extract enough text from the resume.")

        state = new_session(text, tier=target_company_tier, seniority=target_seniority)
        # Override session id so the client can pre-create + upload.
        state.session_id = session_id
        _store.put(state)
        return {"session_id": state.session_id, "char_count": len(text)}

    @app.post("/api/sessions/{session_id}/scan")
    def scan_session(
        session_id: str, orch: Orchestrator = Depends(get_orchestrator)
    ) -> SessionState:
        state = get_session(session_id)
        if state.status != SessionStatus.INTAKE:
            return state
        orch.scan(state)
        _store.put(state)
        return state

    @app.post("/api/sessions/{session_id}/select")
    def select_questions(
        session_id: str,
        req: SelectQuestionsRequest,
        orch: Orchestrator = Depends(get_orchestrator),
    ) -> SessionState:
        state = get_session(session_id)
        orch.select_questions(state, req.question_ids)
        _store.put(state)
        return state

    @app.get("/api/sessions/{session_id}")
    def get_state(session_id: str) -> SessionState:
        return get_session(session_id)

    @app.post("/api/sessions/{session_id}/turn/begin")
    def turn_begin(
        session_id: str, orch: Orchestrator = Depends(get_orchestrator)
    ) -> TurnResponse:
        state = get_session(session_id)
        if not state.selected_question_ids:
            raise HTTPException(400, "No questions selected. Call /select first.")
        result = orch.begin_question(state)
        _store.put(state)
        return _to_turn_response(result)

    @app.post("/api/sessions/{session_id}/turn/answer")
    def turn_answer(
        session_id: str,
        req: AnswerRequest,
        orch: Orchestrator = Depends(get_orchestrator),
    ) -> TurnResponse:
        state = get_session(session_id)
        result = orch.submit_answer(state, req.answer)
        _store.put(state)
        return _to_turn_response(result)

    @app.post("/api/sessions/{session_id}/turn/skip")
    def turn_skip(
        session_id: str, orch: Orchestrator = Depends(get_orchestrator)
    ) -> TurnResponse:
        state = get_session(session_id)
        result = orch.skip_question(state)
        _store.put(state)
        return _to_turn_response(result)

    @app.post("/api/sessions/{session_id}/finish")
    def finish(
        session_id: str, orch: Orchestrator = Depends(get_orchestrator)
    ) -> SessionState:
        state = get_session(session_id)
        orch.evaluate_all(state)
        orch.summarize(state)
        _store.put(state)
        return state

    return app


def _to_turn_response(result) -> TurnResponse:
    if result.session_complete:
        kind = "session_complete"
    elif result.question_finished:
        kind = "question_finished"
    else:
        kind = "interviewer_utterance"
    return TurnResponse(
        kind=kind,
        question_id=result.question.id,
        question_theme=result.question.theme,
        utterance=result.utterance,
        is_followup=result.is_followup,
        next_question_id=result.next_question_id,
    )
