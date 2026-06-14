---
name: gcw-issue-intake
description: Intake an existing GitHub or GitLab issue into GCW, create or switch the issue branch, bootstrap .gcw/issues/ISSUE_ID event files, and move the workflow to issue-opened. Use when starting GCW from an already-created issue.
---

# GCW Issue Intake

Use this as the first GCW step for an already-existing GitHub or GitLab issue.

## Scope

Do:

- Identify the hosting platform, repository, issue number, issue URL, title, and initial context.
- Confirm this issue is intended to enter GCW when the user intent is ambiguous.
- Create or switch to `gcw/issue-<id>`.
- Create `.gcw/issues/<issue-id>/events/`.
- Append `000-gcw-issue-intake.json` and generate `.gcw/issues/<issue-id>/workflow.json`.
- Establish the workflow state as `issue-opened`.

Do not:

- Create a GitHub Action / GitLab CI workflow for this step.
- Create spec files such as `task_plan.md`, `findings.md`, or `progress.md`.
- Publish a `<!-- gcw-progress -->` issue comment.
- Classify the issue or decide whether requirements are ready for planning.

## Inputs

Accept any of these:

- GitHub or GitLab issue URL.
- Platform, repository, and issue number.
- Current repository plus issue number.

If the issue identity is ambiguous, ask for clarification before proceeding.

## Procedure

1. Use `gh` or `glab` to read the issue and comments.
2. Resolve canonical platform, repository, issue number, and issue branch name.
3. Create or switch to the local branch:

```bash
git switch -c gcw/issue-42
```

If the branch already exists, switch to it instead.

4. Initialize the workflow event log:

```bash
python .agents/skills/gcw/scripts/manage_gcw_workflow.py init-workflow \
  --issue-dir .gcw/issues/42 \
  --issue 42 \
  --platform github \
  --repository OWNER/REPO \
  --branch gcw/issue-42 \
  --owner-kind local \
  --owner-id cursor-session
```

5. Report state `issue-opened` and next step `gcw-issue-triage`.

## State Transition

- Starts from: existing Issue outside GCW.
- Completes as: `issue-opened`.
- Next step: `gcw-issue-triage`.

## Stop Conditions

- Stop if the issue cannot be identified.
- Stop if the repository or hosting platform cannot be determined.
- Stop if authentication or permissions prevent reading the issue.
- Stop if the branch or event log cannot be created safely.
