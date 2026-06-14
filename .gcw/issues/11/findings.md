# Findings: P0 统一 GCW 步骤运行器

## 1. 现有步骤执行模式

各 GCW step skill 的 Procedure 遵循相似模式，但细节分散在 8 个 SKILL.md 中：

```text
读取状态 → 执行业务逻辑 → 运行 validation → 发布远端产物 → publish_progress_comment → manage_gcw_workflow record-* → rebuild projection
```

Issue #7 硬化了事件/投影校验后，顺序错误会在更晚阶段失败（如 reducer 拒绝非法 phase），但不会在「步骤入口」给出统一的 `stop_reason`。

## 2. 可复用脚本清单

### 2.1 `manage_gcw_workflow.py`

- `init-workflow`：intake
- `record-issue-prepare` / `record-issue-to-spec` / `record-spec-check` / `record-implement` / `record-implement-check` / `record-pr-publish` / `record-pr-review`
- `rebuild-projection`
- 所有 `record-*` 在内部调用 `append_event` + `write_projection`

Runner 应直接调用这些 handler 或等价 Python API，避免重复实现事件格式。

### 2.2 `render_gcw_hosted_artifacts.py`

- `render_progress_comment(issue_dir)` — 基于 projection 与最新事件渲染 markdown
- `render_review_request(issue_dir)` — 基于 implement-check payload 渲染 PR body
- 使用 `<!-- gcw-progress -->` 与 `<!-- gcw-review-request:start/end -->` 标记

### 2.3 `publish_progress_comment.py`

- 支持 `--dry-run`：只返回 `body` 与 `body_hash`
- 非 dry-run：读 projection 确定 platform/repo/issue，调用 `gh` / `glab`

### 2.4 `validate_gcw_evidence.py`

子命令：

| 命令 | 用途 |
| --- | --- |
| `workflow` | 事件日志 + projection 一致性 |
| `spec-check` | planned 阶段 spec 文件与 spec_refs |
| `implement-check` | implement-check payload 完整性 |
| `pr-publish` | pr-publish 前置条件 |

Runner 应在 record 前调用对应 gate；失败时填充 `validation` 数组。

### 2.5 prepare 专用脚本（`gcw-issue-prepare/scripts/`）

- `evaluate_issue_readiness.py` — 结构 readiness gate
- `manage_triage_metadata.py` — sync / apply-metadata
- `verify_remote_triage.py` — 远端 triage 比对

prepare 是唯一需要 Issue body 分类 + 远端 metadata 同步的步骤，逻辑最重。

## 3. 阶段路由（`gcw_workflow_lib.py`）

`NEXT_ALLOWED_STEPS` 与 reducer 共同约束合法步骤：

| phase | next_allowed_steps |
| --- | --- |
| `issue-opened` | `gcw-issue-prepare` |
| `ready-for-planning` | `gcw-issue-to-spec` |
| `planned` | `gcw-spec-check` |
| `ready-for-implementation` | `gcw-implement` |
| `implementing` | `gcw-implement`, `gcw-implement-check` |
| `ready-for-review` | `gcw-pr-publish` |
| `reviewing` | `gcw-pr-review` |

Runner 第一步应读取 projection 并校验 `step in next_allowed_steps`，否则 `stop_reason: illegal_phase`。

## 4. dry-run 现状

| 脚本 | dry-run 支持 |
| --- | --- |
| `publish_progress_comment.py` | 是 |
| `manage_triage_metadata.py` | 否（需 adapter 跳过） |
| `manage_gcw_workflow.py record-*` | 否 |
| `render_gcw_hosted_artifacts.py` | 隐式（只渲染不写） |

统一 runner 的 dry-run 应在 adapter 层短路所有远端 API，同时跳过 `append_event`。

## 5. 结构化输出需求

Issue #11 要求返回字段便于 Actions 解析：

```json
{
  "ok": true,
  "step": "gcw-spec-check",
  "phase_before": "planned",
  "phase_after": "ready-for-implementation",
  "artifacts": {
    "progress_comment_body": "...",
    "progress_comment_body_hash": "sha256:..."
  },
  "validation": [
    {"command": "validate_gcw_evidence spec-check", "exit_code": 0, "result": "passed"}
  ],
  "stop_reason": null
}
```

失败示例：

```json
{
  "ok": false,
  "step": "gcw-pr-publish",
  "phase_before": "ready-for-review",
  "phase_after": "ready-for-review",
  "artifacts": {},
  "validation": [...],
  "stop_reason": "publication_failed"
}
```

## 6. 测试策略

- 使用 `tmp_path` fixture 复制 issue #7 或 #11 的事件夹具
- `unittest.mock` 替换 adapter 的 `publish_progress_comment` / `apply_metadata` / `upsert_pr`
- 断言 events 目录文件数在失败场景下不变
- 非法 phase：在 `ready-for-planning` 上跑 `gcw-pr-publish`

## 7. 与 Issue #7 硬化的关系

Issue #7 已交付 schema/reducer/validate 硬化。Runner 应：

- 依赖 hardened `append_event` 做最终防线
- 在步骤入口做 UX 层前置检查（更早、更清晰的 `stop_reason`）
- 不削弱现有 validation；runner 是编排层，不是替代层

## 8. 开放问题（规划阶段无阻塞）

- `gcw-issue-to-spec` 是否由 runner 负责 `git push`？当前 skill 要求 agent 手动 push；runner 可接受 `--skip-push` 或检测已推送
- GitLab adapter 优先级：issue 注明 GitHub/GitLab/dry-run 共享接口，首批可实现 GitHub + dry-run
