# Plan — Issue #17: Local Agent vs Hosted Action Step Execution

## Goal

Prevent GCW hosted workflows from re-running milestone steps that were already completed by a local agent (or vice versa), and ensure validation/rendering logic matches the executor context.

## Problem

- `prepare_gcw_hosted_step.py` gates on **phase only** (e.g. `reviewing` for `gcw-pr-review`).
- No check for `last_completed_step`, existing events, or `actor.kind`.
- Local agent recorded `gcw-pr-review` on issue #13; Action still ran, validated `pr-publish`, and failed.

## Phases

### Phase 1 — Idempotent hosted step gate

- [ ] Extend `prepare_gcw_hosted_step.py` to skip when target step already completed or superseded.
- [ ] Return `validate_command` / `skip_reason` / `run_mode` outputs for workflows to branch on.
- [ ] Add tests in `test_gcw_hosted_workflows.py`.

### Phase 2 — `gcw-pr-review` reference implementation

- [ ] When `gcw-pr-review` event exists with `result: passed` → run `review-check` only, skip record.
- [ ] When fresh `reviewing` after `pr-publish` → validate `pr-publish`, then record with `actor.kind: github-actions`.
- [ ] Update `gcw-pr-review.yml` to use gate outputs instead of hard-coded `pr-publish` validation.

### Phase 3 — Hosted actor kind

- [ ] Ensure Action finalize / `run_gcw_step` paths record `actor.kind: github-actions` for hosted milestones.
- [ ] Document local agent must not record hosted-only steps (`gcw-pr-review`) in normal flow.

### Phase 4 — Historical progress render fix

- [ ] Fix `render_recorded_progress_comment` / `_render_reviewing` so later events do not leak into earlier milestone bodies.
- [ ] Add regression test for pr-publish body hash validation after pr-review exists.

### Phase 5 — Documentation

- [ ] Update `docs/hosted-agent.md` with local vs hosted ownership matrix.
- [ ] Update `gcw-implement` / `gcw-pr-review` skill stop conditions.

## Acceptance Criteria

See issue #17 acceptance criteria (all items must pass).

## Out of Scope

- Rewriting all eight workflows beyond gate centralization hooks.
- GitLab CI equivalents in this issue.
