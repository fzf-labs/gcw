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

## Platform Selection

Infer the platform from the issue URL or repository remote:

- `github.com` → `github` with `gh`
- `gitlab.com` or self-hosted GitLab → `gitlab` with `glab`

Repository formats:

- GitHub: `OWNER/REPO`
- GitLab: `GROUP/PROJECT` or `GROUP/NAMESPACE/PROJECT`

Prefer [scripts/manage_triage_labels.py](scripts/manage_triage_labels.py) for label sync and application on both platforms.

## Label Vocabulary

[labels.json](labels.json) defines **20 labels** in six groups.

### Sync label definitions

```bash
# GitHub
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_labels.py sync \
  --platform github --repo OWNER/REPO

# GitLab
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_labels.py sync \
  --platform gitlab --repo GROUP/PROJECT
```

Manual fallback:

```bash
# GitHub
gh label create "triaged" --color "C2E0C6" --description "Reviewed and categorized" --repo OWNER/REPO 2>/dev/null \
  || gh label edit "triaged" --color "C2E0C6" --description "Reviewed and categorized" --repo OWNER/REPO

# GitLab
glab label create --name "triaged" --color "#C2E0C6" --description "Reviewed and categorized" --repo GROUP/PROJECT
```

GitLab label colors must use `#RRGGBB`. Label names with `:` (for example `area:skills`) are supported.

## Classification Rules

| Group | Cardinality | Labels |
| --- | --- | --- |
| `type` | exactly 1 | `bug`, `documentation`, `enhancement`, `question`, `duplicate`, `invalid`, `wontfix` |
| `area` | 0–1 | `area:workflow`, `area:skills`, `area:specs`, `area:tests` |
| `priority` | exactly 1 | `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3` |
| `readiness` | exactly 1 | `ready-to-spec` when clear; `needs-info` when clarifying |
| `triage` | 1 when clear | `triaged` |
| `optional` | any | `good first issue`, `help wanted` |

Priority hints:

- `priority:p0` — production outage, security incident, or blocking release
- `priority:p1` — important; should land soon
- `priority:p2` — normal backlog (default for documentation and routine enhancements)
- `priority:p3` — nice-to-have or deferrable

Rules:

- When `ready` is true: add `triaged` + `ready-to-spec`; remove `needs-info`.
- When `ready` is false: add `needs-info`; remove `ready-to-spec` and `triaged`.
- Terminal types (`duplicate`, `invalid`, `wontfix`) must not carry `ready-to-spec`.
- Replace conflicting labels in the same group; do not stack duplicates.

Area hints for this repository:

- `area:workflow` — `.github/workflows`, `.gitlab/ci`, automation scripts
- `area:skills` — `.agents/skills`
- `area:specs` — `.gcw/issues/*/`, planning docs
- `area:tests` — tests and fixtures

## Procedure

1. Read the issue with `gh` or `glab`.
2. Classify type, area, priority, and whether clarification is needed.
3. Sync label definitions from [labels.json](labels.json).
4. Apply labels on the hosting platform:

```bash
# GitHub or GitLab — replaces conflicting labels in type/area/priority/readiness/triage groups
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_labels.py apply \
  --platform github --repo OWNER/REPO --issue 42 \
  --add "documentation,triaged,area:specs,priority:p2,ready-to-spec"

python .agents/skills/gcw-issue-prepare/scripts/manage_triage_labels.py apply \
  --platform gitlab --repo GROUP/PROJECT --issue 42 \
  --add "documentation,triaged,area:specs,priority:p2,ready-to-spec"
```

Manual fallback:

```bash
gh issue edit 42 --repo OWNER/REPO --add-label "documentation,triaged,area:specs,ready-to-spec"
glab issue update 42 --repo GROUP/PROJECT --label "documentation,triaged,area:specs,ready-to-spec"
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
    "area": "area:specs",
    "priority": "priority:p2"
  },
  "labels_applied": ["documentation", "triaged", "area:specs", "priority:p2", "ready-to-spec"]
}
```

## State Transition

- Starts from: `issue-opened` or `issue-clarifying`.
- Completes as: `ready-for-planning` when the issue is clear.
- Falls back to: `issue-clarifying` when more information is needed.

## Stop Conditions

- Stop in `issue-clarifying` if critical information is missing.
- Stop in `blocked` if permissions or remote access prevents reading or updating the issue.
