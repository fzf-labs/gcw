# Plan — Issue #12: Hosted GCW Step Workflows

## Goal

Add GitHub Actions workflow files for the main GCW milestone steps so hosted automation can run the same validation scripts and progress-comment policy as local agents. Move GCW toward reliable repo / issue / PR handoff with remote gates.

## Phases

### Phase 1 — Shared workflow foundation

- [ ] Add a reusable composite action or shared workflow snippet for: checkout, Python setup, `gh` install (mirror `gcw-labels-sync.yml`), and common env (`GH_TOKEN`).
- [ ] Document least-privilege `permissions` defaults per step kind (read-only gate vs mutating).
- [ ] Add `workflow_dispatch` inputs: `issue_number`, `issue_branch`, `dry_run` (boolean).

### Phase 2 — Read-only gate workflows

- [ ] `gcw-spec-check.yml` — checkout issue branch, run `validate_gcw_evidence.py workflow` and `spec-check`, fail with actionable stderr.
- [ ] `gcw-implement-check.yml` — checkout issue branch, run `validate_gcw_evidence.py implement-check`.
- [ ] `gcw-pr-review.yml` — checkout PR head, run CI/static checks, `validate_gcw_evidence.py` review paths, optional AI review hook point.

### Phase 3 — Mutating milestone workflows

- [ ] `gcw-issue-to-spec.yml` — trigger agent or accept pre-generated spec on branch; push planning commit; run `run_gcw_step.py --step gcw-issue-to-spec`.
- [ ] `gcw-pr-publish.yml` — render PR body via `render_gcw_hosted_artifacts.py`, create/update PR idempotently, run `run_gcw_step.py --step gcw-pr-publish`.
- [ ] Mutating steps must call `publish_progress_comment.py` / `run_gcw_step.py` so each milestone posts a **new** `<!-- gcw-progress -->` comment.

### Phase 4 — Intake / clarify pipeline

- [ ] Resolve naming: issue body lists `gcw-issue-prepare`; contract uses `gcw-issue-triage` + `gcw-issue-clarify`. Implement either:
  - **Option A (preferred):** two workflows (`gcw-issue-triage.yml`, `gcw-issue-clarify.yml`) matching the contract table in `docs/workflow.md`.
  - **Option B:** one orchestration workflow `gcw-issue-prepare.yml` that chains triage then clarify via `workflow_call` or sequential jobs; document mapping in docs.
- [ ] `gcw-issue-triage.yml` — `manage_triage_metadata.py sync` + agent classification inputs; `run_gcw_step.py --step gcw-issue-triage`.
- [ ] `gcw-issue-clarify.yml` — `evaluate_issue_readiness.py`; `run_gcw_step.py --step gcw-issue-clarify`.

### Phase 5 — Tests and documentation

- [ ] Add tests or validation scripts that assert each workflow YAML contains required commands, inputs, and permission blocks.
- [ ] Update `docs/workflow.md`, `docs/quickstart.md`, and relevant `gcw-*` skill instructions: local-agent vs hosted-Action ownership per step.
- [ ] Note intentionally deferred workflows (e.g. `gcw-implement.yml` optional per contract) in spec/progress if not implemented in this issue.

## Acceptance Criteria (from issue)

- [ ] Workflow files for prepare/triage-clarify, to-spec, spec-check, implement-check, pr-publish, pr-review (or documented deferrals).
- [ ] Least-privilege `permissions`; read-only vs mutating separation.
- [ ] `workflow_dispatch` with issue number, branch, dry-run where applicable.
- [ ] Gate workflows run `validate_gcw_evidence.py` and fail with actionable output.
- [ ] Mutating workflows publish new progress comments per GCW policy.
- [ ] Tests/validation for YAML shape and required commands.
- [ ] Docs updated for local vs hosted ownership.

## Out of Scope

- `gcw-issue-intake` (no Action file per contract).
- Product/runtime features unrelated to GCW automation.
- GitLab CI equivalents (GitHub-only for this issue unless findings change).

## Implementation Notes

- Prefer thin workflow files delegating to `run_gcw_step.py` and existing scripts under `.agents/skills/gcw/scripts/`.
- Use `gcw-labels-sync.yml` as the reference for `gh` bootstrap and token usage.
- Branch checkout must use `issue_branch` input defaulting to `gcw/issue-<number>`.
