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

`gcw-issue-triage.yml` 作为分层试点拆成 `preflight -> classify -> finalize`：`preflight` 只解析触发与 phase，`classify` 只运行 Codex 并上传 handoff artifact，`finalize` 下载 artifact 后执行 GitHub 写入与 GCW 事件记录。

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

### Comment command 契约

评论触发推荐使用显式命令：`@AGENT_LOGIN /gcw <step>`。例如：

- `@gcw-bot /gcw triage`
- `@gcw-bot /gcw clarify`
- `@gcw-bot /gcw issue-to-spec`
- `@gcw-bot /gcw spec-check`
- `@gcw-bot /gcw implement`
- `@gcw-bot /gcw implement-check`
- `@gcw-bot /gcw pr-publish`
- `@gcw-bot /gcw pr-review`

### Executor labels（hosted 总开关）

Hosted workflow **仅在** Issue 带有 **`gcw:executor-hosted`** 时才会运行（含 `pull_request: synchronize` 与 `gcw:run-*` 触发）。

| Label | 行为 |
| --- | --- |
| `gcw:executor-hosted` | 允许 hosted Action 执行（仍受 phase 与 idempotent gate 约束） |
| `gcw:executor-local` | 所有 hosted workflow 跳过 |
| （均无） | 默认视为 local，不自动跑 Action |

`gcw:run-*` 只决定**跑哪一步**；必须与 `gcw:executor-hosted` 同时存在才生效。本地 agent 启动 GCW 时应在 triage 打上 `gcw:executor-local`。

Issue/comment 自动触发会在 job `if` 中先检查 `gcw:executor-hosted` 并排除 `gcw:executor-local`，因此缺少 hosted executor 标签时不会 checkout issue branch。`workflow_dispatch` 与 `pull_request` 事件仍由脚本读取远端 Issue labels 做兜底判断。

### Local vs hosted 职责

| 步骤 | 默认（local） | Hosted（`gcw:executor-hosted`） |
| --- | --- | --- |
| intake → spec-check | Agent 本地 | 可选 Action |
| implement → pr-publish | Agent 本地 | 可选 Action |
| `gcw-pr-review` | **不**由本地 agent 记录 | Action 负责自动 review gate |

`prepare_gcw_hosted_step.py` 在 phase gate 之外还会：检查 executor label、跳过已完成步骤，并对已通过的 `gcw-pr-review` 仅运行 `review-check` 校验（`run_mode=verify-only`）。

典型自动触发流程：

1. 本地或 Action 完成 `gcw-issue-clarify` → phase 为 `ready-for-planning`
2. 给 Issue 打 label `gcw:ready-for-planning`，并 assign 给 `AGENT_LOGIN`（若已配置）
3. `gcw-issue-to-spec.yml` 运行 codex → push planning 文件 → 记录 `planned`

## 试点：gcw-issue-to-spec

手动触发示例（GitHub Actions UI）：

- `issue_number`: `12`
- `dry_run`: `false`

事件触发：在 phase 为 `ready-for-planning` 的 Issue 上打 `gcw:ready-for-planning` 并 assign agent。

## Remote evidence verification

`verify_gcw_remote_evidence.py` 可在 hosted gate 中校验 GitHub/GitLab 上的 progress comment 与 review request 正文是否与本地 event log 一致。

### 直接拉取（默认）

在 Action 或已配置 `gh` / `glab` 认证的本地环境中，通常只需 `--issue-dir`：

```bash
python .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py progress-comment \
  --issue-dir .gcw/issues/42

python .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py review-request \
  --issue-dir .gcw/issues/42
```

脚本会从 `workflow.json` `refs` 或最新 `gcw-pr-publish` 事件解析 URL，经平台 adapter 拉取正文，再比对 GCW marker 与记录的 `body_hash`。

需要 `issues: read`（comment）与 `pull-requests: read`（PR body）。GitLab 路径依赖 `glab` 已登录。

可选 `--fetch-url` 覆盖自动解析的 URL；`--progress-comment-url` / `--review-request-url` 仍可显式指定。

### 离线 `--remote-file` 模式

单元测试或无 API 访问时使用本地副本：

```bash
python .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py progress-comment \
  --issue-dir .gcw/issues/42 \
  --remote-file /tmp/progress-comment.md
```

显式提供 `--remote-file` 时不会发起远程拉取。

## 故障排查

| 现象 | 可能原因 |
| --- | --- |
| Workflow 被 skip | Job 级 `if` 未满足 label/assign/mention 契约，或缺少 `gcw:executor-hosted` |
| `should_run=false` | `workflow.json` phase 与步骤不匹配，或步骤已完成 / 被后续步骤取代 |
| `OPENAI_API_ENDPOINT is not set` | 未配置 Variable |
| codex 成功但 milestone 失败 | planning 文件路径不对或未通过 `test -f` |
| push 失败 | `GITHUB_TOKEN` 无 `contents: write` 或分支保护 |

## 参考

- [AICodingFlow create-spec-from-issue.yml](https://github.com/Terry-Mao/AICodingFlow/blob/main/.github/workflows/create-spec-from-issue.yml) — handoff + codex-action + finalize 模式参考
- [CONTRIBUTING.md](../CONTRIBUTING.md) — 本地开发与测试
