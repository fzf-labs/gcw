---
name: gcw-spec-check
description: Verify GCW spec files, event-log projection, issue links, and actionability before implementation. Use when a GCW issue is planned and must pass the implementation gate.
---

# GCW Spec Check

Use this after `gcw-issue-to-spec` when the workflow is `planned`.

## Scope

Do:

- Verify spec files exist on the issue branch.
- Verify the Issue comment links to the current branch versions of the spec files.
- Verify the issue is still actionable.
- Move the workflow to `ready-for-implementation`, `issue-clarifying`, or `blocked`.

Do not:

- Modify product code.
- Treat missing business decisions as implementation assumptions.

## Inputs

Require:

- `.gcw/issues/<issue-id>/events/` and current `workflow.json` projection.
- `.gcw/issues/<issue-id>/task_plan.md`.
- `.gcw/issues/<issue-id>/findings.md`.
- `.gcw/issues/<issue-id>/progress.md`.
- Issue progress/comment link.

## Procedure

1. Read the issue directory and validate the expected spec files.
2. Validate that the spec files have been pushed and linked from the Issue.
3. Use `gh` or `glab` when needed to confirm the Issue has not changed in a way that invalidates the spec.
4. Run the GCW validation scripts when available, especially `validate_gcw_evidence.py workflow` and `validate_gcw_evidence.py spec-check`.
5. Publish a new `<!-- gcw-progress -->` comment for the resulting phase (`ready-for-implementation`, `issue-clarifying`, or `blocked`).
6. Append a `gcw-spec-check` event with the gate result, `progress_comment_url`, rebuild `workflow.json`, and report the exact missing evidence when the gate cannot pass.

Or run the unified step runner:

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-spec-check \
  --issue-dir .gcw/issues/<issue-id> \
  --options-file /tmp/spec_check_options.json
```

`spec_check_options.json` may set `"result": "passed"` (default), `"clarifying"`, or `"blocked"`.

## State Transition

- Starts from: `planned`.
- Completes as: `ready-for-implementation`.
- Falls back to: `issue-clarifying` when Issue decisions are missing. Existing spec files remain as draft and are updated by rerunning `gcw-issue-to-spec`.
- May move to: `blocked` for permissions, remote access, missing branch data, or validation failures that cannot be fixed without intervention.

## Stop Conditions

- Stop before implementation if any gate item is missing.
- Stop in `issue-clarifying` if the spec cannot honestly answer the Issue.
- Stop in `blocked` if infrastructure or permissions prevent validation.
