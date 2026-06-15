# GCW Hosted Agent

本文说明 GitHub Actions 上 **Hosted agent execution** 的配置、触发契约与故障排查。步骤表与状态机见 [GCW 工作流](workflow.md)。

## 架构

```text
Issue/comment 事件 或 workflow_dispatch
  -> gcw_workflow_event.py（解析 issue_number）
  -> prepare_gcw_hosted_step.py（workflow.json phase gate）
  -> prepare_issue_handoff_context.py（issue_context.json + comments）
  -> gcw-run-codex（openai/codex-action@v1，只写 workspace 文件）
  -> validate_gcw_evidence.py / 步骤校验
  -> finalize_gcw_hosted_step.py（commit/push 或 gh pr upsert）
  -> run_gcw_step.py / manage_gcw_workflow.py（记 GCW 事件 + progress 评论）
```

Agent **不得**在 codex prompt 中执行 `git`、`gh` 或 GitHub API；提交与 PR 由 workflow 的 finalize 步骤完成。

## 仓库配置

维护者需在 GitHub 仓库中配置：

| 名称 | 类型 | 必需 | 用途 |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Secret | hosted-agent 步骤是 | `openai/codex-action@v1` 认证 |
| `OPENAI_API_ENDPOINT` | Variable | hosted-agent 步骤是 | API base URL（脚本自动补 `/responses` 后缀） |
| `AGENT_LOGIN` | Variable | 事件触发推荐 | Issue comment `@mention` 与 assignee 匹配 |

另需 **Settings → Actions → General → Workflow permissions** 允许 `contents: write`（mutating 步骤 commit/push）。

## Trigger label 契约

除 `workflow_dispatch` 外，各步骤可通过 **label + assign** 或 **comment @AGENT_LOGIN** 自动触发（须满足 `workflow.json` phase）：

| GCW 步骤 | Workflow 文件 | Trigger label |
| --- | --- | --- |
| `gcw-issue-triage` | `gcw-issue-triage.yml` | `gcw:run-triage` |
| `gcw-issue-clarify` | `gcw-issue-clarify.yml` | `gcw:run-clarify` |
| `gcw-issue-to-spec` | `gcw-issue-to-spec.yml` | `gcw:ready-for-planning` |
| `gcw-spec-check` | `gcw-spec-check.yml` | `gcw:run-spec-check` |
| `gcw-implement` | `gcw-implement.yml` | `gcw:run-implement` |
| `gcw-implement-check` | `gcw-implement-check.yml` | `gcw:run-implement-check` |
| `gcw-pr-publish` | `gcw-pr-publish.yml` | `gcw:run-pr-publish` |
| `gcw-pr-review` | `gcw-pr-review.yml` | `gcw:run-pr-review` |

典型自动触发流程：

1. 本地或 Action 完成 `gcw-issue-clarify` → phase 为 `ready-for-planning`
2. 给 Issue 打 label `gcw:ready-for-planning`，并 assign 给 `AGENT_LOGIN`（若已配置）
3. `gcw-issue-to-spec.yml` 运行 codex → push planning 文件 → 记录 `planned`

## 试点：gcw-issue-to-spec

手动触发示例（GitHub Actions UI）：

- `issue_number`: `12`
- `dry_run`: `false`

事件触发：在 phase 为 `ready-for-planning` 的 Issue 上打 `gcw:ready-for-planning` 并 assign agent。

## 故障排查

| 现象 | 可能原因 |
| --- | --- |
| Workflow 被 skip | Job 级 `if` 未满足 label/assign/mention 契约 |
| `should_run=false` | `workflow.json` phase 与步骤不匹配 |
| `OPENAI_API_ENDPOINT is not set` | 未配置 Variable |
| codex 成功但 milestone 失败 | planning 文件路径不对或未通过 `test -f` |
| push 失败 | `GITHUB_TOKEN` 无 `contents: write` 或分支保护 |

## 参考

- [AICodingFlow create-spec-from-issue.yml](https://github.com/Terry-Mao/AICodingFlow/blob/main/.github/workflows/create-spec-from-issue.yml) — handoff + codex-action + finalize 模式参考
- [CONTRIBUTING.md](../CONTRIBUTING.md) — 本地开发与测试
