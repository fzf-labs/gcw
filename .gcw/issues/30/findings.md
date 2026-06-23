# Findings & Decisions

## Issue Facts
- Issue: `#30` Add clean downstream gcw init smoke test.
- Request: add a clean downstream smoke test for the packaged GCW CLI.
- Target workflow from README: `npm install -g @fzf-labs/gcw`, then `gcw init`, then `gcw doctor`.
- Blockers: none recorded in the issue.
- Classification recorded by GCW triage: `documentation`, `area:tests`, `priority:p2`.

## Relevant Codebase Findings
- `package.json` defines the package as `@fzf-labs/gcw`, exposes the `gcw` bin at `./bin/gcw.js`, runs `npm run build` before pack, and runs tests with `node --test test/*.test.mjs`.
- `bin/gcw.js` imports `../lib/cli/main.js`, so a smoke test can invoke the CLI through the same bin entrypoint.
- `scripts/build-npm-package.mjs` builds `dist/templates/repo` from `.agents/skills/gcw*`, `.agents/skills/planning-with-files`, `.gcw/engine/runtime`, `.gcw/engine/platforms`, `.gcw/engine/hosted`, and workflow assets.
- `test/gcw-cli.test.mjs` already has helpers for temp directories, fake platform CLIs, copying fixtures, and invoking `bin/gcw.js`.
- The existing README quickstart explicitly promises `gcw init` followed by `gcw doctor` in a target repository.

## Planned Technical Approach
- Extend `test/gcw-cli.test.mjs` rather than adding a separate test runner.
- Create a temp downstream repo with `git init` outside the source tree.
- Run the build step before the smoke so package templates exist.
- Invoke the CLI through the package bin path or an installed tarball/bin shim, with `cwd` set to the downstream repo.
- Assert expected initialized assets exist and `.gcw/issues` does not.
- Run `gcw doctor` in the downstream repo and require success.

## Decisions
| Decision | Rationale |
| --- | --- |
| Put the smoke in `test/gcw-cli.test.mjs` | Keeps npm test coverage in the existing Node test workflow. |
| Use a temp downstream git repository | Directly satisfies the issue requirement and catches source-tree coupling. |
| Assert asset presence and absence of `.gcw/issues` | Verifies init copies repo-local assets without copying runtime issue state. |

## Risks
- Installing a tarball inside the test may add time and external npm behavior; a package-bin invocation may be enough if it uses built templates.
- Assertions should avoid being too brittle about `gcw doctor` wording unless the CLI already has stable output.
- Temporary directories must be cleaned even if the smoke fails.

## Validation Targets
- `npm test`
- `npm pack --dry-run` if the implementation changes package/build contents.
