# Findings — Issue #17

## Incident

PR #16 / issue #13: `gcw-pr-review.yml` failed at `Validate pr-publish evidence` after local agent had already recorded `gcw-pr-review`.

Errors:
- `refs.progress_comment_url does not match latest milestone progress comment`
- `gcw-pr-publish progress_comment_body_hash does not match rendered body`

Run: https://github.com/fzf-labs/gcw/actions/runs/27544543786/job/81414441511

## Root Causes

1. **Phase-only gate**: `reviewing` is true both after `pr-publish` (Action should run) and after local `pr-review` (Action should skip).
2. **No executor dimension**: Events support `actor.kind` (`local`, `github-actions`) but workflows ignore it.
3. **Render leak**: `_render_reviewing` reads latest `gcw-pr-review` event from full log, polluting historical pr-publish comment re-render.

## Current Contracts

| Component | Behavior today |
| --- | --- |
| `prepare_gcw_hosted_step.py` | phase ∈ allowed → `should_run=true` |
| `gcw-pr-review.yml` | Always validates `pr-publish` before record |
| GCW skill | `gcw-pr-review` owned by Action; local agent may summarize only |
| Local practice (issue #13) | Local agent ran full chain including `pr-review` |

## Proposed Gate Logic

```text
resolve_trigger(step, event):
  if issue lacks gcw:executor-hosted → should_trigger=false
  if event is pull_request synchronize → only if gcw:executor-hosted
  if event is gcw:run-* / label / assign / comment → only if gcw:executor-hosted

prepare(step):
  if issue lacks gcw:executor-hosted → should_run=false
  if phase not in allowed → skip
  if last_completed_step == step → skip (idempotent)
  if later main-flow step recorded → skip
  if step == gcw-pr-review and passing pr-review exists → run_mode=verify-only
  else → run_mode=full
```

## Label vs actor.kind

| Mechanism | Role |
| --- | --- |
| `gcw:executor-hosted` / `gcw:executor-local` | **Intent** on the Issue; gates whether Actions may run at all |
| `gcw:run-*` | **Which step** to run (only when hosted executor is active) |
| event `actor.kind` | **Audit** of who recorded each milestone after the fact |

## Risks

- Over-skipping if event log manually edited.
- Need clear `skip_reason` in Action logs for debugging.

## References

- Issue: https://github.com/fzf-labs/gcw/issues/17
- Failed run: https://github.com/fzf-labs/gcw/actions/runs/27544543786/job/81414441511
- `prepare_gcw_hosted_step.py`, `gcw-pr-review.yml`, `render_gcw_hosted_artifacts.py`
