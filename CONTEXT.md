# Git Collaboration Workflow

Git Collaboration Workflow 定义了本地 Git 开发与 GitHub/GitLab 托管协作之间的共同语言。它通过面向 agent 的 workflow packages，让 coding agent 能稳定推进 Issue 工作。

## 术语

**Git Collaboration Workflow**:
本项目面向人机协作开发的核心概念。它既支持本地 Git 操作，也可以接入 GitHub/GitLab 上的托管 review workflow。
_避免使用_: Git workflow, Git collaboration, GCW workflow

**Workflow Kit**:
一组可分发的 workflow packages，帮助 coding agent 从接收任务一直推进到审查结束。
_避免使用_: Skill, plugin, toolkit

**Workflow Package**:
Workflow Kit 中的具名能力。顶层编排包是 `gcw`，聚焦包使用 `issue-`、`git-`、`pr-` 等明确前缀。
_避免使用_: 重命名领域概念、泛化 skill 名称

**Agent-Assisted Developer**:
提出开发目标，并将 Git collaboration 工作委托给 coding agent 的人。
_避免使用_: end user, operator

**Coding Agent**:
代表 agent-assisted developer 执行 Git collaboration 步骤的 AI coding system。
_避免使用_: autonomous agent, bot

**Owning Agent**:
在一个 issue worktree 中负责写操作的唯一 coding agent。
_避免使用_: agent pool, shared writer, parallel writer

**Review Lifecycle**:
完整协作闭环。从 Issue 创建或接入开始，经过分类、评论讨论、规划、实现、创建 review request、机审、人审，最终到达 `review-complete`。
_避免使用_: full SDLC, release workflow

**Issue to Review Complete**:
主 `gcw` 工作流。从创建或接入 GitHub/GitLab Issue 开始，以人类审查结束并记录结果为结束点。
_避免使用_: Issue to PR, task to done, implementation workflow

**Issue**:
GCW 必需的工作入口，代表 GitHub 或 GitLab 上可以开发、链接、审查和关闭的协作项。纯本地工作项不属于 GCW 中的 Issue。
_避免使用_: task, request, ticket, local issue

**Issue Triage**:
Issue 创建后的分类步骤，用于判断类型、优先级、影响范围、重复关系和初始 labels。
_避免使用_: ad hoc label update, hidden prioritization

**Issue Discussion**:
通过 Issue comments 补充背景、确认边界、澄清验收标准和记录关键决定的协作过程。
_避免使用_: private clarification, chat-only decision

**Issue Clarification**:
当 Issue 缺少安全开发所需的重要信息时，GCW 会暂停进入规划或实现，并等待澄清。planning files 创建前，澄清写在普通 Issue comment 中；planning files 创建后，澄清也会体现在 issue progress comment 中。
_避免使用_: guessing, speculative implementation

**Ready for Planning**:
Issue 已经讨论清楚、具备可执行信息，可以开始创建 issue worktree 和 planning files 的状态。
_避免使用_: ready for implementation, code-first start

**Planning Files**:
在 Issue 已经进入 `ready-for-planning` 后，于 issue worktree 的 `.gcw/issues/<issue-id>/` 下创建的必需工作记忆。它们记录 plan、findings 和 progress，并会随分支出现在 review request diff 中。
_避免使用_: optional plan, complex-task plan, chat-only plan

**Planning Recovery**:
中断或上下文丢失后，GCW 通过读取 `.gcw/issues/<issue-id>/task_plan.md`、`findings.md`、`progress.md` 恢复工作。
_避免使用_: chat-only recovery, root-only plan discovery

**Planning Commit**:
Issue 分支上的第一个独立提交，用于发布 planning files，并让 Issue comment 能链接到托管平台上的文件。
_避免使用_: local-only plan, uncommitted planning files

**Planning Checkpoint**:
关键阶段更新。更新后的 planning files 会随 Issue 工作一起提交或推送，而不是每次小的 progress 编辑都单独提交。
_避免使用_: progress spam, every-edit commit

**Implementation Gate**:
判断是否可以开始实现的强制检查点。只有当 Issue 已经进入 `ready-for-planning`、planning files 位于 `.gcw/issues/<issue-id>/`、planning commit 已推送、Issue comment 已链接到分支文件，并且 Issue 已具备可执行信息时，gate 才能通过；通过后 workflow 状态进入 `ready-for-implementation`。
_避免使用_: code-first start, unlinked planning

**TDD Implementation**:
GCW 行为变更默认采用的实现纪律，遵循 test-first cycle。非行为变更需要记录为什么 TDD 不适用。
_避免使用_: test-after implementation, unvalidated behavior change

