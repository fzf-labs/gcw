#!/usr/bin/env python3
"""GCW hosted executor label gate."""

# 中文说明：判断当前 Issue 是否允许 hosted runner 执行 GCW 步骤。
# 流程：读取或接收 issue labels，要求存在 `gcw:executor-hosted`，并在
# `gcw:executor-local` 或缺少 hosted 标签时返回跳过原因，避免本地/远端执行器抢跑。

from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

from github import fetch_issue_labels

EXECUTOR_HOSTED = "gcw:executor-hosted"
EXECUTOR_LOCAL = "gcw:executor-local"


def hosted_executor_allowed(labels: list[str]) -> bool:
    return EXECUTOR_HOSTED in labels


def executor_gate_reason(labels: list[str]) -> tuple[bool, str]:
    if hosted_executor_allowed(labels):
        return True, EXECUTOR_HOSTED
    if EXECUTOR_LOCAL in labels:
        return False, f"{EXECUTOR_LOCAL} blocks hosted execution"
    return False, f"missing {EXECUTOR_HOSTED} (default: local)"


def fetch_issue_labels_github(repo: str, issue_number: str) -> list[str]:
    return fetch_issue_labels(repo, issue_number)
