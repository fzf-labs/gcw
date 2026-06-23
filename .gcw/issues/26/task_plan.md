# Plan — Issue #26: Repository LICENSE and npm package license

## Goal

Choose a repository license, add the corresponding `LICENSE` file at the repo root, and align npm package metadata and user-facing docs so `@fzf-labs/gcw` no longer advertises `UNLICENSED`.

## Phases

### Phase 1 — License decision (human review required)

- [ ] Confirm the SPDX license identifier with maintainers (recommended default: `MIT`).
- [ ] Record the decision in this spec and in the issue if the choice differs from the recommendation.
- **Status:** pending

### Phase 2 — Repository license file

- [ ] Add root `LICENSE` with the full license text for the chosen SPDX id.
- [ ] Use the standard copyright holder line for `fzf-labs/gcw` maintainers.
- **Status:** pending

### Phase 3 — Package and documentation alignment

- [ ] Update `package.json` `"license"` field to match the chosen SPDX id.
- [ ] Update `CONTRIBUTING.md` to remove the "license strategy still open" note and describe the chosen license.
- [ ] Scan `README.md` and publish/install notes for any licensing mentions that still reference `UNLICENSED` or an undecided policy.
- **Status:** pending

### Phase 4 — Verification

- [ ] Confirm `LICENSE` exists and matches the chosen license text.
- [ ] Confirm `package.json` license metadata matches the repository license.
- [ ] Run `npm pack --dry-run` and verify package metadata still looks correct.
- [ ] Run existing tests (`npm test`, Python GCW tests) to ensure no packaging regressions.
- **Status:** pending

## Acceptance Criteria

- [ ] The repository contains a `LICENSE` file with the chosen license text.
- [ ] `package.json` license metadata matches the chosen repository license.
- [ ] Any user-facing install/publish notes that mention licensing are updated if needed.

## Out of Scope

- Changing npm publish scope, registry config, or release automation.
- Adding license headers to every source file unless maintainers explicitly request it in review.
- Legal review beyond selecting a standard open-source SPDX license.

## Recommended Default

Use **MIT** unless maintainers prefer another standard permissive license (for example `Apache-2.0`). MIT is common for public npm CLI packages and matches the current public `publishConfig.access: public` posture.

## Risks

- Choosing the wrong license has maintainer/legal implications; implementation must wait for human confirmation during spec review if the default is not accepted.
