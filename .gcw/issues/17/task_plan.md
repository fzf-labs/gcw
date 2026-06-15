# Plan — Issue #17: Local Agent vs Hosted Action Step Execution

## Goal

Prevent GCW hosted workflows from running unless the issue explicitly opts into hosted execution, and avoid re-running milestone steps already completed under a different executor context.

## Executor label policy (required)

Hosted GitHub Actions **must not run** unless the issue has label **`gcw:executor-hosted`**.

| Label | Meaning |
| --- | --- |
| `gcw:executor-hosted` | Issue opts into hosted Action execution; `gcw:run-*` triggers and PR-based auto-triggers may run (subject to phase gate). |
| `gcw:executor-local` | Issue is owned by local agent; **all** hosted workflows skip (including `pull_request: synchronize` and `gcw:run-*`). |
| (neither) | Default: treat as **local** — no hosted auto-execution until `gcw:executor-hosted` is applied. |

`gcw:run-*` labels remain **step triggers** (which step to run). They only take effect when `gcw:executor-hosted` is also present.

## Problem

- `prepare_gcw_hosted_step.py` gates on **phase only** (e.g. `reviewing` for `gcw-pr-review`).
- No check for `last_completed_step`, existing events, or `actor.kind`.
- Local agent recorded `gcw-pr-review` on issue #13; Action still ran, validated `pr-publish`, and failed.

## Phases

### Phase 0 — Executor labels and trigger gate

- [x] Add `gcw:executor-hosted` and `gcw:executor-local` to `labels.json` (mutually exclusive `executor` group); sync to GitHub.
- [x] `gcw_workflow_event.py`: `should_trigger=false` unless issue has `gcw:executor-hosted` (all event types including `pull_request` synchronize).
- [x] `prepare_gcw_hosted_step.py`: secondary check via `gh issue view` labels when event payload lacks labels.
- [x] Local intake/triage: apply `gcw:executor-local` by default when agent starts GCW locally.
- [x] Switching to hosted: human or agent replaces label with `gcw:executor-hosted` before applying any `gcw:run-*` trigger.

### Phase 1 — Idempotent hosted step gate

- [x] Extend `prepare_gcw_hosted_step.py` to skip when target step already completed or superseded.
- [x] Return `validate_command` / `skip_reason` / `run_mode` outputs for workflows to branch on.
- [x] Add tests in `test_gcw_hosted_workflows.py`.

### Phase 2 — `gcw-pr-review` reference implementation

- [x] When `gcw-pr-review` event exists with `result: passed` → run `review-check` only, skip record.
- [x] When fresh `reviewing` after `pr-publish` → validate `pr-publish`, then record with `actor.kind: github-actions`.
- [x] Update `gcw-pr-review.yml` to use gate outputs instead of hard-coded `pr-publish` validation.

### Phase 3 — Hosted actor kind

- [x] Ensure Action finalize / `run_gcw_step` paths record `actor.kind: github-actions` for hosted milestones.
- [x] Document: local agent uses `gcw:executor-local` and does not record hosted-only steps (`gcw-pr-review`) in normal flow.

### Phase 4 — Historical progress render fix

- [x] Fix `render_recorded_progress_comment` / `_render_reviewing` so later events do not leak into earlier milestone bodies.
- [x] Add regression test for pr-publish body hash validation after pr-review exists.

### Phase 5 — Documentation

- [x] Update `docs/hosted-agent.md` with local vs hosted ownership matrix.
- [x] Update `gcw-implement` / `gcw-pr-review` skill stop conditions.

## Acceptance Criteria

See issue #17 acceptance criteria (all items must pass).

## Out of Scope

- Rewriting all eight workflows beyond gate centralization hooks.
- GitLab CI equivalents in this issue.
