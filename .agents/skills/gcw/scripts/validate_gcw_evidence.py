from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")
VALID_STATES = {"planning", "clarifying", "implementing", "blocked", "ready-for-review"}
ALLOWED_NEXT_STEPS = {
    "planning": {"create-issue-worktree", "create-planning-files", "publish-planning", "implementation-gate"},
    "clarifying": set(),
    "implementing": {"implement", "local-self-review", "readiness-check", "create-review-request", "block", "clarify"},
    "blocked": set(),
    "ready-for-review": set(),
}


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{path.name} is missing")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} is not valid JSON: {exc.msg}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return data


def require_non_empty(data: dict[str, Any], path: str, errors: list[str]) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            errors.append(f"{path} is missing")
            return None
        current = current[part]
    if current in ("", None, [], {}):
        errors.append(f"{path} is empty")
    return current


def require_true(data: dict[str, Any], path: str, errors: list[str], message: str) -> None:
    current = require_non_empty(data, path, errors)
    if current is not True:
        errors.append(message)


def require_boolean(data: dict[str, Any], path: str, errors: list[str]) -> Any:
    current = require_non_empty(data, path, errors)
    if not isinstance(current, bool):
        errors.append(f"{path} must be a boolean")
    return current


def validate_planning_files(issue_dir: Path, errors: list[str]) -> None:
    for name in PLANNING_FILES:
        if not (issue_dir / name).is_file():
            errors.append(f"{name} is missing")


def validate_state(issue_dir: Path, errors: list[str]) -> dict[str, Any]:
    state = load_json(issue_dir / "state.json", errors)
    current_state = state.get("state")
    if current_state not in VALID_STATES:
        errors.append("state.json state is missing or invalid")
    require_non_empty(state, "issue", errors)
    require_non_empty(state, "branch", errors)
    require_non_empty(state, "owner.kind", errors)
    next_allowed_steps = state.get("next_allowed_steps")
    if not isinstance(next_allowed_steps, list):
        errors.append("next_allowed_steps must be an array")
    elif current_state in ALLOWED_NEXT_STEPS:
        unexpected_steps = sorted(set(next_allowed_steps) - ALLOWED_NEXT_STEPS[current_state])
        if unexpected_steps:
            errors.append(
                f"next_allowed_steps contains steps not allowed from {current_state}: {', '.join(unexpected_steps)}"
            )
    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    if current_state == "ready-for-review":
        if not isinstance(evidence, dict) or not evidence.get("review_request_url"):
            errors.append("ready-for-review requires state.json evidence.review_request_url")
        if state.get("last_completed_step") != "create-review-request":
            errors.append("ready-for-review requires last_completed_step create-review-request")
    return state


def validate_passing_gate_for_state(issue_dir: Path, errors: list[str]) -> None:
    gate = load_json(issue_dir / "implementation_gate_result.json", errors)
    if not gate:
        errors.append("implementing requires passing implementation_gate_result.json")
        return
    if gate.get("ok") is not True or gate.get("state_transition", {}).get("to") != "implementing":
        errors.append("implementing requires passing implementation_gate_result.json")


