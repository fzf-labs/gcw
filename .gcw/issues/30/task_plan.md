# Task Plan: Add clean downstream gcw init smoke test

## Goal
Add an npm-package smoke test proving the packaged GCW CLI can initialize a brand-new downstream git repository and pass `gcw doctor` there.

## Current Phase
Planned. Human spec review is required before `gcw-spec-check`.

## Acceptance Criteria
- The smoke creates a temporary clean git repository outside this repo.
- The smoke invokes the GCW CLI through the built/package-style entrypoint rather than importing repo source files directly.
- The smoke runs the equivalent of `gcw init` and `gcw doctor` in the downstream repository.
- The smoke verifies repo-local assets are created after init.
- The smoke verifies runtime issue state is not copied into the downstream repository.
- The existing npm/test workflow documents that this covers the README quickstart path.

## Implementation Plan

### Phase 1: Inspect Package And CLI Paths
- [ ] Review `package.json`, `bin/gcw.js`, `lib/cli/main.js`, `lib/cli/init.js`, `lib/cli/doctor.js`, and `scripts/build-npm-package.mjs`.
- [ ] Confirm whether tests can reuse the existing `runCli` helper or need a package-style wrapper around the built artifact.
- [ ] Identify the repo-local assets that `gcw init` must copy.
- **Status:** pending

### Phase 2: Add Downstream Smoke Test
- [ ] Add a `node:test` case in `test/gcw-cli.test.mjs`.
- [ ] Create a temp directory outside this repo and run `git init` there.
- [ ] Build/package assets first, using the same setup expected by the npm package workflow.
- [ ] Invoke the CLI from the packaged/built entrypoint and run `init`, then `doctor`, with `cwd` set to the temp repo.
- **Status:** pending

### Phase 3: Assert Init Results
- [ ] Assert expected repo-local assets exist, including `.agents/skills/gcw`, `.agents/skills/planning-with-files`, and `.gcw/engine/runtime`.
- [ ] Assert `.gcw/issues` is absent, so runtime issue state is not copied.
- [ ] Assert `gcw doctor` exits successfully and reports the initialized repo as healthy.
- **Status:** pending

### Phase 4: Document Test Coverage
- [ ] Update the existing npm/test documentation surface, likely `README.md`, to mention that `npm test` includes a downstream quickstart smoke.
- [ ] Keep the documentation brief and tied to the README quickstart story: install, init, doctor.
- **Status:** pending

### Phase 5: Validation
- [ ] Run `npm test`.
- [ ] Run `npm pack --dry-run` if package contents or build behavior changes.
- [ ] Record validation results in `.gcw/issues/30/progress.md`.
- **Status:** pending

## Risks
- The test may be slow if it shells through `npm pack` on every run; prefer a focused built-package invocation if it still exercises packaged assets.
- The smoke must not depend on developer-global GCW installs.
- The temp repository must be outside this repo to catch accidental source-tree coupling.

## Open Questions
- Should the test invoke a tarball-installed package, or is invoking the built package bin with packaged template assets sufficient for this issue?
- Which exact `gcw doctor` output should be asserted beyond a zero exit code?
