"""`pm-session` — run the full scan + interview + evaluate + summarize loop."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ..contracts import CompanyTier, Seniority, SessionState
from ..llm import build_client
from ..orchestrator import Orchestrator, cli_answer_provider, new_session
from ..orchestrator.session import InterviewerSay
from ..tools import load_resume_text

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def run(
    resume: Path = typer.Option(..., "--resume", "-r"),
    tier: CompanyTier = typer.Option(CompanyTier.FAANG, "--tier"),
    seniority: Seniority = typer.Option(Seniority.SENIOR, "--seniority"),
    answers_file: Path | None = typer.Option(
        None,
        "--answers",
        help="Optional JSON file with prerecorded answers keyed by question id (for non-interactive runs).",
    ),
    out: Path | None = typer.Option(None, "--out", help="Write the session state JSON here."),
) -> None:
    """Run a full session from a resume to a written summary."""
    text = load_resume_text(resume)
    state = new_session(text, tier=tier, seniority=seniority)
    client = build_client()
    orch = Orchestrator(client)

    console.rule("[bold]Scanning resume")
    orch.scan(state)
    if state.scan is None:
        raise typer.Exit(1)
    _print_plan(state)

    console.rule("[bold]Interview")
    answer_provider = (
        _scripted_answer_provider(answers_file) if answers_file else cli_answer_provider()
    )
    orch.run_interview(state, answer_provider)

    console.rule("[bold]Evaluating answers")
    orch.evaluate_all(state)
    _print_evaluations(state)

    console.rule("[bold]Session summary")
    orch.summarize(state)
    _print_summary(state)

    if out:
        out.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"\n[green]Wrote session state to {out}[/green]")


def _scripted_answer_provider(path: Path):
    """Read answers from a JSON file: {"question_id": "answer text"}.

    Useful for CI and demos: avoids interactive stdin.
    """
    answers: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))

    def provider(say: InterviewerSay) -> str:
        ans = answers.get(say.question.id, "I don't have a great example for this one.")
        console.print(
            Panel(say.utterance, title=f"{say.question.theme} ({'follow-up' if say.is_followup else 'question'})")
        )
        console.print(Panel(ans, title="(scripted candidate answer)", style="dim"))
        return ans

    return provider


def _print_plan(state: SessionState) -> None:
    if state.scan is None:
        return
    table = Table(title="Question plan", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Theme", style="cyan")
    table.add_column("Question")
    for i, q in enumerate(state.scan.question_plan, 1):
        table.add_row(str(i), q.theme, q.question_text)
    console.print(table)


def _print_evaluations(state: SessionState) -> None:
    if state.scan is None:
        return
    for q in state.scan.question_plan:
        ev = state.evaluations.get(q.id)
        if ev is None:
            continue
        console.print(
            Panel(
                f"[bold]{q.theme}[/bold] · avg [bold]{ev.rubric_scores.average:.1f}[/bold]/5\n"
                f"[green]✓[/green] " + "\n[green]✓[/green] ".join(ev.what_worked) + "\n\n"
                "[yellow]→[/yellow] " + "\n[yellow]→[/yellow] ".join(ev.what_to_improve) + "\n\n"
                f"[bold]Revision task:[/bold] {ev.revision_task}",
                title=q.question_text,
            )
        )
        console.print(Panel(Markdown(ev.model_answer), title="Model answer (your story, rewritten)"))


def _print_summary(state: SessionState) -> None:
    if state.summary is None:
        return
    s = state.summary
    table = Table(title="Competency heatmap")
    table.add_column("Theme", style="cyan")
    table.add_column("Avg score", justify="right")
    for entry in s.competency_heatmap:
        table.add_row(entry.theme, f"{entry.score:.1f}")
    console.print(table)
    console.print(
        Panel("\n".join(f"• {x}" for x in s.keep_stories), title="[green]Keep these stories")
    )
    console.print(
        Panel("\n".join(f"• {x}" for x in s.rework_stories), title="[yellow]Rework these stories")
    )
    console.print(
        Panel(
            "\n".join(f"{i}. {x}" for i, x in enumerate(s.top_recommendations, 1)),
            title="[bold]Top recommendations",
        )
    )


if __name__ == "__main__":
    app()
