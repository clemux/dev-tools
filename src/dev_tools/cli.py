from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import typer

from dev_tools.github import GhClient, GhError, Project, parse_project
from dev_tools.prs import build_report
from dev_tools.render import render_human_report

app = typer.Typer(no_args_is_help=True, help="Small CLI helpers for development workflows.")


@app.callback()
def main() -> None:
    """Small CLI helpers for development workflows."""


@app.command("prs")
def prs(
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Repository as [HOST/]OWNER/REPO. Defaults to the current gh repository.",
    ),
    limit: int = typer.Option(30, "--limit", "-L", min=1, max=100, help="Maximum open PRs to fetch."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Show open PRs authored by you and their review-thread status."""

    client = GhClient(stderr=sys.stderr)
    try:
        resolved_project = parse_project(project) if project else client.current_project()
        viewer = client.viewer_login(resolved_project)
        report = build_report(client=client, project=resolved_project, viewer=viewer, limit=limit)
    except GhError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(report.to_json(generated_at=datetime.now(UTC)), indent=2))
        return

    render_human_report(report)


if __name__ == "__main__":
    app()
