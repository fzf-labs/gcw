from __future__ import annotations

import hashlib
import json
from pathlib import Path


def file_sha(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def planning_shas(issue_dir: Path) -> dict[str, str]:
    return {
        "task_plan_sha": file_sha(issue_dir / "task_plan.md"),
        "findings_sha": file_sha(issue_dir / "findings.md"),
        "progress_sha": file_sha(issue_dir / "progress.md"),
    }


PROGRESS_COMMENT_BASE = "https://github.com/owner/repo/issues/42#issuecomment"


def progress_comment_url(seq: int) -> str:
    return f"{PROGRESS_COMMENT_BASE}-{seq}"


PREPARE_GATE_OK: dict = {
    "ok": True,
    "rubric_version": "prepare-readiness/v1",
    "profile": "enhancement",
    "checks": [
        {"id": "has_what_to_build", "ok": True, "source": "structural"},
        {"id": "has_acceptance_criteria", "ok": True, "source": "structural"},
        {"id": "blocker_resolved", "ok": True, "source": "structural"},
        {"id": "body_not_placeholder", "ok": True, "source": "structural"},
    ],
    "errors": [],
}

PREPARE_GATE_FAIL: dict = {
    "ok": False,
    "rubric_version": "prepare-readiness/v1",
    "profile": "enhancement",
    "checks": [
        {"id": "has_what_to_build", "ok": True, "source": "structural"},
        {
            "id": "has_acceptance_criteria",
            "ok": False,
            "source": "structural",
            "message": "no acceptance list items found",
        },
        {"id": "blocker_resolved", "ok": True, "source": "structural"},
        {"id": "body_not_placeholder", "ok": False, "source": "structural", "message": "body contains Not provided placeholder"},
    ],
    "errors": [
        "has_acceptance_criteria: no acceptance list items found",
        "body_not_placeholder: body contains Not provided placeholder",
    ],
}


def prepare_event_payload(
    *,
    ready: bool,
    progress_comment_url: str,
    **extra: object,
) -> dict:
    gate = PREPARE_GATE_OK if ready else PREPARE_GATE_FAIL
    payload: dict = {
        "ready": ready,
        "gate": gate,
        "progress_comment_url": progress_comment_url,
    }
    if not ready:
        payload["question"] = "Please update the issue with acceptance criteria and remove placeholders."
        payload["labels_applied"] = ["needs-info"]
    else:
        payload.setdefault(
            "labels_applied",
            ["triaged", "area:tests", "ready-to-spec"],
        )
        payload.setdefault(
            "remote_sync",
            {
                "platform": "github",
                "issue_type": "Feature",
                "priority": "Medium",
                "labels": payload.get("labels_applied", ["triaged", "area:tests", "ready-to-spec"]),
            },
        )
    payload.update(extra)
    return payload


def triage_event_payload(
    *,
    progress_comment_url: str,
    labels: list[str] | None = None,
    **extra: object,
) -> dict:
    labels = labels or ["triaged", "area:tests"]
    payload: dict = {
        "classification": {
            "type": "enhancement",
            "area": "area:tests",
            "priority": "priority:p2",
        },
        "labels_applied": labels,
        "remote_sync": {
            "platform": "github",
            "issue_type": "Feature",
            "priority": "Medium",
            "labels": labels,
        },
        "progress_comment_url": progress_comment_url,
    }
    payload.update(extra)
    return payload


def clarify_event_payload(
    *,
    ready: bool,
    progress_comment_url: str,
    **extra: object,
) -> dict:
    gate = PREPARE_GATE_OK if ready else PREPARE_GATE_FAIL
    payload: dict = {
        "ready": ready,
        "gate": gate,
        "progress_comment_url": progress_comment_url,
    }
    if ready:
        payload["summary"] = "scope clear"
    else:
        payload["question"] = "Please update the issue with acceptance criteria and remove placeholders."
    payload.update(extra)
    return payload


def write_prepare_gate_file(path: Path, *, ready: bool = True) -> Path:
    gate = PREPARE_GATE_OK if ready else PREPARE_GATE_FAIL
    path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_remote_sync_file(path: Path, labels: list[str]) -> Path:
    path.write_text(
        json.dumps(
            {
                "platform": "github",
                "issue_type": "Feature",
                "priority": "Medium",
                "labels": labels,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def prepare_record_cli_args(
    issue_dir: Path,
    *,
    seq: int = 0,
    ready: bool = True,
    labels: list[str] | None = None,
) -> list[str]:
    labels = labels or (["triaged", "area:tests", "ready-to-spec"] if ready else ["needs-info"])
    gate_file = write_prepare_gate_file(issue_dir / "prepare-gate.json", ready=ready)
    remote_sync_file = write_remote_sync_file(issue_dir / "remote-sync.json", labels)
    args = [
        "record-issue-prepare",
        "--issue-dir",
        str(issue_dir),
        "--gate-file",
        str(gate_file),
        "--progress-comment-url",
        progress_comment_url(seq),
        "--labels-applied",
        ",".join(labels),
        "--remote-sync-file",
        str(remote_sync_file),
    ]
    if ready:
        args.append("--ready")
    else:
        args.extend(["--question", "Please update the issue with acceptance criteria and remove placeholders."])
    return args


def triage_record_cli_args(
    issue_dir: Path,
    *,
    seq: int = 0,
    labels: list[str] | None = None,
) -> list[str]:
    labels = labels or ["triaged", "area:tests"]
    remote_sync_file = write_remote_sync_file(issue_dir / "remote-sync.json", labels)
    return [
        "record-issue-triage",
        "--issue-dir",
        str(issue_dir),
        "--progress-comment-url",
        progress_comment_url(seq),
        "--classification-type",
        "enhancement",
        "--classification-area",
        "area:tests",
        "--classification-priority",
        "priority:p2",
        "--labels-applied",
        ",".join(labels),
        "--remote-sync-file",
        str(remote_sync_file),
    ]


def clarify_record_cli_args(
    issue_dir: Path,
    *,
    seq: int = 1,
    ready: bool = True,
) -> list[str]:
    gate_file = write_prepare_gate_file(issue_dir / "clarify-gate.json", ready=ready)
    args = [
        "record-issue-clarify",
        "--issue-dir",
        str(issue_dir),
        "--gate-file",
        str(gate_file),
        "--progress-comment-url",
        progress_comment_url(seq),
    ]
    if ready:
        args.extend(["--ready", "--summary", "scope clear"])
    else:
        args.extend(["--question", "Please update the issue with acceptance criteria and remove placeholders."])
    return args

