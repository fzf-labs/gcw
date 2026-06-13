#!/usr/bin/env python3
"""Sync and apply GCW triage labels on GitHub or GitLab."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

LABELS_FILE = Path(__file__).resolve().parents[1] / "labels.json"
GROUPS_WITH_SINGLE_VALUE = {"type", "area", "priority", "readiness", "triage"}


def load_labels() -> dict[str, dict[str, Any]]:
    data = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    if not isinstance(labels, dict) or not labels:
        raise SystemExit(f"{LABELS_FILE} must define a non-empty labels object")
    return labels


def labels_by_group(labels: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for name, meta in labels.items():
        group = str(meta.get("group", ""))
        grouped.setdefault(group, []).append(name)
    return grouped


def gitlab_color(color: str) -> str:
    color = color.strip().lstrip("#")
    return f"#{color}"


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def sync_github(repo: str, labels: dict[str, dict[str, Any]]) -> None:
    for name, meta in labels.items():
        create = run(
            [
                "gh",
                "label",
                "create",
                name,
                "--color",
                meta["color"],
                "--description",
                meta["description"],
                "--repo",
                repo,
            ],
            check=False,
        )
        if create.returncode != 0:
            run(
                [
                    "gh",
                    "label",
                    "edit",
                    name,
                    "--color",
                    meta["color"],
                    "--description",
                    meta["description"],
                    "--repo",
                    repo,
                ]
            )
        print(f"synced: {name}")


def gitlab_label_index(repo: str) -> dict[str, str]:
    result = run(["glab", "label", "list", "--repo", repo, "--output", "json"])
    items = json.loads(result.stdout or "[]")
    index: dict[str, str] = {}
    for item in items:
        if isinstance(item, dict) and item.get("name") and item.get("id") is not None:
            index[str(item["name"])] = str(item["id"])
    return index


def sync_gitlab(repo: str, labels: dict[str, dict[str, Any]]) -> None:
    existing = gitlab_label_index(repo)
    for name, meta in labels.items():
        color = gitlab_color(str(meta["color"]))
        description = str(meta["description"])
        if name in existing:
            run(
                [
                    "glab",
                    "label",
                    "edit",
                    "--label-id",
                    existing[name],
                    "--color",
                    color,
                    "--description",
                    description,
                    "--repo",
                    repo,
                ]
            )
        else:
            run(
                [
                    "glab",
                    "label",
                    "create",
                    "--name",
                    name,
                    "--color",
                    color,
                    "--description",
                    description,
                    "--repo",
                    repo,
                ]
            )
        print(f"synced: {name}")


def issue_labels_github(repo: str, issue: str) -> list[str]:
    result = run(
        [
            "gh",
            "issue",
            "view",
            issue,
            "--repo",
            repo,
            "--json",
            "labels",
            "--jq",
            ".labels[].name",
        ]
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def issue_labels_gitlab(repo: str, issue: str) -> list[str]:
    result = run(
        [
            "glab",
            "issue",
            "view",
            issue,
            "--repo",
            repo,
            "--output",
            "json",
        ]
    )
    data = json.loads(result.stdout or "{}")
    labels = data.get("labels", [])
    names: list[str] = []
    if isinstance(labels, list):
        for item in labels:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict) and item.get("title"):
                names.append(str(item["title"]))
    return names


def apply_github(repo: str, issue: str, add: list[str], remove: list[str]) -> None:
    cmd = ["gh", "issue", "edit", issue, "--repo", repo]
    if add:
        cmd.extend(["--add-label", ",".join(add)])
    if remove:
        cmd.extend(["--remove-label", ",".join(remove)])
    if len(cmd) > 6:
        run(cmd)


def apply_gitlab(repo: str, issue: str, add: list[str], remove: list[str]) -> None:
    cmd = ["glab", "issue", "update", issue, "--repo", repo]
    if add:
        cmd.extend(["--label", ",".join(add)])
    if remove:
        cmd.extend(["--unlabel", ",".join(remove)])
    if len(cmd) > 6:
        run(cmd)


def resolve_replacements(
    labels: dict[str, dict[str, Any]],
    current: list[str],
    desired: list[str],
) -> tuple[list[str], list[str]]:
    grouped = labels_by_group(labels)
    desired_set = set(desired)
    remove: list[str] = []
    for group in GROUPS_WITH_SINGLE_VALUE:
        desired_in_group = [name for name in desired_set if name in grouped.get(group, [])]
        if not desired_in_group:
            continue
        keep = desired_in_group[0]
        for name in current:
            if name in grouped.get(group, []) and name != keep:
                remove.append(name)
    add = [name for name in desired if name not in current]
    remove = [name for name in remove if name not in desired_set]
    return add, remove


def cmd_sync(args: argparse.Namespace) -> int:
    labels = load_labels()
    if args.platform == "github":
        sync_github(args.repo, labels)
    else:
        sync_gitlab(args.repo, labels)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    labels = load_labels()
    desired = [part.strip() for part in args.add.split(",") if part.strip()]
    unknown = [name for name in desired if name not in labels]
    if unknown:
        raise SystemExit(f"unknown labels: {', '.join(unknown)}")

    if args.platform == "github":
        current = issue_labels_github(args.repo, args.issue)
        add, remove = resolve_replacements(labels, current, desired)
        apply_github(args.repo, args.issue, add, remove)
    else:
        current = issue_labels_gitlab(args.repo, args.issue)
        add, remove = resolve_replacements(labels, current, desired)
        apply_gitlab(args.repo, args.issue, add, remove)

    print(json.dumps({"added": add, "removed": remove, "current_before": current}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync and apply GCW triage labels.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in (("sync", cmd_sync), ("apply", cmd_apply)):
        sub = subparsers.add_parser(name)
        sub.add_argument("--platform", required=True, choices=("github", "gitlab"))
        sub.add_argument("--repo", required=True, help="OWNER/REPO (GitHub) or GROUP/PROJECT (GitLab)")
        sub.set_defaults(handler=handler)

    apply = subparsers.choices["apply"]
    apply.add_argument("--issue", required=True)
    apply.add_argument(
        "--add",
        required=True,
        help="Comma-separated labels to apply; conflicting labels in the same group are replaced",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
