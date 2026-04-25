from pathlib import Path

import pytest

from agents.agents import scan_resume
from agents.contracts import CompanyTier, ResumeScanInput, Seniority
from agents.llm import MockClient


@pytest.fixture
def alex_resume(fixtures_dir: Path) -> str:
    return (fixtures_dir / "resume_alex.txt").read_text()


def test_scanner_returns_grounded_questions(alex_resume: str) -> None:
    scan = scan_resume(
        MockClient(),
        ResumeScanInput(
            resume_text=alex_resume,
            target_company_tier=CompanyTier.FAANG,
            target_seniority=Seniority.SENIOR,
        ),
    )

    assert 5 <= len(scan.question_plan) <= 12

    haystack = alex_resume.lower()
    for q in scan.question_plan:
        if q.is_gap_probe:
            assert q.resume_citation is None
        else:
            assert q.resume_citation is not None, (
                f"Non-gap question must cite the resume: {q.question_text}"
            )
            assert q.resume_citation.span.lower() in haystack, (
                f"Citation must appear verbatim in the resume: {q.resume_citation.span!r}"
            )


def test_scanner_covers_diverse_themes(alex_resume: str) -> None:
    scan = scan_resume(
        MockClient(),
        ResumeScanInput(
            resume_text=alex_resume,
            target_company_tier=CompanyTier.FAANG,
            target_seniority=Seniority.SENIOR,
        ),
    )
    themes = {q.theme for q in scan.question_plan}
    assert len(themes) >= 4, f"Expected at least 4 distinct themes, got {themes}"
