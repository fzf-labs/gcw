from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gcw_workflow_lib import (
    PLANNING_FILES,
    WorkflowError,
    assert_projection_current,
    find_latest_event,
    load_events,
)


def require_non_empty(data: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> None:
    value = data.get(key)
    if value is None or str(value).strip() == "":
        errors.append(f"{prefix}{key} is required")


def workflow_errors(issue_dir: Path) -> list[str]:
    current = assert_projection_current(issue_dir)
    if not current["ok"]:
        return list(current["errors"])
    try:
        load_events(issue_dir)
    except WorkflowError as exc:
        return [str(exc)]
    return []


def spec_check_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]

    missing = [name for name in PLANNING_FILES if not (issue_dir / name).is_file()]
    if missing:
        errors.append(f"missing planning files: {', '.join(missing)}")
    if projection.get("phase") != "ready-for-implementation":
        errors.append("spec-check requires phase ready-for-implementation")
    latest = find_latest_event(issue_dir, "gcw-spec-check")
    payload = latest.get("payload", {}) if latest else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    if gate.get("ok") is not True:
        errors.append("latest gcw-spec-check gate.ok must be true")
    return errors


def implement_check_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]

    if projection.get("phase") != "ready-for-review":
        errors.append("implement-check requires phase ready-for-review")
    latest = find_latest_event(issue_dir, "gcw-implement-check")
    payload = latest.get("payload", {}) if latest else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    if gate.get("ok") is not True:
        errors.append("latest gcw-implement-check gate.ok must be true")

    for key in ("review_request", "risks", "scope", "reviewer_notes", "self_review", "spec_refs"):
        if key not in payload:
            errors.append(f"gcw-implement-check payload missing {key}")
    review_request = payload.get("review_request") if isinstance(payload.get("review_request"), dict) else {}
    for key in ("title", "summary", "issue_link"):
        require_non_empty(review_request, key, errors, "review_request.")
    return errors


def pr_publish_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]
    if projection.get("phase") != "reviewing":
        errors.append("pr-publish requires phase reviewing")
    latest = find_latest_event(issue_dir, "gcw-pr-publish")
    payload = latest.get("payload", {}) if latest else {}
    if not str(payload.get("review_request_url", "")).strip():
        errors.append("review_request_url is required")
    effects = payload.get("effects") if isinstance(payload.get("effects"), list) else []
    if not any(isinstance(effect, dict) and effect.get("status") == "applied" for effect in effects):
        errors.append("gcw-pr-publish requires an applied effect")
    return errors


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "workflow":
        errors = workflow_errors(args.issue_dir)
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
    parser = argparse.ArgumentParser(description="Validate GCW event logs and projections.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("workflow", "spec-check", "implement-check", "pr-publish"):
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
