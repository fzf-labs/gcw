# Findings — Issue #13

## Current State

- `verify_gcw_remote_evidence.py` only reads hosted bodies from `--remote-file` (local path).
- `progress-comment` subcommand already resolves `progress_comment_url` from projection `refs` when not passed explicitly, but still requires a local file for the body.
- `review-request` subcommand has no URL resolution; it only reads `--remote-file`.
- `workflow.json` projection stores `refs.progress_comment_url` and `refs.review_request_url` after relevant milestone events.
- Events record `progress_comment_body_hash` (milestone events) and `body_hash` (`gcw-pr-publish`).
- Existing tests (`test_verify_gcw_remote_evidence.py`, `test_hosted_artifact_hardening.py`) exercise offline verification only.

## Gap

Hosted Actions (e.g. `gcw-pr-review.yml`, `gcw-implement-check.yml`) cannot reliably verify remote artifacts without a manual pre-step to download comment/PR bodies into files. This blocks trustworthy remote gates.

## Proposed Design

### Fetch module

Introduce `remote_fetch.py` (name TBD) with:

| Function | Responsibility |
| --- | --- |
| `detect_platform(url)` | Return `github`, `gitlab`, or error |
| `fetch_text(url, platform=None)` | Return body text via adapter |
| `parse_github_comment_url(url)` | Extract owner/repo/issue/comment id for `gh api` |
| `parse_github_pr_url(url)` | Extract owner/repo/pr number for PR body fetch |
| GitLab equivalents | Issue note / MR note URLs via `glab api` |

Use subprocess to `gh`/`glab` (same pattern as `publish_progress_comment.py`) rather than adding HTTP client dependencies.

### CLI changes

| Mode | When | Args |
| --- | --- | --- |
| Remote fetch (default) | Hosted Actions, local with auth | `--issue-dir` only |
| Offline / test | Unit tests, air-gapped | `--remote-file` |
| Override | Diagnostics | `--fetch-url` |

Mutual exclusion: if both `--remote-file` and fetch URL resolution apply, prefer `--remote-file` (explicit offline wins).

### URL resolution

**Progress comment**

1. `--progress-comment-url` if set
2. Else `workflow.json` → `refs.progress_comment_url`
3. Fetch body → existing verify logic

**Review request**

1. `--review-request-url` if set (new flag)
2. Else `workflow.json` → `refs.review_request_url`
3. Else latest `gcw-pr-publish` event → `payload.review_request_url` or `refs.review_request_url`
4. Fetch PR/MR body → existing marker/hash verify logic

## Error Taxonomy

| Condition | Message shape |
| --- | --- |
| No URL in refs/events | `progress_comment_url is missing from projection refs` (existing) |
| Auth failure | `github fetch failed: authentication required` |
| 404 / not found | `github fetch failed: comment not found` |
| Unsupported URL | `unsupported github URL shape: ...` |
| Empty body | `remote progress comment file is empty` (reuse existing) |

## Risks

- **Token scope in Actions:** `issues: read` for comments, `pull-requests: read` for PR bodies; document in hosted-agent docs.
- **GitLab parity:** `glab` may not be installed in all runners; tests should mock; document GitLab as best-effort if runner lacks `glab`.
- **URL formats:** GitHub issue comment fragment URLs vs API URLs; parser must handle hosted comment links stored in events.

## References

- Issue: https://github.com/fzf-labs/gcw/issues/13
- Related: issue #12 (hosted workflows that will consume this verifier)
- Fixture: `.agents/skills/gcw/tests/fixtures/complete_issue/`
- Existing verifier tests: `.agents/skills/gcw/tests/test_verify_gcw_remote_evidence.py`
