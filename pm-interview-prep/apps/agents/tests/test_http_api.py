"""Integration tests for the FastAPI HTTP surface, against the mock LLM."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.llm import MockClient
from agents.server import create_app
from agents.server.store import SessionStore


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("CORS_ORIGINS", "*")
    app = create_app(client=MockClient(), store=SessionStore())
    return TestClient(app)


@pytest.fixture
def alex_resume(fixtures_dir: Path) -> str:
    return (fixtures_dir / "resume_alex.txt").read_text()


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_session_flow(client: TestClient, alex_resume: str) -> None:
    # 1. Create
    r = client.post(
        "/api/sessions",
        json={
            "resume_text": alex_resume,
            "target_company_tier": "faang",
            "target_seniority": "senior",
        },
    )
    assert r.status_code == 201
    sid = r.json()["session_id"]

    # 2. Scan
    r = client.post(f"/api/sessions/{sid}/scan")
    assert r.status_code == 200
    state = r.json()
    assert state["status"] == "scanned"
    assert state["scan"] is not None
    plan = state["scan"]["question_plan"]
    assert 5 <= len(plan) <= 12

    # 3. Select first 2 questions
    pick_ids = [plan[0]["id"], plan[1]["id"]]
    r = client.post(
        f"/api/sessions/{sid}/select", json={"question_ids": pick_ids}
    )
    assert r.status_code == 200
    state = r.json()
    assert state["selected_question_ids"] == pick_ids
    assert state["status"] == "in_interview"

    # 4. Loop: ask + answer (+ optional follow-ups) for each selected question
    for _qid in pick_ids:
        r = client.post(f"/api/sessions/{sid}/turn/begin")
        assert r.status_code == 200
        turn = r.json()
        assert turn["kind"] == "interviewer_utterance"

        # Submit answers until the question is finished. Cap loop count.
        for _ in range(5):
            r = client.post(
                f"/api/sessions/{sid}/turn/answer",
                json={"answer": "Detailed STAR answer with metrics like +13pp."},
            )
            assert r.status_code == 200
            turn = r.json()
            if turn["kind"] != "interviewer_utterance":
                break
        assert turn["kind"] in {"question_finished", "session_complete"}

    # 5. Finish: evaluations + summary
    r = client.post(f"/api/sessions/{sid}/finish")
    assert r.status_code == 200
    final = r.json()
    assert final["status"] == "complete"
    assert final["summary"] is not None
    assert final["summary"]["competency_heatmap"]
    assert len(final["evaluations"]) == 2


def test_upload_resume(client: TestClient, fixtures_dir: Path) -> None:
    # Pre-create a session so we have an id to upload into
    sid = "abc123def456"
    txt = (fixtures_dir / "resume_alex.txt").read_text()
    files = {"file": ("resume.txt", io.BytesIO(txt.encode()), "text/plain")}
    r = client.post(
        f"/api/sessions/{sid}/upload",
        files=files,
        data={"target_company_tier": "faang", "target_seniority": "senior"},
    )
    assert r.status_code == 201
    assert r.json()["session_id"] == sid
    assert r.json()["char_count"] > 100

    r = client.post(f"/api/sessions/{sid}/scan")
    assert r.status_code == 200
    assert r.json()["status"] == "scanned"


def test_unknown_session_returns_404(client: TestClient) -> None:
    r = client.post("/api/sessions/does-not-exist/scan")
    assert r.status_code == 404


def test_skip_question(client: TestClient, alex_resume: str) -> None:
    r = client.post(
        "/api/sessions",
        json={"resume_text": alex_resume, "target_company_tier": "faang", "target_seniority": "senior"},
    )
    sid = r.json()["session_id"]
    client.post(f"/api/sessions/{sid}/scan")
    plan = client.get(f"/api/sessions/{sid}").json()["scan"]["question_plan"]
    client.post(
        f"/api/sessions/{sid}/select", json={"question_ids": [plan[0]["id"]]}
    )
    client.post(f"/api/sessions/{sid}/turn/begin")
    r = client.post(f"/api/sessions/{sid}/turn/skip")
    assert r.status_code == 200
    assert r.json()["kind"] == "session_complete"
