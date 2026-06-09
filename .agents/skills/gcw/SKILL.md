---
name: gcw
description: Orchestrate the Git Collaboration Workflow from a GitHub or GitLab issue to a complete-on-create review request ready for review. Use when the user invokes /gcw, asks to process an issue end-to-end, or wants an agent to take an issue through branch, planning, implementation, commit, push, and PR/MR creation.
---

# GCW

Run the GCW **Issue to Ready for Review** workflow. This is a top-level orchestration skill: reuse the focused `issue-`, `git-`, `pr-`, `planning-with-files`, and `tdd` packages instead of reimplementing their detailed rules.

## Scope

Do:

- Start from one GitHub or GitLab issue.
- Create an isolated issue worktree and make it the agent workspace when the environment supports it.
- Create planning files under `.gcw/issues/<issue-id>/` for every issue.
- Publish planning files with a first standalone planning commit.
- Maintain one updatable issue progress comment with links to the current planning files on the issue branch.
- Implement behavior changes with TDD unless the issue is not a behavior change.
- Create a complete-on-create review request ready for review.

Do not:

- Start from local-only tasks, chat-only requests, or untracked work items.
- Guess implementation when the issue lacks material information.
- Merge the review request, close the issue, force-push, delete branches, or alter someone else's authored content without explicit approval.
- Automatically run `pr-review` after the review request is ready for review.

## Required Context

Before executing, read `CONTEXT.md` and apply its vocabulary. Key GCW terms include `Issue`, `Issue Worktree`, `Planning Files`, `Issue Progress Comment`, `Implementation Gate`, `TDD Implementation`, `Local Self-Review`, `Complete-on-Create`, and `Ready for Review`.

## Workflow

### 1. Intake the issue

1. Identify the Git hosting platform, repository, and issue number from the user's input or current repository.
2. Use `issue-summarize` to read the issue and comments.
3. Decide whether the issue is actionable.
   - If material information is missing before an issue worktree and planning files exist, add a normal issue clarification comment using `issue-manage` and stop. Do not create a branch, planning files, or progress comment just to ask the question.
   - If material information becomes missing after planning files and an issue progress comment exist, set the progress snapshot status to `clarifying`, update the issue with the missing questions using `issue-manage`, and stop before creating implementation changes.
   - If the issue is actionable, continue.

### 2. Create the issue worktree

1. Use `git-worktree` to create a branch and worktree for the issue.
2. Use issue-backed branch naming from `git-branch` / `git-worktree`.
3. Start from a fresh base before the first planning commit is pushed. After the issue branch has been pushed, do not rebase it without explicit approval; merge the base branch instead when base sync is required.
4. In Cursor, after the worktree is created, move the agent workspace to the issue worktree using `cursor-app-control` when available. Always inspect the MCP tool descriptor before calling MCP tools.
5. Treat the agent in that worktree as the single owning agent for write operations.

### 3. Create planning files

Create these files under `.gcw/issues/<issue-id>/` in the issue worktree:

```text
.gcw/issues/<issue-id>/task_plan.md
.gcw/issues/<issue-id>/findings.md
.gcw/issues/<issue-id>/progress.md
```

Initialize the machine-readable workflow snapshot:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py init-state \
  --issue-dir .gcw/issues/<issue-id> \
  --issue <issue-id> \
  --platform <github|gitlab> \
  --repository <owner/repo> \
  --branch <branch> \
  --owner-kind local \
  --owner-id <agent-session-id>
```

Use the structure and discipline from `planning-with-files`, adapted to the GCW path. Even small issues require planning files. Explicitly read and update the `.gcw/issues/<issue-id>/` files; do not rely on root-level planning hooks to discover them.

For scripted execution, prefer the unified step runner when it supports the step. It keeps check/apply terminology consistent while delegating to the validator and state manager:

```bash
python3 .agents/skills/gcw/scripts/gcw_step.py state --mode check --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/gcw_step.py readiness-check --mode check --issue-dir .gcw/issues/<issue-id>
```

Minimum contents:

- `task_plan.md`: goal, issue link, assumptions, phases, acceptance criteria, validation plan.
- `findings.md`: issue facts, codebase discoveries, decisions, risks, open questions.
- `progress.md`: timestamped progress, commands/checks run, errors, checkpoints.

### 4. Publish planning context

1. Commit only the initial planning files as the first standalone planning commit.
   - Suggested message: `docs: add planning files for issue #<issue-id>`
