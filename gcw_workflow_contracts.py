from __future__ import annotations

MAIN_STEP_ORDER: tuple[str, ...] = (
    "gcw-issue-intake",
    "gcw-issue-triage",
    "gcw-issue-clarify",
    "gcw-issue-to-spec",
    "gcw-spec-check",
    "gcw-implement",
    "gcw-implement-check",
    "gcw-pr-publish",
    "gcw-pr-review",
)

STATES: tuple[str, ...] = (
    "issue-opened",
    "issue-triaged",
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

VALID_EVENT_NAMES = frozenset(
    {
        "gcw-issue-intake",
        "gcw-issue-triage",
        "gcw-issue-clarify",
        "gcw-issue-to-spec",
        "gcw-spec-check",
        "gcw-implement",
        "gcw-implement-check",
        "gcw-pr-publish",
        "gcw-pr-review",
        "gcw-block",
        "gcw-clarify",
        "review-complete",
    }
)

NEXT_ALLOWED_STEPS: dict[str, list[str]] = {
    "issue-opened": ["gcw-issue-triage"],
    "issue-triaged": ["gcw-issue-clarify"],
    "issue-clarifying": ["gcw-issue-clarify"],
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

PLANNING_FILES: tuple[str, ...] = ("task_plan.md", "findings.md", "progress.md")

STEP_TRIGGER_LABELS: dict[str, str] = {
    "gcw-issue-triage": "gcw:run-triage",
    "gcw-issue-clarify": "gcw:run-clarify",
    "gcw-issue-to-spec": "gcw:ready-for-planning",
    "gcw-spec-check": "gcw:run-spec-check",
    "gcw-implement": "gcw:run-implement",
    "gcw-implement-check": "gcw:run-implement-check",
    "gcw-pr-publish": "gcw:run-pr-publish",
    "gcw-pr-review": "gcw:run-pr-review",
}

HOSTED_STEP_PHASES: dict[str, tuple[str, ...]] = {
    "gcw-issue-triage": ("issue-opened",),
    "gcw-issue-clarify": ("issue-triaged", "issue-clarifying"),
    "gcw-issue-to-spec": ("ready-for-planning",),
    "gcw-spec-check": ("planned",),
    "gcw-implement": ("ready-for-implementation", "changes-requested", "implementing"),
    "gcw-implement-check": ("implementing",),
    "gcw-pr-publish": ("ready-for-review",),
    "gcw-pr-review": ("reviewing",),
}

VALIDATE_COMMANDS: dict[str, str] = {
    "gcw-spec-check": "spec-check",
    "gcw-implement-check": "implement-check",
    "gcw-pr-review": "review-check",
}

REPEATABLE_WHILE_PHASE: dict[str, tuple[str, ...]] = {
    "gcw-implement": ("implementing", "changes-requested", "ready-for-implementation"),
    "gcw-issue-clarify": ("issue-clarifying",),
}
