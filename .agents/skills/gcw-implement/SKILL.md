---
name: gcw-implement
description: Advance GCW implementation work for a ready issue using the current spec, tests, commits, and progress updates. Use when GCW is ready-for-implementation, implementing, or changes-requested.
---

# GCW Implement

Use this when the workflow is `ready-for-implementation`, `implementing`, or `changes-requested`.

## Scope

Do:

- Make one implementation advance according to the spec files.
- Use TDD for behavior changes unless not applicable.
- Keep spec/progress files current when implementation discoveries change the plan.
- Commit and push focused changes when appropriate.
- Keep the workflow in `implementing` until `gcw-implement-check` says it is ready for review.

Do not:

- Create or update the review request.
- Skip validation evidence just because the implementation appears small.
- Continue through blockers or unresolved Issue questions.

## Inputs

Require:

- `ready-for-implementation`, `implementing`, or `changes-requested` state.
- Issue branch/worktree.
- `.gcw/issues/<issue-id>/task_plan.md`, `findings.md`, `progress.md`, `events/`, and current `workflow.json` projection.

## Procedure

1. If starting from `ready-for-implementation` or `changes-requested`, append a `gcw-implement` event and rebuild `workflow.json` before editing product code.
2. Read the spec files and current progress.
3. Reuse `tdd` for behavior changes.
4. Make focused code, test, and necessary documentation changes.
5. Update progress/spec files when discoveries or risks change.
6. Commit focused implementation changes and push the issue branch when the change is ready to publish. Do not force push unless the user explicitly approves.

## State Transition

- Starts from: `ready-for-implementation`, `implementing`, or `changes-requested`.
- Completes as: `implementing`.
- The next gate is `gcw-implement-check`.

## Stop Conditions

- Use `gcw-clarify` semantics and stop in `issue-clarifying` if the Issue needs more information.
- Use `gcw-block` semantics and stop in `blocked` if permissions, dependencies, tests, infrastructure, or external services prevent progress.
