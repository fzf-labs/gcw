from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from gcw_workflow_errors import WorkflowError


def fetch_issue_labels(repo: str, issue_number: str) -> list[str]:
    repo = repo.strip()
    issue_number = issue_number.strip()
    if not repo or not issue_number:
        return []
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            issue_number,
            "--repo",
            repo,
            "--json",
            "labels",
            "--jq",
            ".labels[].name",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def publish_issue_comment(issue: str | int, repository: str, body: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(body)
        body_file = handle.name
    try:
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue), "--repo", repository, "--body-file", body_file],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise WorkflowError(f"gh issue comment failed: {detail}") from exc
    finally:
        Path(body_file).unlink(missing_ok=True)
    url = result.stdout.strip()
    if not url:
        raise WorkflowError("gh issue comment did not return a comment URL")
    return url


def find_open_pr(repo: str, branch: str) -> str:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--head",
            branch,
            "--json",
            "url",
            "--jq",
            ".[0].url // empty",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def upsert_pr(repo: str, branch: str, title: str, body_file: Path, base: str) -> str:
    existing = find_open_pr(repo, branch)
    if existing:
        subprocess.run(["gh", "pr", "edit", existing, "--repo", repo, "--title", title, "--body-file", str(body_file)], check=True)
        return existing

    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--head",
            branch,
            "--base",
            base,
            "--title",
            title,
            "--body-file",
            str(body_file),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    url = result.stdout.strip()
    if url:
        return url
    return find_open_pr(repo, branch)
