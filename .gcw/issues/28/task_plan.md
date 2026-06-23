# Plan — Issue #28: Clarify skipped GCW runs in hosted docs

## Goal

Make skipped or no-op GCW hosted runs easier to diagnose by mapping each skip path to the exact gate (executor, phase, idempotent) in workflow logs and `docs/hosted-agent.md`, and document what to check first when `gh run list` shows `skipped`.

## Phases

### Phase 1 — Skip gate taxonomy

- [x] Add a shared classifier for `skip_reason` strings (`executor`, `phase`, `idempotent`, `infrastructure`).
- [x] Emit `skip_gate` from `prepare_gcw_hosted_step.py` alongside existing `skip_reason`.
- **Status:** complete

### Phase 2 — Workflow and CI logging

- [x] Replace bare `echo "$skip_reason"` in GitHub workflow `Report phase skip` steps with a structured summary script.
- [x] Update GitLab `.gitlab-ci.yml` skip path to print the classified gate and `skip_reason` from prepare output.
- **Status:** complete

### Phase 3 — Documentation

- [x] Expand `docs/hosted-agent.md` troubleshooting with a skip matrix (job-level `if` skip vs executor gate vs phase gate vs idempotent no-op).
- [x] Add a “check first” section for `gh run list` showing `skipped`.
- **Status:** complete

### Phase 4 — Tests and verification

- [x] Add or extend tests covering skip gate classification and summary wording.
- [ ] Run existing hosted workflow tests.
- **Status:** in_progress

## Acceptance Criteria

- [ ] `docs/hosted-agent.md` troubleshooting maps common skipped runs to the gate or condition that caused them.
- [ ] Hosted workflow logging or step summaries distinguish executor-gate skips from phase-gate no-ops and idempotent skips.
- [ ] Docs say what to check first when `gh run list` shows `skipped` for GCW workflows.
- [ ] Tests cover the skip/no-op reason wording or mapping.

## Out of Scope

- Changing when gates fire or relaxing executor/phase policy.
- Adding new trigger labels or workflow entrypoints.

## Risks

- GitHub Actions job-level `skipped` (workflow `if` false) is not visible to `prepare_gcw_hosted_step.py`; docs must call that out separately from in-job no-ops.
