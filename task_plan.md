# GCW Remaining Requirements Completion Plan

## Goal

Complete the remaining GCW requirements that were deferred after the local/checkable Phase 1 slice, while keeping all hosted mutations explicit, owned, and testable.

## Scope

- Add hosted apply workflow support for GitHub and GitLab where ownership permits state, issue progress comment, branch, and review request mutations.
- Add remote API verification that checks hosted progress comments and review request bodies against local readiness evidence.
- Complete end-to-end ownership handoff and enforcement for local, GitHub Actions, GitLab CI, and manual owners.
- Add the documented cloud agent or `/fix` loop path when the repository has enough platform primitives to support it safely.
- Keep deterministic local validators and tests as the source of truth for behavior that can run without credentials.
- Update documentation, fixtures, and CI coverage.

## Out of Scope

- Performing real remote write operations from this local session without explicit approval.
- Force-push, branch deletion, merging, issue closing, or overwriting another owner.
- Guessing unavailable cloud runner credentials or platform-specific secrets.

## Phases

1. In progress: Refresh planning files and inventory the existing executable workflow surface.
2. Complete: Add behavior tests for ownership-gated hosted apply.
3. Complete: Add behavior tests for remote API verification inputs and results.
4. Complete: Implement hosted apply helpers and fail-closed workflow wiring.
5. Complete: Implement remote verification helpers for GitHub and GitLab evidence checks.
6. Complete: Add or document the supported cloud agent `/fix` loop path.
7. Complete: Update GCW docs, skill instructions, fixtures, and CI coverage.
8. Complete: Run full validation and inspect final repository status.

## Validation Plan

- `python3 -m unittest discover -s .agents/skills/gcw/tests`
- `python3 -m unittest discover -s .github/tests`
- `python3 -m py_compile .agents/skills/gcw/scripts/*.py`
- Static inspection of `.github/workflows/ci.yml` and `.gitlab-ci.yml`
- Final `git status --short --branch`

## Stop Conditions

- A step requires real hosted write credentials or a remote mutation.
- A workflow would bypass `state.json.owner` or an explicit handoff.
- A requirement depends on a cloud platform primitive that is not present in the repository.
- The same validation failure repeats after three distinct fixes.
