---
name: gcw-issue-triage
description: Classify an intaken GCW GitHub or GitLab issue, apply structured triage metadata, verify remote labels/fields, publish the first progress comment, and move the workflow to issue-triaged. Use after gcw-issue-intake when the workflow is issue-opened.
---

# GCW Issue Triage

Use this after `gcw-issue-intake` when the workflow is at `issue-opened`.

## Scope

Do:

- Classify `type`, optional `area`, and `priority`.
- Sync triage label definitions with [manage_triage_metadata.py](scripts/manage_triage_metadata.py).
- Apply remote metadata using native GitHub Issue Type / Priority fields or GitLab labels.
- Verify local event metadata and remote platform metadata match.
- Publish the first `<!-- gcw-progress -->` comment.
- Record a `gcw-issue-triage` event and move to `issue-triaged`.

Do not:

- Decide whether the requirement is clear enough for spec writing.
- Run the readiness gate.
- Ask or answer product clarification questions.
- Create spec files or implementation changes.
- Put GitHub type or priority values into labels; use native GitHub fields.

## Metadata model

| Channel | Local (`classification`) | GitHub remote | GitLab remote |
| --- | --- | --- | --- |
| Type | `type` | Issue Type (`Bug`, `Feature`, `Task`) | label |
| Priority | `priority` | Issue field `Priority` | label |
| Workflow labels | `labels_applied` | labels (`area:*`, `triaged`, `gcw:executor-*`, optional) | labels |

Mappings live in [triage_mappings.json](triage_mappings.json). Workflow label definitions live in [labels.json](labels.json).

## Procedure

1. Read the issue body, title, labels, and recent comments with `gh` or `glab`.
2. Choose classification values:
   - `type`: exactly one of `bug`, `documentation`, `enhancement`, `question`, `duplicate`, `invalid`, `wontfix`
   - `area`: zero or one of `area:workflow`, `area:skills`, `area:specs`, `area:tests`
   - `priority`: exactly one of `priority:p0`, `priority:p1`, `priority:p2`, `priority:p3`
3. Sync labels:

```bash
python .agents/skills/gcw-issue-triage/scripts/manage_triage_metadata.py sync \
  --platform github --repo OWNER/REPO
```

4. Apply metadata. 本地 agent 接管 GCW 时必须让 issue 带有 `gcw:executor-local`；`apply-metadata` 默认会在缺少 executor label 时补上它，示例中仍显式写出该标签以保持 `triage_options.json` 清晰：

```bash
python .agents/skills/gcw-issue-triage/scripts/manage_triage_metadata.py apply-metadata \
  --platform github --repo OWNER/REPO --issue 42 \
  --type enhancement --priority priority:p2 \
  --labels triaged,area:workflow,gcw:executor-local
```

Hosted triage must not default to local ownership; hosted callers pass `--executor none` and require the issue to already opt in with `gcw:executor-hosted`.

5. Save the command output to a remote sync JSON file and verify:

```bash
python .agents/skills/gcw-issue-triage/scripts/verify_remote_triage.py \
  --issue-dir .gcw/issues/42
```

6. Publish a new progress comment with the pending `gcw-issue-triage` payload, then record the event:

```bash
python .agents/skills/gcw/scripts/run_gcw_step.py --step gcw-issue-triage \
  --issue-dir .gcw/issues/42 \
  --options-file /tmp/triage_options.json
```

`triage_options.json` must include `classification_type`, `classification_priority`, `labels_applied`, and `remote_sync_file`. Include `classification_area` when known. For local agent triage, keep `labels_applied` in sync with the remote sync output and include `gcw:executor-local`.

## Event payload

```json
{
  "classification": {
    "type": "enhancement",
    "area": "area:workflow",
    "priority": "priority:p2"
  },
  "labels_applied": ["triaged", "area:workflow", "gcw:executor-local"],
  "remote_sync": {
    "platform": "github",
    "issue_type": "Feature",
    "priority": "Medium",
    "labels": ["triaged", "area:workflow", "gcw:executor-local"]
  },
  "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1"
}
```

## State transition

- Starts from: `issue-opened`
- Completes as: `issue-triaged`
- Next step: `gcw-issue-clarify`

## Stop conditions

- Stop if platform authentication or permissions prevent metadata updates.
- Stop if classification cannot be chosen from available context.
- Stop if remote verification fails.
