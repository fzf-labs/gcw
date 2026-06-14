#!/usr/bin/env python3
"""Gate hosted GCW workflows by workflow projection phase."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

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


def issue_branch(issue_number: str, issue_branch: str) -> str:
    branch = issue_branch.strip()
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


def prepare(step: str, issue_dir: Path, issue_number: str, issue_branch_input: str) -> dict:
    expected = _STEP_PHASES.get(step)
    if expected is None:
        raise ValueError(f"unsupported hosted step: {step}")

    branch = issue_branch(issue_number, issue_branch_input)
    if not issue_dir.is_dir():
        return {
            "ok": False,
            "should_run": False,
            "skip_reason": f"issue directory not found: {issue_dir}",
            "issue_branch": branch,
            "validate_command": _VALIDATE_COMMAND.get(step, ""),
        }

    projection = load_projection(issue_dir)
    phase = str(projection.get("phase", "")).strip()
    if phase not in expected:
        allowed = ", ".join(expected)
        return {
            "ok": True,
            "should_run": False,
            "skip_reason": f"phase {phase!r} is not in [{allowed}] for {step}",
            "issue_branch": branch,
            "phase": phase,
            "validate_command": _VALIDATE_COMMAND.get(step, ""),
        }

    return {
        "ok": True,
        "should_run": True,
        "skip_reason": "",
        "issue_branch": branch,
        "phase": phase,
        "validate_command": _VALIDATE_COMMAND.get(step, ""),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare hosted GCW workflow step context.")
    parser.add_argument("--step", required=True)
    parser.add_argument("--issue-number", required=True)
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument("--issue-branch", default="")
    parser.add_argument("--github-output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare(args.step, args.issue_dir, args.issue_number, args.issue_branch)
    except ValueError as exc:
        result = {"ok": False, "should_run": False, "skip_reason": str(exc), "issue_branch": ""}
    write_github_output(args.github_output or os.environ.get("GITHUB_OUTPUT"), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
