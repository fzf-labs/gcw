---
name: gcw-issue-prepare
description: Deprecated compatibility skill for older GCW event logs and callers that still use gcw-issue-prepare. New workflows should use gcw-issue-triage followed by gcw-issue-clarify instead.
---

# GCW Issue Prepare

This skill is deprecated. Do not use it for new GCW work.

Use the split workflow instead:

1. `gcw-issue-triage` for classification, labels, native issue fields, remote metadata sync, and `issue-triaged`.
2. `gcw-issue-clarify` for readiness evaluation, clarification questions, and `ready-for-planning` or `issue-clarifying`.

## Compatibility

Existing `gcw-issue-prepare` events remain valid. The GCW reducer, schemas, renderers, and manager still understand historical event logs so old issues can rebuild `workflow.json`.

The old command remains available for compatibility:

```bash
python .agents/skills/gcw/scripts/manage_gcw_workflow.py record-issue-prepare \
  --issue-dir .gcw/issues/42 \
  --ready \
  --gate-file /tmp/prepare_gate.json \
  --progress-comment-url https://github.com/owner/repo/issues/42#issuecomment-1 \
  --labels-applied triaged,area:workflow,ready-to-spec \
  --remote-sync-file /tmp/remote_sync.json
```

Deprecated script paths under this skill are wrappers that delegate to `gcw-issue-triage` or `gcw-issue-clarify`.

## Stop conditions

- Stop and switch to `gcw-issue-triage` + `gcw-issue-clarify` unless you are replaying or repairing a legacy workflow.
