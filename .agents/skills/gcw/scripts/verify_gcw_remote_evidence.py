from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from gcw_workflow_lib import assert_projection_current, find_latest_event

from render_gcw_hosted_artifacts import (
    PROGRESS_MARKER,
    REVIEW_REQUEST_END,
    REVIEW_REQUEST_START,
    render_progress_comment,
    render_recorded_progress_comment,
    render_review_request,
)


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


def normalize_body(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip() + "\n"


def extract_marked_body(remote_text: str, start_marker: str, end_marker: str) -> str | None:
    start = remote_text.find(start_marker)
    end = remote_text.find(end_marker, start + len(start_marker)) if start != -1 else -1
    if start == -1 or end == -1 or end < start:
        return None
    return remote_text[start : end + len(end_marker)]


def _count_markers(text: str, marker: str) -> int:
    count = 0
    pos = 0
    while True:
        idx = text.find(marker, pos)
        if idx == -1:
            break
        count += 1
        pos = idx + len(marker)
    return count


def _verify_body_hash(remote_text: str, issue_dir: Path, errors: list[str]) -> None:
    latest = find_latest_event(issue_dir, "gcw-pr-publish")
    if latest is None:
        return
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    expected_hash = str(payload.get("body_hash", ""))
    if not expected_hash.startswith("sha256:"):
        return
    actual_hash = f"sha256:{hashlib.sha256(normalize_body(remote_text).encode('utf-8')).hexdigest()}"
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


def verify_progress_comment(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    expected_url = str(getattr(args, "progress_comment_url", "") or "").strip()
    if not expected_url:
        projection = assert_projection_current(args.issue_dir)["projection"]
        refs = projection.get("refs") if isinstance(projection.get("refs"), dict) else {}
        expected_url = str(refs.get("progress_comment_url", "")).strip()
    if not expected_url:
        errors.append("progress_comment_url is missing from projection refs")
    remote_text = read_remote_text(args.remote_file, errors, "progress comment")
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
    remote_text = read_remote_text(args.remote_file, errors, "review request")
    can_compare = not errors
    expected_text = ""
    if can_compare:
        try:
            expected_text = render_review_request(argparse.Namespace(issue_dir=args.issue_dir))
        except ValueError as exc:
            errors.append(str(exc))
            can_compare = False

    start_count = _count_markers(remote_text, REVIEW_REQUEST_START)
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
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify hosted GCW artifacts against local evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    progress_parser = subparsers.add_parser(
        "progress-comment",
        help="Verify a hosted issue progress comment body against local GCW events.",
    )
    progress_parser.add_argument("--issue-dir", required=True, type=Path)
    progress_parser.add_argument("--remote-file", required=True, type=Path)
    progress_parser.add_argument(
        "--progress-comment-url",
        default="",
        help="Latest hosted progress comment URL; defaults to projection refs.progress_comment_url.",
    )
    progress_parser.set_defaults(handler=verify_progress_comment)

    review_parser = subparsers.add_parser(
        "review-request",
        help="Verify a hosted review request body against local GCW events.",
    )
    review_parser.add_argument("--issue-dir", required=True, type=Path)
    review_parser.add_argument("--remote-file", required=True, type=Path)
    review_parser.set_defaults(handler=verify_review_request)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.handler(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
