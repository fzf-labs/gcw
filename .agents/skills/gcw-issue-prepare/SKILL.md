---
name: gcw-issue-prepare
description: Prepare an intaken GCW issue by collecting context, classifying it, applying triage labels on GitHub or GitLab, organizing clarifying questions, and deciding whether it is ready for planning. Use after gcw-issue-intake.
---

# GCW Issue Prepare

Use this after `gcw-issue-intake` when the workflow is at `issue-opened` or `issue-clarifying`.

## Scope

Do:

- Collect issue body, comments, labels, discussion, and linked context.
- Classify the issue and identify missing business or implementation information.
- Apply triage labels on GitHub or GitLab using [labels.json](labels.json).
- Run agent-assisted triage and organize clarifying questions.
- Move the workflow to `ready-for-planning` or `issue-clarifying`.
- Record applied labels in the `gcw-issue-prepare` event payload.

Do not:

- Invent product decisions or business answers.
- Create spec files, branches, or implementation changes.
- Force an unclear issue into planning.
- Apply labels outside [labels.json](labels.json).
- Apply post-prepare workflow labels such as `ready-to-implement`; later GCW steps own those.

## Label Vocabulary

[labels.json](labels.json) defines **16 labels** in five groups. Sync definitions to the platform before applying:

```bash
gh label create "triaged" --color "C2E0C6" --description "Reviewed and categorized" --repo OWNER/REPO 2>/dev/null \
  || gh label edit "triaged" --color "C2E0C6" --description "Reviewed and categorized" --repo OWNER/REPO
```

## Classification Rules

| Group | Cardinality | Labels |
| --- | --- | --- |
| `type` | exactly 1 | `bug`, `documentation`, `enhancement`, `question`, `duplicate`, `invalid`, `wontfix` |
| `area` | 0–1 | `area:workflow`, `area:skills`, `area:specs`, `area:tests` |
| `readiness` | exactly 1 | `ready-to-spec` when clear; `needs-info` when clarifying |
| `triage` | 1 when clear | `triaged` |
| `optional` | any | `good first issue`, `help wanted` |

Rules:

- When `ready` is true: add `triaged` + `ready-to-spec`; remove `needs-info`.
- When `ready` is false: add `needs-info`; remove `ready-to-spec` and `triaged`.
- Terminal types (`duplicate`, `invalid`, `wontfix`) must not carry `ready-to-spec`.
- Replace conflicting labels in the same group; do not stack duplicates.

Area hints for this repository:

- `area:workflow` — `.github/workflows`, CI scripts
- `area:skills` — `.agents/skills`
- `area:specs` — `.gcw/issues/*/`, planning docs
- `area:tests` — tests and fixtures

## Procedure

1. Read the issue with `gh` or `glab`.
2. Classify type, area, and whether clarification is needed.
3. Sync label definitions from [labels.json](labels.json).
4. Apply labels:

```bash
gh issue edit 42 --repo OWNER/REPO --add-label "documentation,triaged,area:specs,ready-to-spec"
```

5. If unclear, comment with questions, apply `needs-info`, stay at `issue-clarifying`.
6. If clear, record `ready-for-planning` and append `gcw-issue-prepare` with `labels_applied`.

## Event Payload

```json
{
  "ready": true,
  "summary": "documentation quickstart; scope clear",
  "classification": {
    "type": "documentation",
    "area": "area:specs"
  },
  "labels_applied": ["documentation", "triaged", "area:specs", "ready-to-spec"]
}
```

## State Transition

- Starts from: `issue-opened` or `issue-clarifying`.
- Completes as: `ready-for-planning` when the issue is clear.
- Falls back to: `issue-clarifying` when more information is needed.

## Stop Conditions

- Stop in `issue-clarifying` if critical information is missing.
- Stop in `blocked` if permissions or remote access prevent reading or updating the issue.
