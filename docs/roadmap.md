# 路线图

## 已完成

- 本地 GCW state management。
- `.gcw/issues/<issue-id>/` 下的 planning files。
- JSON evidence schemas。
- Implementation gate validation。
- Readiness evidence validation。
- Local self-review recording。
- Ownership handoff recording。
- GitHub 和 GitLab planning links。
- GitHub Actions 和 GitLab CI 的 read-only validation。
- GitHub Actions 和 GitLab CI 的手动、ownership-gated hosted apply。
- Remote artifact rendering and verification。

## 未来工作

- 真正的 cloud coding agent 或 `/fix` runner，在显式 ownership handoff 后实现代码改动。
- 直接通过 remote API 抓取 hosted artifacts 的检查，而不是接受已抓取的文本文件。
- 如果项目标准化 `glab` 或 GitLab API credentials，补齐更完整的 GitLab review request 创建/更新流程。
- Workflow kit 的 release packaging。

## 边界

当没有配置 cloud runner primitive 时，GCW 不应虚构 autonomous code modification。当前 contract 已暴露 ownership handoff、hosted apply、evidence rendering 和 validation，未来 runner 可以在这些契约上安全集成。
