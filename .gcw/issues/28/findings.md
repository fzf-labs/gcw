# Findings — Issue #28

## Requirements

- Tie each hosted skip/no-op path to the gate that produced it: executor, phase, or idempotent.
- Improve troubleshooting in `docs/hosted-agent.md`.
- Distinguish skip categories in workflow step summaries.
- Document first checks when `gh run list` shows `skipped`.
- Add tests for skip reason wording or mapping.

## Codebase findings

### Skip decision points

| Layer | Where | Typical `skip_reason` / signal |
| --- | --- | --- |
| Job `if` | `.github/workflows/gcw-*.yml` | Workflow run `skipped`; job never starts |
| Executor gate | `gcw_executor_gate.py`, `gcw_workflow_event.py` | `gcw:executor-local blocks hosted execution`, `missing gcw:executor-hosted` |
| Phase gate | `gcw_hosted_policy.prepare_hosted_step` | `phase 'planned' is not in [...] for gcw-spec-check` |
| Idempotent | `gcw_hosted_policy._idempotent_decision` | `gcw-issue-triage already completed`, `superseded by gcw-pr-publish` |
| Infrastructure | `prepare_gcw_hosted_step.prepare` | `issue directory not found: ...` |

### Current logging gaps

- GitHub `Report phase skip` steps only `echo` raw `skip_reason` with no gate label.
- GitLab prints generic `GCW step skipped by phase gate` even for executor skips.
- `docs/hosted-agent.md` troubleshooting table is brief and does not separate job-level skips from in-job gates.

## Decisions

- Add `skip_gate` to `prepare_gcw_hosted_step` output; classify from `skip_reason` text in a shared module.
- Use `report_gcw_skip.py` for consistent step summaries in GitHub workflows and GitLab CI.
- Keep gate behavior unchanged; this issue is diagnostics and docs only.
