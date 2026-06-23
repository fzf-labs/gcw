---
name: gcw-issue-clarify
description: Evaluate whether a triaged GCW issue is clear enough for spec writing, publish structured clarification or readiness progress, and move the workflow to ready-for-planning or issue-clarifying. Use after gcw-issue-triage or when issue-clarifying needs another requirements pass.
---

# GCW Issue Clarify

Use this after `gcw-issue-triage` when the workflow is at `issue-triaged`, or after new information arrives while the workflow is at `issue-clarifying`.

## Scope

Do:

- Read the issue body, comments, linked context, and latest triage metadata.
- Run the structural readiness evaluator.
- Publish a new `<!-- gcw-progress -->` comment.
- Record a `gcw-issue-clarify` event with the readiness gate.
- Move to `ready-for-planning` when clear or `issue-clarifying` when more information is needed.

Do not:

- Change classification or remote labels; use `gcw-issue-triage` for that.
- Invent product decisions or business answers.
- Create spec files, branches, or implementation changes.
- Force an unclear issue into planning.

## Readiness rules

Run [evaluate_issue_readiness.py](scripts/evaluate_issue_readiness.py). Phase 1 uses the `enhancement` profile from [readiness/enhancement.json](readiness/enhancement.json).

| Check ID | Rule |
| --- | --- |
| `has_what_to_build` | Body includes non-empty `## What to build` |
| `has_acceptance_criteria` | Body includes `## Acceptance criteria` with at least one list item |
| `blocker_resolved` | `## Blocked by` is absent or indicates work can start immediately |
| `body_not_placeholder` | Body does not contain `Not provided` |

- `gate.ok === true` -> `ready-for-planning`
- `gate.ok === false` -> `issue-clarifying`; use `gate_to_question` output as `question`

## Procedure

1. Read the current issue body and comments with `gh` or `glab`.
2. Evaluate readiness:

```bash
python .agents/skills/gcw-issue-clarify/scripts/evaluate_issue_readiness.py \
  --profile enhancement \
  --platform github --repo OWNER/REPO --issue 42 \
  --output /tmp/clarify_gate.json \
  --question
```

Or pass `--body-file` when the issue body is already saved locally.

3. Publish a new progress comment with the pending `gcw-issue-clarify` payload, then record the event:

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-issue-clarify \
  --issue-dir .gcw/issues/42 \
  --options-file .gcw/issues/42/artifacts/clarify-options.json
```

`clarify-options.json` must include `gate_file`. Include `summary` when ready and `question` when not ready.

## Event payload

```json
{
  "ready": false,
  "gate": {
    "ok": false,
    "rubric_version": "issue-clarify-readiness/v1",
    "profile": "enhancement",
    "checks": [],
    "errors": ["has_acceptance_criteria: no acceptance list items found"]
  },
  "question": "Please update the issue so GCW can write the spec:\n- has_acceptance_criteria: no acceptance list items found",
  "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-2"
}
```

## State transition

- Starts from: `issue-triaged` or `issue-clarifying`
- Completes as: `ready-for-planning` when the issue is clear
- Falls back to: `issue-clarifying` when more information is needed

## Stop conditions

- Stop in `issue-clarifying` if critical information is missing.
- Stop in `blocked` if permissions or remote access prevents reading the issue.
- Stop if the readiness evaluator fails unexpectedly.
