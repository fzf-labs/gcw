# GCW Hosted Agent

本文说明 GitHub Actions / GitLab CI 上 **Hosted agent execution** 的配置、触发契约与故障排查。步骤表与状态机见 [GCW 工作流](workflow.md)。

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

<!-- gcw-contract:step-matrix:start -->
| GCW step | Workflow file | Trigger label |
| --- | --- | --- |
| gcw-issue-triage | gcw-issue-triage.yml | gcw:run-triage |
| gcw-issue-clarify | gcw-issue-clarify.yml | gcw:run-clarify |
| gcw-issue-to-spec | gcw-issue-to-spec.yml | gcw:ready-for-planning |
| gcw-spec-check | gcw-spec-check.yml | gcw:run-spec-check |
| gcw-implement | gcw-implement.yml | gcw:run-implement |
| gcw-implement-check | gcw-implement-check.yml | gcw:run-implement-check |
| gcw-pr-publish | gcw-pr-publish.yml | gcw:run-pr-publish |
| gcw-pr-review | gcw-pr-review.yml | gcw:run-pr-review |
<!-- gcw-contract:step-matrix:end -->

## 仓库配置

维护者需在 GitHub 仓库中配置：

| 名称 | 类型 | 必需 | 用途 |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | Secret | hosted-agent 步骤是 | `openai/codex-action@v1` 认证 |
| `OPENAI_API_ENDPOINT` | Variable | hosted-agent 步骤是 | API base URL（脚本自动补 `/responses` 后缀） |
| `CODEX_MODEL` | Variable | 否 | 传给 `openai/codex-action@v1` 的 `model`；为空时使用 Codex 默认模型 |
| `CODEX_EFFORT` | Variable | 否 | 传给 `openai/codex-action@v1` 的 `effort`；为空时使用 Codex 默认 reasoning effort |
| `AGENT_LOGIN` | Variable | 事件触发推荐 | Issue comment `@mention` 与 assignee 匹配 |

另需 **Settings → Actions → General → Workflow permissions** 允许 `contents: write`（mutating 步骤 commit/push）。

### GitLab CI 配置

仓库模板包含根级 `.gitlab-ci.yml`，用于在 GitLab 项目中手动运行 GCW hosted jobs。GitLab CI 路径复用同一套 `.gcw/issues/<issue-id>/events/`、`workflow.json`、progress comment 和 validation scripts；平台操作通过 `glab` 与 GitLab API 完成。

维护者需在 GitLab 项目中配置：

| 名称 | 类型 | 必需 | 用途 |
| --- | --- | --- | --- |
| `GLAB_TOKEN` | CI/CD Variable | 是 | `glab` 认证，用于读取/写入 Issue notes、labels、branch 和 MR evidence |
| `GCW_ISSUE_NUMBER` | Pipeline variable | 是 | GitLab Issue IID |
| `GCW_ISSUE_BRANCH` | Pipeline variable | 否 | Issue branch，默认 `gcw/issue-${GCW_ISSUE_NUMBER}` |
| `GCW_DRY_RUN` | Pipeline variable | 否 | `true` 时只做验证，不写远端 |
| `GCW_EXECUTOR` | Pipeline variable | 否 | 默认 `gcw:executor-hosted`；设为 `gcw:executor-local` 时跳过 |

`GLAB_TOKEN` 建议使用 project access token 或机器人 personal access token，并授予最小需要的 repository / issue / merge request 读写权限。若项目启用了 protected branch，需允许该 token push issue branch。

GitLab CI 当前以手动 job 为主：在 pipeline 中设置 `GCW_ISSUE_NUMBER` 后，选择对应 job（例如 `gcw:triage`、`gcw:spec-check`、`gcw:implement-check`）运行。Triage job 可以从默认分支创建 `GCW_ISSUE_BRANCH`；其余 job 会切换到已有 issue branch，再调用 `prepare_gcw_hosted_step.py` 做 phase gate，最后委托现有 Python 脚本执行实际 GCW step。

GitLab hosted path 的 executor gate 来自 pipeline variable `GCW_EXECUTOR`，不是从 Issue labels 反查。若本地 agent 已在 Issue 上标记 `gcw:executor-local`，但维护者仍以默认 `GCW_EXECUTOR=gcw:executor-hosted` 手动运行 GitLab job，CI 仍会按 hosted 路径执行；需要跳过时请把 pipeline variable 设为 `gcw:executor-local`。

