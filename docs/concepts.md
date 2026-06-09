# GCW 概念

规范术语表在 [../CONTEXT.md](../CONTEXT.md)。本文按使用场景整理最重要的概念。

## 协作对象

- **Issue**: GitHub 或 GitLab 上必需的工作入口。
- **Issue Worktree**: 为单个 Issue 使用的隔离 worktree。
- **Review Request**: GitHub Pull Request 或 GitLab Merge Request。
- **Ready for Review**: 完整 review request 存在后的目标状态。

## 工作记忆

- **Planning Files**: `.gcw/issues/<issue-id>/` 下的 `task_plan.md`、`findings.md` 和 `progress.md`。
- **Planning Recovery**: 中断后重新读取 planning files 的恢复行为。
- **Planning Commit**: 发布 planning files 的第一个独立提交。
- **Planning Checkpoint**: 携带更新后 planning context 的后续提交或推送。

## 状态与证据

- **GCW Status**: `planning`、`clarifying`、`implementing`、`blocked` 或 `ready-for-review`。
- **Implementation Gate**: 判断是否可以开始实现的检查点。
- **Readiness Evidence**: 创建或更新 review request 前必需的证据包。
- **Local Self-Review**: 记录在 `progress.md` 中的 pre-review-request 检查。

## Runner 权限

- **Owning Agent**: 对 Issue 分支负责写入的唯一 writer。
- **Hosted Apply Workflow**: 手动触发的 hosted workflow，只有拥有分支时才可以 apply transition。
- **Remote Artifact Verification**: 将 hosted comment/body 文本与本地 readiness evidence 做确定性比较。
- **High-Risk Operation**: 任何可能破坏工作、改变共享历史、merge、close 或编辑他人 authored content 的操作。
