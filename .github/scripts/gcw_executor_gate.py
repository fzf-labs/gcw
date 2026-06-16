#!/usr/bin/env python3
"""GCW hosted executor label gate."""

from __future__ import annotations

import subprocess

from gcw_hosted_policy import step_rank

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
    repo = repo.strip()
    issue_number = issue_number.strip()
    if not repo or not issue_number:
        return []
    result = subprocess.run(
        [
            "gh",
            "issue",
            "view",
            issue_number,
            "--repo",
            repo,
            "--json",
            "labels",
            "--jq",
            ".labels[].name",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
