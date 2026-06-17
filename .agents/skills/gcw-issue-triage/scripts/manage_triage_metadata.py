#!/usr/bin/env python3
"""Sync and apply GCW triage metadata on GitHub or GitLab."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from triage_lib import (
    GITHUB_API_VERSION,
    apply_github_labels,
    apply_gitlab_labels,
    ensure_executor_label,
    expected_remote_sync,
    github_issue_type,
    github_priority_field_id,
    github_priority_value,
    issue_labels_github,
    issue_labels_gitlab,
    labels_for_platform,
    legacy_github_labels,
    load_labels,
    repo_id,
    resolve_replacements,
    run,
)


def gitlab_color(color: str) -> str:
    color = color.strip().lstrip("#")
    return f"#{color}"


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


def patch_github_issue_type(repo: str, issue: str, issue_type: str) -> None:
    payload = json.dumps({"type": issue_type})
    subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{issue}",
            "-X",
            "PATCH",
            "-H",
            f"X-GitHub-Api-Version: {GITHUB_API_VERSION}",
            "--input",
            "-",
        ],
        input=payload,
        text=True,
        check=True,
        capture_output=True,
    )


def set_github_priority(repo: str, issue: str, priority_value: str) -> None:
    org = repo.split("/")[0]
    field_id = github_priority_field_id(org)
    payload = json.dumps([{"field_id": field_id, "value": priority_value}])
    subprocess.run(
        [
            "gh",
            "api",
            f"/repositories/{repo_id(repo)}/issues/{issue}/issue-field-values",
            "-X",
            "POST",
            "-H",
            f"X-GitHub-Api-Version: {GITHUB_API_VERSION}",
            "--input",
            "-",
        ],
        input=payload,
        text=True,
        check=True,
        capture_output=True,
    )


def cmd_sync(args: argparse.Namespace) -> int:
    labels = labels_for_platform(load_labels(), args.platform)
    if args.platform == "github":
        sync_github(args.repo, labels)
    else:
        sync_gitlab(args.repo, labels)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    labels = labels_for_platform(load_labels(), args.platform)
    desired = [part.strip() for part in args.add.split(",") if part.strip()]
    unknown = [name for name in desired if name not in labels]
    if unknown:
        raise SystemExit(f"unknown labels: {', '.join(unknown)}")

    if args.platform == "github":
        current = issue_labels_github(args.repo, args.issue)
        add, remove = resolve_replacements(labels, current, desired)
        apply_github_labels(args.repo, args.issue, add, remove)
    else:
        current = issue_labels_gitlab(args.repo, args.issue)
        add, remove = resolve_replacements(labels, current, desired)
        apply_gitlab_labels(args.repo, args.issue, add, remove)

    print(json.dumps({"added": add, "removed": remove, "current_before": current}, indent=2))
    return 0


def cmd_apply_metadata(args: argparse.Namespace) -> int:
    all_labels = load_labels()
    labels = labels_for_platform(all_labels, args.platform)
    workflow_labels = [part.strip() for part in args.labels.split(",") if part.strip()]
    workflow_labels = ensure_executor_label(workflow_labels, getattr(args, "executor", "local"))
    unknown = [name for name in workflow_labels if name not in labels]
    if unknown:
        raise SystemExit(f"unknown workflow labels: {', '.join(unknown)}")

    if args.platform == "github":
        if not args.type or not args.priority:
            raise SystemExit("--type and --priority are required for github apply-metadata")
        issue_type = github_issue_type(args.type)
        priority_value = github_priority_value(args.priority)
        patch_github_issue_type(args.repo, args.issue, issue_type)
        set_github_priority(args.repo, args.issue, priority_value)

        current = issue_labels_github(args.repo, args.issue)
        add, remove = resolve_replacements(labels, current, workflow_labels)
        legacy_remove = [name for name in current if name in legacy_github_labels(all_labels)]
        remove = sorted(set(remove + legacy_remove))
        apply_github_labels(args.repo, args.issue, add, remove)

        remote_sync = {
            "platform": "github",
            "issue_type": issue_type,
            "priority": priority_value,
            "labels": workflow_labels,
        }
        print(
            json.dumps(
                {
                    "ok": True,
                    "remote_sync": remote_sync,
                    "labels_added": add,
                    "labels_removed": remove,
                },
                indent=2,
            )
        )
        return 0

    desired = list(workflow_labels)
    if args.type:
        desired.append(args.type)
    if args.priority:
        desired.append(args.priority)
    current = issue_labels_gitlab(args.repo, args.issue)
    add, remove = resolve_replacements(all_labels, current, desired)
    apply_gitlab_labels(args.repo, args.issue, add, remove)
    remote_sync = expected_remote_sync(
        "gitlab",
        {"type": args.type, "priority": args.priority},
        workflow_labels,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "remote_sync": remote_sync,
                "labels_added": add,
                "labels_removed": remove,
            },
            indent=2,
        )
    )
    return 0


def cmd_migrate_triage_labels(args: argparse.Namespace) -> int:
    if args.platform != "github":
        raise SystemExit("migrate-triage-labels currently supports github only")
    all_labels = load_labels()
    current = issue_labels_github(args.repo, args.issue)
    remove = [name for name in current if name in legacy_github_labels(all_labels)]
    if remove:
        apply_github_labels(args.repo, args.issue, [], remove)
    print(json.dumps({"ok": True, "removed": remove}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync and apply GCW triage metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in (
        ("sync", cmd_sync),
        ("apply", cmd_apply),
        ("apply-metadata", cmd_apply_metadata),
        ("migrate-triage-labels", cmd_migrate_triage_labels),
    ):
        sub = subparsers.add_parser(name)
        sub.add_argument("--platform", required=True, choices=("github", "gitlab"))
        sub.add_argument("--repo", required=True, help="OWNER/REPO (GitHub) or GROUP/PROJECT (GitLab)")
        sub.set_defaults(handler=handler)

    subparsers.choices["apply"].add_argument("--issue", required=True)
    subparsers.choices["apply"].add_argument(
        "--add",
        required=True,
        help="Comma-separated labels to apply; conflicting labels in the same group are replaced",
    )

    metadata = subparsers.choices["apply-metadata"]
    metadata.add_argument("--issue", required=True)
    metadata.add_argument("--type", default="")
    metadata.add_argument("--priority", default="")
    metadata.add_argument(
        "--labels",
        required=True,
        help="Comma-separated workflow labels (area/readiness/triage/optional only on GitHub)",
    )
    metadata.add_argument(
        "--executor",
        default="local",
        choices=("local", "hosted", "none"),
        help="Default executor label to add when --labels does not already include one.",
    )

    subparsers.choices["migrate-triage-labels"].add_argument("--issue", required=True)
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
