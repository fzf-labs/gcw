# GCW 证据

每个 Issue 分支都会在以下目录中保存人类可读记录和机器可读记录：

```text
.gcw/issues/<issue-id>/
```

## 人类记录

```text
.gcw/issues/<issue-id>/task_plan.md
.gcw/issues/<issue-id>/findings.md
.gcw/issues/<issue-id>/progress.md
```

- `task_plan.md` 记录目标、阶段、验收条件和验证计划。
- `findings.md` 记录 Issue facts、发现、决策、风险和开放问题。
- `progress.md` 记录命令、错误、checkpoint 和 local self-review。

## 机器记录

```text
.gcw/issues/<issue-id>/state.json
.gcw/issues/<issue-id>/implementation_gate_result.json
.gcw/issues/<issue-id>/readiness_evidence.json
```

JSON schemas 位于：

```text
.agents/skills/gcw/schemas/state.schema.json
.agents/skills/gcw/schemas/implementation_gate_result.schema.json
.agents/skills/gcw/schemas/readiness_evidence.schema.json
```

## State Snapshot

`state.json` 记录当前 issue、platform、repository、branch、owner、GCW state、last completed step、next allowed steps 和 evidence flags。

`planned` 要求 planning files 真实存在于磁盘，且 `evidence.planning_files_exist`、`evidence.planning_commit_pushed` 为 `true`、`evidence.progress_comment_url` 非空；`record-publish-planning` 在任一条件不满足时直接失败，不会改写 `state.json`。`planning_commit_pushed` 由调用方通过 `--planning-commit-pushed` 显式断言，implementation gate 会复核这条记录而不是凭空认定已推送。

`ready-for-review` 要求 `evidence.review_request_url` 非空，并且 `last_completed_step` 为 `create-review-request`。机审和人审结论继续记录在 `state.json` 的 evidence 中，而不是只留在 CI 日志或聊天记录里。

state manager 与 validator 覆盖从 `planning` 到 `review-complete` 的完整状态机，包括 `planned`、`ready-for-implementation`、`implementing`、`issue-clarifying`、`ready-for-review-request`、`ready-for-review`、`machine-reviewing`、`machine-review-failed`、`human-reviewing`、`changes-requested`、`approved`、`blocked` 和 `review-complete`。`issue-opened`、`issue-triaging`、`ready-for-planning` 发生在 issue worktree 和 `state.json` 创建之前，由 issue progress comment 跟踪，因此不写入本地 `state.json`。

## Implementation Gate

`implementation_gate_result.json` 记录是否可以开始实现：

- `ok: true` 表示状态从 `planned` 转换到 `ready-for-implementation`；随后 `implement` 步骤进入 `implementing`。
- `ok: false` 表示状态转换到 `issue-clarifying`（信息不清）或 `blocked`。
- 通过 gate 需要 planning files、已推送的 planning commit、已链接的 progress comment，以及可执行的 Issue 信息。

## Readiness Evidence

`readiness_evidence.json` 记录 issue、branch、base branch、commit range、review request title/summary/issue link、validation results、local self-review、planning links、progress comment URL 和 risks，以及可选的 scope 与 reviewer_notes。可选字段一旦记录就会渲染进 review request body，并被 remote artifact verification 复核。

创建或更新 review request 前，先运行 validator：

```bash
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py readiness-check --issue-dir .gcw/issues/<issue-id>
```
