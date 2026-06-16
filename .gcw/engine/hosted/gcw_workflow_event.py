#!/usr/bin/env python3
"""Resolve GCW workflow inputs from workflow_dispatch and issue events."""

# 中文说明：把 GitHub Actions 触发事件解析成 GCW workflow 可以消费的标准输入。
# 流程：处理 `workflow_dispatch`、Issue 事件和 PR 事件，解析 issue 编号、分支、
# dry-run 与触发原因，再结合 executor label gate 决定后续 hosted job 是否继续运行。

from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from gcw_executor_gate import executor_gate_reason, fetch_issue_labels_github
from gcw_hosted_policy import comment_requests_step, should_run_event as hosted_should_run_event


def load_event(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def label_names(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels") or []
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict):
            name = str(label.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def should_run_event(step: str, event: dict[str, Any], agent_login: str) -> tuple[bool, str]:
    issue = event.get("issue") if isinstance(event.get("issue"), dict) else {}
    labels = label_names(issue)
    allowed, gate_reason = executor_gate_reason(labels)
    if not allowed:
        return False, gate_reason
    return hosted_should_run_event(step, event, agent_login)


def apply_executor_gate(
    result: dict[str, Any],
    *,
    labels: list[str] | None,
    repo: str,
    issue_number: str,
) -> dict[str, Any]:
    if not result.get("should_trigger"):
        return result
    resolved_labels = list(labels or [])
    if not resolved_labels and repo.strip() and issue_number.strip():
        resolved_labels = fetch_issue_labels_github(repo, issue_number)
    allowed, gate_reason = executor_gate_reason(resolved_labels)
    if allowed:
        return result
    updated = dict(result)
    updated["should_trigger"] = False
    updated["trigger_reason"] = gate_reason
    return updated


def resolve(
    *,
    step: str,
    event_name: str,
    event_path: str,
    dispatch_issue_number: str,
    dispatch_issue_branch: str,
    dispatch_dry_run: str,
    agent_login: str,
    repo: str,
) -> dict[str, Any]:
    if event_name == "workflow_dispatch":
        issue_number = dispatch_issue_number.strip()
        result = {
            "should_trigger": bool(issue_number),
            "trigger_reason": "workflow_dispatch" if issue_number else "workflow_dispatch missing issue_number",
            "issue_number": issue_number,
            "issue_branch": dispatch_issue_branch.strip(),
            "dry_run": dispatch_dry_run.strip().lower() in {"1", "true", "yes"},
        }
        return apply_executor_gate(result, labels=None, repo=repo, issue_number=issue_number)

    event = load_event(event_path)
    if event_name == "pull_request":
        pull_request = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
        head_ref = str((pull_request.get("head") or {}).get("ref", "")).strip()
        issue_number = ""
        if head_ref.startswith("gcw/issue-"):
            issue_number = head_ref.removeprefix("gcw/issue-")
        result = {
            "should_trigger": bool(issue_number),
            "trigger_reason": "pull_request synchronize on gcw/issue branch",
            "issue_number": issue_number,
            "issue_branch": head_ref,
            "dry_run": False,
        }
        return apply_executor_gate(result, labels=None, repo=repo, issue_number=issue_number)

    payload = {
        "event_name": event_name,
        "action": event.get("action", ""),
        "issue": event.get("issue", {}),
        "label": event.get("label", {}),
        "assignee": event.get("assignee", {}),
        "comment": event.get("comment", {}),
        "pull_request": event.get("issue", {}).get("pull_request"),
    }
    ok, reason = should_run_event(step, {**payload, "event_name": event_name}, agent_login)
    issue = payload["issue"] if isinstance(payload["issue"], dict) else {}
    number = str(issue.get("number", "")).strip()
    result = {
        "should_trigger": ok,
        "trigger_reason": reason,
        "issue_number": number,
        "issue_branch": "",
        "dry_run": False,
    }
    return apply_executor_gate(result, labels=label_names(issue), repo=repo, issue_number=number)


def write_github_output(path: str | None, result: dict[str, Any]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"should_trigger={'true' if result.get('should_trigger') else 'false'}\n")
        handle.write(f"trigger_reason={result.get('trigger_reason', '')}\n")
        handle.write(f"issue_number={result.get('issue_number', '')}\n")
        handle.write(f"issue_branch={result.get('issue_branch', '')}\n")
        handle.write(f"dry_run={'true' if result.get('dry_run') else 'false'}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve GCW hosted workflow event inputs.")
    parser.add_argument("--step", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", default="")
    parser.add_argument("--agent-login", default="")
    parser.add_argument("--dispatch-issue-number", default="")
    parser.add_argument("--dispatch-issue-branch", default="")
    parser.add_argument("--dispatch-dry-run", default="false")
    parser.add_argument("--repo", default="")
    parser.add_argument("--github-output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    event_path = args.event_path or os.environ.get("GITHUB_EVENT_PATH", "")
    if args.event_name != "workflow_dispatch" and not event_path:
        print("GITHUB_EVENT_PATH is required for issue events", file=sys.stderr)
        return 1

    agent_login = args.agent_login or os.environ.get("AGENT_LOGIN", "")
    repo = args.repo.strip() or os.environ.get("GITHUB_REPOSITORY", "").strip()
    result = resolve(
        step=args.step,
        event_name=args.event_name,
        event_path=event_path,
        dispatch_issue_number=args.dispatch_issue_number,
        dispatch_issue_branch=args.dispatch_issue_branch,
        dispatch_dry_run=args.dispatch_dry_run,
        agent_login=agent_login,
        repo=repo,
    )
    write_github_output(args.github_output or os.environ.get("GITHUB_OUTPUT"), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("issue_number") or not result.get("should_trigger") else 1


if __name__ == "__main__":
    sys.exit(main())
