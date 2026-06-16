# Findings — Issue #21

## Issue Facts

- Issue: https://github.com/fzf-labs/gcw/issues/21
- Title: `Add GitLab CI support for GCW hosted actions`
- Platform: GitHub issue tracking the repository `fzf-labs/gcw`
- Branch: `gcw/issue-21`
- Classification: `enhancement`, `area:workflow`, `priority:p2`
- Readiness: `gcw-issue-clarify` passed all structural checks and moved the issue to `ready-for-planning`

## Requirements

- GCW already documents GitHub/GitLab as collaboration platforms, but hosted execution currently ships GitHub Actions workflows.
- Add GitLab CI support for the same GCW hosted steps so GitLab projects can opt into hosted execution.
- Preserve equivalent trigger gating, handoff, validation, branch push, PR/MR publication, and event recording behavior.
- Do not regress the existing GitHub Actions path.
- Add tests and documentation for GitLab CI setup and behavioral differences.

## Current Codebase Observations

- Existing hosted workflows live under `.github/workflows/gcw-*.yml`.
- Existing hosted helper scripts live under `.github/scripts/` and `.agents/skills/gcw/scripts/`.
- `docs/hosted-agent.md` is GitHub Actions-first and references GitHub runner behavior, `openai/codex-action`, `gh`, and GitHub permissions.
- `docs/workflow.md` describes Action as GitHub Actions / GitLab CI conceptually, but current implementation artifacts are GitHub-specific.
- Triage tooling already supports GitHub and GitLab metadata models in `.agents/skills/gcw-issue-triage/scripts/`.
- Remote evidence verification documentation mentions GitLab support via `glab`, which suggests some platform abstraction already exists and should be reused.

## Technical Direction

- Add GitLab CI configuration to the repository template, likely under `dist/templates/repo`, and decide whether the working repository should also carry a root `.gitlab-ci.yml` example.
- Keep GCW event files and `workflow.json` platform-neutral; GitLab CI should consume the same `.gcw/issues/<issue-id>/` artifacts.
- Introduce or extend platform adapters where GitHub-specific assumptions appear in publication, PR/MR creation, progress comments, and remote evidence fetching.
- Prefer thin CI jobs that delegate to existing Python scripts, matching the existing hosted workflow style.
- Keep executor labels and phase gating semantically identical across platforms.

## Open Questions

- Should GitLab CI jobs be generated as a single pipeline file with multiple jobs, or as reusable include files per GCW step?
- Which GitLab token should be documented as the default: `CI_JOB_TOKEN`, project access token, or personal access token?
- Should GitLab hosted execution attempt in-runner agent execution for planning/implementation immediately, or first support local-agent handoff plus hosted gates?

## Risks

- GitLab CI lacks a direct equivalent for GitHub Issue Type / Priority fields; existing GCW metadata model uses labels for GitLab, so docs and tests must make that explicit.
- MR upsert behavior differs from PR upsert behavior and may need a dedicated idempotency strategy.
- GitLab protected branch and token policies may prevent branch push from CI unless setup instructions are precise.
- GitLab comments, labels, and MR APIs may require pagination or different URL parsing for remote evidence verification.

## Useful References

- `docs/hosted-agent.md`
- `docs/workflow.md`
- `.github/workflows/gcw-*.yml`
- `.github/scripts/prepare_gcw_hosted_step.py`
- `.github/scripts/finalize_gcw_hosted_step.py`
- `.agents/skills/gcw/scripts/run_gcw_step.py`
- `.agents/skills/gcw/scripts/verify_gcw_remote_evidence.py`
- `.agents/skills/gcw-issue-triage/scripts/manage_triage_metadata.py`
- `.agents/skills/gcw/tests/test_gcw_hosted_workflows.py`
