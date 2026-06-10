from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLANNING_NEXT_STEPS = ["publish-planning"]
IMPLEMENTING_NEXT_STEPS = ["implement", "local-self-review", "readiness-check", "block", "clarify"]
MACHINE_FAILED_NEXT_STEPS = ["address-machine-feedback", "block", "clarify"]
HUMAN_REVIEW_TRANSITIONS = {
    "approved": ("approved", ["review-complete", "implement"]),
    "changes-requested": ("changes-requested", ["address-human-feedback"]),
    "blocked": ("blocked", []),
    "closed": ("review-complete", []),
}
PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected a boolean value")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def init_state(args: argparse.Namespace) -> dict[str, Any]:
    state = {
        "issue": args.issue,
        "platform": args.platform,
        "repository": args.repository,
        "state": "planning",
        "branch": args.branch,
        "owner": {
            "kind": args.owner_kind,
            "id": args.owner_id,
        },
        "last_completed_step": "",
        "next_allowed_steps": PLANNING_NEXT_STEPS,
        "evidence": {
            "planning_files_exist": False,
            "planning_commit_pushed": False,
            "progress_comment_url": "",
            "self_review_recorded": False,
            "review_request_url": "",
        },
    }
    write_json(args.issue_dir / "state.json", state)
    return {"ok": True, "path": str(args.issue_dir / "state.json"), "state": state}


