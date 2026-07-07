from __future__ import annotations

import typer

from dev_tools.prs import PullRequestReport, PullRequestSummary


GROUPS = (
    ("Needs attention", {"change requested"}, typer.colors.RED),
    ("Waiting review", {"review required"}, typer.colors.YELLOW),
    ("Approved", {"approved"}, typer.colors.GREEN),
    ("Draft", {"draft"}, typer.colors.BRIGHT_BLACK),
)


def render_human_report(report: PullRequestReport) -> None:
    typer.secho("PR triage", bold=True)
    typer.echo(f"Project: {report.project.slug}")
    typer.echo(f"Viewer:  {report.viewer}")
    typer.echo(f"Open PRs: {len(report.prs)}")
    if not report.prs:
        typer.echo("")
        typer.secho("No open PRs authored by you.", fg=typer.colors.GREEN)
        return

    for heading, statuses, color in GROUPS:
        prs = [pr for pr in report.prs if pr.status in statuses]
        if not prs:
            continue
        typer.echo("")
        typer.secho(f"{heading} ({len(prs)})", fg=color, bold=True)
        for pr in prs:
            render_pr(pr)


def render_pr(pr: PullRequestSummary) -> None:
    typer.echo(f"  #{pr.number}  {pr.title}")
    _field("Status", pr.status)
    _field("Branch", pr.branch)
    _field(
        "Threads",
        f"{pr.threads.unresolved} unresolved, {pr.threads.resolved} resolved, {pr.threads.total} total",
    )
    if pr.latest_reviewer_comment:
        comment = pr.latest_reviewer_comment
        _field("Latest", f"{comment.author} at {comment.created_at}")
        _field("", comment.body)
        _field("", comment.url)
    _field("URL", pr.url)


def _field(label: str, value: str) -> None:
    typer.echo(f"    {label + ':' if label else '':<9} {value}")
