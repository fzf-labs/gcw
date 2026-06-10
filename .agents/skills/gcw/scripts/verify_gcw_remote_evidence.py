from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from render_gcw_hosted_artifacts import (
    REVIEW_REQUEST_END,
    REVIEW_REQUEST_START,
    render_progress_comment,
    render_review_request,
)

def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{path.name} is missing")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} is not valid JSON: {exc.msg}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return data


def read_remote_text(path: Path, errors: list[str], artifact_name: str) -> str:
    if not path.is_file():
        errors.append(f"remote {artifact_name} file is missing")
        return ""
    text = path.read_text(encoding="utf-8")
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


def verify_progress_comment(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    _ = load_json(args.issue_dir / "readiness_evidence.json", errors)
    remote_text = read_remote_text(args.remote_file, errors, "progress comment")
    can_compare = not errors
    expected_text = ""
    if can_compare:
        try:
            expected_text = render_progress_comment(argparse.Namespace(issue_dir=args.issue_dir))
        except ValueError as exc:
            errors.append(str(exc))
            can_compare = False
    if can_compare and normalize_body(remote_text) != normalize_body(expected_text):
        errors.append("remote progress comment does not match rendered body")

    return {
        "step": "remote-progress-comment",
        "ok": not errors,
        "errors": errors,
    }


def verify_review_request(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    _ = load_json(args.issue_dir / "readiness_evidence.json", errors)
    remote_text = read_remote_text(args.remote_file, errors, "review request")
    can_compare = not errors
    expected_text = ""
    if can_compare:
        try:
            expected_text = render_review_request(argparse.Namespace(issue_dir=args.issue_dir))
        except ValueError as exc:
            errors.append(str(exc))
            can_compare = False
    rendered_section = extract_marked_body(remote_text, REVIEW_REQUEST_START, REVIEW_REQUEST_END)
    if rendered_section is None:
        errors.append("remote review request is missing gcw review request markers")
    elif can_compare and normalize_body(rendered_section) != normalize_body(expected_text):
        errors.append("remote review request body does not match rendered body")

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
        help="Verify a hosted issue progress comment body against readiness evidence.",
    )
    progress_parser.add_argument("--issue-dir", required=True, type=Path)
    progress_parser.add_argument("--remote-file", required=True, type=Path)
    progress_parser.set_defaults(handler=verify_progress_comment)

    review_parser = subparsers.add_parser(
        "review-request",
        help="Verify a hosted review request body against readiness evidence.",
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
