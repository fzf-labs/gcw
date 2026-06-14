---
name: gcw-pr-review
description: Run the automatic GCW review step for a published PR or MR, covering CI, static checks, remote artifact verification, and optional AI review. Use when GCW is reviewing.
---

# GCW PR Review

Use this when the workflow is `reviewing` and a PR/MR exists.

## Scope

Do:

- Run or summarize automatic PR/MR checks.
- Inspect changed code directly when AI review is part of the automatic review.
- Record whether automatic review keeps the workflow in `reviewing`, moves to `changes-requested`, or becomes `blocked`.

Do not:

- Perform the human platform review itself.
- Merge, approve, close, or reject the review request.
- Post remote review comments unless explicitly requested by the user or workflow policy.

## Inputs

Require:

- `reviewing` state.
- PR/MR URL.
- Current issue branch and base branch.
- CI/check results or permission to inspect them.

## Procedure

1. Inspect CI and required checks for the PR/MR.
2. Run remote artifact verification when applicable.
3. For AI review, inspect the PR/MR diff and relevant nearby code. Prioritize correctness bugs, security risks, behavioral regressions, missing tests, and documentation mismatches.
4. Summarize automatic review outcome and evidence.
5. Publish a new Issue `<!-- gcw-progress -->` comment for the resulting phase (`reviewing`, `changes-requested`, or `blocked`).
6. Record `feedback_source: pr-review` when automatic review produces requested changes.

Or record the automatic review outcome via the unified step runner after checks complete:

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-pr-review \
  --issue-dir .gcw/issues/<issue-id> \
  --options-file /tmp/pr_review_options.json
```

`pr_review_options.json` must include `"result": "passed"`, `"changes-requested"`, or `"blocked"`.

## State Transition

- Starts from: `reviewing`.
- Completes as: `reviewing` when automatic checks pass and the workflow waits for human review.
- Moves to: `changes-requested` when automatic review requests fixes.
- Moves to: `blocked` when CI, permissions, or external systems prevent review.

## Stop Conditions

- Stop in `blocked` if PR/MR metadata, diff, CI results, or artifacts cannot be accessed.
- Stop in `changes-requested` if automatic review finds issues that require implementation changes.
