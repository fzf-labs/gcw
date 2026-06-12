---
name: gcw-issue-prepare
description: Prepare an intaken GCW issue by collecting context, classifying it, organizing clarifying questions, and deciding whether it is ready for planning. Use after gcw-issue-intake.
---

# GCW Issue Prepare

Use this after `gcw-issue-intake` when the workflow is at `issue-opened` or `issue-clarifying`.

## Scope

Do:

- Collect issue body, comments, labels, discussion, and linked context.
- Classify the issue and identify missing business or implementation information.
- Run agent-assisted triage and organize clarifying questions.
- Move the workflow to `ready-for-planning` or `issue-clarifying`.

Do not:

- Invent product decisions or business answers.
- Create spec files, branches, or implementation changes.
- Force an unclear issue into planning.

## Inputs

Require:

- Issue URL or platform/repository/issue number.
- Current status: `issue-opened` or `issue-clarifying`.

Optional:

- Existing clarifying questions and answers.
- Labels or comments that indicate scope, priority, owner, or constraints.

## Procedure

1. Use `gh` or `glab` to read the current issue, comments, labels, assignees, and linked context.
2. Classify the issue inside this step: type, area, priority, actionability, missing information, and likely owner/reviewer context when available.
3. If details are missing, write focused clarifying questions to the Issue and keep the state at `issue-clarifying`.
4. If the issue is sufficiently clear, record or report `ready-for-planning`.

## State Transition

- Starts from: `issue-opened` or `issue-clarifying`.
- Completes as: `ready-for-planning` when the issue is clear.
- Falls back to: `issue-clarifying` when more information is needed.

## Action Role

This step needs Action support. The hosted workflow may collect context, run agent classification, organize clarifying questions, and record discussion/status. It must not replace human or trusted-source business judgment.

## Stop Conditions

- Stop in `issue-clarifying` if critical information is missing.
- Stop in `blocked` if permissions, authentication, or remote access prevents reading or updating the issue.
