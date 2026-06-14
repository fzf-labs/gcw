from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gcw_workflow_lib import (
    NEXT_ALLOWED_STEPS,
    PLANNING_FILES,
    WorkflowError,
    append_event,
    assert_projection_current,
    find_latest_event,
    load_projection,
    validate_event_log,
    write_projection,
)


def emit(result: dict[str, Any]) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def read_payload(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{path.name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"{path.name} must contain a JSON object")
    return data


def current_projection(issue_dir: Path) -> dict[str, Any]:
    current = assert_projection_current(issue_dir)
    if not current["ok"]:
        raise WorkflowError("; ".join(current["errors"]))
    return load_projection(issue_dir)["projection"]


def finish(issue_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    workflow = write_projection(issue_dir)
    return {
        "ok": True,
        "event": event,
        "workflow": workflow,
        "projection": workflow["projection"],
    }


def progress_comment_url_from_args(args: argparse.Namespace) -> str:
    url = str(getattr(args, "progress_comment_url", "") or "").strip()
    if not url:
        raise WorkflowError("progress_comment_url is required")
    return url


def attach_progress_comment_body_hash(issue_dir: Path, event_name: str, payload: dict[str, Any]) -> None:
    if not str(payload.get("progress_comment_url", "")).strip():
        return
    if str(payload.get("progress_comment_body_hash", "")).strip():
        return

    from publish_progress_comment import body_hash, render_milestone_progress_body

    try:
        body = render_milestone_progress_body(issue_dir, event_name, payload)
    except (WorkflowError, ValueError) as exc:
        raise WorkflowError(f"could not render progress comment body for {event_name}: {exc}") from exc
    payload["progress_comment_body_hash"] = body_hash(body)


def append_and_finish(args: argparse.Namespace, event_name: str, payload: dict[str, Any], refs: dict[str, Any] | None = None) -> dict[str, Any]:
    attach_progress_comment_body_hash(args.issue_dir, event_name, payload)
    event = append_event(
        args.issue_dir,
        {
            "event": event_name,
            "actor": {"kind": getattr(args, "actor_kind", "local"), "id": getattr(args, "actor_id", "cursor-session")},
            "refs": refs or {},
            "payload": payload,
        },
        expected_last_seq=getattr(args, "expected_last_seq", None),
        parent_projection_hash=getattr(args, "parent_projection_hash", None) or None,
    )
    return finish(args.issue_dir, event)


def init_workflow(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "issue": args.issue,
        "platform": args.platform,
        "repository": args.repository,
        "branch": args.branch,
        "owner": {
            "kind": args.owner_kind,
            "id": args.owner_id,
        },
    }
    return append_and_finish(args, "gcw-issue-intake", payload, {"issue": args.issue, "branch": args.branch})


def record_issue_prepare(args: argparse.Namespace) -> dict[str, Any]:
    if not args.gate_file or not args.gate_file.is_file():
        raise WorkflowError("record-issue-prepare requires --gate-file")
    gate = read_payload(args.gate_file)
    ready = bool(gate.get("ok"))
    if args.ready and not ready:
        raise WorkflowError("record-issue-prepare --ready conflicts with gate.ok false")

    payload: dict[str, Any] = {
        "ready": ready,
        "gate": gate,
        "progress_comment_url": progress_comment_url_from_args(args),
    }
    if args.question:
        payload["question"] = args.question
    if args.summary:
        payload["summary"] = args.summary
    if args.classification_type:
        payload["classification"] = {
            "type": args.classification_type,
            "area": args.classification_area or None,
            "priority": args.classification_priority or None,
        }
        payload["classification"] = {k: v for k, v in payload["classification"].items() if v is not None}
    if args.labels_applied:
        payload["labels_applied"] = [label.strip() for label in args.labels_applied.split(",") if label.strip()]
    if args.remote_sync_file and args.remote_sync_file.is_file():
        payload["remote_sync"] = read_payload(args.remote_sync_file)
    return append_and_finish(args, "gcw-issue-prepare", payload)


def record_issue_to_spec(args: argparse.Namespace) -> dict[str, Any]:
    missing = [name for name in PLANNING_FILES if not (args.issue_dir / name).is_file()]
    if missing:
        raise WorkflowError(f"missing planning files: {', '.join(missing)}")
    payload = {
        "planning_commit_pushed": args.planning_commit_pushed,
        "progress_comment_url": args.progress_comment_url,
        "spec_refs": {
            "task_plan_sha": args.task_plan_sha,
            "findings_sha": args.findings_sha,
            "progress_sha": args.progress_sha,
        },
    }
    return append_and_finish(args, "gcw-issue-to-spec", payload)


def record_spec_check(args: argparse.Namespace) -> dict[str, Any]:
    ok = args.result == "passed"
    payload: dict[str, Any] = {
        "result": args.result,
        "progress_comment_url": progress_comment_url_from_args(args),
        "gate": {
            "ok": ok,
            "checks": [],
            "errors": [] if ok else [args.reason or args.question],
        },
    }
    if args.question:
        payload["question"] = args.question
    if args.reason:
        payload["reason"] = args.reason
    return append_and_finish(args, "gcw-spec-check", payload)


def record_implement(args: argparse.Namespace) -> dict[str, Any]:
    projection = current_projection(args.issue_dir)
    phase = str(projection.get("phase", ""))
    payload: dict[str, Any] = {"work_summary": args.work_summary}
    url = str(getattr(args, "progress_comment_url", "") or "").strip()
    if phase in ("ready-for-implementation", "changes-requested"):
        if not url:
            raise WorkflowError("progress_comment_url is required when entering implementing")
        payload["progress_comment_url"] = url
    elif url:
        payload["progress_comment_url"] = url
    if args.feedback_source:
        payload["feedback_source"] = args.feedback_source
    if args.feedback_ref:
        payload["feedback_ref"] = args.feedback_ref
    return append_and_finish(args, "gcw-implement", payload)


def record_implement_check(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_payload(args.payload_file)
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    if gate.get("ok") is True:
        payload["progress_comment_url"] = progress_comment_url_from_args(args)
    return append_and_finish(args, "gcw-implement-check", payload)


def record_pr_publish(args: argparse.Namespace) -> dict[str, Any]:
    rendered_from_event_id = args.rendered_from_event_id
    if not str(rendered_from_event_id).strip():
        latest = find_latest_event(args.issue_dir, "gcw-implement-check")
        if latest is None:
            raise WorkflowError("gcw-implement-check event is required before gcw-pr-publish")
        rendered_from_event_id = str(latest.get("event_id", ""))
    if not str(rendered_from_event_id).strip():
        raise WorkflowError("rendered_from_event_id is required")
    payload = {
        "review_request_url": args.review_request_url,
        "rendered_from_event_id": rendered_from_event_id,
        "body_hash": args.body_hash,
        "progress_comment_url": progress_comment_url_from_args(args),
        "effects": [
            {
                "kind": args.effect_kind,
                "operation_id": args.operation_id,
                "target": args.target,
                "body_hash": args.body_hash,
                "remote_updated_at": args.remote_updated_at,
                "status": "applied",
            }
        ],
    }
    return append_and_finish(args, "gcw-pr-publish", payload)


def record_pr_review(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "result": args.result,
        "progress_comment_url": progress_comment_url_from_args(args),
    }
    if args.feedback_source:
        payload["feedback_source"] = args.feedback_source
    if args.reason:
        payload["reason"] = args.reason
        payload["block_reason"] = args.reason
    return append_and_finish(args, "gcw-pr-review", payload)


def record_block(args: argparse.Namespace) -> dict[str, Any]:
    projection = current_projection(args.issue_dir)
    resume_phase = args.resume_phase or projection["phase"]
    resume_step = args.resume_step or (projection.get("next_allowed_steps") or [""])[0]
    payload = {
        "reason": args.reason,
        "resume_phase": resume_phase,
        "resume_step": resume_step,
        "progress_comment_url": progress_comment_url_from_args(args),
    }
    return append_and_finish(args, "gcw-block", payload)


def record_clarify(args: argparse.Namespace) -> dict[str, Any]:
    projection = current_projection(args.issue_dir)
    payload = {
        "question": args.question,
        "source_phase": args.source_phase or projection["phase"],
        "progress_comment_url": progress_comment_url_from_args(args),
    }
    return append_and_finish(args, "gcw-clarify", payload)


def record_review_complete(args: argparse.Namespace) -> dict[str, Any]:
    return append_and_finish(
        args,
        "review-complete",
        {
            "result": args.result,
            "progress_comment_url": progress_comment_url_from_args(args),
        },
    )


def rebuild_projection(args: argparse.Namespace) -> dict[str, Any]:
    errors = validate_event_log(args.issue_dir)
    if errors:
        raise WorkflowError("; ".join(errors))
    workflow = write_projection(args.issue_dir)
    return {"ok": True, "workflow": workflow, "projection": workflow["projection"]}


def add_common(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--issue-dir", required=True, type=Path)
    subparser.add_argument("--actor-kind", default="local")
    subparser.add_argument("--actor-id", default="cursor-session")
    subparser.add_argument("--expected-last-seq", type=int, default=None)
    subparser.add_argument("--parent-projection-hash", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage GCW workflow event logs and projections.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init-workflow")
    add_common(init)
    init.add_argument("--issue", required=True)
    init.add_argument("--platform", required=True, choices=("github", "gitlab"))
    init.add_argument("--repository", required=True)
    init.add_argument("--branch", required=True)
    init.add_argument("--owner-kind", required=True, choices=("local", "github-actions", "gitlab-ci", "manual"))
    init.add_argument("--owner-id", required=True)
    init.set_defaults(handler=init_workflow)

    prepare = subparsers.add_parser("record-issue-prepare")
    add_common(prepare)
    prepare.add_argument("--ready", action="store_true", help="Required when gate.ok is true")
    prepare.add_argument("--progress-comment-url", required=True)
    prepare.add_argument("--question", default="")
    prepare.add_argument("--summary", default="")
    prepare.add_argument("--classification-type", default="")
    prepare.add_argument("--classification-area", default="")
    prepare.add_argument("--classification-priority", default="")
    prepare.add_argument("--classification-repro", default="")
    prepare.add_argument("--labels-applied", default="")
    prepare.add_argument(
        "--gate-file",
        required=True,
        type=Path,
        help="JSON file with prepare readiness gate from evaluate_issue_readiness.py",
    )
    prepare.add_argument(
        "--remote-sync-file",
        default="",
        type=Path,
        help="JSON file with remote_sync payload from manage_triage_metadata apply-metadata",
    )
    prepare.set_defaults(handler=record_issue_prepare)

    to_spec = subparsers.add_parser("record-issue-to-spec")
    add_common(to_spec)
    to_spec.add_argument("--progress-comment-url", required=True)
    to_spec.add_argument("--planning-commit-pushed", action="store_true")
    to_spec.add_argument("--task-plan-sha", default="")
    to_spec.add_argument("--findings-sha", default="")
    to_spec.add_argument("--progress-sha", default="")
    to_spec.set_defaults(handler=record_issue_to_spec)

    spec_check = subparsers.add_parser("record-spec-check")
    add_common(spec_check)
    spec_check.add_argument("--result", required=True, choices=("passed", "clarifying", "blocked"))
    spec_check.add_argument("--progress-comment-url", required=True)
    spec_check.add_argument("--question", default="")
    spec_check.add_argument("--reason", default="")
    spec_check.set_defaults(handler=record_spec_check)

    implement = subparsers.add_parser("record-implement")
    add_common(implement)
    implement.add_argument("--work-summary", required=True)
    implement.add_argument("--progress-comment-url", default="")
    implement.add_argument("--feedback-source", choices=("pr-review", "human-review"), default="")
    implement.add_argument("--feedback-ref", default="")
    implement.set_defaults(handler=record_implement)

    implement_check = subparsers.add_parser("record-implement-check")
    add_common(implement_check)
    implement_check.add_argument("--payload-file", required=True, type=Path)
    implement_check.add_argument("--progress-comment-url", required=True)
    implement_check.set_defaults(handler=record_implement_check)

    pr_publish = subparsers.add_parser("record-pr-publish")
    add_common(pr_publish)
    pr_publish.add_argument("--review-request-url", required=True)
    pr_publish.add_argument("--progress-comment-url", required=True)
    pr_publish.add_argument("--rendered-from-event-id", default="")
    pr_publish.add_argument("--body-hash", required=True)
    pr_publish.add_argument("--target", required=True)
    pr_publish.add_argument("--effect-kind", default="github_pr_upsert")
    pr_publish.add_argument("--operation-id", default="gcw-pr-publish")
    pr_publish.add_argument("--remote-updated-at", default="")
    pr_publish.set_defaults(handler=record_pr_publish)

    pr_review = subparsers.add_parser("record-pr-review")
    add_common(pr_review)
    pr_review.add_argument("--result", required=True, choices=("passed", "changes-requested", "blocked"))
    pr_review.add_argument("--progress-comment-url", required=True)
    pr_review.add_argument("--feedback-source", choices=("pr-review", "human-review"), default="pr-review")
    pr_review.add_argument("--reason", default="")
    pr_review.set_defaults(handler=record_pr_review)

    block = subparsers.add_parser("record-block")
    add_common(block)
    block.add_argument("--reason", required=True)
    block.add_argument("--progress-comment-url", required=True)
    block.add_argument("--resume-phase", default="")
    block.add_argument("--resume-step", default="")
    block.set_defaults(handler=record_block)

    clarify = subparsers.add_parser("record-clarify")
    add_common(clarify)
    clarify.add_argument("--question", required=True)
    clarify.add_argument("--progress-comment-url", required=True)
    clarify.add_argument("--source-phase", default="")
    clarify.set_defaults(handler=record_clarify)

    complete = subparsers.add_parser("record-review-complete")
    add_common(complete)
    complete.add_argument("--result", required=True, choices=("merged", "closed", "accepted", "rejected"))
    complete.add_argument("--progress-comment-url", required=True)
    complete.set_defaults(handler=record_review_complete)

    rebuild = subparsers.add_parser("rebuild-projection")
    rebuild.add_argument("--issue-dir", required=True, type=Path)
    rebuild.set_defaults(handler=rebuild_projection)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return emit(args.handler(args))
    except WorkflowError as exc:
        return emit({"ok": False, "errors": [str(exc)]})


if __name__ == "__main__":
    sys.exit(main())
