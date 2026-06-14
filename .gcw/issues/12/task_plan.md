# Plan — Issue #12: Hosted GCW Step Workflows

## Goal

Add GitHub Actions workflow files for **all GCW main steps 2–9** (`gcw-issue-triage` through `gcw-pr-review`) so hosted automation can run or verify each milestone using the same local evidence and validation scripts as a local agent. Move GCW toward reliable repo / issue / PR handoff with remote gates.

Step 1 (`gcw-issue-intake`) remains local/human only — no Action file.

## Target Workflows (steps 2–9)

| Step | Workflow file | Kind |
| --- | --- | --- |
| 2 | `gcw-issue-triage.yml` | mutating |
| 3 | `gcw-issue-clarify.yml` | mutating |
| 4 | `gcw-issue-to-spec.yml` | mutating |
| 5 | `gcw-spec-check.yml` | read-only gate |
| 6 | `gcw-implement.yml` | mutating |
| 7 | `gcw-implement-check.yml` | read-only gate |
| 8 | `gcw-pr-publish.yml` | mutating |
| 9 | `gcw-pr-review.yml` | read-only gate (+ CI) |

## Phases

### Phase 1 — Shared workflow foundation

- [ ] Add a reusable composite action or shared workflow snippet for: checkout, Python setup, `gh` install (mirror `gcw-labels-sync.yml`), and common env (`GH_TOKEN`).
- [ ] Document least-privilege `permissions` defaults per step kind (read-only gate vs mutating).
- [ ] Add `workflow_dispatch` inputs: `issue_number`, `issue_branch`, `dry_run` (boolean).

### Phase 2 — Read-only gate workflows (steps 5, 7, 9)

- [ ] `gcw-spec-check.yml` — checkout issue branch, run `validate_gcw_evidence.py workflow` and `spec-check`, fail with actionable stderr.
- [ ] `gcw-implement-check.yml` — checkout issue branch, run `validate_gcw_evidence.py implement-check`.
- [ ] `gcw-pr-review.yml` — checkout PR head, run CI/static checks, `validate_gcw_evidence.py` review paths, optional AI review hook point.

### Phase 3 — Mutating milestone workflows (steps 4, 6, 8)

- [ ] `gcw-issue-to-spec.yml` — trigger agent or accept pre-generated spec on branch; push planning commit; run `run_gcw_step.py --step gcw-issue-to-spec`.
- [ ] `gcw-implement.yml` — record an implementation advance on the issue branch:
  - Support **local-agent handoff** (default): checkout issue branch, verify spec/refs, publish progress comment, call `manage_gcw_workflow.py record-implement` with `work_summary` input.
  - Support **optional in-runner agent** hook (documented extension point; not required to embed an LLM in v1).
  - Inputs: `issue_number`, `issue_branch`, `work_summary`, `dry_run`, optional `feedback_source` / `feedback_ref` when resuming from `changes-requested`.
- [ ] `gcw-pr-publish.yml` — render PR body via `render_gcw_hosted_artifacts.py`, create/update PR idempotently, run `run_gcw_step.py --step gcw-pr-publish`.
- [ ] Mutating steps must call `publish_progress_comment.py` / `run_gcw_step.py` (or equivalent for `record-implement`) so each milestone posts a **new** `<!-- gcw-progress -->` comment.

### Phase 4 — Triage / clarify pipeline (steps 2, 3)

- [ ] Implement as **two separate workflows** aligned with `docs/workflow.md` (not a single `gcw-issue-prepare` orchestrator).
- [ ] `gcw-issue-triage.yml` — `manage_triage_metadata.py sync` + classification inputs; `run_gcw_step.py --step gcw-issue-triage`.
- [ ] `gcw-issue-clarify.yml` — `evaluate_issue_readiness.py`; `run_gcw_step.py --step gcw-issue-clarify`.

### Phase 5 — Tests and documentation

- [ ] Add tests or validation scripts that assert **all eight** workflow YAML files exist and contain required commands, inputs, and permission blocks.
- [ ] Update `docs/workflow.md`, `docs/quickstart.md`, and relevant `gcw-*` skill instructions: local-agent vs hosted-Action ownership per step (steps 2–9 all have hosted entrypoints).
- [ ] Document `gcw-implement.yml` handoff model (local agent commits code; Action records event + progress comment).

## Acceptance Criteria

- [ ] GitHub workflow files for **all steps 2–9**: `gcw-issue-triage`, `gcw-issue-clarify`, `gcw-issue-to-spec`, `gcw-spec-check`, `gcw-implement`, `gcw-implement-check`, `gcw-pr-publish`, `gcw-pr-review`.
- [ ] Least-privilege `permissions`; read-only vs mutating separation.
- [ ] `workflow_dispatch` with issue number, issue branch, dry-run where applicable.
- [ ] Gate workflows run `validate_gcw_evidence.py` and fail with actionable output.
- [ ] Mutating workflows publish new progress comments per GCW policy.
- [ ] Tests/validation for YAML shape and required commands (covering all eight files).
- [ ] Docs updated for local vs hosted ownership across steps 2–9.

## Out of Scope

- `gcw-issue-intake` (step 1; no Action file per contract).
- Product/runtime features unrelated to GCW automation.
- GitLab CI equivalents (GitHub-only for this issue unless findings change).
- Embedding a specific LLM provider inside `gcw-implement.yml` (handoff + extension point only).

## Implementation Notes

- Prefer thin workflow files delegating to `run_gcw_step.py` and existing scripts under `.agents/skills/gcw/scripts/`.
- `gcw-implement` is not in `run_gcw_step.py` today; use `manage_gcw_workflow.py record-implement` + `publish_progress_comment.py`, or extend `run_gcw_step.py` if that keeps workflows thinner.
- Use `gcw-labels-sync.yml` as the reference for `gh` bootstrap and token usage.
- Branch checkout must use `issue_branch` input defaulting to `gcw/issue-<number>`.
