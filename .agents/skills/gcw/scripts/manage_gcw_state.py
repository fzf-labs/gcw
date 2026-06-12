from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


STATES = (
    "issue-opened",
    "issue-clarifying",
    "ready-for-planning",
    "planned",
    "ready-for-implementation",
    "implementing",
    "ready-for-review",
    "reviewing",
    "changes-requested",
    "blocked",
    "review-complete",
)

NEXT_ALLOWED_STEPS: dict[str, list[str]] = {
    "issue-opened": ["gcw-issue-prepare"],
    "issue-clarifying": ["gcw-issue-prepare"],
    "ready-for-planning": ["gcw-issue-to-spec"],
    "planned": ["gcw-spec-check"],
    "ready-for-implementation": ["gcw-implement"],
    "implementing": ["gcw-implement", "gcw-implement-check", "gcw-block", "gcw-clarify"],
    "ready-for-review": ["gcw-pr-publish"],
    "reviewing": ["gcw-pr-review"],
    "changes-requested": ["gcw-implement"],
    "blocked": [],
    "review-complete": [],
}

PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def emit(result: dict[str, Any]) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def state_path(issue_dir: Path) -> Path:
    return issue_dir / "state.json"


def default_evidence() -> dict[str, Any]:
    return {
        "planning_files_exist": False,
        "planning_commit_pushed": False,
        "progress_comment_url": "",
        "spec_check_passed": False,
        "implement_check_passed": False,
        "self_review_recorded": False,
        "review_request_url": "",
    }


def set_state(state: dict[str, Any], new_state: str, step: str) -> None:
    state["state"] = new_state
    state["last_completed_step"] = step
    state["next_allowed_steps"] = NEXT_ALLOWED_STEPS[new_state]


def require_state(state: dict[str, Any], expected: set[str], step: str) -> list[str]:
    current = state.get("state")
    if current not in expected:
        return [f"{step} requires state {', '.join(sorted(expected))}; current state is {current}"]
    return []


def load_state(args: argparse.Namespace) -> tuple[Path, dict[str, Any] | None, list[str]]:
    path = state_path(args.issue_dir)
    try:
        return path, read_json(path), []
    except FileNotFoundError:
        return path, None, [f"{path} is missing"]
    except json.JSONDecodeError as exc:
        return path, None, [f"{path} is not valid JSON: {exc.msg}"]


def finish(path: Path, state: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    write_json(path, state)
    result: dict[str, Any] = {"ok": True, "path": str(path), "state": state}
    if extra:
        result.update(extra)
    return result


def fail(path: Path, state: dict[str, Any] | None, errors: list[str]) -> dict[str, Any]:
    return {"ok": False, "path": str(path), "state": state or {}, "errors": errors}


def init_state(args: argparse.Namespace) -> dict[str, Any]:
    state = {
        "issue": args.issue,
        "platform": args.platform,
        "repository": args.repository,
        "state": args.state,
        "branch": args.branch,
        "owner": {
            "kind": args.owner_kind,
            "id": args.owner_id,
        },
        "last_completed_step": "",
        "next_allowed_steps": NEXT_ALLOWED_STEPS[args.state],
        "evidence": default_evidence(),
        "metadata": {},
    }
    path = state_path(args.issue_dir)
    return finish(path, state)


def record_issue_prepare(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"issue-opened", "issue-clarifying"}, "gcw-issue-prepare")
    if errors:
        return fail(path, state, errors)
    evidence = state.setdefault("evidence", {})
    metadata = state.setdefault("metadata", {})
    evidence["issue_prepare_recorded"] = True
    if args.summary:
        evidence["issue_prepare_summary"] = args.summary
    if args.ready:
        metadata.pop("clarifying_question", None)
        set_state(state, "ready-for-planning", "gcw-issue-prepare")
    else:
        if not args.question:
            return fail(path, state, ["--question is required when --ready false"])
        metadata["clarifying_question"] = args.question
        set_state(state, "issue-clarifying", "gcw-issue-prepare")
    return finish(path, state)


