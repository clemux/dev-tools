from __future__ import annotations

import typer

from dev_tools.prs import PullRequestReport, PullRequestSummary


GROUPS = (
    ("Needs attention", {"change requested"}),
    ("Approved", {"approved"}),
    ("Waiting review", {"review required"}),
    ("Draft", {"draft"}),
)


def render_human_report(report: PullRequestReport) -> None:
    typer.echo(f"PR triage for {report.project.slug} as {report.viewer}")
    if not report.prs:
        typer.echo("No open PRs authored by you.")
        return

    for heading, statuses in GROUPS:
        prs = [pr for pr in report.prs if pr.status in statuses]
        if not prs:
            continue
        typer.echo("")
        typer.echo(f"{heading}")
        for pr in prs:
            render_pr(pr)


def render_pr(pr: PullRequestSummary) -> None:
    typer.echo(f"  #{pr.number} {pr.title}")
    typer.echo(f"    status: {pr.status} | branch: {pr.branch}")
    typer.echo(
        f"    threads: {pr.threads.unresolved} unresolved, "
        f"{pr.threads.resolved} resolved, {pr.threads.total} total"
    )
    if pr.latest_reviewer_comment:
        comment = pr.latest_reviewer_comment
        typer.echo(f"    latest reviewer: {comment.author} at {comment.created_at}")
        typer.echo(f"    {comment.body}")
        typer.echo(f"    {comment.url}")
    typer.echo(f"    {pr.url}")
