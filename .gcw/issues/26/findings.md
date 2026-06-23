# Findings — Issue #26: Repository LICENSE and npm package license

## Issue summary

Issue #26 asks GCW to resolve the open licensing question called out during issue #19 implementation: the repo has no root `LICENSE`, while `package.json` currently declares `"license": "UNLICENSED"`.

## Current state

| Artifact | Current value | Notes |
| --- | --- | --- |
| Root `LICENSE` | Missing | No license file in repository root |
| `package.json` `"license"` | `UNLICENSED` | Blocks accurate npm metadata |
| `CONTRIBUTING.md` | Notes license strategy is undecided | Line references open question |
| `README.md` | No explicit license section | Install/publish guidance does not mention licensing |
| Issue #19 artifacts | Flagged UNLICENSED as moderate risk | Expected follow-up issue |

## Constraints from prior work

- Issue #19 packaged `@fzf-labs/gcw` for public npm install with `publishConfig.access: public`.
- Prior implement-check notes explicitly deferred license selection to a follow-up issue (this issue).
- GCW structural readiness checks pass; the remaining gap is the business choice of license, not missing acceptance criteria.

## License options considered

| Option | Pros | Cons |
| --- | --- | --- |
| **MIT** (recommended) | Simple, widely understood, common for npm CLIs/tools | Very permissive; no patent grant language |
| **Apache-2.0** | Explicit patent grant, common in tooling ecosystems | Longer license text; slightly heavier for a small CLI package |
| **ISC** | Functionally similar to MIT, shorter text | Less immediately recognizable to some contributors |

## Recommended approach

1. Human reviewers confirm SPDX id during the `planned` handoff.
2. Add standard root `LICENSE` text for the confirmed id.
3. Set `package.json` `"license"` to the same SPDX id.
4. Update `CONTRIBUTING.md` and any install/publish notes that still describe licensing as undecided.

## Decisions (confirmed)

1. **SPDX license:** `MIT`
2. **Copyright holder line:** `fzf-labs`
3. **Source file headers:** out of scope for this issue
