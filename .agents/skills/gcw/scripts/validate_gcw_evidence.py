from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")
VALID_STATES = {
    "issue-opened",
    "issue-triaging",
    "issue-clarifying",
    "ready-for-planning",
    "planning",
    "planned",
    "ready-for-implementation",
    "implementing",
    "ready-for-review-request",
    "ready-for-review",
    "machine-reviewing",
    "machine-review-failed",
    "human-reviewing",
    "changes-requested",
    "approved",
    "blocked",
    "review-complete",
}
ALLOWED_NEXT_STEPS = {
    "issue-opened": {"triage-issue"},
    "issue-triaging": {"discuss-issue", "mark-issue-actionable"},
    "issue-clarifying": {"discuss-issue", "mark-issue-actionable"},
    "ready-for-planning": {"create-issue-worktree", "create-planning-files"},
    "planning": {"publish-planning"},
    "planned": {"implementation-gate"},
    "ready-for-implementation": {"implement"},
    "implementing": {"implement", "local-self-review", "readiness-check", "block", "clarify"},
    "ready-for-review-request": {"create-review-request"},
    "ready-for-review": {"machine-review-start"},
    "machine-reviewing": {"machine-review-result"},
    "machine-review-failed": {"address-machine-feedback", "block", "clarify"},
    "human-reviewing": {"human-review-result"},
    "changes-requested": {"address-human-feedback"},
    "approved": {"review-complete", "implement"},
    "blocked": set(),
    "review-complete": set(),
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


def require_string(data: dict[str, Any], path: str, errors: list[str], *, allow_empty: bool = False) -> str | None:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            errors.append(f"{path} is missing")
            return None
        current = current[part]
    if not isinstance(current, str):
        errors.append(f"{path} must be a string")
        return None
    if not allow_empty and current == "":
        errors.append(f"{path} is empty")
    return current


def require_issue_identifier(data: dict[str, Any], path: str, errors: list[str]) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            errors.append(f"{path} is missing")
            return None
        current = current[part]
    if type(current) is int:
        return current
    if isinstance(current, str):
        if current == "":
            errors.append(f"{path} is empty")
            return None
        return current
    errors.append(f"{path} must be an integer or a non-empty string")
    return None


def require_string_enum(
    data: dict[str, Any],
    path: str,
    allowed: set[str],
    errors: list[str],
    *,
    allow_empty: bool = False,
) -> str | None:
    current = require_string(data, path, errors, allow_empty=allow_empty)
    if current is None:
        return None
    if current not in allowed:
        errors.append(f"{path} must be one of: {', '.join(sorted(allowed))}")
    return current


def require_string_list(data: dict[str, Any], path: str, errors: list[str]) -> list[str] | None:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            errors.append(f"{path} is missing")
            return None
        current = current[part]
    if not isinstance(current, list):
        errors.append(f"{path} must be an array")
        return None
    for item in current:
        if not isinstance(item, str):
            errors.append(f"{path} items must be strings")
            return None
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


def require_last_completed_step(state_name: str, state: dict[str, Any], expected: str, errors: list[str]) -> None:
    actual = state.get("last_completed_step")
    if expected == "":
        if actual != "":
            errors.append(f"{state_name} requires last_completed_step to be empty")
        return
    if actual != expected:
        errors.append(f"{state_name} requires last_completed_step {expected}")


def require_next_allowed_steps_include(
    state_name: str,
    state: dict[str, Any],
    expected_steps: list[str],
    errors: list[str],
) -> None:
    actual = state.get("next_allowed_steps")
    if not isinstance(actual, list):
        return
    missing = [step for step in expected_steps if step not in actual]
    if missing:
        if len(expected_steps) == 1:
            errors.append(f"{state_name} requires next_allowed_steps to include {expected_steps[0]}")
        else:
            errors.append(
                f"{state_name} requires next_allowed_steps to include {', '.join(expected_steps)}"
            )


def validate_planning_files(issue_dir: Path, errors: list[str]) -> None:
    for name in PLANNING_FILES:
        if not (issue_dir / name).is_file():
            errors.append(f"{name} is missing")


def validate_state(issue_dir: Path, errors: list[str]) -> dict[str, Any]:
    state = load_json(issue_dir / "state.json", errors)
    require_issue_identifier(state, "issue", errors)
    require_string_enum(state, "platform", {"github", "gitlab"}, errors)
    require_string(state, "repository", errors)
    require_string(state, "branch", errors)
    require_string_enum(state, "owner.kind", {"local", "github-actions", "gitlab-ci", "manual"}, errors)
    require_string(state, "owner.id", errors)
    require_string(state, "last_completed_step", errors, allow_empty=True)
    require_string_list(state, "next_allowed_steps", errors)
    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    require_boolean(evidence, "planning_files_exist", errors)
    require_boolean(evidence, "planning_commit_pushed", errors)
    require_string(evidence, "progress_comment_url", errors, allow_empty=True)
    require_boolean(evidence, "self_review_recorded", errors)
    require_string(evidence, "review_request_url", errors, allow_empty=True)
    current_state = state.get("state")
    if current_state not in VALID_STATES:
        errors.append("state.json state is missing or invalid")
    next_allowed_steps = state.get("next_allowed_steps")
    if isinstance(next_allowed_steps, list) and current_state in ALLOWED_NEXT_STEPS:
        unexpected_steps = sorted(set(next_allowed_steps) - ALLOWED_NEXT_STEPS[current_state])
        if unexpected_steps:
            errors.append(
                f"next_allowed_steps contains steps not allowed from {current_state}: {', '.join(unexpected_steps)}"
            )
    if current_state == "issue-opened":
        require_last_completed_step("issue-opened", state, "", errors)
        require_next_allowed_steps_include("issue-opened", state, ["triage-issue"], errors)
    if current_state == "issue-triaging":
        require_last_completed_step("issue-triaging", state, "triage-issue", errors)
        require_next_allowed_steps_include(
            "issue-triaging",
            state,
            ["discuss-issue", "mark-issue-actionable"],
            errors,
        )
    if current_state == "ready-for-planning":
        require_last_completed_step("ready-for-planning", state, "mark-issue-actionable", errors)
        require_next_allowed_steps_include(
            "ready-for-planning",
            state,
            ["create-issue-worktree", "create-planning-files"],
            errors,
        )
    if current_state == "planning":
        require_next_allowed_steps_include("planning", state, ["publish-planning"], errors)
    if current_state == "planned":
        validate_planning_files(issue_dir, errors)
        require_last_completed_step("planned", state, "publish-planning", errors)
        require_next_allowed_steps_include("planned", state, ["implementation-gate"], errors)
        require_true(evidence, "planning_files_exist", errors, "planned requires evidence.planning_files_exist")
        require_true(evidence, "planning_commit_pushed", errors, "planned requires evidence.planning_commit_pushed")
        require_non_empty(evidence, "progress_comment_url", errors)
    if current_state == "ready-for-implementation":
        require_last_completed_step("ready-for-implementation", state, "implementation-gate", errors)
        require_next_allowed_steps_include("ready-for-implementation", state, ["implement"], errors)
    if current_state == "ready-for-review-request":
        if not (issue_dir / "readiness_evidence.json").is_file():
            errors.append("ready-for-review-request requires readiness_evidence.json")
        require_last_completed_step("ready-for-review-request", state, "readiness-check", errors)
        require_next_allowed_steps_include("ready-for-review-request", state, ["create-review-request"], errors)
    if current_state == "ready-for-review":
        if not (issue_dir / "readiness_evidence.json").is_file():
            errors.append("ready-for-review requires readiness_evidence.json")
        if not isinstance(evidence, dict) or not evidence.get("review_request_url"):
            errors.append("ready-for-review requires state.json evidence.review_request_url")
        require_last_completed_step("ready-for-review", state, "create-review-request", errors)
        require_next_allowed_steps_include("ready-for-review", state, ["machine-review-start"], errors)
    if current_state in {"machine-reviewing", "machine-review-failed", "human-reviewing", "changes-requested", "approved", "review-complete"}:
        if not (issue_dir / "readiness_evidence.json").is_file():
            errors.append(f"{current_state} requires readiness_evidence.json")
        if not isinstance(evidence, dict) or not evidence.get("review_request_url"):
            errors.append(f"{current_state} requires state.json evidence.review_request_url")
    if current_state == "machine-reviewing":
        require_last_completed_step("machine-reviewing", state, "machine-review-start", errors)
        require_next_allowed_steps_include("machine-reviewing", state, ["machine-review-result"], errors)
    if current_state == "machine-review-failed":
        require_last_completed_step("machine-review-failed", state, "machine-review-result", errors)
        require_next_allowed_steps_include(
            "machine-review-failed",
            state,
            ["address-machine-feedback", "block", "clarify"],
            errors,
        )
    if current_state == "human-reviewing":
        require_last_completed_step("human-reviewing", state, "machine-review-result", errors)
        require_next_allowed_steps_include("human-reviewing", state, ["human-review-result"], errors)
    if current_state == "changes-requested":
        require_last_completed_step("changes-requested", state, "human-review-result", errors)
        require_next_allowed_steps_include("changes-requested", state, ["address-human-feedback"], errors)
    if current_state == "approved":
        require_last_completed_step("approved", state, "human-review-result", errors)
        require_next_allowed_steps_include("approved", state, ["review-complete", "implement"], errors)
    if current_state == "review-complete":
        require_last_completed_step("review-complete", state, "review-complete", errors)
        if not isinstance(evidence, dict) or not evidence.get("review_complete_result"):
            errors.append("review-complete requires state.json evidence.review_complete_result")
        if isinstance(next_allowed_steps, list) and next_allowed_steps:
            errors.append("review-complete requires next_allowed_steps to be empty")
    return state


def validate_passing_gate_for_state(issue_dir: Path, errors: list[str]) -> None:
    gate = load_json(issue_dir / "implementation_gate_result.json", errors)
    if not gate:
        errors.append("implementing requires passing implementation_gate_result.json")
        return
    if gate.get("ok") is not True or gate.get("state_transition", {}).get("to") != "ready-for-implementation":
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
    if transition_from != "planned":
        errors.append("implementation gate transition source is invalid")
    if transition_to not in {"ready-for-implementation", "issue-clarifying", "blocked"}:
        errors.append("implementation gate transition target is invalid")
    if gate_ok is True and transition_to != "ready-for-implementation":
        errors.append("passing implementation gate must transition to ready-for-implementation")
    if gate_ok is False and transition_to not in {"issue-clarifying", "blocked"}:
        errors.append("non-passing implementation gate must transition to issue-clarifying or blocked")
    if state.get("state") == "planned":
        errors.append("implementation gate requires state.json state to advance beyond planned")

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


def validate_readiness(issue_dir: Path, step_name: str = "readiness-check") -> dict[str, Any]:
    errors: list[str] = []
    validate_planning_files(issue_dir, errors)
    state = validate_state(issue_dir, errors)
    if state.get("state") != "ready-for-review-request":
        errors.append(f"{step_name} must leave state.json state as ready-for-review-request")
    gate_result = validate_implementation_gate(issue_dir)
    if not gate_result["ok"]:
        errors.extend(f"implementation gate: {error}" for error in gate_result["errors"])
    gate_errors: list[str] = []
    gate = load_json(issue_dir / "implementation_gate_result.json", gate_errors)
    if gate.get("ok") is not True or gate.get("state_transition", {}).get("to") != "ready-for-implementation":
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

    return {"step": step_name, "ok": not errors, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GCW issue workflow evidence.")
    parser.add_argument("command", choices=("state", "implementation-gate", "readiness-check", "create-review-request"))
    parser.add_argument("--issue-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    issue_dir = args.issue_dir
    if args.command == "state":
        result = validate_state_file(issue_dir)
    elif args.command == "implementation-gate":
        result = validate_implementation_gate(issue_dir)
    else:
        result = validate_readiness(issue_dir, step_name=args.command)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
