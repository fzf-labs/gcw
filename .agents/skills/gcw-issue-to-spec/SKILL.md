---
name: gcw-issue-to-spec
description: Convert a ready GCW issue into an issue branch with GCW event log and spec files under .gcw/issues/<issue-id>/. Use when an issue is ready-for-planning.
---

# GCW Issue To Spec

Use this after `gcw-issue-prepare` moves the workflow to `ready-for-planning`.

## Scope

Do:

- Create or select the issue branch/worktree.
- Append GCW workflow events under `.gcw/issues/<issue-id>/events/` and rebuild `workflow.json`.
- Create `task_plan.md`, `findings.md`, and `progress.md`.
- Push the issue branch and link the spec files from the Issue.
- Move the workflow to `planned`.

Do not:

- Start implementation changes.
- Put spec files directly into the Issue body.
- Continue if the issue becomes unclear.

## Inputs

Require:

- Issue URL or platform/repository/issue number.
- `ready-for-planning` status.
- Repository and base branch.

## Procedure

1. Create a repository-compliant issue branch and, when useful, an isolated worktree using Git directly.
2. Reuse `planning-with-files` to create planning content under `.gcw/issues/<issue-id>/`.
3. Append the `gcw-issue-intake` event if needed, then append `gcw-issue-to-spec` with planning links and spec refs.
4. Commit only the initial spec/event/projection files as a focused planning commit, then push the issue branch without force pushing.
5. Publish a new `<!-- gcw-progress -->` comment with `publish_progress_comment.py` using `--milestone-event gcw-issue-to-spec` and a payload file containing `spec_refs` (and `planning_commit_pushed` when applicable), then record the event with the returned URL. Do not edit previous progress comments.

Or run the unified step runner:

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-issue-to-spec \
  --issue-dir .gcw/issues/<issue-id>
```

Use `--dry-run` to render artifacts and validation without pushing events.

## State Transition

- Starts from: `ready-for-planning`.
- Completes as: `planned`.
- Falls back to: `issue-clarifying` if planning reveals missing Issue decisions.

## Stop Conditions

- Stop in `issue-clarifying` if the issue is not clear enough to write useful spec files.
- Stop in `blocked` if branch creation, push, or Issue comment publication fails.
