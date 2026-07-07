from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dev_tools.github import GhClient, Project


PRS_QUERY = """
query($searchQuery: String!, $limit: Int!) {
  search(type: ISSUE, query: $searchQuery, first: $limit) {
    nodes {
      ... on PullRequest {
        number
        title
        url
        headRefName
        isDraft
        reviewDecision
        author { login }
        reviewThreads(first: 100) {
          totalCount
          nodes {
            isResolved
            isOutdated
            comments(first: 20) {
              nodes {
                author { login }
                bodyText
                createdAt
                url
              }
            }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class CommentSummary:
    author: str
    created_at: str
    body: str
    url: str

    def to_json(self) -> dict[str, str]:
        return {
            "author": self.author,
            "created_at": self.created_at,
            "body": self.body,
            "url": self.url,
        }


@dataclass(frozen=True)
class ThreadSummary:
    total: int
    resolved: int
    unresolved: int

    def to_json(self) -> dict[str, int]:
        return {
            "total": self.total,
            "resolved": self.resolved,
            "unresolved": self.unresolved,
        }


@dataclass(frozen=True)
class PullRequestSummary:
    number: int
    title: str
    url: str
    branch: str
    status: str
    is_draft: bool
    review_decision: str | None
    threads: ThreadSummary
    latest_reviewer_comment: CommentSummary | None

    def to_json(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "branch": self.branch,
            "status": self.status,
            "is_draft": self.is_draft,
            "review_decision": self.review_decision,
            "threads": self.threads.to_json(),
            "latest_reviewer_comment": (
                self.latest_reviewer_comment.to_json() if self.latest_reviewer_comment else None
            ),
        }


@dataclass(frozen=True)
class PullRequestReport:
    project: Project
    viewer: str
    prs: list[PullRequestSummary]

    def to_json(self, *, generated_at: datetime) -> dict[str, Any]:
        return {
            "project": self.project.slug,
            "viewer": self.viewer,
            "generated_at": generated_at.isoformat(),
            "prs": [pr.to_json() for pr in self.prs],
        }


def build_report(client: GhClient, project: Project, viewer: str, limit: int) -> PullRequestReport:
    payload = client.graphql(
        project,
        PRS_QUERY,
        {
            "searchQuery": f"repo:{project.owner}/{project.repo} is:pr is:open author:{viewer}",
            "limit": limit,
        },
    )
    nodes = payload.get("data", {}).get("search", {}).get("nodes", [])
    prs = [
        parse_pull_request_node(node, viewer)
        for node in nodes
        if isinstance(node, dict) and node.get("author", {}).get("login") == viewer
    ]
    return PullRequestReport(project=project, viewer=viewer, prs=prs)


def parse_pull_request_node(node: dict[str, Any], viewer: str) -> PullRequestSummary:
    is_draft = bool(node.get("isDraft"))
    review_decision = node.get("reviewDecision")
    threads = summarize_threads(node.get("reviewThreads") or {}, viewer)
    return PullRequestSummary(
        number=int(node["number"]),
        title=str(node.get("title") or ""),
        url=str(node.get("url") or ""),
        branch=str(node.get("headRefName") or ""),
        status=status_for_pr(is_draft=is_draft, review_decision=review_decision, threads=threads),
        is_draft=is_draft,
        review_decision=review_decision if isinstance(review_decision, str) else None,
        threads=threads,
        latest_reviewer_comment=latest_reviewer_comment(node.get("reviewThreads") or {}, viewer),
    )


def status_for_pr(*, is_draft: bool, review_decision: Any, threads: ThreadSummary) -> str:
    if is_draft:
        return "draft"
    if review_decision == "CHANGES_REQUESTED":
        return "change requested"
    if threads.unresolved > 0:
        return "change requested"
    if review_decision == "APPROVED":
        return "approved"
    return "review required"


def summarize_threads(review_threads: dict[str, Any], viewer: str) -> ThreadSummary:
    nodes = [node for node in review_threads.get("nodes", []) if isinstance(node, dict)]
    total = int(review_threads.get("totalCount") or len(nodes))
    resolved = sum(1 for node in nodes if node.get("isResolved") is True)
    unresolved = sum(1 for node in nodes if node.get("isResolved") is not True)
    if total > len(nodes):
        unresolved += total - len(nodes)
    return ThreadSummary(total=total, resolved=resolved, unresolved=unresolved)


def latest_reviewer_comment(review_threads: dict[str, Any], viewer: str) -> CommentSummary | None:
    comments: list[CommentSummary] = []
    fallback_comments: list[CommentSummary] = []
    for thread in review_threads.get("nodes", []):
        if not isinstance(thread, dict):
            continue
        for raw_comment in (thread.get("comments") or {}).get("nodes", []):
            if not isinstance(raw_comment, dict):
                continue
            comment = _comment_from_node(raw_comment)
            if comment is None:
                continue
            fallback_comments.append(comment)
            if comment.author != viewer:
                comments.append(comment)

    pool = comments or fallback_comments
    if not pool:
        return None
    return max(pool, key=lambda comment: comment.created_at)


def _comment_from_node(node: dict[str, Any]) -> CommentSummary | None:
    author = (node.get("author") or {}).get("login")
    created_at = node.get("createdAt")
    url = node.get("url")
    if not isinstance(author, str) or not isinstance(created_at, str) or not isinstance(url, str):
        return None
    return CommentSummary(
        author=author,
        created_at=created_at,
        body=single_line_snippet(str(node.get("bodyText") or "")),
        url=url,
    )


def single_line_snippet(value: str, limit: int = 160) -> str:
    snippet = " ".join(value.split())
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3].rstrip() + "..."
