from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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


def require_remote_text(remote_text: str, value: Any, label: str, errors: list[str]) -> None:
    if value in ("", None, [], {}):
        errors.append(f"readiness_evidence.json {label} is missing")
    elif str(value) not in remote_text:
        errors.append(f"remote artifact is missing {label}")


def verify_progress_comment(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    evidence = load_json(args.issue_dir / "readiness_evidence.json", errors)
    remote_text = read_remote_text(args.remote_file, errors, "progress comment")

    planning_links = evidence.get("planning_links") if isinstance(evidence.get("planning_links"), dict) else {}
    for name in ("task_plan", "findings", "progress"):
        link = planning_links.get(name)
        if not link:
            errors.append(f"readiness_evidence.json planning_links.{name} is missing")
        elif link not in remote_text:
            errors.append(f"remote progress comment is missing planning_links.{name}")

    return {
        "step": "remote-progress-comment",
        "ok": not errors,
        "errors": errors,
    }


def verify_review_request(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    evidence = load_json(args.issue_dir / "readiness_evidence.json", errors)
    remote_text = read_remote_text(args.remote_file, errors, "review request")

    review_request = evidence.get("review_request") if isinstance(evidence.get("review_request"), dict) else {}
    require_remote_text(remote_text, review_request.get("title"), "review_request.title", errors)
    require_remote_text(remote_text, review_request.get("summary"), "review_request.summary", errors)
    require_remote_text(remote_text, review_request.get("issue_link"), "review_request.issue_link", errors)

    validations = evidence.get("validation")
    if not isinstance(validations, list) or not validations:
        errors.append("readiness_evidence.json validation is missing")
    else:
        for index, validation in enumerate(validations):
            if not isinstance(validation, dict):
                errors.append(f"readiness_evidence.json validation[{index}] must be an object")
                continue
            require_remote_text(remote_text, validation.get("command"), f"validation[{index}].command", errors)
            require_remote_text(remote_text, validation.get("result"), f"validation[{index}].result", errors)

    planning_links = evidence.get("planning_links") if isinstance(evidence.get("planning_links"), dict) else {}
    for name in ("task_plan", "findings", "progress"):
        require_remote_text(remote_text, planning_links.get(name), f"planning_links.{name}", errors)

    require_remote_text(remote_text, evidence.get("progress_comment_url"), "progress_comment_url", errors)
    require_remote_text(remote_text, evidence.get("risks"), "risks", errors)

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
