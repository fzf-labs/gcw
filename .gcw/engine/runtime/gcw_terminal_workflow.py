from __future__ import annotations

from dataclasses import dataclass
from typing import Any


HUMAN_REVIEW_REQUIRED_STATES: tuple[str, ...] = (
    "planned",
    "issue-clarifying",
    "blocked",
    "reviewing",
    "review-complete",
)


def human_handoff_reason(phase: str) -> str:
    if phase == "planned":
        return "Waiting for human spec review before gcw-spec-check."
    if phase == "issue-clarifying":
        return "Waiting for issue clarification before GCW can continue."
    if phase == "blocked":
        return "Workflow is blocked and needs human intervention."
    if phase == "reviewing":
        return "Waiting for hosted or human review after review request publication."
    if phase == "review-complete":
        return "Workflow is complete."
    return ""


def should_stop_for_human_handoff(phase: str) -> bool:
    return phase in HUMAN_REVIEW_REQUIRED_STATES


def has_meaningful_implementation_changes(changed_paths: list[str], issue_dir: str) -> bool:
    issue_root = issue_dir.rstrip("/")
    issue_prefix = f"{issue_root}/"
    for path in changed_paths:
        if not path:
            continue
        if path.startswith(issue_prefix):
            continue
        if path.startswith(".gcw-runtime"):
            continue
        return True
    return False


def select_next_run_step(projection: dict[str, Any], changed_paths: list[str], issue_dir: str) -> str | None:
    next_steps = projection.get("next_allowed_steps") or []
    if not next_steps:
        return None

    if projection.get("phase") == "implementing" and "gcw-implement-check" in next_steps:
        return "gcw-implement-check"

    next_step = next_steps[0]
    if next_step == "gcw-implement" and not has_meaningful_implementation_changes(changed_paths, issue_dir):
        return None
    return next_step


@dataclass(frozen=True)
class WorkflowSummary:
    issue: str
    phase: str
    last_completed_step: str
    next_allowed_steps: list[str]
    stop_reason: str = ""
