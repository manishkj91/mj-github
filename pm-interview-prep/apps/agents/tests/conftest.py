"""Shared pytest setup."""

from __future__ import annotations

import pytest

from agents.config import reset_settings_for_tests


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    reset_settings_for_tests()
    yield
    reset_settings_for_tests()


@pytest.fixture
def fixtures_dir():
    from pathlib import Path

    return Path(__file__).parent / "fixtures"
