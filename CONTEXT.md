# Git Collaboration Workflow

Git Collaboration Workflow 定义了本地 Git 开发与 GitHub/GitLab 托管协作流程之间的协调语言。它通过面向 agent 的 workflow packages，让 coding agent 能稳定地推进 Issue 工作。

## 术语

**Git Collaboration Workflow**:
面向 agent-assisted development 的产品上下文。它可以通过本地 Git 操作，也可以通过 GitHub/GitLab 托管 review workflow 运行。
_避免_: Git workflow, Git collaboration, GCW workflow

**Workflow Kit**:
可分发的 workflow package 集合，用于装备 coding agent，让它能从任务接入推进到 ready for review。
_避免_: Skill, plugin, toolkit

**Workflow Package**:
Workflow kit 中的具名能力。顶层编排包是 `gcw`，聚焦包使用 `issue-`、`git-`、`pr-` 等明确前缀。
_避免_: 重命名领域概念、泛化 skill 名称

**Agent-Assisted Developer**:
拥有开发意图，并将 Git collaboration 工作委托给 coding agent 的人。
_避免_: end user, operator

**Coding Agent**:
代表 agent-assisted developer 执行 Git collaboration 步骤的 AI coding system。
_避免_: autonomous agent, bot

**Owning Agent**:
在一个 issue worktree 中负责写操作的唯一 coding agent。
_避免_: agent pool, shared writer, parallel writer

**Review-Ready Loop**:
v1 协作闭环，从 Issue 接入开始，经过分支、实现、提交、推送，直到 ready for review。
_避免_: full SDLC, release workflow

**Issue to Ready for Review**:
主 `gcw` 工作流，从 GitHub/GitLab Issue 开始，到创建 complete-on-create review request 并准备好 code review 结束。
_避免_: Issue to PR, task to done, implementation workflow

**Issue**:
GCW 必需的工作入口，代表 GitHub 或 GitLab 上可开发、可链接、可 review、可关闭的协作项。纯本地工作项不是 GCW 中的 Issue。
_避免_: task, request, ticket, local issue

**Issue Clarification**:
当 Issue 缺少安全开发所需的重要信息时，GCW 暂停实现的状态。规划文件存在前，这是普通 Issue clarification comment；规划文件存在后，它会体现在 issue progress comment 中。
_避免_: guessing, speculative implementation

**Planning Files**:
在 issue worktree 的 `.gcw/issues/<issue-id>/` 下创建的必需文件型工作记忆。它们记录 plan、findings 和 progress，并会作为 review request diff 的一部分进入分支。
_避免_: optional plan, complex-task plan, chat-only plan

**Planning Recovery**:
中断或上下文丢失后，GCW 通过读取 `.gcw/issues/<issue-id>/task_plan.md`、`findings.md`、`progress.md` 恢复工作的行为。
_避免_: chat-only recovery, root-only plan discovery

**Planning Commit**:
Issue 分支上的第一个独立提交，用于发布 planning files，让 issue progress comment 可以链接到托管平台上的文件。
_避免_: local-only plan, uncommitted planning files

**Planning Checkpoint**:
关键阶段更新。变化后的 planning files 会随 Issue 工作提交或推送，而不是每次微小 progress 编辑都提交。
_避免_: progress spam, every-edit commit

**Implementation Gate**:
判断是否可以开始实现的强制检查点。只有当 planning files 存在于 `.gcw/issues/<issue-id>/`、planning commit 已推送、issue progress comment 链接到分支文件、progress snapshot 已进入 `implementing` 时，gate 才通过。
_避免_: code-first start, unlinked planning

**TDD Implementation**:
GCW 行为变更的默认实现纪律，使用 test-first cycle。非行为变更需要记录为什么 TDD 不适用。
_避免_: test-after implementation, unvalidated behavior change

**Issue Progress Comment**:
一个可更新的 Issue comment，用于记录 coding agent 的 GCW 进度，并链接到 issue branch 上的当前 planning files。
_避免_: hidden local plan, chat-only progress, unlinked planning files, progress comment stream

**Progress Snapshot**:
Issue progress comment 中的当前状态摘要，包含 status、branch、planning file links、latest checkpoint，以及可用时的 review request link。
_避免_: full progress log, comment history, ad hoc update

**GCW Status**:
Progress snapshot 中展示的稳定阶段。v1 状态为 `planning`、`clarifying`、`implementing`、`blocked`、`ready-for-review`。
_避免_: command state, transient step, detailed progress log

**Issue Worktree**:
GCW 默认为一个 Issue 创建的隔离 worktree，用于避免干扰开发者当前工作区或其他 Issue 工作。
_避免_: shared checkout, current workspace by default

**Agent Workspace**:
coding agent 执行命令和编辑文件的仓库根目录。在 Cursor 中，GCW 创建 issue worktree 后会将 agent workspace 移到该 worktree。
_避免_: original checkout, terminal cwd only

**Git Hosting Platform**:
提供 Issue 和 code review 对象的托管 Git 协作服务。v1 平台是 GitHub 和 GitLab，其中 GitHub 是第一条完整实现路径。
_避免_: Git server, remote, forge

**Review Request**:
从分支创建的托管 code review 对象，用于让 Issue 工作进入 ready for review。GitHub Pull Request 和 GitLab Merge Request 是平台特定的 review request。
_避免_: PR/MR, pull request, merge request

**Complete-on-Create**:
Review request 创建时应直接包含有效 review 所需的 Issue link、summary、validation、scope、risks 和 reviewer notes。
_避免_: empty review request, placeholder PR, placeholder MR

**Ready for Review**:
Issue 的 review request 已经准备好进行 code review 的目标状态。
_避免_: review-ready candidate, merge ready, draft

**Review Support**:
Ready for review 之后的可选 workflow package 活动，例如 review review request、调查 CI 失败、协助响应 reviewer feedback。
_避免_: required ready-for-review step, automatic self-review

**Hosted Apply Workflow**:
手动触发的 GitHub Actions 或 GitLab CI workflow。只有当 `state.json.owner.kind` 与 hosted runner 匹配时，它才可以 apply GCW 状态转换、更新 issue progress comment、更新 review request body、提交 evidence changes 并推送。
_避免_: unowned CI write, automatic remote mutation

**Remote Artifact Verification**:
确定性检查。它将从 GitHub/GitLab 抓取的 hosted issue progress comment 文本和 review request body 文本，与本地 readiness evidence 进行比较。
_避免_: assuming hosted state matches local files

**Readiness Evidence**:
证明 review request 已准备好进入 review 的证据包。它覆盖 linked issue、branch、intended diff、commit boundaries、validation、planning file links、local self-review result、risks，以及 complete-on-create review request summary。
_避免_: completion note, final message, status update

**Local Self-Review**:
创建或更新 review request 前必需的检查。coding agent 会检查 local diff、planning files、validation results、commit boundaries 和 review request content，并将结果作为 readiness evidence 记录在 `progress.md`。
_避免_: remote code review, reviewer approval, casual final scan

**High-Risk Operation**:
可能破坏工作、改变共享历史、合并代码、关闭工作项或修改他人 authored content 的 Git collaboration 操作。它需要明确的人类批准。
_避免_: normal review-ready step, routine operation
