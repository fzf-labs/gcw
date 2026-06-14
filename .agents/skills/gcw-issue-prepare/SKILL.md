---
name: gcw-issue-prepare
description: Prepare an intaken GCW issue by collecting context, classifying it, applying structured triage metadata on GitHub or GitLab, organizing clarifying questions, and deciding whether it is ready for planning. Use after gcw-issue-intake.
---

# GCW Issue Prepare

Use this after `gcw-issue-intake` when the workflow is at `issue-opened` or `issue-clarifying`.

## Scope

Do:

- Collect issue body, comments, labels, discussion, and linked context.
- Classify the issue and identify missing business or implementation information.
- Sync and apply triage metadata using [manage_triage_metadata.py](scripts/manage_triage_metadata.py).
- Verify local and remote metadata match before recording the event.
- Move the workflow to `ready-for-planning` or `issue-clarifying`.
- Record `classification`, `labels_applied`, and `remote_sync` in the `gcw-issue-prepare` event payload.

Do not:

- Invent product decisions or business answers.
- Create spec files, branches, or implementation changes.
- Force an unclear issue into planning.
- Put GitHub `type` or `priority` values into labels; use Issue Type and Issue Fields on GitHub.
- Apply post-prepare workflow labels such as `ready-to-implement`; later GCW steps own those.

## Metadata model

| Channel | Local (`classification`) | GitHub remote | GitLab remote |
| --- | --- | --- | --- |
| Type | `type` | Issue Type (`Bug`, `Feature`, `Task`) | label |
| Priority | `priority` | Issue field `Priority` | label |
| Workflow labels | `labels_applied` | labels (`area:*`, readiness, triage, optional) | labels (includes type/priority labels) |

Mappings live in [triage_mappings.json](triage_mappings.json). Workflow label definitions live in [labels.json](labels.json).

## Platform selection

- `github.com` → `github` with `gh`
- `gitlab.com` or self-hosted GitLab → `gitlab` with `glab`

Repository formats:

- GitHub: `OWNER/REPO`
- GitLab: `GROUP/PROJECT` or `GROUP/NAMESPACE/PROJECT`

## Classification rules

| Group | Cardinality | Values |
| --- | --- | --- |
| `type` | exactly 1 | `bug`, `documentation`, `enhancement`, `question`, `duplicate`, `invalid`, `wontfix` |
| `area` | 0–1 | `area:workflow`, `area:skills`, `area:specs`, `area:tests` |
| `priority` | exactly 1 | `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3` |
| `readiness` | exactly 1 | `ready-to-spec` when clear; `needs-info` when clarifying |
| `triage` | 1 when clear | `triaged` |
| `optional` | any | `good first issue`, `help wanted` |

On GitHub, only `area`, `readiness`, `triage`, and `optional` groups are written as labels. Type and priority use native fields via `apply-metadata`.

## Readiness rules (Phase 1)

Run [evaluate_issue_readiness.py](scripts/evaluate_issue_readiness.py) before applying readiness labels. Phase 1 uses the `enhancement` profile from [readiness/enhancement.json](readiness/enhancement.json), aligned with [issue-create/issue-template.md](../issue-create/issue-template.md).

| Check ID | Rule |
| --- | --- |
| `has_what_to_build` | Body includes non-empty `## What to build` |
| `has_acceptance_criteria` | Body includes `## Acceptance criteria` with at least one list item |
| `blocker_resolved` | `## Blocked by` is absent or indicates work can start immediately |
| `body_not_placeholder` | Body does not contain `Not provided` |

- `gate.ok === true` → `ready-to-spec` and `ready-for-planning`
- `gate.ok === false` → `needs-info` and `issue-clarifying`; use `gate_to_question` output as `question`
- Do not skip the evaluator or mark `ready-to-spec` when structural checks fail

## Procedure

1. Read the issue with `gh` or `glab`.
2. Classify type, area, priority, and whether clarification is needed.
3. Evaluate structural readiness:

