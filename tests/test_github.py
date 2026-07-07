from __future__ import annotations

from dev_tools.github import (
    Project,
    parse_include_response,
    parse_project,
    primary_rate_limit_wait,
    secondary_rate_limit_wait,
)


def test_parse_project_owner_repo() -> None:
    assert parse_project("clemux/plant-manager") == Project(owner="clemux", repo="plant-manager")


def test_parse_project_host_owner_repo() -> None:
    assert parse_project("github.example.com/org/private") == Project(
        host="github.example.com",
        owner="org",
        repo="private",
    )


def test_parse_include_response_extracts_headers_and_body() -> None:
    response = parse_include_response(
        "HTTP/2 200\r\n"
        "x-ratelimit-remaining: 42\r\n"
        "x-ratelimit-reset: 200\r\n"
        "\r\n"
        "{\"ok\": true}"
    )

    assert response.headers["x-ratelimit-remaining"] == "42"
    assert response.headers["x-ratelimit-reset"] == "200"
    assert response.json() == {"ok": True}


def test_primary_rate_limit_wait_uses_reset_plus_buffer() -> None:
    assert (
        primary_rate_limit_wait(
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "200"},
            now=150,
        )
        == 52
    )


def test_primary_rate_limit_wait_ignores_available_capacity() -> None:
    assert primary_rate_limit_wait({"x-ratelimit-remaining": "1"}, now=150) is None


def test_secondary_rate_limit_wait_uses_retry_after() -> None:
    assert (
        secondary_rate_limit_wait(
            {"retry-after": "10"},
            message="You have exceeded a secondary rate limit",
            attempt=0,
        )
        == 11
    )


def test_secondary_rate_limit_wait_uses_exponential_fallback() -> None:
    assert (
        secondary_rate_limit_wait(
            {},
            message="secondary rate limit",
            attempt=3,
        )
        == 8
    )
