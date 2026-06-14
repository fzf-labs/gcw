# Findings — Issue #12

## Current State

- Only hosted workflow today: `.github/workflows/gcw-labels-sync.yml` (label sync on `workflow_dispatch`, `contents: read`).
- Unified step runner exists: `.agents/skills/gcw/scripts/run_gcw_step.py` supports triage, clarify, to-spec, spec-check, implement-check, pr-publish, pr-review.
- Validation entrypoints: `validate_gcw_evidence.py` with subcommands `workflow`, `spec-check`, `implement-check`, etc.
- Progress comments: `publish_progress_comment.py` + `<!-- gcw-progress -->` marker; events store `progress_comment_body_hash`.
- PR rendering: `render_gcw_hosted_artifacts.py` consumes event log under `.gcw/issues/<id>/`.

## Contract vs Issue Wording

| Issue body | `docs/workflow.md` contract |
| --- | --- |
| `gcw-issue-prepare` | `gcw-issue-triage.yml` + `gcw-issue-clarify.yml` (pipeline name "接入、分类与澄清") |
| Lists 6 workflow files | Table names 8 Action files; `gcw-issue-intake` explicitly has no workflow |
| `gcw-implement` not listed | Optional per contract (`gcw-implement.yml` may be deferred) |

**Decision for spec:** implement triage and clarify as separate workflows (contract-aligned). If a single `gcw-issue-prepare.yml` orchestrator is desired later, it can `workflow_call` both without changing step semantics.

## Permission Model (draft)

| Step kind | Suggested `permissions` |
| --- | --- |
| Read-only gates (spec-check, implement-check, pr-review validation) | `contents: read` |
| Triage/clarify/to-spec/pr-publish | `contents: write`, `issues: write`, `pull-requests: write` (pr-publish only) |
| Labels sync (existing) | `contents: read` |

Mutating workflows should use environment protection or `dry_run` input to avoid accidental remote writes during testing.

## Risks

- **Token scope:** `GITHUB_TOKEN` in Actions may lack Issue Type / Priority field APIs; triage workflow may need `issues: write` and documented org settings.
- **Branch checkout:** gates must fetch the issue branch (`gcw/issue-<n>`), not default `GITHUB_REF`.
- **Chicken-and-egg:** this issue's deliverable is the workflow files themselves; dogfooding hosted gates on issue #12 validates the design after implementation.
- **Agent in runner:** `gcw-issue-to-spec` and `gcw-implement` may need human/agent handoff initially; workflows should support recording local agent output via `run_gcw_step.py` options files rather than requiring an in-runner LLM.

## References

- Issue: https://github.com/fzf-labs/gcw/issues/12
- Workflow contract: `docs/workflow.md`
- Example progress flow: `docs/quickstart.md`
- Test fixture with complete event chain: `.agents/skills/gcw/tests/fixtures/complete_issue/`
