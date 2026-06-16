#!/usr/bin/env python3
"""Gate hosted GCW workflows by workflow projection phase."""

# 中文说明：在 hosted job 真正执行前做 phase gate 和幂等性判断。
# 流程：读取 `.gcw/issues/<id>/workflow.json`，结合 executor 标签和 runtime policy
# 判断当前 step 是否允许运行、是否只需 verify-only，并输出 branch、validate command 等上下文。

from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

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
)
from gcw_hosted_policy import prepare_hosted_step, validate_command_for_step


def issue_branch(issue_number: str, issue_branch_input: str) -> str:
    branch = issue_branch_input.strip()
    if branch:
        return branch
    return f"gcw/issue-{issue_number.strip()}"


def parse_issue_labels(value: str) -> list[str]:
    return [label.strip() for label in value.split(",") if label.strip()]


def load_projection(issue_dir: Path) -> dict:
    workflow_path = issue_dir / "workflow.json"
    if not workflow_path.is_file():
        raise ValueError(f"missing workflow projection: {workflow_path}")
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    projection = data.get("projection") if isinstance(data.get("projection"), dict) else {}
    if not projection:
        raise ValueError("workflow.json projection is missing")
    return projection


def prepare(
    step: str,
    issue_dir: Path,
    issue_number: str,
    issue_branch_input: str,
    *,
    issue_labels: list[str] | None = None,
    repo: str = "",
) -> dict:
    branch = issue_branch(issue_number, issue_branch_input)
    base = {
        "issue_branch": branch,
        "validate_command": validate_command_for_step(step),
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
    idempotent = prepare_hosted_step(step, projection, issue_dir)
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
    parser.add_argument("--issue-labels", default="", help="Comma-separated issue labels supplied by non-GitHub CI.")
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
            issue_labels=parse_issue_labels(args.issue_labels),
            repo=repo,
        )
    except ValueError as exc:
        result = {"ok": False, "should_run": False, "skip_reason": str(exc), "issue_branch": ""}
    write_github_output(args.github_output or os.environ.get("GITHUB_OUTPUT"), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
