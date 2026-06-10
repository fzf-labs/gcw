# GCW 概览

GCW 用于协调本地 Git 开发与 GitHub/GitLab 上的托管协作流程，面向把 Issue 工作委托给 coding agent 的开发者。

## GCW 提供什么

- 面向 Issue 开发的统一领域语言。
- Issue 创建、分类、评论讨论和可开发判断的状态拆解。
- `.gcw/issues/<issue-id>/` 下的 planning files，也就是随分支保存的计划、发现和进展记录。
- 机器可读的状态文件和证据文件。
- 本地 agent 与 hosted runner 共用的验证脚本。
- 创建即完整的 review request，也就是 complete-on-create review request，确保它创建时就包含审查所需信息。
- PR/MR 机审、人类审查、反馈修复和审查结束的目标状态拆解。
- local、GitHub Actions、GitLab CI 和 manual runner 的 ownership 与 handoff 规则，用来说明谁可以写入当前分支。

## GCW 避免什么

- 只存在于聊天里的工作记忆。
- 没有经过 Issue 分类和讨论，就直接进入 planning files 或开发。
- reviewer 无法检查的隐藏本地 plan。
- 未取得 ownership 的托管写操作。
- 没有审查准备证据（readiness evidence）就创建 review request。
- 机审失败或人审要求修改后，不记录反馈、不重新验证就继续推进。
- 未经明确批准就 merge、close issue、force-push 或 delete branch。

## 主要文档

- [concepts.md](concepts.md)：核心概念。
- [workflow.md](workflow.md)：从 Issue 接入到人类审查结束的状态、步骤和 Action 流水线。
- [evidence.md](evidence.md)：文件与 schema。
- [hosted-runners.md](hosted-runners.md)：CI 权限。
- [validation.md](validation.md)：验证方式。
- [roadmap.md](roadmap.md)：当前已实现能力和后续目标。