def record_issue_to_spec(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"ready-for-planning"}, "gcw-issue-to-spec")
    missing = [name for name in PLANNING_FILES if not (args.issue_dir / name).is_file()]
    if missing:
        errors.append(f"missing planning files: {', '.join(missing)}")
    if not args.planning_commit_pushed:
        errors.append("planning commit is not pushed")
    if not args.progress_comment_url:
        errors.append("progress comment URL is required")
    if errors:
        return fail(path, state, errors)
    evidence = state.setdefault("evidence", {})
    evidence["planning_files_exist"] = True
    evidence["planning_commit_pushed"] = True
    evidence["progress_comment_url"] = args.progress_comment_url
    set_state(state, "planned", "gcw-issue-to-spec")
    return finish(path, state)


def record_spec_check(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"planned"}, "gcw-spec-check")
    if errors:
        return fail(path, state, errors)
    evidence = state.setdefault("evidence", {})
    metadata = state.setdefault("metadata", {})
    if args.result == "passed":
        evidence["spec_check_passed"] = True
        metadata.pop("clarifying_question", None)
        set_state(state, "ready-for-implementation", "gcw-spec-check")
    elif args.result == "clarifying":
        if not args.question:
            return fail(path, state, ["--question is required for clarifying result"])
        evidence["spec_check_passed"] = False
        metadata["clarifying_question"] = args.question
        set_state(state, "issue-clarifying", "gcw-spec-check")
    else:
        if args.reason:
            metadata["block_reason"] = args.reason
        evidence["spec_check_passed"] = False
        set_state(state, "blocked", "gcw-spec-check")
    return finish(path, state)


def record_implement(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(
        state,
        {"ready-for-implementation", "implementing", "changes-requested"},
        "gcw-implement",
    )
    if errors:
        return fail(path, state, errors)
    metadata = state.setdefault("metadata", {})
    if args.feedback_source:
        metadata["feedback_source"] = args.feedback_source
    set_state(state, "implementing", "gcw-implement")
    return finish(path, state)


def record_implement_check(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"implementing"}, "gcw-implement-check")
    if errors:
        return fail(path, state, errors)
    evidence = state.setdefault("evidence", {})
    metadata = state.setdefault("metadata", {})
    if args.passed:
        evidence["implement_check_passed"] = True
        evidence["self_review_recorded"] = True
        if args.readiness_evidence:
            evidence["readiness_evidence_path"] = args.readiness_evidence
        set_state(state, "ready-for-review", "gcw-implement-check")
    else:
        evidence["implement_check_passed"] = False
        if args.reason:
            metadata["implement_check_failure"] = args.reason
        set_state(state, "implementing", "gcw-implement-check")
    return finish(path, state)


def record_pr_publish(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"ready-for-review"}, "gcw-pr-publish")
    if not args.review_request_url:
        errors.append("--review-request-url is required")
    if errors:
        return fail(path, state, errors)
    state.setdefault("evidence", {})["review_request_url"] = args.review_request_url
    set_state(state, "reviewing", "gcw-pr-publish")
    return finish(path, state)


def record_pr_review(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"reviewing"}, "gcw-pr-review")
    if errors:
        return fail(path, state, errors)
    metadata = state.setdefault("metadata", {})
    if args.result == "passed":
        set_state(state, "reviewing", "gcw-pr-review")
    elif args.result == "changes-requested":
        metadata["feedback_source"] = args.feedback_source or "pr-review"
        set_state(state, "changes-requested", "gcw-pr-review")
    else:
        if args.reason:
            metadata["block_reason"] = args.reason
        set_state(state, "blocked", "gcw-pr-review")
    return finish(path, state)


