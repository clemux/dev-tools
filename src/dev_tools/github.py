from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import IO, Any


class GhError(RuntimeError):
    """Raised when a gh command cannot produce usable data."""


@dataclass(frozen=True)
class Project:
    owner: str
    repo: str
    host: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}" if self.host is None else f"{self.host}/{self.owner}/{self.repo}"

    @property
    def repo_arg(self) -> str:
        return f"{self.owner}/{self.repo}" if self.host is None else self.slug


@dataclass(frozen=True)
class GhResponse:
    headers: dict[str, str]
    body: str

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except json.JSONDecodeError as exc:
            raise GhError(f"gh returned invalid JSON: {exc}") from exc


def parse_project(value: str) -> Project:
    parts = value.split("/")
    if len(parts) == 2:
        owner, repo = parts
        host = None
    elif len(parts) == 3:
        host, owner, repo = parts
    else:
        raise GhError("project must be OWNER/REPO or HOST/OWNER/REPO")

    if not owner or not repo or (len(parts) == 3 and not host):
        raise GhError("project must be OWNER/REPO or HOST/OWNER/REPO")
    return Project(owner=owner, repo=repo, host=host)


class GhClient:
    def __init__(
        self,
        *,
        stderr: IO[str] | None = None,
        sleep=time.sleep,
        now=time.time,
        max_secondary_retries: int = 5,
    ) -> None:
        self.stderr = stderr if stderr is not None else sys.stderr
        self.sleep = sleep
        self.now = now
        self.max_secondary_retries = max_secondary_retries

    def current_project(self) -> Project:
        response = self._run_json(["repo", "view", "--json", "nameWithOwner,url"])
        name_with_owner = response.get("nameWithOwner")
        if not isinstance(name_with_owner, str):
            raise GhError("could not resolve current repository from gh")

        url = response.get("url")
        host = _host_from_url(url) if isinstance(url, str) else None
        project = parse_project(name_with_owner)
        return Project(owner=project.owner, repo=project.repo, host=host if host != "github.com" else None)

    def viewer_login(self, project: Project) -> str:
        response = self.api_json(project, "user")
        login = response.get("login")
        if not isinstance(login, str):
            raise GhError("could not resolve authenticated gh user")
        return login

    def graphql(self, project: Project, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        args = ["api", "--include", "graphql"]
        args.extend(self._hostname_args(project))
        for key, value in variables.items():
            args.extend(["-F", f"{key}={value}"])
        args.extend(["-f", f"query={query}"])
        response = self._run_api_with_rate_limit(args)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GhError("GitHub GraphQL response was not an object")
        errors = payload.get("errors")
        if errors:
            raise GhError(f"GitHub GraphQL returned errors: {errors}")
        return payload

    def api_json(self, project: Project, endpoint: str) -> dict[str, Any]:
        args = ["api", "--include", endpoint]
        args.extend(self._hostname_args(project))
        response = self._run_api_with_rate_limit(args)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GhError(f"gh api {endpoint} did not return a JSON object")
        return payload

    def _run_json(self, args: list[str]) -> dict[str, Any]:
        completed = subprocess.run(
            ["gh", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise GhError(_format_gh_failure(args, completed.stderr))
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GhError(f"gh returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise GhError("gh returned JSON, but not an object")
        return payload

    def _run_api_with_rate_limit(self, args: list[str]) -> GhResponse:
        secondary_attempt = 0
        while True:
            completed = subprocess.run(
                ["gh", *args],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            response = parse_include_response(completed.stdout)
            if completed.returncode == 0:
                return response

            wait_seconds = primary_rate_limit_wait(response.headers, now=self.now())
            reason = "GitHub API primary rate limit"
            if wait_seconds is None:
                wait_seconds = secondary_rate_limit_wait(
                    headers=response.headers,
                    message=f"{completed.stderr}\n{response.body}",
                    attempt=secondary_attempt,
                )
                reason = "GitHub API secondary rate limit"
                if wait_seconds is not None:
                    secondary_attempt += 1
                    if secondary_attempt > self.max_secondary_retries:
                        raise GhError(_format_gh_failure(args, completed.stderr))

            if wait_seconds is None:
                raise GhError(_format_gh_failure(args, completed.stderr))

            self._wait_for_rate_limit(reason, wait_seconds)

    def _wait_for_rate_limit(self, reason: str, wait_seconds: int) -> None:
        wait_seconds = max(1, wait_seconds)
        retry_at = datetime.fromtimestamp(self.now() + wait_seconds, tz=UTC).astimezone()
        print(f"{reason}; retrying at {retry_at.isoformat(timespec='seconds')}", file=self.stderr)
        self.sleep(wait_seconds)

    @staticmethod
    def _hostname_args(project: Project) -> list[str]:
        return ["--hostname", project.host] if project.host else []


def parse_include_response(stdout: str) -> GhResponse:
    header_text, sep, body = stdout.partition("\r\n\r\n")
    if not sep:
        header_text, sep, body = stdout.partition("\n\n")
    if not sep:
        return GhResponse(headers={}, body=stdout)

    header_blocks = re.split(r"\r?\n\r?\n", stdout)
    body = header_blocks[-1]
    headers: dict[str, str] = {}
    for block in header_blocks[:-1]:
        for line in block.splitlines():
            if line.upper().startswith("HTTP/"):
                continue
            key, sep, value = line.partition(":")
            if sep:
                headers[key.strip().lower()] = value.strip()
    return GhResponse(headers=headers, body=body)


def primary_rate_limit_wait(headers: dict[str, str], *, now: float) -> int | None:
    if headers.get("x-ratelimit-remaining") != "0":
        return None
    reset = headers.get("x-ratelimit-reset")
    if reset is None:
        return None
    try:
        return max(1, int(float(reset)) - int(now) + 2)
    except ValueError:
        return None


def secondary_rate_limit_wait(headers: dict[str, str], message: str, attempt: int) -> int | None:
    text = message.lower()
    secondary_markers = (
        "secondary rate limit",
        "abuse detection",
        "you have exceeded a secondary rate limit",
    )
    if not any(marker in text for marker in secondary_markers):
        return None

    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(1, int(float(retry_after)) + 1)
        except ValueError:
            pass
    return min(300, 2 ** min(attempt, 8))


def _format_gh_failure(args: list[str], stderr: str) -> str:
    message = stderr.strip() or "gh command failed"
    return f"gh {' '.join(args)} failed: {message}"


def _host_from_url(url: str) -> str | None:
    match = re.match(r"https?://([^/]+)/", url)
    return match.group(1) if match else None
