#!/usr/bin/env python3
"""Verify local GCW triage metadata matches the remote hosting platform."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from triage_lib import (
    expected_remote_sync,
    github_issue_metadata,
    issue_labels_gitlab,
    legacy_github_labels,
    load_labels,
    validate_labels_applied_for_platform,
)


def latest_triage_event(issue_dir: Path) -> dict[str, Any] | None:
    events_dir = issue_dir / "events"
    if not events_dir.is_dir():
        return None
    events = []
    for path in sorted(events_dir.glob("*.json")):
        try:
            events.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    for event in reversed(events):
        if event.get("event") == "gcw-issue-triage":
            return event
    return None


def intake_platform(issue_dir: Path) -> str:
    intake_path = issue_dir / "events" / "000-gcw-issue-intake.json"
    if intake_path.is_file():
        intake = json.loads(intake_path.read_text(encoding="utf-8"))
        payload = intake.get("payload") if isinstance(intake.get("payload"), dict) else {}
        platform = str(payload.get("platform", "")).strip()
        if platform:
            return platform
    return "github"


def verify_github(repo: str, issue: str, triage: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    payload = triage.get("payload") if isinstance(triage.get("payload"), dict) else {}
    classification = payload.get("classification") if isinstance(payload.get("classification"), dict) else {}
    labels_applied = payload.get("labels_applied") if isinstance(payload.get("labels_applied"), list) else []
    remote_sync = payload.get("remote_sync") if isinstance(payload.get("remote_sync"), dict) else {}

    errors.extend(validate_labels_applied_for_platform("github", [str(x) for x in labels_applied]))

    expected = expected_remote_sync("github", classification, [str(x) for x in labels_applied])
    if remote_sync:
        for key in ("issue_type", "priority", "labels"):
            if remote_sync.get(key) != expected.get(key):
                errors.append(f"remote_sync.{key} does not match expected {expected.get(key)}")

    remote = github_issue_metadata(repo, issue)
    if remote["issue_type"] != expected["issue_type"]:
        errors.append(
            f"remote issue type {remote['issue_type']!r} does not match expected {expected['issue_type']!r}"
        )
    if remote["priority"] != expected["priority"]:
        errors.append(
            f"remote priority {remote['priority']!r} does not match expected {expected['priority']!r}"
        )

    expected_labels = sorted(expected["labels"])
    remote_labels = sorted(remote["labels"])
    if remote_labels != expected_labels:
        errors.append(f"remote labels {remote_labels} do not match expected {expected_labels}")

    legacy = legacy_github_labels(load_labels())
    stale = [name for name in remote["labels"] if name in legacy]
    if stale:
        errors.append(f"remote still has legacy type/priority labels: {', '.join(stale)}")
    return errors


def verify_gitlab(repo: str, issue: str, triage: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    payload = triage.get("payload") if isinstance(triage.get("payload"), dict) else {}
    classification = payload.get("classification") if isinstance(payload.get("classification"), dict) else {}
    labels_applied = payload.get("labels_applied") if isinstance(payload.get("labels_applied"), list) else []
    remote_sync = payload.get("remote_sync") if isinstance(payload.get("remote_sync"), dict) else {}

    expected = expected_remote_sync("gitlab", classification, [str(x) for x in labels_applied])
    if remote_sync and remote_sync.get("labels") != expected["labels"]:
        errors.append(f"remote_sync.labels does not match expected {expected['labels']}")

    remote_labels = sorted(issue_labels_gitlab(repo, issue))
    if remote_labels != expected["labels"]:
        errors.append(f"remote labels {remote_labels} do not match expected {expected['labels']}")
    return errors


def verify_issue(
    issue_dir: Path,
    *,
    repo: str | None = None,
    issue: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    triage = latest_triage_event(issue_dir)
    if triage is None:
        return {"ok": False, "errors": ["no gcw-issue-triage event found"]}

    payload = triage.get("payload") if isinstance(triage.get("payload"), dict) else {}
    if not payload.get("remote_sync"):
        return {
            "ok": True,
            "warnings": ["remote_sync missing; skipping strict remote verification"],
            "errors": [],
        }

    intake = json.loads((issue_dir / "events" / "000-gcw-issue-intake.json").read_text(encoding="utf-8"))
    intake_payload = intake.get("payload") if isinstance(intake.get("payload"), dict) else {}
    resolved_platform = platform or intake_platform(issue_dir)
    resolved_repo = repo or str(intake_payload.get("repository", ""))
    resolved_issue = issue or str(intake_payload.get("issue", ""))
    if not resolved_repo or not resolved_issue:
        return {"ok": False, "errors": ["repository and issue are required"]}

    if resolved_platform == "github":
        errors = verify_github(resolved_repo, resolved_issue, triage)
    else:
        errors = verify_gitlab(resolved_repo, resolved_issue, triage)

    return {"ok": not errors, "errors": errors, "platform": resolved_platform}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify GCW triage metadata against remote issue state.")
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument("--platform", choices=("github", "gitlab"), default=None)
    parser.add_argument("--repo", default="")
    parser.add_argument("--issue", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = verify_issue(
        args.issue_dir,
        repo=args.repo or None,
        issue=args.issue or None,
        platform=args.platform,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
