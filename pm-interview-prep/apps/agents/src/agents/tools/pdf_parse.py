"""Load resume text from PDF, DOCX, or plain text."""

from __future__ import annotations

from pathlib import Path


def load_resume_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Resume not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(p)
    if suffix == ".docx":
        return _from_docx(p)
    if suffix in {".txt", ".md", ""}:
        return p.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported resume file type: {suffix}")


def _from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts).strip()


def _from_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs).strip()
