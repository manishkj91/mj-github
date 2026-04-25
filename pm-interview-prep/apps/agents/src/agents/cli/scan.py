"""`pm-scan` — run only the Resume Scanner Agent and print the question plan."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..agents import scan_resume
from ..contracts import CompanyTier, ResumeScanInput, Seniority
from ..llm import build_client
from ..tools import load_resume_text

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def main(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume (.pdf, .docx, .txt)"),
    tier: CompanyTier = typer.Option(CompanyTier.FAANG, "--tier"),
    seniority: Seniority = typer.Option(Seniority.SENIOR, "--seniority"),
    json_out: bool = typer.Option(False, "--json", help="Print raw JSON instead of pretty output"),
) -> None:
    """Scan a resume and print the proposed question plan."""
    text = load_resume_text(resume)
    client = build_client()
    scan = scan_resume(
        client,
        ResumeScanInput(
            resume_text=text,
            target_company_tier=tier,
            target_seniority=seniority,
        ),
    )

    if json_out:
        typer.echo(json.dumps(scan.model_dump(), indent=2))
        return

    console.print(
        Panel.fit(
            f"[bold]{len(scan.candidate_profile.roles)}[/bold] roles · "
            f"[bold]{len(scan.candidate_profile.metrics)}[/bold] metrics · "
            f"[bold]{len(scan.inferred_competencies)}[/bold] inferred competencies · "
            f"[bold]{len(scan.gap_areas)}[/bold] gap areas",
            title=f"Resume scanned ({tier.value} / {seniority.value})",
        )
    )

    table = Table(title="Question plan", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Theme", style="cyan", no_wrap=True)
    table.add_column("Question")
    table.add_column("Citation", style="green")
    for i, q in enumerate(scan.question_plan, 1):
        cite = (
            "(gap probe)"
            if q.is_gap_probe
            else (q.resume_citation.span if q.resume_citation else "")
        )
        table.add_row(str(i), q.theme, q.question_text, cite)
    console.print(table)


if __name__ == "__main__":
    app()
