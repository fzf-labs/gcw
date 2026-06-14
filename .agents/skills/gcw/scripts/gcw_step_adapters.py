from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Protocol

from gcw_workflow_lib import WorkflowError

from publish_progress_comment import body_hash, publish_progress_comment
from render_gcw_hosted_artifacts import render_progress_comment, render_review_request


class PlatformAdapter(Protocol):
    def publish_progress_comment(self, issue_dir: Any, *, dry_run: bool = False) -> dict[str, Any]: ...

    def upsert_review_request(
        self,
        issue_dir: Any,
        *,
        body: str,
        title: str,
        dry_run: bool = False,
    ) -> dict[str, Any]: ...


@dataclass
class DryRunAdapter:
    def publish_progress_comment(self, issue_dir: Any, *, dry_run: bool = False) -> dict[str, Any]:
        body = render_progress_comment(argparse.Namespace(issue_dir=issue_dir))
        digest = body_hash(body)
        return {
            "ok": True,
            "dry_run": True,
            "body": body,
            "body_hash": digest,
            "progress_comment_url": "",
        }

    def upsert_review_request(
        self,
        issue_dir: Any,
        *,
        body: str,
        title: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        digest = body_hash(body)
        return {
            "ok": True,
            "dry_run": True,
            "body": body,
            "body_hash": digest,
            "review_request_url": "",
        }


@dataclass
class GitHubAdapter:
    def publish_progress_comment(self, issue_dir: Any, *, dry_run: bool = False) -> dict[str, Any]:
        return publish_progress_comment(
            argparse.Namespace(issue_dir=issue_dir, dry_run=dry_run),
        )

    def upsert_review_request(
        self,
        issue_dir: Any,
        *,
        body: str,
        title: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return DryRunAdapter().upsert_review_request(
                issue_dir,
                body=body,
                title=title,
                dry_run=True,
            )
        raise WorkflowError("GitHubAdapter.upsert_review_request requires gh integration; pass review_request_url via step options")


@dataclass
class RecordingAdapter:
    """Test double that records calls and can simulate publication failures."""

    fail_on: str = ""
    published_urls: list[str] = field(default_factory=list)

    def publish_progress_comment(self, issue_dir: Any, *, dry_run: bool = False) -> dict[str, Any]:
        if self.fail_on == "progress_comment":
            raise WorkflowError("simulated progress comment publication failure")
        result = DryRunAdapter().publish_progress_comment(issue_dir, dry_run=True)
        url = f"https://github.com/test/repo/issues/1#issuecomment-{len(self.published_urls) + 1}"
        self.published_urls.append(url)
        result["progress_comment_url"] = url
        result["dry_run"] = dry_run
        return result

    def upsert_review_request(
        self,
        issue_dir: Any,
        *,
        body: str,
        title: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if self.fail_on == "review_request":
            raise WorkflowError("simulated review request publication failure")
        result = DryRunAdapter().upsert_review_request(issue_dir, body=body, title=title, dry_run=True)
        url = f"https://github.com/test/repo/pull/{len(self.published_urls) + 1}"
        self.published_urls.append(url)
        result["review_request_url"] = url
        return result


def render_progress_artifacts(issue_dir: Any) -> dict[str, Any]:
    body = render_progress_comment(argparse.Namespace(issue_dir=issue_dir))
    return {
        "progress_comment_body": body,
        "progress_comment_body_hash": body_hash(body),
    }


def render_review_request_artifacts(issue_dir: Any) -> dict[str, Any]:
    body = render_review_request(argparse.Namespace(issue_dir=issue_dir))
    return {
        "review_request_body": body,
        "review_request_body_hash": body_hash(body),
    }
