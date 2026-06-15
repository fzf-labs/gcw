from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Callable
from urllib.parse import urlparse

GITHUB_API_VERSION = "2026-03-10"

GITHUB_ISSUE_COMMENT_URL = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<issue>\d+)(?:#issuecomment-(?P<comment_id>\d+))?$",
    re.IGNORECASE,
)
GITHUB_PULL_URL = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)/?$",
    re.IGNORECASE,
)
GITLAB_ISSUE_NOTE_URL = re.compile(
    r"^https?://[^/]+/(?P<project>.+)/-/issues/(?P<issue>\d+)(?:#note_(?P<note_id>\d+))?$",
    re.IGNORECASE,
)
GITLAB_MR_URL = re.compile(
    r"^https?://[^/]+/(?P<project>.+)/-/merge_requests/(?P<number>\d+)/?$",
    re.IGNORECASE,
)

FetchFn = Callable[[str], str]
RunFn = Callable[[list[str]], subprocess.CompletedProcess[str]]


class RemoteFetchError(Exception):
    pass


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "github" in host:
        return "github"
    if "gitlab" in host or "/-/" in url:
        return "gitlab"
    raise RemoteFetchError(f"unsupported remote URL host for fetch: {host or url}")


def _run(cmd: list[str], *, runner: RunFn) -> subprocess.CompletedProcess[str]:
    return runner(cmd)


def _github_api_json(endpoint: str, *, runner: RunFn) -> Any:
    cmd = ["gh", "api", endpoint, "-H", f"X-GitHub-Api-Version: {GITHUB_API_VERSION}"]
    try:
        result = _run(cmd, runner=runner)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        lowered = detail.lower()
        if "401" in detail or "bad credentials" in lowered or "authentication" in lowered:
            raise RemoteFetchError(f"github fetch failed: authentication required ({detail})") from exc
        if "404" in detail or "not found" in lowered:
            raise RemoteFetchError(f"github fetch failed: artifact not found ({detail})") from exc
        raise RemoteFetchError(f"github fetch failed: {detail}") from exc
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def _gitlab_api_json(args: list[str], *, runner: RunFn) -> Any:
    cmd = ["glab", "api", *args]
    try:
        result = _run(cmd, runner=runner)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        lowered = detail.lower()
        if "401" in detail or "unauthorized" in lowered or "authentication" in lowered:
            raise RemoteFetchError(f"gitlab fetch failed: authentication required ({detail})") from exc
        if "404" in detail or "not found" in lowered:
            raise RemoteFetchError(f"gitlab fetch failed: artifact not found ({detail})") from exc
        raise RemoteFetchError(f"gitlab fetch failed: {detail}") from exc
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def _gitlab_project_path(project: str) -> str:
    return project.strip("/")


def fetch_github(url: str, *, runner: RunFn | None = None) -> str:
    run = runner or (lambda cmd: subprocess.run(cmd, check=True, text=True, capture_output=True))

    comment_match = GITHUB_ISSUE_COMMENT_URL.match(url)
    if comment_match:
        owner = comment_match.group("owner")
        repo = comment_match.group("repo")
        comment_id = comment_match.group("comment_id")
        if not comment_id:
            raise RemoteFetchError(f"unsupported github URL shape: missing issuecomment id in {url}")
        data = _github_api_json(f"repos/{owner}/{repo}/issues/comments/{comment_id}", runner=run)
        body = str(data.get("body", "")).strip()
        if not body:
            raise RemoteFetchError("github fetch failed: comment body is empty")
        return body

    pull_match = GITHUB_PULL_URL.match(url)
    if pull_match:
        owner = pull_match.group("owner")
        repo = pull_match.group("repo")
        number = pull_match.group("number")
        data = _github_api_json(f"repos/{owner}/{repo}/pulls/{number}", runner=run)
        body = str(data.get("body", "")).strip()
        if not body:
            raise RemoteFetchError("github fetch failed: pull request body is empty")
        return body

    raise RemoteFetchError(f"unsupported github URL shape: {url}")


def fetch_gitlab(url: str, *, runner: RunFn | None = None) -> str:
    run = runner or (lambda cmd: subprocess.run(cmd, check=True, text=True, capture_output=True))

    note_match = GITLAB_ISSUE_NOTE_URL.match(url)
    if note_match:
        project = _gitlab_project_path(note_match.group("project"))
        issue = note_match.group("issue")
        note_id = note_match.group("note_id")
        if not note_id:
            raise RemoteFetchError(f"unsupported gitlab URL shape: missing note id in {url}")
        encoded = project.replace("/", "%2F")
        data = _gitlab_api_json(
            [f"projects/{encoded}/issues/{issue}/notes/{note_id}"],
            runner=run,
        )
        body = str(data.get("body", "")).strip()
        if not body:
            raise RemoteFetchError("gitlab fetch failed: issue note body is empty")
        return body

    mr_match = GITLAB_MR_URL.match(url)
    if mr_match:
        project = _gitlab_project_path(mr_match.group("project"))
        number = mr_match.group("number")
        try:
            result = _run(
                ["glab", "mr", "view", number, "-R", project, "--output", "json"],
                runner=run,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RemoteFetchError(f"gitlab fetch failed: {detail}") from exc
        data = json.loads(result.stdout or "{}")
        body = str(data.get("description", "")).strip()
        if not body:
            raise RemoteFetchError("gitlab fetch failed: merge request description is empty")
        return body

    raise RemoteFetchError(f"unsupported gitlab URL shape: {url}")


def fetch_url(url: str, *, fetcher: FetchFn | None = None, runner: RunFn | None = None) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        raise RemoteFetchError("fetch URL is required")
    if fetcher is not None:
        return fetcher(normalized)
    platform = detect_platform(normalized)
    if platform == "github":
        return fetch_github(normalized, runner=runner)
    return fetch_gitlab(normalized, runner=runner)