**Issue Progress Comment**:
一个可更新的 Issue comment，用于记录 coding agent 的 GCW 进度，并链接到 issue branch 上当前版本的 planning files。
_避免使用_: hidden local plan, chat-only progress, unlinked planning files, progress comment stream

**Progress Snapshot**:
Issue progress comment 中的当前状态摘要，包含 status、branch、planning file links、latest checkpoint，以及可用时的 review request link。
_避免使用_: full progress log, comment history, ad hoc update

**GCW Status**:
Progress snapshot 中展示的稳定阶段。目标状态包括 `issue-opened`、`issue-triaging`、`issue-clarifying`、`ready-for-planning`、`planning`、`planned`、`ready-for-implementation`、`implementing`、`ready-for-review-request`、`ready-for-review`、`machine-reviewing`、`machine-review-failed`、`human-reviewing`、`changes-requested`、`approved`、`blocked`、`review-complete`。
_避免使用_: command state, transient step, detailed progress log

**Issue Worktree**:
GCW 默认会为每个 Issue 创建隔离 worktree，用于避免干扰开发者当前工作区或其他 Issue 工作。
_避免使用_: shared checkout, current workspace by default

**Agent Workspace**:
coding agent 执行命令和编辑文件时所在的仓库根目录。在 Cursor 中，GCW 创建 issue worktree 后，会将 agent workspace 移到该 worktree。
_避免使用_: original checkout, terminal cwd only

**Git Hosting Platform**:
提供 Issue 和 code review 对象的托管 Git 协作服务。目标平台是 GitHub 和 GitLab，其中 GitHub 是第一条完整实现路径。
_避免使用_: Git server, remote, forge

**Review Request**:
从分支创建的托管 code review 对象，用于让 Issue 工作进入机审和人审流程。GitHub Pull Request 和 GitLab Merge Request 是平台特定的 review request。
_避免使用_: PR/MR, pull request, merge request

**Complete-on-Create**:
Review request 创建时就应包含有效 review 所需的 Issue link、summary、validation、scope、risks 和 reviewer notes。
_避免使用_: empty review request, placeholder PR, placeholder MR

**Ready for Review**:
Review request 已创建或更新，并包含进入代码审查所需信息的中间状态。它不是 GCW 的终点。
_避免使用_: review-ready candidate, merge ready, draft

**Machine Review**:
Review request 创建后由 CI、静态检查、remote artifact verification 或 AI review 执行的自动审查阶段。
_避免使用_: human approval, merge gate, casual CI check

**Human Review**:
Machine review 通过或被人类接受后，由 reviewer 对 review request 做出的审查阶段。
_避免使用_: automatic approval, self-approval, machine-only review

**Changes Requested**:
人类 reviewer 要求修改后的状态。coding agent 需要回到实现流程，修复后重新自查、更新 evidence 和 review request。
_避免使用_: final rejection, blocked, machine failure

**Review Complete**:
人类审查已经结束且结果已记录的终点状态。结果可以是已批准、已合并、已关闭、明确不再继续，或项目定义的其他终结结论。
_避免使用_: ready for review, machine passed, draft complete

**Action Pipeline**:
可以由一个 GitHub Actions、GitLab CI 或其他自动化入口连续执行的一组 GCW steps。
_避免使用_: one giant script, hidden automation, unowned mutation

**Hosted Apply Workflow**:
手动触发的 GitHub Actions 或 GitLab CI workflow。只有当 `state.json.owner.kind` 与 hosted runner 匹配时，它才能应用 GCW 状态转换、更新 issue progress comment 和 review request body、提交 evidence changes 并推送。
_避免使用_: unowned CI write, automatic remote mutation

**Remote Artifact Verification**:
确定性检查。它会将从 GitHub/GitLab 抓取的 issue progress comment 文本和 review request body 文本，与本地 readiness evidence 进行比较。
_避免使用_: assuming hosted state matches local files

**Readiness Evidence**:
证明 review request 已准备好进入 review 的证据包。它覆盖 linked issue、branch、intended diff、commit boundaries、validation、planning file links、local self-review result、risks，以及 complete-on-create review request summary。
_避免使用_: completion note, final message, status update

**Local Self-Review**:
创建或更新 review request 前必需的检查。coding agent 会检查 local diff、planning files、validation results、commit boundaries 和 review request content，并将结果作为 readiness evidence 记录在 `progress.md`。
_避免使用_: remote code review, reviewer approval, casual final scan

**High-Risk Operation**:
可能破坏工作、改变共享历史、合并代码、关闭工作项或修改他人 authored content 的 Git collaboration 操作。执行这类操作前，必须获得明确的人类批准。
_避免使用_: normal review-ready step, routine operation
