# Findings — Issue #19

## Issue Facts

- Issue: https://github.com/fzf-labs/gcw/issues/19
- Requested package name: `@fzf-labs/gcw`
- Installed command: `gcw`
- Preferred usage model: `gcw init` copies GCW assets into the target repository.
- Triage: `enhancement` / `area:workflow` / `priority:p2`
- Readiness: all structural checks passed.

## Current Repository State

- There is no `package.json` yet; GCW is currently distributed as repo-local Agent Skills and Python scripts.
- Main user entrypoint is the `gcw` skill under `.agents/skills/gcw/`.
- Step scripts live under `.agents/skills/gcw/scripts/` and related step skill directories.
- Shared Python runtime has moved under `.gcw/runtime/`.
- Existing docs describe enabling repo-bundled skills, not npm installation.

## Assets Required for `gcw init`

Required local-agent assets:

- `.agents/skills/gcw/`
- `.agents/skills/gcw-issue-intake/`
- `.agents/skills/gcw-issue-triage/`
- `.agents/skills/gcw-issue-clarify/`
- `.agents/skills/gcw-issue-to-spec/`
- `.agents/skills/gcw-spec-check/`
- `.agents/skills/gcw-implement/`
- `.agents/skills/gcw-implement-check/`
- `.agents/skills/gcw-pr-publish/`
- `.agents/skills/gcw-pr-review/`
- `.agents/skills/planning-with-files/`
- `.gcw/runtime/`

Optional hosted workflow assets:

- `.github/workflows/gcw-*.yml`
- `.github/actions/gcw-setup/action.yml`
- `.github/actions/gcw-run-codex/action.yml`
- `.github/scripts/`

Do not include per-issue runtime state such as `.gcw/issues/`.

## Trellis Reference

- Trellis publishes a scoped npm CLI package with `bin` entries.
- Trellis uses a Node CLI as the distribution and initialization layer.
- The useful pattern for GCW is npm CLI + copied templates, not rewriting workflow semantics.
- GCW should keep Python workflow scripts repo-local after initialization so existing skills, workflows, and tests remain meaningful.

## Path and Bootstrap Risks

- Several Python files assume a repo-shaped layout and use paths such as `.agents/skills/...` or `.gcw/runtime/...`.
- `_bootstrap.py` works when scripts are copied into the target repo beside `.gcw/runtime/`.
- Running Python scripts directly from the global npm package would likely break path assumptions; `gcw init` should install assets into the target repo instead.
- Package build must avoid copying `.gcw/issues/`, local temporary files, or current branch-only workflow state into templates.

## Validation Notes

- Existing GCW Python regression command:

```bash
python3 -m unittest discover -s .agents/skills/gcw/tests
```

- New npm checks should include:

```bash
npm test
npm run build
npm pack --dry-run
```

## Open Questions

- None blocking for initial implementation.
