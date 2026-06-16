#!/usr/bin/env python3
"""Prepare stable handoff files for hosted GCW codex steps."""

# 中文说明：为 hosted agent 准备稳定的 issue 上下文与 handoff 约束文件。
# 流程：从 GitHub 拉取 issue、评论和当前 workflow projection，写出
# `.gcw-runtime/handoff/issue_context.json` 与评论快照，供 Codex action 按指定 skill 执行。

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_STEP_CONFIG: dict[str, dict[str, Any]] = {
    "gcw-issue-triage": {
        "skill_paths": [".agents/skills/gcw-issue-triage/SKILL.md"],
        "allowed_write_globs": [".gcw-runtime/handoff/triage_result.json"],
        "handoff_outputs": ["triage_result.json"],
    },
    "gcw-issue-clarify": {
        "skill_paths": [
            ".agents/skills/gcw-issue-clarify/SKILL.md",
        ],
        "allowed_write_globs": [".gcw-runtime/handoff/clarify_result.json"],
        "handoff_outputs": ["clarify_result.json"],
    },
    "gcw-issue-to-spec": {
        "skill_paths": [
            ".agents/skills/planning-with-files/SKILL.md",
            ".agents/skills/gcw-issue-to-spec/SKILL.md",
        ],
        "allowed_write_globs": [
            ".gcw/issues/*/task_plan.md",
            ".gcw/issues/*/findings.md",
            ".gcw/issues/*/progress.md",
        ],
        "handoff_outputs": [],
    },
    "gcw-implement": {
        "skill_paths": [".agents/skills/gcw-implement/SKILL.md"],
        "allowed_write_globs": ["**/*"],
        "handoff_outputs": ["implement_summary.json"],
    },
    "gcw-implement-check": {
        "skill_paths": [".agents/skills/gcw-implement-check/SKILL.md"],
        "allowed_write_globs": [".gcw/issues/*/implement-check-payload.json"],
        "handoff_outputs": [],
    },
    "gcw-pr-review": {
        "skill_paths": [".agents/skills/gcw-pr-review/SKILL.md"],
        "allowed_write_globs": [".gcw-runtime/handoff/pr_review_summary.json"],
        "handoff_outputs": ["pr_review_summary.json"],
    },
}


def issue_branch(issue_number: str, issue_branch_input: str) -> str:
    branch = issue_branch_input.strip()
    if branch:
        return branch
    return f"gcw/issue-{issue_number.strip()}"


def gh_json(args: list[str]) -> Any:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def fetch_issue(repo: str, issue_number: str) -> dict[str, Any]:
    return gh_json(["gh", "api", f"repos/{repo}/issues/{issue_number}"])


def fetch_comments(repo: str, issue_number: str) -> list[dict[str, Any]]:
    data = gh_json(["gh", "api", f"repos/{repo}/issues/{issue_number}/comments", "--paginate", "--slurp"])
    if not isinstance(data, list):
        return []
    if data and all(isinstance(page, list) for page in data):
        return [item for page in data for item in page if isinstance(item, dict)]
    return [item for item in data if isinstance(item, dict)]


def load_projection(issue_dir: Path) -> dict[str, Any]:
    workflow_path = issue_dir / "workflow.json"
    if not workflow_path.is_file():
        return {}
    data = json.loads(workflow_path.read_text(encoding="utf-8"))
    projection = data.get("projection")
    return projection if isinstance(projection, dict) else {}


def format_comments(comments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in comments:
        user = item.get("user") or {}
        login = user.get("login", "unknown")
        created = item.get("created_at", "")
        body = str(item.get("body", "")).strip()
        lines.append(f"--- comment by {login} at {created} ---")
        lines.append(body)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def prepare(
    *,
    repo: str,
    issue_number: str,
    step: str,
    issue_dir: Path,
    issue_branch_input: str,
    output_dir: Path,
) -> dict[str, Any]:
    config = _STEP_CONFIG.get(step)
    if config is None:
        raise ValueError(f"unsupported handoff step: {step}")

    branch = issue_branch(issue_number, issue_branch_input)
    output_dir.mkdir(parents=True, exist_ok=True)

    issue = fetch_issue(repo, issue_number)
    comments = fetch_comments(repo, issue_number)
    projection = load_projection(issue_dir)

    context = {
        "repo": repo,
        "issue_number": int(issue_number),
        "step": step,
        "target_branch": branch,
        "issue_title": issue.get("title", ""),
        "issue_body": issue.get("body", ""),
        "issue_labels": [label.get("name", "") for label in issue.get("labels", []) if isinstance(label, dict)],
        "issue_assignees": [
            (assignee.get("login") or "") for assignee in issue.get("assignees", []) if isinstance(assignee, dict)
        ],
        "issue_url": issue.get("html_url", ""),
        "phase": projection.get("phase", ""),
        "issue_dir": str(issue_dir),
        "skill_paths": config["skill_paths"],
        "allowed_write_globs": config["allowed_write_globs"],
        "handoff_outputs": config["handoff_outputs"],
        "coauthor_directives": [],
    }

    context_path = output_dir / "issue_context.json"
    comments_path = output_dir / "issue_comments.txt"
    context_path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    comments_path.write_text(format_comments(comments), encoding="utf-8")

    return {
        "ok": True,
        "issue_context": str(context_path),
        "issue_comments": str(comments_path),
        "target_branch": branch,
        "phase": context["phase"],
    }


def write_github_output(path: str | None, result: dict[str, Any]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in result.items():
            if key == "ok":
                continue
            handle.write(f"{key}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare hosted GCW codex handoff context.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument("--issue-branch", default="")
    parser.add_argument("--output-dir", default=".gcw-runtime/handoff", type=Path)
    parser.add_argument("--github-output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare(
            repo=args.repo,
            issue_number=args.issue,
            step=args.step,
            issue_dir=args.issue_dir,
            issue_branch_input=args.issue_branch,
            output_dir=args.output_dir,
        )
    except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": str(exc)}
        print(json.dumps(result, indent=2), file=sys.stderr)
        write_github_output(args.github_output or os.environ.get("GITHUB_OUTPUT"), result)
        return 1

    write_github_output(args.github_output or os.environ.get("GITHUB_OUTPUT"), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
