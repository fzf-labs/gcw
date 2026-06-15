# Findings — Issue #12

## Current State

- Only hosted workflow today: `.github/workflows/gcw-labels-sync.yml` (label sync on `workflow_dispatch`, `contents: read`).
- Unified step runner: `.agents/skills/gcw/scripts/run_gcw_step.py` supports triage, clarify, to-spec, spec-check, implement-check, pr-publish, pr-review — **not** `gcw-implement`.
- Implement event recording: `manage_gcw_workflow.py record-implement` with `--work-summary` and optional `--feedback-source`.
- Validation entrypoints: `validate_gcw_evidence.py` with subcommands `workflow`, `spec-check`, `implement-check`, etc.
- Progress comments: `publish_progress_comment.py` + `<!-- gcw-progress -->` marker; events store `progress_comment_body_hash`.
- PR rendering: `render_gcw_hosted_artifacts.py` consumes event log under `.gcw/issues/<id>/`.

## Scope Decision (updated)

**Implement all hosted steps 2–9**, including `gcw-implement.yml` (step 6). Previously the spec treated step 6 as optional/deferred; scope is now expanded to match full contract coverage except step 1.

| Step | Workflow | In scope |
| --- | --- | --- |
| 2 | `gcw-issue-triage.yml` | yes |
| 3 | `gcw-issue-clarify.yml` | yes |
| 4 | `gcw-issue-to-spec.yml` | yes |
| 5 | `gcw-spec-check.yml` | yes |
| 6 | `gcw-implement.yml` | yes |
| 7 | `gcw-implement-check.yml` | yes |
| 8 | `gcw-pr-publish.yml` | yes |
| 9 | `gcw-pr-review.yml` | yes |

**Naming:** use separate `gcw-issue-triage.yml` + `gcw-issue-clarify.yml` (contract-aligned), not a single `gcw-issue-prepare.yml` orchestrator.

## `gcw-implement.yml` Design

- **Primary mode — local-agent handoff:** developer/agent pushes implementation commits to the issue branch; workflow verifies branch state, publishes progress comment, records `gcw-implement` event with supplied `work_summary`.
- **Does not** require running codegen inside GitHub Actions in v1.
- **Optional later:** workflow input or reusable job to invoke an in-runner agent; document as extension point only.
- May need a small `run_gcw_step.py` extension to include `gcw-implement` for consistency with other mutating steps.

## Permission Model (draft)

| Step kind | Workflows | Suggested `permissions` |
| --- | --- | --- |
| Read-only gates | spec-check, implement-check, pr-review | `contents: read` |
| Issue mutating | triage, clarify, to-spec, implement | `contents: write`, `issues: write` |
| PR mutating | pr-publish | `contents: write`, `issues: write`, `pull-requests: write` |
| Labels sync (existing) | gcw-labels-sync | `contents: read` |

Mutating workflows should use `dry_run` input to avoid accidental remote writes during testing.

## Risks

- **Token scope:** `GITHUB_TOKEN` may lack Issue Type / Priority field APIs; triage workflow may need `issues: write` and documented org settings.
- **Branch checkout:** all workflows must fetch the issue branch (`gcw/issue-<n>`), not default `GITHUB_REF`.
- **Implement without runner LLM:** hosted `gcw-implement` records milestones but does not replace local coding; docs must state the handoff clearly.
- **Runner gap:** `run_gcw_step.py` lacks `gcw-implement`; implement workflow may call lower-level scripts until unified.

## References

- Issue: https://github.com/fzf-labs/gcw/issues/12
- Workflow contract: `docs/workflow.md`
- Example progress flow: `docs/quickstart.md`
- Test fixture with complete event chain: `.agents/skills/gcw/tests/fixtures/complete_issue/`
