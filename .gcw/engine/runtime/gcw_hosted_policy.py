from __future__ import annotations

from pathlib import Path
from typing import Any

from gcw_workflow_contracts import HOSTED_STEP_PHASES, MAIN_STEP_ORDER, REPEATABLE_WHILE_PHASE, STEP_TRIGGER_LABELS, VALIDATE_COMMANDS
from gcw_workflow_store import find_latest_event


def step_rank(step: str) -> int | None:
    try:
        return MAIN_STEP_ORDER.index(step)
    except ValueError:
        return None


def trigger_label_for_step(step: str) -> str:
    return STEP_TRIGGER_LABELS.get(step, "")


def validate_command_for_step(step: str) -> str:
    return VALIDATE_COMMANDS.get(step, "")


def comment_requests_step(comment_body: str, agent_login: str, step: str) -> bool:
    body = (comment_body or "").lower()
    login = agent_login.strip().lstrip("@").lower()
    if not login:
        return False
    return f"@{login}" in body and f"/gcw {step.removeprefix('gcw-')}" in body


def should_run_event(step: str, event: dict[str, Any], agent_login: str) -> tuple[bool, str]:
    if event.get("pull_request") is not None:
        return False, "issue event is a pull request"

    trigger_label = trigger_label_for_step(step)
    event_name = str(event.get("event_name", ""))
    action = str(event.get("action", ""))
    issue = event.get("issue") if isinstance(event.get("issue"), dict) else {}
    labels = [str(label.get("name", "")).strip() for label in issue.get("labels", []) if isinstance(label, dict)]
    assignees = [str(assignee.get("login", "")).strip() for assignee in issue.get("assignees", []) if isinstance(assignee, dict)]
    agent = agent_login.strip().lstrip("@")

    if event_name == "issues" and action == "labeled":
        label = event.get("label") if isinstance(event.get("label"), dict) else {}
        label_name = str(label.get("name", "")).strip()
        if label_name == trigger_label:
            if agent and agent not in assignees:
                return False, f"issue not assigned to agent {agent}"
            return True, f"labeled {trigger_label}"
        return False, f"ignored label {label_name!r}"

    if event_name == "issues" and action == "assigned":
        assignee = event.get("assignee") if isinstance(event.get("assignee"), dict) else {}
        login = str(assignee.get("login", "")).strip()
        if agent and login == agent and trigger_label in labels:
            return True, f"assigned to {agent} with {trigger_label}"
        return False, "assignment does not match agent trigger contract"

    if event_name == "issue_comment" and action == "created":
        comment = event.get("comment") if isinstance(event.get("comment"), dict) else {}
        body = str(comment.get("body", ""))
        if comment_requests_step(body, agent_login, step) and trigger_label in labels:
            return True, "comment requests step"
        return False, "comment does not match agent trigger contract"

    return False, f"unsupported event {event_name}:{action}"


def _idempotent_decision(step: str, projection: dict[str, Any], issue_dir: Path) -> dict[str, str | bool]:
    last = str(projection.get("last_completed_step", "")).strip()
    phase = str(projection.get("phase", "")).strip()
    current_rank = step_rank(step)
    last_rank = step_rank(last) if last else None

    if step == "gcw-pr-review":
        pr_review = find_latest_event(issue_dir, "gcw-pr-review")
        result = ""
        if pr_review:
            result = str(pr_review.get("payload", {}).get("result", "")).strip().lower()
        if result == "passed":
            return {
                "should_run": True,
                "skip_reason": "",
                "run_mode": "verify-only",
                "record_step": False,
                "validate_command": "review-check",
            }

    if last == step:
        repeatable_phases = REPEATABLE_WHILE_PHASE.get(step, ())
        if phase not in repeatable_phases:
            return {
                "should_run": False,
                "skip_reason": f"{step} already completed",
                "run_mode": "skip",
                "record_step": False,
                "validate_command": validate_command_for_step(step),
            }

    if current_rank is not None and last_rank is not None and last_rank > current_rank:
        return {
            "should_run": False,
            "skip_reason": f"superseded by {last}",
            "run_mode": "skip",
            "record_step": False,
            "validate_command": validate_command_for_step(step),
        }

    validate_command = validate_command_for_step(step)
    return {
        "should_run": True,
        "skip_reason": "",
        "run_mode": "full",
        "record_step": True,
        "validate_command": validate_command,
    }


def prepare_hosted_step(
    step: str,
    projection: dict[str, Any],
    issue_dir: Path,
) -> dict[str, str | bool]:
    expected = HOSTED_STEP_PHASES.get(step)
    if expected is None:
        raise ValueError(f"unsupported hosted step: {step}")
    phase = str(projection.get("phase", "")).strip()
    idempotent = _idempotent_decision(step, projection, issue_dir)
    if not idempotent["should_run"] and idempotent.get("skip_reason"):
        return idempotent | {
            "phase": phase,
        }
    if phase not in expected:
        allowed_phases = ", ".join(expected)
        return {
            "should_run": False,
            "skip_reason": f"phase {phase!r} is not in [{allowed_phases}] for {step}",
            "run_mode": str(idempotent["run_mode"]),
            "record_step": bool(idempotent["record_step"]),
            "validate_command": str(idempotent["validate_command"]),
            "phase": phase,
        }
    return {
        "should_run": bool(idempotent["should_run"]),
        "skip_reason": str(idempotent["skip_reason"]),
        "run_mode": str(idempotent["run_mode"]),
        "record_step": bool(idempotent["record_step"]),
        "validate_command": str(idempotent["validate_command"]),
        "phase": phase,
    }
