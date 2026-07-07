from __future__ import annotations

from dev_tools.cli import resolve_project
from dev_tools.github import Project


class FakeClient:
    def current_project(self) -> Project:
        return Project(owner="current", repo="repo")


def test_resolve_project_prefers_explicit_project() -> None:
    assert resolve_project(
        project="github.example.com/org/repo",
        default_project=Project(owner="default", repo="repo"),
        client=FakeClient(),
    ) == Project(owner="org", repo="repo", host="github.example.com")


def test_resolve_project_uses_default_before_current_repo() -> None:
    assert resolve_project(
        project=None,
        default_project=Project(owner="default", repo="repo"),
        client=FakeClient(),
    ) == Project(owner="default", repo="repo")


def test_resolve_project_falls_back_to_current_repo() -> None:
    assert resolve_project(project=None, default_project=None, client=FakeClient()) == Project(
        owner="current",
        repo="repo",
    )