```bash
python .agents/skills/gcw-issue-prepare/scripts/evaluate_issue_readiness.py \
  --profile enhancement \
  --platform github --repo OWNER/REPO --issue 42 \
  --output /tmp/prepare_gate.json
```

Or pass `--body-file` when the issue body is already saved locally.

4. Sync workflow label definitions:

```bash
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_metadata.py sync \
  --platform github --repo OWNER/REPO
```

5. Apply structured metadata (`ready-to-spec` only when `gate.ok` is true; otherwise use `needs-info`):

```bash
# GitHub — Issue Type + Priority field + workflow labels
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_metadata.py apply-metadata \
  --platform github --repo OWNER/REPO --issue 42 \
  --type enhancement --priority priority:p0 \
  --labels triaged,area:workflow,ready-to-spec

# GitLab — label fallback for type/priority
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_metadata.py apply-metadata \
  --platform gitlab --repo GROUP/PROJECT --issue 42 \
  --type enhancement --priority priority:p0 \
  --labels triaged,area:workflow,ready-to-spec
```

6. Verify remote state:

```bash
python .agents/skills/gcw-issue-prepare/scripts/verify_remote_triage.py \
  --issue-dir .gcw/issues/42
```

7. Publish a **new** `<!-- gcw-progress -->` comment (never edit an existing one). Clarification questions use the structured `## Clarification` section:

```bash
python .agents/skills/gcw/scripts/publish_progress_comment.py --issue-dir .gcw/issues/42
```

8. If `gate.ok` is false, stay at `issue-clarifying` with `needs-info`, publish the progress comment, and record the event with `question` from the gate output.
9. If `gate.ok` is true, record the event with `remote_sync`, `gate`, and the new comment URL:

```bash
python .agents/skills/gcw/scripts/manage_gcw_workflow.py record-issue-prepare \
  --issue-dir .gcw/issues/42 \
  --ready \
  --gate-file /tmp/prepare_gate.json \
  --progress-comment-url https://github.com/owner/repo/issues/42#issuecomment-1 \
  --summary "scope clear" \
  --classification-type enhancement \
  --classification-area area:workflow \
  --classification-priority priority:p0 \
  --labels-applied triaged,area:workflow,ready-to-spec \
  --remote-sync-file /tmp/remote_sync.json
```

Or run the unified step runner (same ordering; publication before event record):

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-issue-prepare \
  --issue-dir .gcw/issues/42 \
  --options-file /tmp/prepare_options.json
```

`prepare_options.json` must include `gate_file`, `remote_sync_file`, `ready`, `labels_applied`, and classification fields.

## Event payload

```json
{
  "ready": true,
  "gate": {
    "ok": true,
    "rubric_version": "prepare-readiness/v1",
    "profile": "enhancement",
    "checks": [
      {"id": "has_what_to_build", "ok": true, "source": "structural"},
      {"id": "has_acceptance_criteria", "ok": true, "source": "structural"},
      {"id": "blocker_resolved", "ok": true, "source": "structural"},
      {"id": "body_not_placeholder", "ok": true, "source": "structural"}
    ],
    "errors": []
  },
  "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
  "summary": "P0 enhancement: add hard validation",
  "classification": {
    "type": "enhancement",
    "area": "area:workflow",
    "priority": "priority:p0"
  },
  "labels_applied": ["triaged", "area:workflow", "ready-to-spec"],
  "remote_sync": {
    "platform": "github",
    "issue_type": "Feature",
    "priority": "Urgent",
    "labels": ["triaged", "area:workflow", "ready-to-spec"]
  }
}
```

## Migration

For issues that still have legacy GitHub type/priority labels, see [MIGRATE-TRIAGE-LABELS.md](MIGRATE-TRIAGE-LABELS.md).

## State transition

- Starts from: `issue-opened` or `issue-clarifying`.
- Completes as: `ready-for-planning` when the issue is clear.
- Falls back to: `issue-clarifying` when more information is needed.

## Stop conditions

- Stop in `issue-clarifying` if critical information is missing.
- Stop in `blocked` if permissions or remote access prevents reading or updating the issue.
- Stop if `verify_remote_triage.py` or `prepare-check` fails.
