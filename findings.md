# GCW Remaining Requirements Findings

## Current State

- The repository has a completed local/checkable Phase 1 slice on top of `master`.
- `manage_gcw_state.py` writes local state, implementation gate, readiness evidence, blocked/clarifying records, self-review records, review request URLs, and ownership handoff.
- `validate_gcw_evidence.py` validates local state, implementation gate, and readiness evidence.
- `gcw_step.py` dispatches deterministic `check` mode and selected local `apply` mode operations.
- `.github/workflows/ci.yml` and `.gitlab-ci.yml` currently provide read-only CI evidence checks.

## Remaining Requirements

- Hosted apply workflows that can safely mutate branches, issue progress comments, state files, and review requests after ownership is explicit.
- Remote API verification for progress comments and PR/MR bodies against local evidence.
- Full GitLab write parity, beyond read-only CI checks.
- Cloud agent or `/fix` loop support if the repository exposes enough safe primitives for that path.
- End-to-end tests and fixtures covering allowed and rejected hosted ownership cases.

## Decisions

- Treat hosted runners as read-only checkers by default.
- Require `state.json.owner.kind` to match the hosted runner before any apply workflow writes state or hosted artifacts.
- Prefer deterministic local helpers that can be tested without credentials; hosted workflows should call those helpers.
- Do not perform real remote writes during local development without explicit approval.

## Codebase Discoveries

- `gcw_step.py` currently delegates `check` steps to `validate_gcw_evidence.py` and `apply` steps to `manage_gcw_state.py`, but it does not yet enforce runner ownership before apply mode.
- `manage_gcw_state.py` already has the local mutation primitives needed by hosted apply: implementation gate, readiness evidence, review request recording, blocked/clarifying, local self-review, and handoff.
- `validate_gcw_evidence.py` validates local files only. It does not yet compare hosted progress comment or PR/MR body text with `readiness_evidence.json`.
- `.github/workflows/ci.yml` and `.gitlab-ci.yml` currently run read-only validation jobs and deliberately avoid remote writes.
- The cleanest first implementation slice is an ownership gate in `gcw_step.py`, followed by an offline remote verification script that accepts fetched hosted text as input.
- `gcw_step.py` now supports ownership-gated apply mode through `--runner-kind`, defaulting to `local` for existing local usage.
- `verify_gcw_remote_evidence.py` now verifies fetched progress comment and review request body text against local `readiness_evidence.json`.
- `gcw_step.py` exposes remote verification through `remote-progress-comment` and `remote-review-request` check steps.
- `.github/workflows/gcw-hosted-apply.yml` provides a manual, owner-gated GitHub Actions apply path that can update state files, issue progress comments, review request bodies, and branch evidence.
- `.gitlab-ci.yml` now includes a manual, owner-gated `gcw:hosted-apply` job with GitLab API update hooks for issue notes and merge request descriptions.
- `render_gcw_hosted_artifacts.py` generates hosted progress comment and review request body content from local GCW evidence.
- No existing cloud coding agent or `/fix` execution primitive is present in the repository. The implemented path exposes the contracts such a runner must use instead of pretending to support autonomous code modification without a configured runner.

## Open Questions

- A future cloud coding agent integration must choose its actual runner, authentication model, and trigger shape before GCW can safely automate code changes in hosted CI.
