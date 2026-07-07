from __future__ import annotations

from datetime import UTC, datetime

from dev_tools.github import Project
from dev_tools.prs import (
    PullRequestReport,
    ThreadSummary,
    latest_reviewer_comment,
    parse_pull_request_node,
    single_line_snippet,
    status_for_pr,
    summarize_threads,
)


def test_status_mapping_prioritizes_draft() -> None:
    assert (
        status_for_pr(
            is_draft=True,
            review_decision="APPROVED",
            threads=ThreadSummary(total=0, resolved=0, unresolved=0),
        )
        == "draft"
    )


def test_status_mapping_change_requested_from_review_decision() -> None:
    assert (
        status_for_pr(
            is_draft=False,
            review_decision="CHANGES_REQUESTED",
            threads=ThreadSummary(total=0, resolved=0, unresolved=0),
        )
        == "change requested"
    )


def test_status_mapping_change_requested_from_unresolved_threads() -> None:
    assert (
        status_for_pr(
            is_draft=False,
            review_decision=None,
            threads=ThreadSummary(total=1, resolved=0, unresolved=1),
        )
        == "change requested"
    )


def test_status_mapping_approved() -> None:
    assert (
        status_for_pr(
            is_draft=False,
            review_decision="APPROVED",
            threads=ThreadSummary(total=0, resolved=0, unresolved=0),
        )
        == "approved"
    )


def test_status_mapping_review_required() -> None:
    assert (
        status_for_pr(
            is_draft=False,
            review_decision=None,
            threads=ThreadSummary(total=0, resolved=0, unresolved=0),
        )
        == "review required"
    )


def test_summarize_threads_counts_resolved_and_unresolved() -> None:
    assert summarize_threads(
        {
            "totalCount": 3,
            "nodes": [
                {"isResolved": True},
                {"isResolved": False},
                {"isResolved": False},
            ],
        },
        viewer="clemux",
    ) == ThreadSummary(total=3, resolved=1, unresolved=2)


def test_latest_reviewer_comment_ignores_viewer_when_possible() -> None:
    comment = latest_reviewer_comment(
        {
            "nodes": [
                {
                    "comments": {
                        "nodes": [
                            {
                                "author": {"login": "reviewer"},
                                "bodyText": "Please change this",
                                "createdAt": "2026-07-07T10:00:00Z",
                                "url": "https://example.test/1",
                            },
                            {
                                "author": {"login": "clemux"},
                                "bodyText": "Done",
                                "createdAt": "2026-07-07T11:00:00Z",
                                "url": "https://example.test/2",
                            },
                        ]
                    }
                }
            ]
        },
        viewer="clemux",
    )

    assert comment is not None
    assert comment.author == "reviewer"
    assert comment.body == "Please change this"


def test_parse_pull_request_node() -> None:
    pr = parse_pull_request_node(
        {
            "number": 12,
            "title": "Fix thing",
            "url": "https://example.test/pull/12",
            "headRefName": "fix-thing",
            "isDraft": False,
            "reviewDecision": "APPROVED",
            "reviewThreads": {"totalCount": 0, "nodes": []},
        },
        viewer="clemux",
    )

    assert pr.number == 12
    assert pr.status == "approved"
    assert pr.branch == "fix-thing"


def test_report_json_shape() -> None:
    report = PullRequestReport(project=Project("clemux", "plant-manager"), viewer="clemux", prs=[])

    assert report.to_json(generated_at=datetime(2026, 7, 7, tzinfo=UTC)) == {
        "project": "clemux/plant-manager",
        "viewer": "clemux",
        "generated_at": "2026-07-07T00:00:00+00:00",
        "prs": [],
    }


def test_single_line_snippet_collapses_whitespace_and_truncates() -> None:
    assert single_line_snippet("a\n\nb\tc", limit=10) == "a b c"
    assert single_line_snippet("x" * 20, limit=10) == "xxxxxxx..."
