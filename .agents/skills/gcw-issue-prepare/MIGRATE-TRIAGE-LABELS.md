# Migrate legacy type/priority labels (GitHub)

Older GCW prepare steps wrote `type` and `priority` as GitHub labels (for example `enhancement`, `priority:p0`). The structured metadata flow stores those values in GitHub Issue Type and the org `Priority` issue field instead.

## One issue

```bash
python .agents/skills/gcw-issue-prepare/scripts/manage_triage_metadata.py apply-metadata \
  --platform github --repo OWNER/REPO --issue ISSUE_NUMBER \
  --type enhancement --priority priority:p0 \
  --labels triaged,area:workflow,ready-to-spec

python .agents/skills/gcw-issue-prepare/scripts/manage_triage_metadata.py migrate-triage-labels \
  --platform github --repo OWNER/REPO --issue ISSUE_NUMBER
```

`apply-metadata` sets Issue Type, Priority field, workflow labels, and removes legacy type/priority labels. `migrate-triage-labels` only removes legacy labels if you already updated type/priority elsewhere.

## Local event

After remote sync succeeds, record the event with `remote_sync` from the `apply-metadata` JSON output:

```bash
python .agents/skills/gcw-issue-prepare/scripts/evaluate_issue_readiness.py \
  --profile enhancement --platform github --repo OWNER/REPO --issue ISSUE_NUMBER \
  --output /tmp/prepare_gate.json

python .agents/skills/gcw/scripts/manage_gcw_workflow.py record-issue-prepare \
  --issue-dir .gcw/issues/ISSUE_NUMBER \
  --ready \
  --gate-file /tmp/prepare_gate.json \
  --classification-type enhancement \
  --classification-area area:workflow \
  --classification-priority priority:p0 \
  --labels-applied triaged,area:workflow,ready-to-spec \
  --remote-sync-file /tmp/remote_sync.json
```

`labels_applied` on GitHub must not include type or priority labels.

## Verify

```bash
python .agents/skills/gcw-issue-prepare/scripts/verify_remote_triage.py \
  --issue-dir .gcw/issues/ISSUE_NUMBER

python .agents/skills/gcw/scripts/validate_gcw_evidence.py prepare-check \
  --issue-dir .gcw/issues/ISSUE_NUMBER
```
