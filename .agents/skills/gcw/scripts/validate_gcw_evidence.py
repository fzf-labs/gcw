from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from gcw_workflow_lib import (
    PLANNING_FILES,
    WorkflowError,
    assert_projection_current,
    find_latest_event,
    validate_event_log,
)

VERIFY_REMOTE_TRIAGE = (
    Path(__file__).resolve().parents[2] / "gcw-issue-prepare" / "scripts" / "verify_remote_triage.py"
)


def require_non_empty(data: dict[str, Any], key: str, errors: list[str], prefix: str = "") -> None:
    value = data.get(key)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        errors.append(f"{prefix}{key} is required")
    elif isinstance(value, (list, dict)) and not value:
        errors.append(f"{prefix}{key} must not be empty")


def _verify_spec_refs_hashes(issue_dir: Path, spec_refs: dict[str, Any], errors: list[str]) -> None:
    sha_map = {
        "task_plan_sha": "task_plan.md",
        "findings_sha": "findings.md",
        "progress_sha": "progress.md",
    }
    for sha_key, filename in sha_map.items():
        expected_sha = spec_refs.get(sha_key)
        if not expected_sha or not str(expected_sha).startswith("sha256:"):
            continue
        file_path = issue_dir / filename
        if file_path.is_file():
            actual = f"sha256:{hashlib.sha256(file_path.read_bytes()).hexdigest()}"
            if actual != expected_sha:
                errors.append(f"{sha_key} does not match actual {filename} content")


def workflow_errors(issue_dir: Path) -> list[str]:
    errors = validate_event_log(issue_dir)
    current = assert_projection_current(issue_dir)
    if not current["ok"]:
        errors.extend(current["errors"])
    return errors


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
    to_spec = find_latest_event(issue_dir, "gcw-issue-to-spec")
    if to_spec:
        spec_refs = to_spec.get("payload", {}).get("spec_refs")
        if isinstance(spec_refs, dict):
            _verify_spec_refs_hashes(issue_dir, spec_refs, errors)
    return errors


def prepare_check_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]
    if projection.get("phase") not in (
        "ready-for-planning",
        "planned",
        "ready-for-implementation",
        "implementing",
        "ready-for-review",
        "reviewing",
        "changes-requested",
        "blocked",
        "review-complete",
        "issue-clarifying",
    ):
        errors.append("prepare-check requires a post-prepare phase")
    latest = find_latest_event(issue_dir, "gcw-issue-prepare")
    if latest is None:
        errors.append("no gcw-issue-prepare event found")
        return errors
    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    if payload.get("ready") is True and not payload.get("remote_sync"):
        errors.append("gcw-issue-prepare remote_sync is required when ready is true")
    if VERIFY_REMOTE_TRIAGE.is_file():
        result = subprocess.run(
            [sys.executable, str(VERIFY_REMOTE_TRIAGE), "--issue-dir", str(issue_dir)],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            try:
                output = json.loads(result.stdout or "{}")
            except json.JSONDecodeError:
                output = {"errors": [result.stderr or result.stdout or "verify_remote_triage failed"]}
            errors.extend(output.get("errors", []))
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
    self_review = payload.get("self_review") if isinstance(payload.get("self_review"), dict) else {}
    if self_review.get("recorded") is not True:
        errors.append("gcw-implement-check payload.self_review.recorded must be true")
    spec_refs = payload.get("spec_refs") if isinstance(payload.get("spec_refs"), dict) else {}
    for sha_key in ("task_plan_sha", "findings_sha", "progress_sha"):
        if sha_key not in spec_refs:
            errors.append(f"gcw-implement-check payload.spec_refs.{sha_key} is required")
    if spec_refs:
        _verify_spec_refs_hashes(issue_dir, spec_refs, errors)
    gate_checks = gate.get("checks") if isinstance(gate.get("checks"), list) else []
    for i, check in enumerate(gate_checks):
        if not isinstance(check, dict):
            errors.append(f"gate.checks[{i}] must be an object")
        elif "id" not in check or "ok" not in check:
            errors.append(f"gate.checks[{i}] missing id or ok")
    gate_validation = gate.get("validation") if isinstance(gate.get("validation"), list) else []
    for i, val in enumerate(gate_validation):
        if not isinstance(val, dict):
            errors.append(f"gate.validation[{i}] must be an object")
        elif not all(k in val for k in ("command", "exit_code", "result")):
            errors.append(f"gate.validation[{i}] missing command, exit_code, or result")
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
    for i, effect in enumerate(effects):
        if not isinstance(effect, dict):
            errors.append(f"effects[{i}] must be an object")
            continue
        for key in ("kind", "operation_id", "target", "body_hash", "status"):
            if key not in effect:
                errors.append(f"effects[{i}] missing {key}")
        body_hash = str(effect.get("body_hash", ""))
        if body_hash and not body_hash.startswith("sha256:"):
            errors.append(f"effects[{i}].body_hash must start with sha256:")
    body_hash = str(payload.get("body_hash", ""))
    if body_hash and not body_hash.startswith("sha256:"):
        errors.append("payload.body_hash must start with sha256:")
    return errors


def review_check_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]
    if projection.get("phase") not in ("reviewing", "review-complete"):
        errors.append("review-check requires phase reviewing or review-complete")
    latest = find_latest_event(issue_dir, "gcw-pr-review")
    if latest is None:
        errors.append("no gcw-pr-review event found")
    else:
        result = latest.get("payload", {}).get("result")
        if result not in ("passed", "changes-requested", "blocked"):
            errors.append(f"gcw-pr-review result must be passed, changes-requested, or blocked; got {result}")
    return errors


def block_check_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]
    if projection.get("phase") != "blocked":
        errors.append("block-check requires phase blocked")
    else:
        blocker = projection.get("active_blocker") if isinstance(projection.get("active_blocker"), dict) else {}
        if not blocker.get("reason"):
            errors.append("active_blocker.reason is required")
        if not blocker.get("resume_phase"):
            errors.append("active_blocker.resume_phase is required")
        if not blocker.get("resume_step"):
            errors.append("active_blocker.resume_step is required")
    return errors


def clarify_check_errors(issue_dir: Path) -> list[str]:
    errors = workflow_errors(issue_dir)
    if errors:
        return errors
    projection = assert_projection_current(issue_dir)["projection"]
    if projection.get("phase") != "issue-clarifying":
        errors.append("clarify-check requires phase issue-clarifying")
    else:
        feedback = projection.get("active_feedback") if isinstance(projection.get("active_feedback"), dict) else {}
        if not feedback.get("reason"):
            errors.append("active_feedback.reason (question) is required")
    return errors


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    check_map = {
        "workflow": workflow_errors,
        "prepare-check": prepare_check_errors,
        "spec-check": spec_check_errors,
        "implement-check": implement_check_errors,
        "pr-publish": pr_publish_errors,
        "review-check": review_check_errors,
        "block-check": block_check_errors,
        "clarify-check": clarify_check_errors,
    }
    handler = check_map.get(args.command)
    if handler is None:
        return {"check": args.command, "ok": False, "errors": [f"unknown check: {args.command}"]}
    errors = handler(args.issue_dir)
    return {
        "check": args.command,
        "ok": not errors,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GCW event logs and projections.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("workflow", "prepare-check", "spec-check", "implement-check", "pr-publish", "review-check", "block-check", "clarify-check"):
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
