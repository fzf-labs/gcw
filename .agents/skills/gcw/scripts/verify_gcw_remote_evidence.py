from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from gcw_workflow_lib import assert_projection_current, find_latest_event

from remote_fetch import RemoteFetchError, fetch_url
from gcw_artifact_contracts import (
    PROGRESS_MARKER,
    REVIEW_REQUEST_END,
    REVIEW_REQUEST_START,
    body_hash,
    count_markers,
    extract_marked_body,
    normalize_body,
)
from render_gcw_hosted_artifacts import (
    render_progress_comment,
    render_recorded_progress_comment,
    render_review_request,
)

FetchFn = Callable[[str], str]


def read_remote_text(path: Path, errors: list[str], artifact_name: str) -> str:
    if not path.is_file():
        errors.append(f"remote {artifact_name} file is missing")
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"remote {artifact_name} file is not valid UTF-8")
        return ""
    if not text:
        errors.append(f"remote {artifact_name} file is empty")
    return text


def load_remote_text(
    *,
    remote_file: Path | None,
    fetch_target_url: str,
    artifact_name: str,
    errors: list[str],
    fetcher: FetchFn | None = None,
) -> str:
    if remote_file is not None:
        return read_remote_text(remote_file, errors, artifact_name)
    if not fetch_target_url:
        errors.append(f"no fetch URL available for remote {artifact_name}")
        return ""
    try:
        text = fetch_url(fetch_target_url, fetcher=fetcher)
    except RemoteFetchError as exc:
        errors.append(str(exc))
        return ""
    if not text:
        errors.append(f"remote {artifact_name} file is empty")
    return text


def _verify_body_hash(remote_text: str, issue_dir: Path, errors: list[str]) -> None:
    latest = find_latest_event(issue_dir, "gcw-pr-publish")
    if latest is None:
        return
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    expected_hash = str(payload.get("body_hash", ""))
    if not expected_hash.startswith("sha256:"):
        return
    actual_hash = body_hash(remote_text)
    if actual_hash != expected_hash:
        errors.append(f"remote body hash {actual_hash} does not match event body_hash {expected_hash}")


def _latest_progress_event(issue_dir: Path) -> dict[str, Any] | None:
    current = assert_projection_current(issue_dir)
    if not current["ok"]:
        return None
    projection = current["projection"]
    last_completed = str(projection.get("last_completed_step", "")).strip()
    if not last_completed:
        return None
    latest = find_latest_event(issue_dir, last_completed)
    payload = latest.get("payload") if isinstance(latest, dict) and isinstance(latest.get("payload"), dict) else {}
    if str(payload.get("progress_comment_url", "")).strip():
        return latest
    return None


def _verify_progress_body_hash(remote_text: str, issue_dir: Path, errors: list[str]) -> None:
    latest = _latest_progress_event(issue_dir)
    if latest is None:
        return
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    expected_hash = str(payload.get("progress_comment_body_hash", "")).strip()
    if not expected_hash:
        return
    actual_hash = f"sha256:{hashlib.sha256(normalize_body(remote_text).encode('utf-8')).hexdigest()}"
    if actual_hash != expected_hash:
        errors.append(f"remote progress comment body hash {actual_hash} does not match event progress_comment_body_hash {expected_hash}")


def resolve_progress_comment_url(issue_dir: Path, args: argparse.Namespace, errors: list[str]) -> str:
    expected_url = str(getattr(args, "progress_comment_url", "") or "").strip()
    if expected_url:
        return expected_url
    if str(getattr(args, "fetch_url", "") or "").strip():
        return str(args.fetch_url).strip()
    current = assert_projection_current(issue_dir)
    if not current.get("ok"):
        errors.extend(str(item) for item in current.get("errors", []))
    projection = current.get("projection") if isinstance(current.get("projection"), dict) else {}
    refs = projection.get("refs") if isinstance(projection.get("refs"), dict) else {}
    return str(refs.get("progress_comment_url", "")).strip()


def resolve_review_request_url(issue_dir: Path, args: argparse.Namespace, errors: list[str]) -> str:
    expected_url = str(getattr(args, "review_request_url", "") or "").strip()
    if expected_url:
        return expected_url
    if str(getattr(args, "fetch_url", "") or "").strip():
        return str(args.fetch_url).strip()
    current = assert_projection_current(issue_dir)
    if not current.get("ok"):
        errors.extend(str(item) for item in current.get("errors", []))
    projection = current.get("projection") if isinstance(current.get("projection"), dict) else {}
    refs = projection.get("refs") if isinstance(projection.get("refs"), dict) else {}
    expected_url = str(refs.get("review_request_url", "")).strip()
    if expected_url:
        return expected_url
    try:
        latest = find_latest_event(issue_dir, "gcw-pr-publish")
    except Exception as exc:
        errors.append(str(exc))
        return ""
    if latest is None:
        return ""
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    return str(payload.get("review_request_url", "")).strip()


