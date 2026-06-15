# Plan — Issue #13: Fetch Hosted Remote Evidence During Verification

## Goal

Enhance `verify_gcw_remote_evidence.py` so GCW can fetch hosted progress comments and review request bodies directly from GitHub or GitLab using URLs recorded in `workflow.json` and events. Callers should verify remote evidence from `--issue-dir` alone in the normal case, without first saving remote bodies into local files.

This is a prerequisite for reliable hosted review gates: Actions must verify what is actually on the platform.

## Current State

- `verify_gcw_remote_evidence.py` supports `progress-comment` and `review-request` subcommands.
- Both subcommands require `--remote-file` pointing at a local copy of the hosted body.
- Verification already compares rendered content, validates GCW markers, and checks recorded `body_hash` / `progress_comment_body_hash` where available.
- Tests in `test_verify_gcw_remote_evidence.py` cover offline `--remote-file` mode only.

## Phases

### Phase 1 — Platform fetch adapters

- [ ] Add a small `remote_fetch.py` (or equivalent module) with platform adapters behind a common interface:
  - `fetch_url(url: str) -> str` returning normalized UTF-8 body text.
  - GitHub adapter: parse issue comment URLs (`.../issues/<n>#issuecomment-<id>`) and PR/MR body URLs (`.../pull/<n>`); use `gh api` subprocess (consistent with existing GCW scripts).
  - GitLab adapter: parse issue note and MR URLs; use `glab api` subprocess.
- [ ] Clear error messages for: authentication failure, missing permissions, artifact not found, unsupported URL shape.
- [ ] Keep fetch logic separate from verification so tests can inject a fetch function.

### Phase 2 — CLI integration

- [ ] Make `--remote-file` optional for both subcommands.
- [ ] When `--remote-file` is omitted, resolve fetch URL from:
  - **Progress comment:** `workflow.json` `refs.progress_comment_url` (existing fallback in verifier).
  - **Review request:** `workflow.json` `refs.review_request_url` or latest `gcw-pr-publish` event payload.
- [ ] Add `--fetch-url` override for tests and diagnostics.
- [ ] Preserve existing `--remote-file` behavior unchanged for offline/local-substitutable checks.

### Phase 3 — Tests

- [ ] Mock/inject fetch layer; do not require live GitHub/GitLab in unit tests.
- [ ] GitHub fetch success path (mocked `gh api` or injected fetch).
- [ ] GitLab fetch success path or documented fallback when `glab` unavailable.
- [ ] Missing refs in projection (no URL to fetch).
- [ ] Body hash mismatch (existing cases extended to fetch path).
- [ ] Duplicate review-request markers (existing `test_hosted_artifact_hardening.py` coverage).
- [ ] Offline `--remote-file` mode regression (existing tests unchanged).

### Phase 4 — Documentation

- [ ] Document when to use direct remote fetch vs `--remote-file` in `docs/hosted-agent.md` or adjacent GCW docs.
- [ ] Note token requirements (`GITHUB_TOKEN` / `GH_TOKEN`, `glab` auth) for hosted Actions.

## Acceptance Criteria

- [ ] `verify_gcw_remote_evidence.py progress-comment` verifies latest progress comment by reading `refs.progress_comment_url` and fetching hosted body.
- [ ] `verify_gcw_remote_evidence.py review-request` verifies review request body from `refs.review_request_url` or latest `gcw-pr-publish` event.
- [ ] `--remote-file` mode remains available for tests and offline checks.
- [ ] Verification compares rendered content, validates GCW markers, checks recorded hashes.
- [ ] GitHub and GitLab fetch paths use platform adapters with actionable errors.
- [ ] Tests cover success, missing refs, hash mismatch, duplicate markers, and offline mode.
- [ ] Documentation explains fetch vs `--remote-file`.

## Out of Scope

- Changing progress comment or PR publish semantics.
- New hosted workflow YAML files (issue #12 territory).
- Live integration tests against real GitHub/GitLab APIs in CI.

## Implementation Notes

- Relevant files: `verify_gcw_remote_evidence.py`, `render_gcw_hosted_artifacts.py`, `validate_gcw_evidence.py`, `publish_progress_comment.py`.
- Follow existing subprocess patterns from `publish_progress_comment.py` and `triage_lib.py` for `gh`/`glab`.
- Prefer thin CLI changes delegating fetch to a testable module.
