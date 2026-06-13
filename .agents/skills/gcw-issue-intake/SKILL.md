---
name: gcw-issue-intake
description: Intake an existing GitHub or GitLab issue into GCW, record the issue identity and initial context, and move the workflow to issue-opened. Use when starting GCW from an already-created issue.
---

# GCW Issue Intake

Use this as the first GCW step for an already-existing GitHub or GitLab issue.

## Scope

Do:

- Identify the hosting platform, repository, issue number, issue URL, title, and initial context.
- Confirm this issue is intended to enter GCW.
- Establish the workflow state conceptually as `issue-opened`.

Do not:

- Create a GitHub Action / GitLab CI workflow for this step.
- Create an issue branch, worktree, event files, projection files, or spec files.
- Decide whether the issue is actionable beyond basic intake.

## Inputs

Accept any of these:

- GitHub or GitLab issue URL.
- Platform, repository, and issue number.
- Current repository plus issue number.

If the issue identity is ambiguous, ask for clarification before proceeding.

## Procedure

1. Use `gh` or `glab` to read the issue and comments without mutating remote state.
2. Record the canonical issue identity and short initial context in the conversation or handoff notes.
3. If the user has not clearly asked to process this issue through GCW, confirm before continuing.
4. Report that the issue is now in `issue-opened` and the next step is `gcw-issue-prepare`.

## State Transition

- Starts from: existing Issue outside GCW.
- Completes as: `issue-opened`.
- Persistence: before issue-branch files exist, this state may be carried by Issue comments, labels, or agent context. Once files are created, append `gcw-issue-intake` under `.gcw/issues/<issue-id>/events/` and rebuild `workflow.json`.

## Stop Conditions

- Stop if the issue cannot be identified.
- Stop if the repository or hosting platform cannot be determined.
- Stop if authentication or permissions prevent reading the issue.
