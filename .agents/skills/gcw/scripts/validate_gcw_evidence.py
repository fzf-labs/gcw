from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


STATES = {
    "issue-opened",
    "issue-clarifying",
    "ready-for-planning",
    "planned",
    "ready-for-implementation",
    "implementing",
    "ready-for-review",
    "reviewing",
    "changes-requested",
    "blocked",
    "review-complete",
}

NEXT_ALLOWED_STEPS: dict[str, list[str]] = {
    "issue-opened": ["gcw-issue-prepare"],
    "issue-clarifying": ["gcw-issue-prepare"],
    "ready-for-planning": ["gcw-issue-to-spec"],
    "planned": ["gcw-spec-check"],
    "ready-for-implementation": ["gcw-implement"],
    "implementing": ["gcw-implement", "gcw-implement-check", "gcw-block", "gcw-clarify"],
    "ready-for-review": ["gcw-pr-publish"],
    "reviewing": ["gcw-pr-review"],
    "changes-requested": ["gcw-implement"],
    "blocked": [],
    "review-complete": [],
}

PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")


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


def require_non_empty(data: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> None:
    value = data.get(key)
    if value is None or str(value).strip() == "":
        errors.append(f"{prefix}{key} is required")


def state_errors(issue_dir: Path) -> list[str]:
    errors: list[str] = []
    state = load_json(issue_dir / "state.json", errors)
    if errors:
        return errors

    for key in ("issue", "platform", "repository", "state", "branch", "owner", "last_completed_step", "next_allowed_steps", "evidence"):
        if key not in state:
            errors.append(f"state.json missing {key}")

    current = state.get("state")
    if current not in STATES:
        errors.append(f"state.json has unknown state {current}")
        return errors

    expected_next = NEXT_ALLOWED_STEPS[current]
    if state.get("next_allowed_steps") != expected_next:
        errors.append(f"{current} requires next_allowed_steps {expected_next}")

    evidence = state.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("state.json evidence must be an object")
    else:
        for key in (
            "planning_files_exist",
            "planning_commit_pushed",
            "progress_comment_url",
            "spec_check_passed",
            "implement_check_passed",
            "self_review_recorded",
            "review_request_url",
        ):
            if key not in evidence:
                errors.append(f"state.json evidence missing {key}")

    metadata = state.get("metadata")
    if current == "blocked":
        if not isinstance(metadata, dict):
            errors.append("blocked requires metadata")
        else:
            require_non_empty(metadata, "resume_state", errors, "metadata.")
            require_non_empty(metadata, "resume_step", errors, "metadata.")
    if current == "changes-requested":
        if not isinstance(metadata, dict):
            errors.append("changes-requested requires metadata")
        else:
            source = metadata.get("feedback_source")
            if source not in {"pr-review", "human-review"}:
                errors.append("changes-requested requires metadata.feedback_source pr-review or human-review")

    return errors


def spec_check_errors(issue_dir: Path) -> list[str]:
    errors = state_errors(issue_dir)
    state = load_json(issue_dir / "state.json", []) if (issue_dir / "state.json").is_file() else {}
    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}

    missing = [name for name in PLANNING_FILES if not (issue_dir / name).is_file()]
    if missing:
        errors.append(f"missing planning files: {', '.join(missing)}")
    if evidence.get("planning_files_exist") is not True:
        errors.append("planning_files_exist must be true")
    if evidence.get("planning_commit_pushed") is not True:
        errors.append("planning_commit_pushed must be true")
    if not str(evidence.get("progress_comment_url", "")).strip():
        errors.append("progress_comment_url is required")
    if state.get("state") == "ready-for-implementation" and evidence.get("spec_check_passed") is not True:
        errors.append("ready-for-implementation requires spec_check_passed true")
    return errors


def implement_check_errors(issue_dir: Path) -> list[str]:
    errors = state_errors(issue_dir)
    state = load_json(issue_dir / "state.json", []) if (issue_dir / "state.json").is_file() else {}
    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    readiness = load_json(issue_dir / "readiness_evidence.json", errors)

    if state.get("state") != "ready-for-review":
        errors.append("implement-check requires state ready-for-review")
    if evidence.get("implement_check_passed") is not True:
        errors.append("implement_check_passed must be true")
    if evidence.get("self_review_recorded") is not True:
        errors.append("self_review_recorded must be true")

    if readiness:
        for key in ("issue", "branch", "base_branch", "commit_range", "review_request", "validation", "local_self_review", "planning_links", "progress_comment_url", "risks"):
            if key not in readiness:
                errors.append(f"readiness_evidence.json missing {key}")
    return errors


def pr_publish_errors(issue_dir: Path) -> list[str]:
    errors = state_errors(issue_dir)
    state = load_json(issue_dir / "state.json", []) if (issue_dir / "state.json").is_file() else {}
    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    if state.get("state") != "reviewing":
        errors.append("pr-publish requires state reviewing")
    if not str(evidence.get("review_request_url", "")).strip():
        errors.append("review_request_url is required")
    return errors


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "state":
        errors = state_errors(args.issue_dir)
    elif args.command == "spec-check":
        errors = spec_check_errors(args.issue_dir)
    elif args.command == "implement-check":
        errors = implement_check_errors(args.issue_dir)
    else:
        errors = pr_publish_errors(args.issue_dir)
    return {
        "check": args.command,
        "ok": not errors,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GCW state and evidence for the current workflow contract.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("state", "spec-check", "implement-check", "pr-publish"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--issue-dir", required=True, type=Path)
        subparser.set_defaults(handler=run_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.handler(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
