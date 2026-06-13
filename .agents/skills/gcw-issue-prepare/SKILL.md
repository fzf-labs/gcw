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
- Create repository labels outside the vocabulary in `labels.json`.

## Inputs

Require:

- Issue URL or platform/repository/issue number.
- Current status: `issue-opened` or `issue-clarifying`.

Optional:

- Existing clarifying questions and answers.
- Labels or comments that indicate scope, priority, owner, or constraints.

## Label Vocabulary

Use [labels.json](labels.json) as the canonical label set. Before applying labels, ensure each required label exists on the hosting platform:

```bash
# GitHub — create or update one label
gh label create "triaged" --color "C2E0C6" --description "Issue has been reviewed and categorized" --repo OWNER/REPO 2>/dev/null \
  || gh label edit "triaged" --color "C2E0C6" --description "Issue has been reviewed and categorized" --repo OWNER/REPO

# GitLab
glab label create "triaged" --color "#C2E0C6" --description "Issue has been reviewed and categorized" --repo OWNER/REPO
```

## Classification Rules

Apply labels in these groups:

| Group | Cardinality | Labels |
| --- | --- | --- |
| Type | exactly 1 | `bug`, `documentation`, `enhancement`, `question`, `duplicate`, `invalid`, `wontfix` |
| Area | 0–1 | `area:workflow`, `area:skills`, `area:specs`, `area:tests` |
| Reproducibility | 0–1, bugs only | `repro:high`, `repro:medium`, `repro:low`, `repro:unknown` |
| GCW readiness | exactly 1 | `ready-to-spec` when clear; `needs-info` when clarifying |
| Triage marker | 1 when classified | `triaged` after classification is recorded |
| Optional | any | `good first issue`, `help wanted` |

When `ready` is true, add `triaged` and `ready-to-spec`, and remove `needs-info` if present. When `ready` is false, add `needs-info`, remove `ready-to-spec`, and do not add `triaged` until the issue is actionable.

Replace conflicting labels in the same group instead of accumulating duplicates. Preserve unrelated labels already on the issue unless they contradict the new classification.

## Procedure

1. Use `gh` or `glab` to read the current issue, comments, labels, assignees, and linked context.
2. Classify the issue: type, area, reproducibility (for bugs), actionability, missing information, and likely owner/reviewer context when available.
3. Ensure required labels from [labels.json](labels.json) exist on the platform; create or update missing definitions.
4. Apply the classification labels to the issue:

```bash
# GitHub
gh issue edit 42 --repo OWNER/REPO --add-label "documentation,triaged,area:specs,ready-to-spec"

# GitLab
glab issue update 42 --repo OWNER/REPO --label "documentation,triaged,area:specs,ready-to-spec"
```

5. If details are missing, write focused clarifying questions to the Issue, apply `needs-info`, and keep the state at `issue-clarifying`.
6. If the issue is sufficiently clear, apply `triaged` and `ready-to-spec`, record `ready-for-planning`, and append a `gcw-issue-prepare` event with `labels_applied` in the payload.

## Event Payload

Record classification in the event:

```json
{
  "ready": true,
  "summary": "documentation quickstart; scope clear",
  "classification": {
    "type": "documentation",
    "area": "area:specs",
    "repro": null
  },
  "labels_applied": ["documentation", "triaged", "area:specs", "ready-to-spec"]
}
```

When `ready` is false, include `question` and set `labels_applied` to include `needs-info` instead of `ready-to-spec`.

## State Transition

- Starts from: `issue-opened` or `issue-clarifying`.
- Completes as: `ready-for-planning` when the issue is clear.
- Falls back to: `issue-clarifying` when more information is needed.

## Action Role

This step needs Action support. The hosted workflow may collect context, run agent classification, sync label definitions, apply triage labels, organize clarification questions, and record discussion/status. It must not replace human or trusted-source business judgment.

## Stop Conditions

- Stop in `issue-clarifying` if critical information is missing.
- Stop in `blocked` if permissions, authentication, or remote access prevents reading or updating the issue or labels.