## Trigger label 契约

除 `workflow_dispatch` 外，issue-based 步骤可通过 **label + assign** 或 **comment @AGENT_LOGIN** 自动触发（须满足 `workflow.json` phase）；`gcw-pr-review` 另外支持 `pull_request` 触发：

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

- `@gcw-bot /gcw issue-triage`
- `@gcw-bot /gcw issue-clarify`
- `@gcw-bot /gcw issue-to-spec`
- `@gcw-bot /gcw spec-check`
- `@gcw-bot /gcw implement`
- `@gcw-bot /gcw implement-check`
- `@gcw-bot /gcw pr-publish`
- `@gcw-bot /gcw pr-review`

### Executor labels（hosted 总开关）

Hosted workflow 只有在 executor gate 通过时才会继续执行：目标 Issue 需要带有 **`gcw:executor-hosted`** 且不能带有 **`gcw:executor-local`**。`issues` / `issue_comment` 触发会在 job `if` 中先做这层过滤；`workflow_dispatch` 与 `pull_request` 触发则由脚本再做同一层 gate。

| Label | 行为 |
| --- | --- |
| `gcw:executor-hosted` | 允许 hosted Action 执行（仍受 phase 与 idempotent gate 约束） |
| `gcw:executor-local` | 所有 hosted workflow 跳过 |
| （均无） | 默认视为 local，不自动跑 Action |

`gcw:run-*` 只决定**跑哪一步**；必须与 `gcw:executor-hosted` 同时存在才生效。本地 agent 启动 GCW 时，`gcw-issue-triage` 默认会把 `gcw:executor-local` 写入 Issue 和 triage event。

如需从本地切换到 hosted，先用平台 label 操作或 `manage_triage_metadata.py apply/apply-metadata` 将 `gcw:executor-local` 替换为 `gcw:executor-hosted`，再添加对应 `gcw:run-*` trigger label 或使用 comment / dispatch 触发。Hosted triage 自身不会默认写入 `gcw:executor-local`。

Issue/comment 自动触发会在 job `if` 中先检查 `gcw:executor-hosted` 并排除 `gcw:executor-local`，因此缺少 hosted executor 标签时不会 checkout issue branch。`workflow_dispatch` 与 `pull_request` 事件仍由脚本读取远端 Issue labels 做兜底判断。

### Local vs hosted 职责

| 步骤 | 默认（local） | Hosted（`gcw:executor-hosted`） |
| --- | --- | --- |
| triage → spec-check | Agent 本地 | 可选 Action |
| implement → pr-publish | Agent 本地 | 可选 Action |
| `gcw-pr-review` | **不**由本地 agent 记录 | Action 负责自动 review gate |

`gcw-issue-triage.yml` 可以在 issue branch 不存在时从默认分支创建并推送 `gcw/issue-<n>`，写入 `.gcw/issues/<n>/events/000-gcw-issue-triage.json` 和 `workflow.json`。`prepare_gcw_hosted_step.py` 在 phase gate 之外还会：检查 executor label、跳过已完成步骤，并对已通过的 `gcw-pr-review` 仅运行 `review-check` 校验（`run_mode=verify-only`）。

典型自动触发流程：

1. 本地或 Action 完成 `gcw-issue-clarify` → phase 为 `ready-for-planning`
2. 给 Issue 打 label `gcw:ready-for-planning`，并 assign 给 `AGENT_LOGIN`（若已配置）
3. `gcw-issue-to-spec.yml` 运行 codex → push planning 文件 → 记录 `planned`

## 试点：gcw-issue-to-spec

手动触发示例（GitHub Actions UI）：

- `issue_number`: `12`
- `dry_run`: `false`

事件触发：在 phase 为 `ready-for-planning` 的 Issue 上打 `gcw:ready-for-planning` 并 assign agent。

GitLab CI 手动触发示例：

- `GCW_ISSUE_NUMBER`: `12`
- `GCW_ISSUE_BRANCH`: `gcw/issue-12`
- `GCW_DRY_RUN`: `false`
- 运行 job：`gcw:issue-to-spec`

