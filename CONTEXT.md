# Git Collaboration Workflow

Git Collaboration Workflow defines the language for coordinating local Git development with hosted GitHub or GitLab collaboration workflows through agent-facing workflow packages.

## Language

**Git Collaboration Workflow**:
The product context for agent-assisted development that can run through local Git operations or hosted GitHub/GitLab review workflows.
_Avoid_: Git workflow, Git collaboration, GCW workflow

**Workflow Kit**:
A distributable set of workflow packages that equips coding agents to carry Git collaboration work from task intake through review readiness.
_Avoid_: Skill, plugin, toolkit

**Workflow Package**:
A named capability within the workflow kit. The top-level orchestration package is `gcw`, while focused packages use explicit prefixes such as `issue-`, `git-`, and `pr-`.
_Avoid_: Renamed domain concept, generic skill name

**Agent-Assisted Developer**:
The person who owns the development intent and delegates Git collaboration work to coding agents.
_Avoid_: End user, operator

**Coding Agent**:
An AI coding system that performs delegated Git collaboration steps on behalf of an agent-assisted developer.
_Avoid_: Autonomous agent, bot

**Owning Agent**:
The single coding agent responsible for write operations in an issue worktree during the review-ready loop.
_Avoid_: Agent pool, shared writer, parallel writer

**Review-Ready Loop**:
The v1 collaboration loop that carries an issue from intake through branch, implementation, commit, push, and ready for review.
_Avoid_: Full SDLC, release workflow

**Issue to Ready for Review**:
The main `gcw` workflow that starts from a GitHub or GitLab issue and ends with a complete-on-create review request ready for code review.
_Avoid_: Issue to PR, task to done, implementation workflow

**Issue**:
The required work entry point for GCW, representing a GitHub or GitLab collaboration item that can be developed, linked, reviewed, and closed through the review-ready loop. Local-only work items are not issues in GCW.
_Avoid_: Task, request, ticket, local issue

**Issue Clarification**:
The state where GCW pauses implementation because an issue lacks material information needed for safe development. Before planning exists this is a normal issue comment; after planning exists it is reflected in the issue progress comment.
_Avoid_: Guessing, speculative implementation

**Planning Files**:
The required file-based working memory created under `.gcw/issues/<issue-id>/` inside the issue worktree, capturing the plan, findings, and progress from intake through ready for review. Planning files are part of the review request diff and may be merged to the base branch.
_Avoid_: Optional plan, complex-task plan, chat-only plan

**Planning Recovery**:
The resume behavior where GCW reads `.gcw/issues/<issue-id>/task_plan.md`, `findings.md`, and `progress.md` before continuing issue work after interruption or context loss.
_Avoid_: Chat-only recovery, root-only plan discovery

**Planning Commit**:
The first standalone commit on an issue branch, publishing planning files so the issue progress comment can link to them on the Git hosting platform.
_Avoid_: Local-only plan, uncommitted planning files

**Planning Checkpoint**:
A key-stage update where changed planning files are committed or pushed with the issue work, rather than after every minor progress edit.
_Avoid_: Progress spam, every-edit commit

**Implementation Gate**:
The requirement that planning files are published and linked from the issue progress comment before GCW begins implementation work.
_Avoid_: Code-first start, unlinked planning

**TDD Implementation**:
The default implementation discipline for GCW behavior changes, using test-first cycles and recording why TDD is not applicable for non-behavior changes.
_Avoid_: Test-after implementation, unvalidated behavior change

**Issue Progress Comment**:
A single updatable issue comment that records the coding agent's GCW progress and links to the current planning files on the issue branch.
_Avoid_: Hidden local plan, chat-only progress, unlinked planning files, progress comment stream

**Progress Snapshot**:
The current status summary inside an issue progress comment, including status, branch, planning file links, latest checkpoint, and review request link when available.
_Avoid_: Full progress log, comment history, ad hoc update

**GCW Status**:
The stable stage shown in a progress snapshot. The v1 statuses are `planning`, `clarifying`, `implementing`, `blocked`, and `ready-for-review`.
_Avoid_: Command state, transient step, detailed progress log

**Issue Worktree**:
The isolated worktree GCW creates by default for developing one issue without disturbing the developer's current workspace or other issue work.
_Avoid_: Shared checkout, current workspace by default

**Agent Workspace**:
The repository root where a coding agent performs commands and edits files. In Cursor, GCW moves the agent workspace to the issue worktree after creating it.
_Avoid_: Original checkout, terminal cwd only

**Git Hosting Platform**:
A hosted Git collaboration service that supplies issues and code review objects for GCW. GitHub and GitLab are the v1 platforms, with GitHub as the first complete implementation path.
_Avoid_: Git server, remote, forge

**Review Request**:
The hosted code review object created from a branch to make issue work ready for review. A GitHub Pull Request and a GitLab Merge Request are platform-specific review requests.
_Avoid_: PR/MR, pull request, merge request

**Complete-on-Create**:
The quality rule that a review request should be created with the issue link, summary, validation, scope, risks, and reviewer notes needed for effective review.
_Avoid_: Empty review request, placeholder PR, placeholder MR

**Ready for Review**:
The target state where an issue's review request is prepared for code review on its Git hosting platform.
_Avoid_: Review-ready candidate, merge ready, draft

**Review Support**:
Optional workflow package activity after ready for review, such as reviewing a review request, investigating CI failures, or helping respond to reviewer feedback.
_Avoid_: Required ready-for-review step, automatic self-review

**Readiness Evidence**:
The evidence a coding agent provides when creating a ready for review request, covering the linked issue, branch, diff, commits, validation, and review request summary.
_Avoid_: Completion note, final message, status update

**Local Self-Review**:
The required pre-review-request check where the coding agent inspects the local diff, planning files, validation results, commit boundaries, and review request content.
_Avoid_: Remote code review, reviewer approval, casual final scan

**High-Risk Operation**:
A Git collaboration action that requires explicit human approval because it can destroy work, change shared history, merge code, close work, or alter someone else's authored content.
_Avoid_: Normal review-ready step, routine operation