def validate_state_file(issue_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    state = validate_state(issue_dir, errors)
    if state.get("state") == "implementing":
        validate_passing_gate_for_state(issue_dir, errors)
    return {"step": "state", "ok": not errors, "errors": errors}


def validate_implementation_gate(issue_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    state = validate_state(issue_dir, errors)
    gate = load_json(issue_dir / "implementation_gate_result.json", errors)

    step = require_non_empty(gate, "step", errors)
    if step is not None and step != "implementation-gate":
        errors.append("implementation gate step is invalid")
    gate_ok = require_boolean(gate, "ok", errors)
    transition_from = require_non_empty(gate, "state_transition.from", errors)
    transition_to = require_non_empty(gate, "state_transition.to", errors)
    if transition_from not in {"planning", "implementing"}:
        errors.append("implementation gate transition source is invalid")
    if transition_to not in {"implementing", "clarifying", "blocked"}:
        errors.append("implementation gate transition target is invalid")
    if gate_ok is True and transition_to != "implementing":
        errors.append("passing implementation gate must transition to implementing")
    if gate_ok is False and transition_to not in {"clarifying", "blocked"}:
        errors.append("non-passing implementation gate must transition to clarifying or blocked")

    checks = gate.get("checks") if isinstance(gate.get("checks"), dict) else {}
    if not checks:
        errors.append("implementation gate checks are missing")
    else:
        for check_name in (
            "planning_files_exist",
            "planning_commit_pushed",
            "progress_comment_linked",
            "issue_actionable",
        ):
            require_boolean(checks, check_name, errors)
        if gate_ok is True:
            require_true(checks, "planning_files_exist", errors, "gate check planning_files_exist is not passing")
            require_true(checks, "planning_commit_pushed", errors, "gate check planning_commit_pushed is not passing")
            require_true(checks, "progress_comment_linked", errors, "gate check progress_comment_linked is not passing")
            require_true(checks, "issue_actionable", errors, "gate check issue_actionable is not passing")

    if gate_ok is True:
        validate_planning_files(issue_dir, errors)
        evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
        if not evidence:
            errors.append("state.json evidence is missing")
        else:
            require_true(evidence, "planning_files_exist", errors, "planning files are not marked as existing")
            require_true(evidence, "planning_commit_pushed", errors, "planning commit is not marked as pushed")
            require_non_empty(evidence, "progress_comment_url", errors)
    elif gate_ok is False:
        gate_errors = gate.get("errors")
        if not isinstance(gate_errors, list) or not gate_errors:
            errors.append("non-passing implementation gate requires errors")

    return {"step": "implementation-gate", "ok": not errors, "errors": errors}


def validate_readiness(issue_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    validate_planning_files(issue_dir, errors)
    state = validate_state(issue_dir, errors)
    if state.get("state") != "implementing":
        errors.append("readiness-check must leave state.json state as implementing")
    gate_result = validate_implementation_gate(issue_dir)
    if not gate_result["ok"]:
        errors.extend(f"implementation gate: {error}" for error in gate_result["errors"])
    gate_errors: list[str] = []
    gate = load_json(issue_dir / "implementation_gate_result.json", gate_errors)
    if gate.get("ok") is not True or gate.get("state_transition", {}).get("to") != "implementing":
        errors.append("readiness-check requires passing implementation gate")

    evidence = load_json(issue_dir / "readiness_evidence.json", errors)
    require_non_empty(evidence, "issue", errors)
    require_non_empty(evidence, "branch", errors)
    require_non_empty(evidence, "base_branch", errors)
    require_non_empty(evidence, "commit_range", errors)
    require_non_empty(evidence, "review_request.title", errors)
    require_non_empty(evidence, "review_request.summary", errors)
    require_non_empty(evidence, "review_request.issue_link", errors)
    require_non_empty(evidence, "validation", errors)
    require_true(evidence, "local_self_review.recorded", errors, "local self-review is not recorded")
    progress_section = require_non_empty(evidence, "local_self_review.progress_section", errors)
    require_non_empty(evidence, "planning_links.task_plan", errors)
    require_non_empty(evidence, "planning_links.findings", errors)
    require_non_empty(evidence, "planning_links.progress", errors)
    require_non_empty(evidence, "progress_comment_url", errors)
    require_non_empty(evidence, "risks", errors)

    progress_path = issue_dir / "progress.md"
    if progress_path.is_file() and isinstance(progress_section, str):
        progress_text = progress_path.read_text(encoding="utf-8")
        if progress_section not in progress_text:
            errors.append("local self-review progress section is not present in progress.md")

    return {"step": "readiness-check", "ok": not errors, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GCW issue workflow evidence.")
    parser.add_argument("command", choices=("state", "implementation-gate", "readiness-check"))
    parser.add_argument("--issue-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    issue_dir = args.issue_dir
    if args.command == "state":
        result = validate_state_file(issue_dir)
    elif args.command == "implementation-gate":
        result = validate_implementation_gate(issue_dir)
    else:
        result = validate_readiness(issue_dir)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
