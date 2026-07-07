from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

import typer

from dev_tools.config import load_config, save_default_project
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
        help="Repository as [HOST/]OWNER/REPO. Defaults to saved config or the current gh repository.",
    ),
    limit: int = typer.Option(30, "--limit", "-L", min=1, max=100, help="Maximum open PRs to fetch."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
    save_project_default: bool = typer.Option(
        False,
        "--save-project-default",
        help="Save the resolved project as the default for future runs.",
    ),
) -> None:
    """Show open PRs authored by you and their review-thread status."""

    client = GhClient(stderr=sys.stderr)
    try:
        default_project = None if project else load_config().default_project
        resolved_project = resolve_project(project=project, default_project=default_project, client=client)
        if save_project_default:
            save_default_project(resolved_project)
        viewer = client.viewer_login(resolved_project)
        report = build_report(client=client, project=resolved_project, viewer=viewer, limit=limit)
    except GhError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(report.to_json(generated_at=datetime.now(UTC)), indent=2))
        return

    render_human_report(report)


def resolve_project(*, project: str | None, default_project: Project | None, client: GhClient) -> Project:
    if project:
        return parse_project(project)
    if default_project is not None:
        return default_project
    return client.current_project()


if __name__ == "__main__":
    app()
