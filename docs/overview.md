# GCW 概览

GCW 用于协调本地 Git 开发和 GitHub/GitLab 上的托管协作流程。它面向 agent-assisted developer，将 Issue 工作委托给 coding agent 执行。

## GCW 提供什么

- 面向 Issue 开发的统一领域语言。
- `.gcw/issues/<issue-id>/` 下的 planning files。
- 机器可读的 state 和 evidence files。
- 本地 agent 与 hosted runner 可复用的验证脚本。
- Complete-on-create review request 准备流程。
- local、GitHub Actions、GitLab CI 和 manual runner 的 ownership 与 handoff 规则。

## GCW 避免什么

- 只存在于聊天里的工作记忆。
- reviewer 无法检查的隐藏本地 plan。
- 未拥有权限的 hosted mutation。
- 没有 readiness evidence 就创建 review request。
- 未经明确人类批准就 merge、close issue、force-push 或 delete branch。

## 主要文档

- [concepts.md](concepts.md) 解释核心概念。
- [workflow.md](workflow.md) 解释 review-ready loop。
- [evidence.md](evidence.md) 解释文件和 schema。
- [hosted-runners.md](hosted-runners.md) 解释 CI 权限。
- [validation.md](validation.md) 解释验证方式。
- [roadmap.md](roadmap.md) 解释阶段状态。