注意：`planned` 状态必须先由人工审核 spec 文件；审核通过后再运行 `gcw:spec-check` 进入 `ready-for-implementation`。

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

### `gh run list` 显示 `skipped` 时先查什么

1. **Workflow run 整行就是 `skipped`**：通常是 job 级 `if` 未满足（见下表「Job `if` gate」）。Actions 不会 checkout issue branch，也不会运行 `prepare_gcw_hosted_step.py`。
2. **Run 为 `success` 但日志里出现 `GCW hosted skip`**：job 已启动，跳过发生在 `prepare_gcw_hosted_step.py` 的 executor / phase / idempotent gate。查看 `Report phase skip` 步骤输出中的 `Gate:` 行。
3. **Issue labels**：确认 `gcw:executor-hosted` 存在且没有 `gcw:executor-local`（本地 agent 默认会打后者）。
4. **Phase**：在 issue branch 上读 `.gcw/issues/<id>/workflow.json` 的 `phase` 与 `next_allowed_steps`，对照 trigger label 是否匹配。
5. **幂等**：查 `events/` 中 `last_completed_step`；若步骤已完成或被更晚的 milestone 取代，hosted job 会 no-op。

```bash
gh run list --workflow gcw-spec-check.yml --limit 5
gh run view <run-id> --log | rg 'GCW hosted skip|Gate:'
gh issue view <n> --json labels
git fetch origin gcw/issue-<n> && git show origin/gcw/issue-<n>:.gcw/issues/<n>/workflow.json
```

### Skip gate 对照表

| Gate | 典型日志 / `skip_reason` | 含义 | 优先检查 |
| --- | --- | --- | --- |
| Job `if` gate | Workflow run 状态 `skipped`，无 `GCW hosted skip` 日志 | `issues`/`issue_comment` 触发时 job `if` 要求 `gcw:executor-hosted`、对应 `gcw:run-*`、assign/mention 契约 | Issue labels、assignee、`AGENT_LOGIN`、评论是否 `@mention` |
| Executor gate | `Gate: executor gate`；`gcw:executor-local blocks hosted execution` 或 `missing gcw:executor-hosted` | Hosted 总开关未通过 | Issue labels；GitLab 另查 `GCW_EXECUTOR` |
| Phase gate | `Gate: phase gate`；`phase '…' is not in […] for <step>` | 当前 workflow phase 不允许该步骤 | `workflow.json` phase、`next_allowed_steps`、trigger label |
| Idempotent no-op | `Gate: idempotent no-op`；`<step> already completed` 或 `superseded by <step>` | 步骤已完成或已被后续 milestone 取代 | `.gcw/issues/<id>/events/`、`last_completed_step` |
| Infrastructure | `Gate: infrastructure`；`issue directory not found` 等 | Issue branch 上缺少 GCW 状态 | 是否 checkout 正确 branch、是否已 triage |

### 常见现象（简表）

| 现象 | 可能原因 |
| --- | --- |
| Workflow 被 skip | Job 级 `if` 未满足 label/assign/mention 契约，或缺少 `gcw:executor-hosted` |
| `GCW hosted skip` + `executor gate` | Issue 带 `gcw:executor-local` 或未打 `gcw:executor-hosted` |
| `GCW hosted skip` + `phase gate` | `workflow.json` phase 与步骤不匹配 |
| `GCW hosted skip` + `idempotent no-op` | 步骤已完成或被更晚步骤取代 |
| `should_run=false`（旧日志） | 同上；新日志应包含 `Gate:` 分类行 |
| `OPENAI_API_ENDPOINT is not set` | 未配置 Variable |
| codex 成功但 milestone 失败 | planning 文件路径不对或未通过 `test -f` |
| push 失败 | `GITHUB_TOKEN` 无 `contents: write` 或分支保护 |

## 参考

- [AICodingFlow create-spec-from-issue.yml](https://github.com/Terry-Mao/AICodingFlow/blob/main/.github/workflows/create-spec-from-issue.yml) — handoff + codex-action + finalize 模式参考
- [CONTRIBUTING.md](../CONTRIBUTING.md) — 本地开发与测试
