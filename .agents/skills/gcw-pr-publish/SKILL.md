---
name: gcw-pr-publish
description: Idempotently create or update the GitHub PR or GitLab MR for a GCW issue branch after implementation readiness passes. Use when GCW is ready-for-review.
---

# GCW PR Publish

Use this when the workflow is `ready-for-review`.

## Scope

Do:

- Create or update the review request for the issue branch.
- Include complete-on-create summary, Issue link, validation, risks, scope, and planning links.
- Move the workflow to `reviewing`.

Do not:

- Start automatic PR review; that is `gcw-pr-review`.
- Merge, close, approve, or request changes.
- Overwrite human-authored PR/MR text without preserving it.

## Inputs

Require:

- `ready-for-review` state.
- Pushed issue branch.
- Latest passing `gcw-implement-check` event payload and current planning/progress links.
- GitHub or GitLab repository context.

## Procedure

1. Confirm `validate_gcw_evidence.py implement-check` passes.
2. Create or update the GitHub PR or GitLab MR with `gh` or `glab`. The rendered body includes `Closes #<issue-id>` (from workflow projection) so GitHub auto-closes the linked issue on merge.
3. Publish a new Issue `<!-- gcw-progress -->` comment for `reviewing`.
4. Preserve user-authored PR/MR content when updating an existing review request.
5. Append a `gcw-pr-publish` event with the review request URL, progress comment URL, rendered body hash, and applied platform effect.
6. Report the review request URL and next step.

Or run the unified step runner:

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-pr-publish \
  --issue-dir .gcw/issues/<issue-id> \
  --options-file /tmp/pr_publish_options.json
```

`pr_publish_options.json` must include `review_request_url` and `target` after the PR/MR upsert succeeds.

## State Transition

- Starts from: `ready-for-review`.
- Completes as: `reviewing`.

## Stop Conditions

- Stop in `blocked` if authentication, permissions, branch push, or platform API access prevents publishing.
- Stop in `implementing` if the implement-check event payload is incomplete and implementation work must continue.