def record_publish_planning(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    planning_files_exist = all((args.issue_dir / name).is_file() for name in PLANNING_FILES)
    evidence = state.setdefault("evidence", {})
    evidence["planning_files_exist"] = planning_files_exist
    evidence["planning_commit_pushed"] = True
    evidence["progress_comment_url"] = args.progress_comment_url
    state["state"] = "planned"
    state["last_completed_step"] = "publish-planning"
    state["next_allowed_steps"] = ["implementation-gate"]
    write_json(state_path, state)
    ok = planning_files_exist and bool(args.progress_comment_url)
    return {"ok": ok, "path": str(state_path), "state": state}


def record_implementation_gate(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    planning_files_exist = all((args.issue_dir / name).is_file() for name in PLANNING_FILES)
    progress_comment_linked = bool(args.progress_comment_url)
    issue_actionable = args.issue_actionable
    ok = planning_files_exist and progress_comment_linked and issue_actionable
    if ok:
        target_state = "ready-for-implementation"
    elif not issue_actionable and args.clarifying_question:
        target_state = "issue-clarifying"
    else:
        target_state = "blocked"
    gate = {
        "step": "implementation-gate",
        "ok": ok,
        "state_transition": {"from": state.get("state", "planned"), "to": target_state},
        "checks": {
            "planning_files_exist": planning_files_exist,
            "planning_commit_pushed": True,
            "progress_comment_linked": progress_comment_linked,
            "issue_actionable": issue_actionable,
        },
        "errors": [] if ok else ["implementation gate evidence is incomplete or the issue needs clarification"],
    }
    write_json(args.issue_dir / "implementation_gate_result.json", gate)

    evidence = state.setdefault("evidence", {})
    evidence["planning_files_exist"] = planning_files_exist
    evidence["planning_commit_pushed"] = True
    evidence["progress_comment_url"] = args.progress_comment_url
    if args.clarifying_question:
        evidence["clarifying_question"] = args.clarifying_question
    state["state"] = target_state
    state["last_completed_step"] = "implementation-gate"
    state["next_allowed_steps"] = ["implement"] if ok else []
    write_json(state_path, state)
    return {"ok": ok, "path": str(args.issue_dir / "implementation_gate_result.json"), "state": state}


def record_implement(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    ok = state.get("state") == "ready-for-implementation"
    if ok:
        state["state"] = "implementing"
        state["last_completed_step"] = "implement"
        state["next_allowed_steps"] = IMPLEMENTING_NEXT_STEPS
        write_json(state_path, state)
    return {
        "ok": ok,
        "path": str(state_path),
        "state": state,
        "errors": [] if ok else ["implement requires ready-for-implementation state"],
    }


def planning_link(platform: str, repository: str, branch: str, issue: Any, filename: str) -> str:
    if platform == "gitlab":
        return f"https://gitlab.com/{repository}/-/blob/{branch}/.gcw/issues/{issue}/{filename}"
    return f"https://github.com/{repository}/blob/{branch}/.gcw/issues/{issue}/{filename}"


def record_readiness_evidence(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    issue = state["issue"]
    branch = state["branch"]
    repository = state["repository"]
    platform = state.get("platform", "github")
    state_evidence = state.get("evidence", {}) if isinstance(state.get("evidence"), dict) else {}
    progress_comment_url = state_evidence.get("progress_comment_url", "")
    progress_section = state_evidence.get("self_review_progress_section", "## Local Self-Review")
    if state_evidence.get("self_review_recorded") is not True:
        return {
            "ok": False,
            "path": str(args.issue_dir / "readiness_evidence.json"),
            "state": state,
            "errors": ["readiness evidence requires prior local self-review"],
        }
    evidence = {
        "issue": issue,
        "branch": branch,
        "base_branch": args.base_branch,
        "commit_range": args.commit_range,
        "review_request": {
            "title": args.title,
            "summary": args.summary,
            "issue_link": args.issue_link,
        },
        "validation": [
            {
                "command": args.validation_command,
                "result": args.validation_result,
            }
        ],
        "local_self_review": {
            "recorded": True,
            "progress_section": progress_section,
        },
        "planning_links": {
            "task_plan": planning_link(platform, repository, branch, issue, "task_plan.md"),
            "findings": planning_link(platform, repository, branch, issue, "findings.md"),
            "progress": planning_link(platform, repository, branch, issue, "progress.md"),
        },
        "progress_comment_url": progress_comment_url,
        "risks": args.risks,
    }
    write_json(args.issue_dir / "readiness_evidence.json", evidence)

    state["state"] = "ready-for-review-request"
    state["last_completed_step"] = "readiness-check"
    state["next_allowed_steps"] = ["create-review-request"]
    write_json(state_path, state)
    return {"ok": True, "path": str(args.issue_dir / "readiness_evidence.json"), "state": state}


def record_review_request(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    readiness_path = args.issue_dir / "readiness_evidence.json"
    ok = readiness_path.is_file() and state.get("state") == "ready-for-review-request"
    if state.get("last_completed_step") != "readiness-check":
        ok = False
    evidence = state.setdefault("evidence", {})
    evidence["review_request_url"] = args.review_request_url
    if ok:
        state["state"] = "ready-for-review"
        state["last_completed_step"] = "create-review-request"
        state["next_allowed_steps"] = ["machine-review-start"]
    write_json(state_path, state)
    return {
        "ok": ok,
        "path": str(state_path),
        "state": state,
        "errors": [] if ok else ["review request requires ready-for-review-request state and readiness-check completion"],
    }


def record_machine_review_start(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    ok = state.get("state") == "ready-for-review"
    if ok:
        state["state"] = "machine-reviewing"
        state["last_completed_step"] = "machine-review-start"
        state["next_allowed_steps"] = ["machine-review-result"]
        write_json(state_path, state)
    return {
        "ok": ok,
        "path": str(state_path),
        "state": state,
        "errors": [] if ok else ["machine-review-start requires ready-for-review state"],
    }


def record_machine_review_result(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    if state.get("state") != "machine-reviewing":
        return {
            "ok": False,
            "path": str(state_path),
            "state": state,
            "errors": ["machine-review-result requires machine-reviewing state"],
        }
    evidence = state.setdefault("evidence", {})
    evidence["machine_review_result"] = args.result
    state["last_completed_step"] = "machine-review-result"
    if args.result == "passed":
        state["state"] = "human-reviewing"
        state["next_allowed_steps"] = ["human-review-result"]
        ok = True
        errors: list[str] = []
    else:
        state["state"] = "machine-review-failed"
        state["next_allowed_steps"] = MACHINE_FAILED_NEXT_STEPS
        ok = False
        errors = ["machine review reported failing checks"]
    write_json(state_path, state)
    return {"ok": ok, "path": str(state_path), "state": state, "errors": errors}


def record_address_machine_feedback(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    ok = state.get("state") == "machine-review-failed"
    if ok:
        state["state"] = "implementing"
        state["last_completed_step"] = "address-machine-feedback"
        state["next_allowed_steps"] = IMPLEMENTING_NEXT_STEPS
        write_json(state_path, state)
    return {
        "ok": ok,
        "path": str(state_path),
        "state": state,
        "errors": [] if ok else ["address-machine-feedback requires machine-review-failed state"],
    }


def record_human_review_result(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    if state.get("state") != "human-reviewing":
        return {
            "ok": False,
            "path": str(state_path),
            "state": state,
            "errors": ["human-review-result requires human-reviewing state"],
        }
    target_state, next_steps = HUMAN_REVIEW_TRANSITIONS[args.result]
    evidence = state.setdefault("evidence", {})
    evidence["human_review_result"] = args.result
    state["state"] = target_state
    state["last_completed_step"] = "human-review-result"
    state["next_allowed_steps"] = next_steps
    write_json(state_path, state)
    return {"ok": True, "path": str(state_path), "state": state}


def record_address_human_feedback(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    ok = state.get("state") == "changes-requested"
    if ok:
        state["state"] = "implementing"
        state["last_completed_step"] = "address-human-feedback"
        state["next_allowed_steps"] = IMPLEMENTING_NEXT_STEPS
        write_json(state_path, state)
    return {
        "ok": ok,
        "path": str(state_path),
        "state": state,
        "errors": [] if ok else ["address-human-feedback requires changes-requested state"],
    }


def record_review_complete(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    ok = state.get("state") == "approved"
    if ok:
        evidence = state.setdefault("evidence", {})
        evidence["review_complete_result"] = args.result
        state["state"] = "review-complete"
        state["last_completed_step"] = "review-complete"
        state["next_allowed_steps"] = []
        write_json(state_path, state)
    return {
        "ok": ok,
        "path": str(state_path),
        "state": state,
        "errors": [] if ok else ["review-complete requires approved state"],
    }


def record_block(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    evidence = state.setdefault("evidence", {})
    evidence["block_reason"] = args.reason
    state["state"] = "blocked"
    state["last_completed_step"] = "block"
    state["next_allowed_steps"] = []
    write_json(state_path, state)
    return {"ok": True, "path": str(state_path), "state": state}


def record_clarify(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    evidence = state.setdefault("evidence", {})
    evidence["clarifying_question"] = args.question
    state["state"] = "issue-clarifying"
    state["last_completed_step"] = "clarify"
    state["next_allowed_steps"] = []
    write_json(state_path, state)
    return {"ok": True, "path": str(state_path), "state": state}


def record_local_self_review(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    evidence = state.setdefault("evidence", {})
    evidence["self_review_recorded"] = True
    evidence["self_review_progress_section"] = args.progress_section
    state["state"] = "implementing"
    state["last_completed_step"] = "local-self-review"
    state["next_allowed_steps"] = IMPLEMENTING_NEXT_STEPS
    write_json(state_path, state)
    return {"ok": True, "path": str(state_path), "state": state}


def record_handoff(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.issue_dir / "state.json"
    state = read_json(state_path)
    state["owner"] = {
        "kind": args.owner_kind,
        "id": args.owner_id,
    }
    state["last_completed_step"] = "ownership-handoff"
    state.setdefault("evidence", {})["handoff_reason"] = args.reason
    write_json(state_path, state)
    return {"ok": True, "path": str(state_path), "state": state}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and update GCW issue workflow state files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-state", help="Create an initial planning state.json.")
    init_parser.add_argument("--issue-dir", required=True, type=Path)
    init_parser.add_argument("--issue", required=True)
    init_parser.add_argument("--platform", required=True, choices=("github", "gitlab"))
    init_parser.add_argument("--repository", required=True)
    init_parser.add_argument("--branch", required=True)
    init_parser.add_argument("--owner-kind", required=True, choices=("local", "github-actions", "gitlab-ci", "manual"))
    init_parser.add_argument("--owner-id", required=True)
    init_parser.set_defaults(handler=init_state)

    publish_parser = subparsers.add_parser(
        "record-publish-planning",
        help="Mark planning files as published and link the issue progress comment.",
    )
    publish_parser.add_argument("--issue-dir", required=True, type=Path)
    publish_parser.add_argument("--progress-comment-url", required=True)
    publish_parser.set_defaults(handler=record_publish_planning)

    gate_parser = subparsers.add_parser(
        "record-implementation-gate",
        help="Write implementation_gate_result.json and update state.json.",
    )
    gate_parser.add_argument("--issue-dir", required=True, type=Path)
    gate_parser.add_argument("--progress-comment-url", required=True)
    gate_parser.add_argument("--issue-actionable", type=parse_bool, default=True)
    gate_parser.add_argument("--clarifying-question", default="")
    gate_parser.set_defaults(handler=record_implementation_gate)

    implement_parser = subparsers.add_parser(
        "record-implement",
        help="Move state.json from ready-for-implementation to implementing.",
    )
    implement_parser.add_argument("--issue-dir", required=True, type=Path)
    implement_parser.set_defaults(handler=record_implement)

    readiness_parser = subparsers.add_parser(
        "record-readiness-evidence",
        help="Write readiness_evidence.json and move state.json to ready-for-review-request.",
    )
    readiness_parser.add_argument("--issue-dir", required=True, type=Path)
    readiness_parser.add_argument("--base-branch", required=True)
    readiness_parser.add_argument("--commit-range", required=True)
    readiness_parser.add_argument("--title", required=True)
    readiness_parser.add_argument("--summary", required=True)
    readiness_parser.add_argument("--issue-link", required=True)
    readiness_parser.add_argument("--validation-command", required=True)
    readiness_parser.add_argument("--validation-result", required=True)
    readiness_parser.add_argument("--risks", required=True)
    readiness_parser.set_defaults(handler=record_readiness_evidence)

    review_parser = subparsers.add_parser(
        "record-review-request",
        help="Move state.json to ready-for-review after creating the review request.",
    )
    review_parser.add_argument("--issue-dir", required=True, type=Path)
    review_parser.add_argument("--review-request-url", required=True)
    review_parser.set_defaults(handler=record_review_request)

    machine_start_parser = subparsers.add_parser(
        "record-machine-review-start",
        help="Move state.json from ready-for-review to machine-reviewing.",
    )
    machine_start_parser.add_argument("--issue-dir", required=True, type=Path)
    machine_start_parser.set_defaults(handler=record_machine_review_start)

    machine_result_parser = subparsers.add_parser(
        "record-machine-review-result",
        help="Record the machine review outcome and move to human-reviewing or machine-review-failed.",
    )
    machine_result_parser.add_argument("--issue-dir", required=True, type=Path)
    machine_result_parser.add_argument("--result", required=True, choices=("passed", "failed"))
    machine_result_parser.set_defaults(handler=record_machine_review_result)

    address_machine_parser = subparsers.add_parser(
        "record-address-machine-feedback",
        help="Move state.json from machine-review-failed back to implementing.",
    )
    address_machine_parser.add_argument("--issue-dir", required=True, type=Path)
    address_machine_parser.set_defaults(handler=record_address_machine_feedback)

    human_result_parser = subparsers.add_parser(
        "record-human-review-result",
        help="Record the human review outcome.",
    )
    human_result_parser.add_argument("--issue-dir", required=True, type=Path)
    human_result_parser.add_argument(
        "--result",
        required=True,
        choices=("approved", "changes-requested", "blocked", "closed"),
    )
    human_result_parser.set_defaults(handler=record_human_review_result)

    address_human_parser = subparsers.add_parser(
        "record-address-human-feedback",
        help="Move state.json from changes-requested back to implementing.",
    )
    address_human_parser.add_argument("--issue-dir", required=True, type=Path)
    address_human_parser.set_defaults(handler=record_address_human_feedback)

    review_complete_parser = subparsers.add_parser(
        "record-review-complete",
        help="Move state.json from approved to review-complete.",
    )
    review_complete_parser.add_argument("--issue-dir", required=True, type=Path)
    review_complete_parser.add_argument("--result", default="completed")
    review_complete_parser.set_defaults(handler=record_review_complete)

    block_parser = subparsers.add_parser(
        "record-block",
        help="Move state.json to blocked with a blocker reason.",
    )
    block_parser.add_argument("--issue-dir", required=True, type=Path)
    block_parser.add_argument("--reason", required=True)
    block_parser.set_defaults(handler=record_block)

    clarify_parser = subparsers.add_parser(
        "record-clarify",
        help="Move state.json to issue-clarifying with the open question.",
    )
    clarify_parser.add_argument("--issue-dir", required=True, type=Path)
    clarify_parser.add_argument("--question", required=True)
    clarify_parser.set_defaults(handler=record_clarify)

    self_review_parser = subparsers.add_parser(
        "record-local-self-review",
        help="Record local self-review evidence while staying in implementing.",
    )
    self_review_parser.add_argument("--issue-dir", required=True, type=Path)
    self_review_parser.add_argument("--progress-section", required=True)
    self_review_parser.set_defaults(handler=record_local_self_review)

    handoff_parser = subparsers.add_parser(
        "record-handoff",
        help="Transfer ownership for future write operations without changing workflow state.",
    )
    handoff_parser.add_argument("--issue-dir", required=True, type=Path)
    handoff_parser.add_argument("--owner-kind", required=True, choices=("local", "github-actions", "gitlab-ci", "manual"))
    handoff_parser.add_argument("--owner-id", required=True)
    handoff_parser.add_argument("--reason", required=True)
    handoff_parser.set_defaults(handler=record_handoff)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.handler(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