def record_block(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    if state.get("state") == "review-complete":
        return fail(path, state, ["gcw-block cannot run after review-complete"])
    metadata = state.setdefault("metadata", {})
    metadata["block_reason"] = args.reason
    metadata["resume_state"] = args.resume_state or state.get("state", "")
    metadata["resume_step"] = args.resume_step or (state.get("next_allowed_steps") or [""])[0]
    set_state(state, "blocked", "gcw-block")
    return finish(path, state)


def record_clarify(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    if state.get("state") == "review-complete":
        return fail(path, state, ["gcw-clarify cannot run after review-complete"])
    metadata = state.setdefault("metadata", {})
    metadata["clarifying_question"] = args.question
    set_state(state, "issue-clarifying", "gcw-clarify")
    return finish(path, state)


def record_review_complete(args: argparse.Namespace) -> dict[str, Any]:
    path, state, errors = load_state(args)
    if errors or state is None:
        return fail(path, state, errors)
    errors = require_state(state, {"reviewing"}, "review-complete")
    if errors:
        return fail(path, state, errors)
    metadata = state.setdefault("metadata", {})
    metadata["review_result"] = args.result
    set_state(state, "review-complete", "review-complete")
    return finish(path, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage GCW state for the current workflow contract.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init-state")
    init.add_argument("--issue-dir", required=True, type=Path)
    init.add_argument("--issue", required=True)
    init.add_argument("--platform", required=True, choices=("github", "gitlab"))
    init.add_argument("--repository", required=True)
    init.add_argument("--branch", required=True)
    init.add_argument("--owner-kind", required=True, choices=("local", "github-actions", "gitlab-ci", "manual"))
    init.add_argument("--owner-id", required=True)
    init.add_argument("--state", choices=STATES, default="issue-opened")
    init.set_defaults(handler=init_state)

    prepare = subparsers.add_parser("record-issue-prepare")
    prepare.add_argument("--issue-dir", required=True, type=Path)
    prepare.add_argument("--ready", action="store_true")
    prepare.add_argument("--question", default="")
    prepare.add_argument("--summary", default="")
    prepare.set_defaults(handler=record_issue_prepare)

    to_spec = subparsers.add_parser("record-issue-to-spec")
    to_spec.add_argument("--issue-dir", required=True, type=Path)
    to_spec.add_argument("--progress-comment-url", required=True)
    to_spec.add_argument("--planning-commit-pushed", action="store_true")
    to_spec.set_defaults(handler=record_issue_to_spec)

    spec_check = subparsers.add_parser("record-spec-check")
    spec_check.add_argument("--issue-dir", required=True, type=Path)
    spec_check.add_argument("--result", required=True, choices=("passed", "clarifying", "blocked"))
    spec_check.add_argument("--question", default="")
    spec_check.add_argument("--reason", default="")
    spec_check.set_defaults(handler=record_spec_check)

    implement = subparsers.add_parser("record-implement")
    implement.add_argument("--issue-dir", required=True, type=Path)
    implement.add_argument("--feedback-source", choices=("pr-review", "human-review"), default="")
    implement.set_defaults(handler=record_implement)

    implement_check = subparsers.add_parser("record-implement-check")
    implement_check.add_argument("--issue-dir", required=True, type=Path)
    implement_check.add_argument("--passed", action="store_true")
    implement_check.add_argument("--readiness-evidence", default="")
    implement_check.add_argument("--reason", default="")
    implement_check.set_defaults(handler=record_implement_check)

    pr_publish = subparsers.add_parser("record-pr-publish")
    pr_publish.add_argument("--issue-dir", required=True, type=Path)
    pr_publish.add_argument("--review-request-url", required=True)
    pr_publish.set_defaults(handler=record_pr_publish)

    pr_review = subparsers.add_parser("record-pr-review")
    pr_review.add_argument("--issue-dir", required=True, type=Path)
    pr_review.add_argument("--result", required=True, choices=("passed", "changes-requested", "blocked"))
    pr_review.add_argument("--feedback-source", choices=("pr-review", "human-review"), default="pr-review")
    pr_review.add_argument("--reason", default="")
    pr_review.set_defaults(handler=record_pr_review)

    block = subparsers.add_parser("record-block")
    block.add_argument("--issue-dir", required=True, type=Path)
    block.add_argument("--reason", required=True)
    block.add_argument("--resume-state", default="")
    block.add_argument("--resume-step", default="")
    block.set_defaults(handler=record_block)

    clarify = subparsers.add_parser("record-clarify")
    clarify.add_argument("--issue-dir", required=True, type=Path)
    clarify.add_argument("--question", required=True)
    clarify.set_defaults(handler=record_clarify)

    complete = subparsers.add_parser("record-review-complete")
    complete.add_argument("--issue-dir", required=True, type=Path)
    complete.add_argument("--result", required=True, choices=("merged", "closed", "accepted", "rejected"))
    complete.set_defaults(handler=record_review_complete)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return emit(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
