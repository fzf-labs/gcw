# 路线图

## 已完成

- 本地 GCW 状态管理。
- `.gcw/issues/<issue-id>/` 下的 planning files 持久化。
- JSON evidence schemas。
- Implementation gate 校验。
- Readiness evidence 校验。
- Local self-review 记录。
- Ownership handoff 记录。
- GitHub 和 GitLab planning links。
- GitHub Actions 和 GitLab CI 的只读 validation。
- GitHub Actions 和 GitLab CI 中手动触发、受 ownership gate 保护的 hosted apply。
- GitHub Actions 和 GitLab CI 中手动触发、受 ownership gate 保护的 Action pipeline 入口，覆盖 issue intake、issue clarify、planning、machine review、feedback loop 和 review complete。
- Remote artifact 渲染与校验。
- `issue-opened`、`issue-triaging`、`issue-clarifying`、`ready-for-planning` 的本地 state.json 初始化和状态推进。
- state manager 与 validator 覆盖从 `planning` 到 `review-complete` 的完整状态机，包括 implementation gate、`implement`、readiness、机审、人审、反馈回环和 review-complete。
- 从 Issue 创建、分类、评论讨论到人类审查结束的目标流程、状态和 Action 流水线拆解。

## 未来工作

- 扩展 Action pipeline 与托管平台 API 的深度集成，例如自动创建 Issue、创建 review request、补充评论和同步远程 artifact。
- 接入真正的 cloud coding agent 或 `/fix` runner，在显式 ownership handoff 后执行代码改动。
- 增加通过 remote API 直接抓取 hosted artifacts 的检查，不再只依赖已抓取的文本文件。
- 如果项目标准化 `glab` 或 GitLab API credentials，补齐更完整的 GitLab review request 创建和更新流程。
- 为 workflow kit 增加 release packaging。

## 边界

没有配置 cloud runner primitive 时，GCW 不应虚构 autonomous code modification。当前 contract 已暴露 ownership handoff、hosted apply、evidence rendering 和 validation，未来 runner 可以基于这些契约安全接入。
