from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from gcw_workflow_lib import WorkflowError, append_event, write_json, write_projection


LEGACY_FILES = ("state.json", "readiness_evidence.json", "implementation_gate_result.json")


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{path.name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"{path.name} must contain a JSON object")
    return data


def file_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def append_synthetic(issue_dir: Path, event: str, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return append_event(
        issue_dir,
        {
            "event": event,
            "synthetic": True,
            "actor": state.get("owner", {"kind": "local", "id": "migration"}),
            "refs": {
                "issue": state.get("issue", ""),
                "branch": state.get("branch", ""),
                "base_branch": payload.get("base_branch", ""),
            },
            "payload": payload,
        },
    )


def readiness_to_payload(readiness: dict[str, Any]) -> dict[str, Any]:
    validation = readiness.get("validation") if isinstance(readiness.get("validation"), list) else []
    normalized_validation: list[dict[str, Any]] = []
    for item in validation:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized.setdefault("exit_code", 0 if item.get("result") == "passed" else 1)
        normalized_validation.append(normalized)
    return {
        "gate": {
            "ok": True,
            "checks": [{"id": "legacy_readiness_evidence", "ok": True}],
            "validation": normalized_validation,
        },
        "review_request": readiness.get("review_request", {}),
        "risks": readiness.get("risks", ""),
        "scope": readiness.get("scope", ""),
        "reviewer_notes": readiness.get("reviewer_notes", ""),
        "self_review": readiness.get("local_self_review", {}),
        "planning_links": readiness.get("planning_links", {}),
        "spec_refs": {
            "task_plan_sha": "legacy:unknown",
            "findings_sha": "legacy:unknown",
            "progress_sha": "legacy:unknown",
        },
        "base_branch": readiness.get("base_branch", ""),
    }


def migrate_issue_dir(issue_dir: Path) -> dict[str, Any]:
    state = read_json_if_exists(issue_dir / "state.json")
    if not state:
        raise WorkflowError("state.json is required for legacy migration")
    readiness = read_json_if_exists(issue_dir / "readiness_evidence.json")
    gate_result = read_json_if_exists(issue_dir / "implementation_gate_result.json")
    legacy_hashes = {
        name: file_hash(issue_dir / name)
        for name in LEGACY_FILES
        if (issue_dir / name).is_file()
    }

    events_path = issue_dir / "events"
    if events_path.exists() and any(events_path.iterdir()):
        raise WorkflowError("events directory already contains files")

    generated: list[str] = []
    append_synthetic(
        issue_dir,
        "gcw-issue-intake",
        {
            "issue": state.get("issue", ""),
            "platform": state.get("platform", "github"),
            "repository": state.get("repository", ""),
            "branch": state.get("branch", ""),
            "owner": state.get("owner", {"kind": "local", "id": "migration"}),
        },
        state,
    )
    generated.append("gcw-issue-intake")

    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    if state.get("state") in {
        "ready-for-planning",
        "planned",
        "ready-for-implementation",
        "implementing",
        "ready-for-review",
        "reviewing",
        "changes-requested",
        "blocked",
        "review-complete",
    } or evidence.get("planning_files_exist"):
        append_synthetic(issue_dir, "gcw-issue-prepare", {"ready": True}, state)
        generated.append("gcw-issue-prepare")

    if evidence.get("planning_commit_pushed") or evidence.get("progress_comment_url"):
        append_synthetic(
            issue_dir,
            "gcw-issue-to-spec",
            {
                "planning_commit_pushed": bool(evidence.get("planning_commit_pushed")),
                "progress_comment_url": evidence.get("progress_comment_url", ""),
                "spec_refs": {
                    "task_plan_sha": "legacy:unknown",
                    "findings_sha": "legacy:unknown",
                    "progress_sha": "legacy:unknown",
                },
            },
            state,
        )
        generated.append("gcw-issue-to-spec")

    if evidence.get("spec_check_passed") or gate_result:
        append_synthetic(
            issue_dir,
            "gcw-spec-check",
            {
                "result": "passed",
                "gate": {
                    "ok": True,
                    "checks": gate_result.get("checks", []),
                    "errors": gate_result.get("errors", []),
                },
            },
            state,
        )
        generated.append("gcw-spec-check")

    if state.get("state") in {"implementing", "ready-for-review", "reviewing", "changes-requested", "review-complete"} or evidence.get("implement_check_passed"):
        append_synthetic(issue_dir, "gcw-implement", {"work_summary": "Migrated legacy implementation state."}, state)
        generated.append("gcw-implement")

    if evidence.get("implement_check_passed") or readiness:
        append_synthetic(issue_dir, "gcw-implement-check", readiness_to_payload(readiness), state)
        generated.append("gcw-implement-check")

    review_url = evidence.get("review_request_url", "")
    if review_url:
        append_synthetic(
            issue_dir,
            "gcw-pr-publish",
            {
                "review_request_url": review_url,
                "rendered_from_event_id": "",
                "body_hash": "legacy:unknown",
                "effects": [
                    {
                        "kind": "github_pr_upsert" if state.get("platform", "github") == "github" else "gitlab_mr_upsert",
                        "operation_id": f"gcw-{state.get('issue', '')}-legacy-pr-publish",
                        "target": review_url,
                        "body_hash": "legacy:unknown",
                        "remote_updated_at": "",
                        "status": "applied",
                    }
                ],
            },
            state,
        )
        generated.append("gcw-pr-publish")

    metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    if state.get("state") == "changes-requested":
        append_synthetic(
            issue_dir,
            "gcw-pr-review",
            {
                "result": "changes-requested",
                "feedback_source": metadata.get("feedback_source", "pr-review"),
                "reason": metadata.get("block_reason", ""),
            },
            state,
        )
        generated.append("gcw-pr-review")
    elif state.get("state") == "review-complete":
        append_synthetic(issue_dir, "review-complete", {"result": metadata.get("review_result", "accepted")}, state)
        generated.append("review-complete")

    workflow = write_projection(issue_dir)
    deleted: list[str] = []
    for name in LEGACY_FILES:
        path = issue_dir / name
        if path.is_file():
            path.unlink()
            deleted.append(name)

    report = {
        "legacy_hashes": legacy_hashes,
        "generated_events": generated,
        "synthetic_events": generated,
        "unrestored_fields": ["precise event timestamps", "exact git tree shas"],
        "events_hash": workflow["generated_from"]["events_hash"],
        "projection": workflow["projection"],
        "deleted_legacy_files": deleted,
    }
    write_json(issue_dir / "migration_report.json", report)
    return {"ok": True, "issue_dir": str(issue_dir), "migration_report": report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate legacy GCW state/evidence files to event log storage.")
    parser.add_argument("--issue-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = migrate_issue_dir(args.issue_dir)
    except WorkflowError as exc:
        result = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
