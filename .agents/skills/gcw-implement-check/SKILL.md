---
name: gcw-implement-check
description: Check a GCW implementation before review by validating diff boundaries, tests, implement-check event payload, risks, and spec synchronization. Use before publishing a PR or MR.
---

# GCW Implement Check

Use this after one or more `gcw-implement` passes while the workflow is `implementing`.

## Scope

Do:

- Review the branch diff for accidental files, secrets, conflict markers, and unrelated changes.
- Confirm validation results and skipped-test reasons.
- Confirm spec files and progress reflect the current implementation.
- Generate or validate the `gcw-implement-check` event payload used for PR/MR rendering.
- Move the workflow to `ready-for-review`.

Do not:

- Create or update the PR/MR.
- Hide failed checks or missing validation.

## Inputs

Require:

- `implementing` state.
- Current issue branch.
- Latest implementation commits.
- `.gcw/issues/<issue-id>/` files.

## Procedure

1. Inspect the current branch diff and commit boundaries.
2. Confirm tests, linters, or validation commands have been run, or record why they were skipped.
3. Confirm planning files are current.
4. Write or validate the implement-check payload for summary, issue link, validation, risks, scope, reviewer notes, self-review, and spec refs.
5. Publish a new `<!-- gcw-progress -->` comment for `ready-for-review` when the gate passes.
6. Append a `gcw-implement-check` event with `progress_comment_url`, rebuild `workflow.json`, and reuse GCW validation scripts when available, especially `validate_gcw_evidence.py implement-check`.

## State Transition

- Starts from: `implementing`.
- Completes as: `ready-for-review`.
- Remains in: `implementing` when more work is needed.

## Stop Conditions

- Stop in `implementing` if the diff, tests, or implement-check payload is incomplete.
- Stop in `blocked` if required validation cannot run for external reasons.
- Stop in `issue-clarifying` if final review uncovers missing Issue decisions.
