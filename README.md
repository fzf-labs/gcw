# GCW

**Git Collaboration Workflow** — 从已有 Issue 出发，把人、agent 与 Action 组织成可追踪的协作开发流程。

GCW 不替代 GitHub / GitLab 上的 Issue 与 PR 机制，而是在其上增加明确的步骤、状态与门禁，让 AI 编码工具与托管流水线能按同一套契约接力推进，直到人类完成最终审查。

## 安装到其他项目

可以通过 npm 全局安装 GCW CLI，然后在目标仓库初始化 repo-local assets：

```bash
npm install -g @fzf-labs/gcw
cd <target-repo>
gcw init
gcw doctor
```

`gcw init` 默认复制本地 agent 所需的 `.agents/skills/gcw*`、`.agents/skills/planning-with-files` 与 `.gcw/runtime`。如果目标仓库也要安装 hosted workflow assets，按平台选择：

```bash
gcw init --with-github-actions
gcw init --with-gitlab-ci
```

默认不会覆盖已有文件；需要明确覆盖时加 `--force`。发布包前可用 `npm pack --dry-run` 检查实际包含的 template assets。

## 适用场景

- 已有 Issue，需要 agent 接入、分类、规划后再实现
- 希望 spec、实现、PR 与审查过程可审计、可恢复
- 需要在本地 agent 与 GitHub Actions / GitLab CI 之间交接

## 协作分工

| 角色 | 职责 |
| --- | --- |
| **人** | 在 GitHub / GitLab 上做关键业务判断与最终审查 |
| **agent** | Codex、Cursor、Claude Code 等 AI 编码工具，承担需要判断与代码能力的工作 |
| **Action** | GitHub Actions、GitLab CI 等托管流水线，负责远端自动化、门禁与记录 |

## 主流程

```text
已有 Issue
  -> gcw-issue-intake
  -> gcw-issue-triage
  -> gcw-issue-clarify
  -> gcw-issue-to-spec
  -> gcw-spec-check
  -> gcw-implement
  -> gcw-implement-check
  -> gcw-pr-publish
  -> gcw-pr-review
  -> 等待 GitHub / GitLab 上的人类审查和结束结果
```

spec files 提交在 Issue 分支的 `.gcw/issues/<issue-id>/`，通过 Issue 评论链接到远程文件，而不是直接写入 Issue 正文。

## 文档

- [Contributing](CONTRIBUTING.md) — 环境、测试、分支约定与提 Issue / PR
- [GCW Quickstart](docs/quickstart.md) — 用 Issue #3 跟着走一遍端到端流程
- [GCW 工作流](docs/workflow.md) — 步骤、状态、Action 流水线与门禁的完整说明
