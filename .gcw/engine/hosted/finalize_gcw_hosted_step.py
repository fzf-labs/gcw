#!/usr/bin/env python3
"""Finalize hosted GCW steps: commit/push artifacts and upsert review requests."""

# 中文说明：负责 hosted GCW 步骤的收尾动作，包括提交事件产物、推送分支和创建/更新 PR。
# 流程：workflow 在 step runner 或 agent 产出文件后调用本脚本；脚本按子命令执行
# `commit-push`、`commit-push-all` 或 `upsert-pr`，并把结果写回 GitHub Actions output。

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from _bootstrap import add_repo_root

add_repo_root()

from github import upsert_pr as upsert_github_pr


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def configure_git() -> None:
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run(["git", "config", "user.name", "github-actions[bot]"])


def has_changes(paths: list[str] | None = None) -> bool:
    if paths:
        result = run(["git", "status", "--porcelain", "--untracked-files=all", "--", *paths], check=True)
    else:
        result = run(["git", "status", "--porcelain", "--untracked-files=all"], check=True)
    return bool(result.stdout.strip())


def commit_push(paths: list[str], message: str, branch: str) -> str:
    configure_git()
    if not has_changes(paths):
        result = run(["git", "rev-parse", "HEAD"], check=True)
        return result.stdout.strip()

    run(["git", "add", "--", *paths])
    run(["git", "commit", "-m", message])
    run(["git", "push", "origin", f"HEAD:{branch}"])
    result = run(["git", "rev-parse", "HEAD"], check=True)
    return result.stdout.strip()


def commit_push_all(message: str, branch: str, exclude_prefixes: list[str]) -> str:
    configure_git()
    if not has_changes():
        result = run(["git", "rev-parse", "HEAD"], check=True)
        return result.stdout.strip()

    run(["git", "add", "-A"])
    for prefix in exclude_prefixes:
        run(["git", "reset", "--", prefix], check=False)
    if has_changes():
        run(["git", "commit", "-m", message])
    run(["git", "push", "origin", f"HEAD:{branch}"])
    result = run(["git", "rev-parse", "HEAD"], check=True)
    return result.stdout.strip()


def upsert_pr(repo: str, branch: str, title: str, body_file: Path, base: str) -> str:
    return upsert_github_pr(repo, branch, title, body_file, base)


def write_github_output(path: str | None, result: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in result.items():
            handle.write(f"{key}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finalize hosted GCW workflow artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    commit = subparsers.add_parser("commit-push")
    commit.add_argument("--paths", nargs="+", required=True)
    commit.add_argument("--message", required=True)
    commit.add_argument("--branch", required=True)
    commit.add_argument("--github-output", default="")

    commit_all = subparsers.add_parser("commit-push-all")
    commit_all.add_argument("--message", required=True)
    commit_all.add_argument("--branch", required=True)
    commit_all.add_argument("--exclude", nargs="*", default=[".gcw-runtime"])
    commit_all.add_argument("--github-output", default="")

    pr = subparsers.add_parser("upsert-pr")
    pr.add_argument("--repo", required=True)
    pr.add_argument("--branch", required=True)
    pr.add_argument("--base", default="master")
    pr.add_argument("--title", required=True)
    pr.add_argument("--body-file", required=True, type=Path)
    pr.add_argument("--github-output", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    github_output = args.github_output or os.environ.get("GITHUB_OUTPUT", "")

    try:
        if args.command == "commit-push":
            commit_sha = commit_push(args.paths, args.message, args.branch)
            result = {"commit_sha": commit_sha}
            write_github_output(github_output, result)
            print(json.dumps(result, indent=2))
            return 0

        if args.command == "commit-push-all":
            commit_sha = commit_push_all(args.message, args.branch, list(args.exclude))
            result = {"commit_sha": commit_sha}
            write_github_output(github_output, result)
            print(json.dumps(result, indent=2))
            return 0

        if args.command == "upsert-pr":
            review_request_url = upsert_pr(args.repo, args.branch, args.title, args.body_file, args.base)
            if not review_request_url:
                raise RuntimeError("failed to resolve review request URL after upsert")
            result = {"review_request_url": review_request_url}
            write_github_output(github_output, result)
            print(json.dumps(result, indent=2))
            return 0
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(message, file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