2. Push the issue branch using `git-push`.
3. Create or update one issue progress comment using `issue-manage`.

The progress comment is a current-state dashboard, not a comment stream. Include:

```markdown
<!-- gcw-progress -->
## GCW Progress

Status: planning
Branch: <branch>

Planning Files:
- task_plan.md: <branch file URL>
- findings.md: <branch file URL>
- progress.md: <branch file URL>

Latest Checkpoint:
- Planning files created and published.

Review Request: Not created yet.
```

Use branch file URLs, not commit-SHA URLs, so links point to the latest planning files on the issue branch.

Branch file URL templates:

```text
GitHub: https://github.com/<owner>/<repo>/blob/<branch>/.gcw/issues/<issue-id>/<file>
GitLab: https://gitlab.com/<group>/<project>/-/blob/<branch>/.gcw/issues/<issue-id>/<file>
```

If the branch name contains `/`, use the hosting platform's copied file URL or URL-encode the branch when required.

When updating the progress comment, target the comment containing `<!-- gcw-progress -->` that was authored by the authenticated user. If no such comment exists, create it. If a marker exists only on a comment authored by someone else, ask before editing it.

Record the published planning evidence in `state.json`:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-publish-planning \
  --issue-dir .gcw/issues/<issue-id> \
  --progress-comment-url <issue-progress-comment-url>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py state --issue-dir .gcw/issues/<issue-id>
```

### 5. Pass the implementation gate

Do not modify product code until the Implementation Gate passes. Verify and record each gate item in `.gcw/issues/<issue-id>/progress.md`:

- Planning files exist under `.gcw/issues/<issue-id>/`.
- The planning commit has been pushed to the issue branch.
- The issue progress comment links to the branch versions of `task_plan.md`, `findings.md`, and `progress.md`.
- The issue is still actionable; otherwise move to `clarifying` or `blocked`.
- The progress snapshot status has moved from `planning` to `implementing`.

Update the issue progress comment to `implementing` immediately before editing product code. If any gate item is missing, stop before implementation, update `progress.md` with the missing evidence, and update the issue progress comment with the current blocker.

Write `.gcw/issues/<issue-id>/implementation_gate_result.json`, update `state.json` to `implementing`, and validate the gate before implementation:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-implementation-gate \
  --issue-dir .gcw/issues/<issue-id> \
  --progress-comment-url <issue-progress-comment-url> \
  --issue-actionable true
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py implementation-gate --issue-dir .gcw/issues/<issue-id>
```

If the gate finds a missing decision, record the clarifying transition instead of beginning implementation:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-implementation-gate \
  --issue-dir .gcw/issues/<issue-id> \
  --progress-comment-url <issue-progress-comment-url> \
  --issue-actionable false \
  --clarifying-question <question-for-the-issue>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py state --issue-dir .gcw/issues/<issue-id>
```

### 6. Implement the issue

1. For behavior changes, use `tdd` by default.
2. For docs, config, chore, or other non-behavior changes, record why TDD is not applicable in `progress.md`.
3. Keep planning files current locally as work progresses.
4. Use planning checkpoints at key stages instead of committing every small planning edit.
5. Use `git-commit` for focused implementation commits and `git-push` to publish them.

If blocked, update planning files and the issue progress comment with status `blocked` or `clarifying`, record one matching state transition, then stop with a concise blocker summary:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-block \
  --issue-dir .gcw/issues/<issue-id> \
  --reason <blocker-summary>
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-clarify \
  --issue-dir .gcw/issues/<issue-id> \
  --question <clarifying-question>
```

### 7. Perform local self-review

Before creating the review request:

- Inspect the local diff for accidental files, secrets, conflict markers, generated churn, and unrelated changes.
- Confirm planning files reflect the final state.
- Confirm tests or validation were run, or record why they were not.
- Confirm commit boundaries are clear.
- Prepare complete-on-create review request content.

Record the local self-review result in `.gcw/issues/<issue-id>/progress.md` with:

- Diff reviewed: notable files and any excluded changes.
- Validation: commands or checks run, with results.
- Planning state: whether `task_plan.md`, `findings.md`, and `progress.md` reflect the final implementation.
- Commit boundaries: why the current commits are reviewable.
- Risks and reviewer notes to carry into the review request.

Then record local self-review evidence in `state.json`:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-local-self-review \
  --issue-dir .gcw/issues/<issue-id> \
  --progress-section "## Local Self-Review"
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py state --issue-dir .gcw/issues/<issue-id>
```

Then create a final planning checkpoint before the review request:

- Commit any changed planning files together with the final implementation commit when they belong to that change, or as a focused planning checkpoint commit when only planning files changed.
- Push the branch with `git-push`.
- Update the issue progress comment with the latest checkpoint.
- Ensure the worktree is clean, except for changes intentionally excluded from the review request.

### 8. Create the review request

Before invoking `pr-create`, assemble Readiness Evidence from the current branch:

- Linked issue and intended closing/reference keyword.
- Branch name, base branch, and commit range.
- Summary of implementation scope and non-goals.
- Validation performed, including any skipped validation and why.
- Local self-review result from `progress.md`.
- Links to planning files and the issue progress comment.
- Known risks, migration notes, or reviewer notes.

Write `.gcw/issues/<issue-id>/readiness_evidence.json` and validate it. This records readiness evidence but keeps `state.json` in `implementing`; only `create-review-request` moves the workflow to `ready-for-review`.

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-readiness-evidence \
  --issue-dir .gcw/issues/<issue-id> \
  --base-branch <base-branch> \
  --commit-range <base-branch>...<branch> \
  --title <review-request-title> \
  --summary <summary> \
  --issue-link "Closes #<issue-id>" \
  --validation-command <validation-command> \
  --validation-result <passed|failed|skipped> \
  --risks <risks-or-reviewer-notes>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py readiness-check --issue-dir .gcw/issues/<issue-id>
```

Use `pr-create` to create or update the GitHub Pull Request or GitLab Merge Request.

After the review request exists, record the transition to `ready-for-review`:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-review-request \
  --issue-dir .gcw/issues/<issue-id> \
  --review-request-url <review-request-url>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py state --issue-dir .gcw/issues/<issue-id>
```

The review request must be complete-on-create. Include:

- Summary.
- Issue link such as `Closes #<issue-id>`, `Fixes #<issue-id>`, or `Refs #<issue-id>`.
- Validation performed.
- Scope and notable non-goals.
- Risks or reviewer notes.
- Links to the planning files or issue progress comment.

After creation, update the issue progress comment:

- Status: `ready-for-review`.
- Latest checkpoint: review request created.
- Review Request: URL.

## Ownership Handoff

When a local agent, hosted workflow, or human is intentionally taking over future write operations, record the handoff in `state.json` and update the issue progress comment with the same reason:

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-handoff \
  --issue-dir .gcw/issues/<issue-id> \
  --owner-kind <local|github-actions|gitlab-ci|manual> \
  --owner-id <runner-or-session-id> \
  --reason <handoff-reason>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py state --issue-dir .gcw/issues/<issue-id>
```

Do not use handoff to bypass another active owner. If ownership is unclear, ask before allowing a runner to push branch changes or update hosted state.

## High-Risk Operations

Ask for explicit approval before any high-risk operation:

- Force push or history rewrite.
- Merge a review request.
- Close or delete an issue.
- Delete branches or worktrees.
- Modify someone else's authored issue comment or review request text.
- Publish content that may contain secrets, credentials, private customer data, or sensitive security details.

Routine GCW steps do not require extra confirmation when the user has asked `/gcw` to process a specific issue.
