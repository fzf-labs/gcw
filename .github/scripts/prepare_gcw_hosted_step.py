#!/usr/bin/env python3
"""Gate hosted GCW workflows by workflow projection phase."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from gcw_executor_gate import (
    EXECUTOR_HOSTED,
    executor_gate_reason,
    fetch_issue_labels_github,
    hosted_executor_allowed,
    step_rank,
)

_STEP_PHASES: dict[str, tuple[str, ...]] = {
    "gcw-issue-triage": ("issue-opened",),
    "gcw-issue-clarify": ("issue-triaged", "issue-clarifying"),
    "gcw-issue-to-spec": ("ready-for-planning",),
    "gcw-spec-check": ("planned",),
    "gcw-implement": ("ready-for-implementation", "changes-requested", "implementing"),
    "gcw-implement-check": ("implementing",),
    "gcw-pr-publish": ("ready-for-review",),
    "gcw-pr-review": ("reviewing",),
}

_VALIDATE_COMMAND: dict[str, str] = {
    "gcw-spec-check": "spec-check",
    "gcw-implement-check": "implement-check",
    "gcw-pr-review": "review-check",
}


def issue_branch(issue_number: str, issue_branch_input: str) -> str:
    branch = issue_branch_input.strip()
    if branch:
        return branch
    return f"gcw/issue-{issue_number.strip()}"


def load_projection(issue_dir: Path) -> dict:
    workflow_path = issue_dir / "workflow.json"
    if not workflow_path.is_file():
        raise ValueError(f"missing workflow projection: {workflow_path}")
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    projection = data.get("projection") if isinstance(data.get("projection"), dict) else {}
    if not projection:
        raise ValueError("workflow.json projection is missing")
    return projection


def _find_latest_event(issue_dir: Path, event_name: str) -> dict | None:
    events_dir = issue_dir / "events"
    if not events_dir.is_dir():
        return None
    latest: dict | None = None
    latest_seq = -1
    for path in sorted(events_dir.glob("*.json")):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if event.get("event") != event_name:
            continue
        seq = event.get("seq")
        if isinstance(seq, int) and seq > latest_seq:
            latest = event
            latest_seq = seq
    return latest


_REPEATABLE_WHILE_PHASE: dict[str, tuple[str, ...]] = {
    "gcw-implement": ("implementing", "changes-requested", "ready-for-implementation"),
    "gcw-issue-clarify": ("issue-clarifying",),
}


def _idempotent_decision(step: str, projection: dict, issue_dir: Path) -> dict[str, str | bool]:
    last = str(projection.get("last_completed_step", "")).strip()
    phase = str(projection.get("phase", "")).strip()
    current_rank = step_rank(step)
    last_rank = step_rank(last) if last else None

    if step == "gcw-pr-review":
        pr_review = _find_latest_event(issue_dir, "gcw-pr-review")
        result = ""
        if pr_review:
            result = str(pr_review.get("payload", {}).get("result", "")).strip().lower()
        if result == "passed":
            return {
                "should_run": True,
                "skip_reason": "",
                "run_mode": "verify-only",
                "record_step": False,
                "validate_command": "review-check",
            }

    if last == step:
        repeatable_phases = _REPEATABLE_WHILE_PHASE.get(step, ())
        if phase not in repeatable_phases:
            return {
                "should_run": False,
                "skip_reason": f"{step} already completed",
                "run_mode": "skip",
                "record_step": False,
                "validate_command": _VALIDATE_COMMAND.get(step, ""),
            }

    if current_rank is not None and last_rank is not None and last_rank > current_rank:
        return {
            "should_run": False,
            "skip_reason": f"superseded by {last}",
            "run_mode": "skip",
            "record_step": False,
            "validate_command": _VALIDATE_COMMAND.get(step, ""),
        }

    validate_command = _VALIDATE_COMMAND.get(step, "")
    if step == "gcw-pr-review":
        validate_command = "pr-publish"
    return {
        "should_run": True,
        "skip_reason": "",
        "run_mode": "full",
        "record_step": True,
        "validate_command": validate_command,
    }


def prepare(
    step: str,
    issue_dir: Path,
    issue_number: str,
    issue_branch_input: str,
    *,
    issue_labels: list[str] | None = None,
    repo: str = "",
) -> dict:
    expected = _STEP_PHASES.get(step)
    if expected is None:
        raise ValueError(f"unsupported hosted step: {step}")

    branch = issue_branch(issue_number, issue_branch_input)
    base = {
        "issue_branch": branch,
        "validate_command": _VALIDATE_COMMAND.get(step, ""),
        "run_mode": "full",
        "record_step": True,
    }

    labels = list(issue_labels or [])
    if not labels and repo.strip() and issue_number.strip():
        labels = fetch_issue_labels_github(repo, issue_number)
    allowed, gate_reason = executor_gate_reason(labels)
    if not allowed:
        return {
            **base,
            "ok": True,
            "should_run": False,
            "skip_reason": gate_reason,
            "executor_gate": EXECUTOR_HOSTED if hosted_executor_allowed(labels) else "",
        }

    if not issue_dir.is_dir():
        return {
            **base,
            "ok": False,
            "should_run": False,
            "skip_reason": f"issue directory not found: {issue_dir}",
        }

    projection = load_projection(issue_dir)
    idempotent = _idempotent_decision(step, projection, issue_dir)
    if not idempotent["should_run"] and idempotent.get("skip_reason"):
        return {
            **base,
            "ok": True,
            "should_run": False,
            "skip_reason": str(idempotent["skip_reason"]),
            "phase": str(projection.get("phase", "")).strip(),
            "run_mode": str(idempotent["run_mode"]),
            "record_step": bool(idempotent["record_step"]),
            "validate_command": str(idempotent["validate_command"]),
            "executor_gate": EXECUTOR_HOSTED,
        }

    phase = str(projection.get("phase", "")).strip()
    if phase not in expected:
        allowed_phases = ", ".join(expected)
        return {
            **base,
            "ok": True,
            "should_run": False,
            "skip_reason": f"phase {phase!r} is not in [{allowed_phases}] for {step}",
            "phase": phase,
            "run_mode": str(idempotent["run_mode"]),
            "record_step": bool(idempotent["record_step"]),
            "validate_command": str(idempotent["validate_command"]),
            "executor_gate": EXECUTOR_HOSTED,
        }

    return {
        **base,
        "ok": True,
        "should_run": bool(idempotent["should_run"]),
        "skip_reason": str(idempotent["skip_reason"]),
        "phase": phase,
        "run_mode": str(idempotent["run_mode"]),
        "record_step": bool(idempotent["record_step"]),
        "validate_command": str(idempotent["validate_command"]),
        "executor_gate": EXECUTOR_HOSTED,
    }


def write_github_output(path: str | None, result: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"should_run={'true' if result.get('should_run') else 'false'}\n")
        handle.write(f"skip_reason={result.get('skip_reason', '')}\n")
        handle.write(f"issue_branch={result.get('issue_branch', '')}\n")
        handle.write(f"phase={result.get('phase', '')}\n")
        handle.write(f"validate_command={result.get('validate_command', '')}\n")
        handle.write(f"run_mode={result.get('run_mode', '')}\n")
        handle.write(f"record_step={'true' if result.get('record_step') else 'false'}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare hosted GCW workflow step context.")
    parser.add_argument("--step", required=True)
    parser.add_argument("--issue-number", required=True)
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument("--issue-branch", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--github-output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.strip() or os.environ.get("GITHUB_REPOSITORY", "").strip()
    try:
        result = prepare(
            args.step,
            args.issue_dir,
            args.issue_number,
            args.issue_branch,
            repo=repo,
        )
    except ValueError as exc:
        result = {"ok": False, "should_run": False, "skip_reason": str(exc), "issue_branch": ""}
    write_github_output(args.github_output or os.environ.get("GITHUB_OUTPUT"), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