def verify_progress_comment(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    remote_file = getattr(args, "remote_file", None)
    fetcher = getattr(args, "fetcher", None)
    expected_url = ""
    if remote_file is None:
        expected_url = resolve_progress_comment_url(args.issue_dir, args, errors)
        if not expected_url:
            errors.append("progress_comment_url is missing from projection refs")
    else:
        expected_url = str(getattr(args, "progress_comment_url", "") or getattr(args, "fetch_url", "") or "").strip()
    remote_text = load_remote_text(
        remote_file=remote_file,
        fetch_target_url=expected_url,
        artifact_name="progress comment",
        errors=errors,
        fetcher=fetcher,
    )
    if remote_text and PROGRESS_MARKER not in remote_text:
        errors.append("remote progress comment is missing gcw progress marker")
    can_compare = not errors
    expected_text = ""
    if can_compare:
        try:
            latest_progress_event = _latest_progress_event(args.issue_dir)
            if latest_progress_event is None:
                expected_text = render_progress_comment(argparse.Namespace(issue_dir=args.issue_dir))
            else:
                expected_text = render_recorded_progress_comment(args.issue_dir, latest_progress_event)
        except ValueError as exc:
            errors.append(str(exc))
            can_compare = False
    if can_compare and normalize_body(remote_text) != normalize_body(expected_text):
        errors.append("remote progress comment does not match rendered body")
    if remote_text:
        _verify_progress_body_hash(remote_text, args.issue_dir, errors)

    return {
        "step": "remote-progress-comment",
        "ok": not errors,
        "errors": errors,
        "progress_comment_url": expected_url,
    }


def verify_review_request(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    remote_file = getattr(args, "remote_file", None)
    fetcher = getattr(args, "fetcher", None)
    expected_url = ""
    if remote_file is None:
        expected_url = resolve_review_request_url(args.issue_dir, args, errors)
        if not expected_url:
            errors.append("review_request_url is missing from projection refs and gcw-pr-publish events")
    else:
        expected_url = str(getattr(args, "review_request_url", "") or getattr(args, "fetch_url", "") or "").strip()
    remote_text = load_remote_text(
        remote_file=remote_file,
        fetch_target_url=expected_url,
        artifact_name="review request",
        errors=errors,
        fetcher=fetcher,
    )
    can_compare = not errors
    expected_text = ""
    if can_compare:
        try:
            expected_text = render_review_request(argparse.Namespace(issue_dir=args.issue_dir))
        except ValueError as exc:
            errors.append(str(exc))
            can_compare = False

    start_count = count_markers(remote_text, REVIEW_REQUEST_START)
    if start_count > 1:
        errors.append(f"remote review request has {start_count} start markers; expected 1")

    rendered_section = extract_marked_body(remote_text, REVIEW_REQUEST_START, REVIEW_REQUEST_END)
    if rendered_section is None:
        errors.append("remote review request is missing gcw review request markers")
    elif can_compare and normalize_body(rendered_section) != normalize_body(expected_text):
        errors.append("remote review request body does not match rendered body")

    if can_compare:
        _verify_body_hash(remote_text, args.issue_dir, errors)

    return {
        "step": "remote-review-request",
        "ok": not errors,
        "errors": errors,
        "review_request_url": expected_url,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify hosted GCW artifacts against local evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    progress_parser = subparsers.add_parser(
        "progress-comment",
        help="Verify a hosted issue progress comment body against local GCW events.",
    )
    progress_parser.add_argument("--issue-dir", required=True, type=Path)
    progress_parser.add_argument(
        "--remote-file",
        default=None,
        type=Path,
        help="Offline/local copy of the hosted comment body. When omitted, fetch from the resolved comment URL.",
    )
    progress_parser.add_argument(
        "--fetch-url",
        default="",
        help="Override the hosted comment URL to fetch.",
    )
    progress_parser.add_argument(
        "--progress-comment-url",
        default="",
        help="Latest hosted progress comment URL; defaults to projection refs.progress_comment_url.",
    )
    progress_parser.set_defaults(handler=verify_progress_comment, fetcher=None)

    review_parser = subparsers.add_parser(
        "review-request",
        help="Verify a hosted review request body against local GCW events.",
    )
    review_parser.add_argument("--issue-dir", required=True, type=Path)
    review_parser.add_argument(
        "--remote-file",
        default=None,
        type=Path,
        help="Offline/local copy of the hosted review request body. When omitted, fetch from the resolved review URL.",
    )
    review_parser.add_argument(
        "--fetch-url",
        default="",
        help="Override the hosted review request URL to fetch.",
    )
    review_parser.add_argument(
        "--review-request-url",
        default="",
        help="Hosted review request URL; defaults to projection refs or latest gcw-pr-publish event.",
    )
    review_parser.set_defaults(handler=verify_review_request, fetcher=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.handler(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
