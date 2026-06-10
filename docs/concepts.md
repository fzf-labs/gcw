# GCW 概念

完整术语表见 [../CONTEXT.md](../CONTEXT.md)。本文按使用场景整理最常用的概念。

## 协作对象

- **Issue**: GitHub 或 GitLab 上的工作入口，先经过创建、分类和评论讨论，再进入规划。
- **Issue Triage**: 对 Issue 做类型、优先级、影响范围、重复关系和标签判断。
- **Issue Discussion**: 通过 Issue 评论澄清背景、边界、验收标准和关键决定。
- **Ready for Planning**: Issue 已经讨论清楚，可以开始创建 worktree 和 planning files。
- **Issue Worktree**: 为单个 Issue 创建的隔离 worktree。
- **Review Request**: GitHub Pull Request 或 GitLab Merge Request。
- **Ready for Review**: review request 已完整创建、可以进入机审和人审的中间状态。
- **Machine Review**: CI、静态检查、remote artifact verification 或 AI review 执行的自动审查阶段。
- **Human Review**: 机审通过或被接受后，由 reviewer 对 review request 做出的人工审查。
- **Review Complete**: 人类审查已经结束且结果已记录的终点状态。

## 工作记忆

- **Planning Files**: `.gcw/issues/<issue-id>/` 下的 `task_plan.md`、`findings.md` 和 `progress.md`。
- **Planning Recovery**: 中断后通过重新读取 planning files 恢复上下文。
- **Planning Commit**: 发布 planning files 的第一个独立提交。
- **Planning Checkpoint**: 后续携带 planning context 的提交或推送。

## 状态与证据

- **GCW Status**: `issue-opened`、`issue-triaging`、`issue-clarifying`、`ready-for-planning`、`planning`、`planned`、`ready-for-implementation`、`implementing`、`ready-for-review-request`、`ready-for-review`、`machine-reviewing`、`machine-review-failed`、`human-reviewing`、`changes-requested`、`approved`、`blocked` 或 `review-complete`。
- **Implementation Gate**: 判断是否可以开始实现的检查点。
- **Readiness Evidence**: 创建或更新 review request 前必须具备的证据包。
- **Local Self-Review**: 创建 review request 前记录在 `progress.md` 中的自查结果。

## Runner 权限

- **Owning Agent**: 对 Issue 分支承担写入责任的唯一 writer。
- **Hosted Apply Workflow**: 手动触发的 hosted workflow，只有取得分支 ownership 且 `state.json.owner.kind` / `state.json.owner.id` 与 runner 身份一致时才可以执行 apply 操作。
- **Remote Artifact Verification**: 将托管平台上的 comment/body 文本与本地 readiness evidence 做确定性比较。
- **Action Pipeline**: 可以由一个 GitHub Actions、GitLab CI 或其他自动化入口连续执行的一组 GCW steps。
- **High-Risk Operation**: 任何可能破坏工作、改变共享历史、merge、close 或编辑他人创建内容的操作。
