# Task Plan: P0 统一 GCW 步骤运行器

## Issue

- **Number**: 11
- **Title**: P0: Add a unified GCW step runner
- **Priority**: P0
- **Area**: area:workflow

## Goal

实现一个统一的 GCW 步骤运行器（step runner），让本地 agent 与未来 hosted Actions 通过单一、稳定的入口执行每个 GCW 里程碑步骤，而不是在 skill markdown 中重复手写「渲染产物 → 发布进度评论 → 记录事件 → 重建投影 → 运行校验门」的顺序。

运行器必须：

1. 覆盖至少这些里程碑步骤：`gcw-issue-prepare`、`gcw-issue-to-spec`、`gcw-spec-check`、`gcw-implement-check`、`gcw-pr-publish`、`gcw-pr-review`
2. 支持 `dry-run`：渲染计划产物与校验结果，但不修改 GitHub/GitLab、不追加事件
3. 仅在远端产物发布成功后记录事件，并立即重建 `workflow.json`
4. 返回结构化输出：`ok`、`step`、`phase_before`、`phase_after`、`artifacts`、`validation`、`stop_reason`（阻塞或澄清时）

## Current State Analysis

### 现有脚本职责

| 脚本 | 职责 |
| --- | --- |
| `manage_gcw_workflow.py` | 事件追加、投影重建、各步骤 `record-*` 子命令 |
| `render_gcw_hosted_artifacts.py` | 渲染 progress comment、review request body |
| `publish_progress_comment.py` | 渲染并发布 Issue 进度评论 |
| `validate_gcw_evidence.py` | workflow / spec-check / implement-check / pr-publish 等校验门 |
| `verify_gcw_remote_evidence.py` | 远端产物与本地渲染结果比对 |
| `gcw-issue-prepare/scripts/*` | prepare 专用：readiness gate、triage metadata |

### 当前痛点

1. **顺序分散**：各 `gcw-*` skill 的 Procedure 各自描述相似流水线，易漂移
2. **无统一契约**：agent 与 Action 没有共享的 JSON 结果结构
3. **副作用顺序脆弱**：若先 `record-*` 再发布远端产物，会出现事件与平台状态不一致
4. **dry-run 缺失**：本地调试只能 `--dry-run` 部分脚本（如 `publish_progress_comment.py`），无法端到端预览整步
5. **非法路由无集中拦截**：阶段错误通常在 `append_event` / reducer 才失败，缺少步骤级前置检查

## Design

### 模块布局

```
.agents/skills/gcw/scripts/
  run_gcw_step.py          # CLI 入口
  gcw_step_runner.py       # 核心 Runner 接口与步骤注册表
  gcw_step_adapters.py     # GitHub / GitLab / dry-run 平台适配器
```

### Runner 接口（概念）

```python
class GcwStepRunner:
    def run(self, step: str, issue_dir: Path, *, dry_run: bool = False) -> StepResult: ...
```

`StepResult` 字段：

- `ok: bool`
- `step: str`
- `phase_before: str`
- `phase_after: str`
- `artifacts: dict` — 渲染的 body、body_hash、planned event payload 等
- `validation: list[dict]` — 各校验命令及 exit_code
- `stop_reason: str | None` — `clarifying` / `blocked` / `illegal_phase` / `publication_failed` 等

### 单步执行顺序（非 dry-run）

```text
1. 加载并校验 projection（assert_projection_current）
2. 校验 step 在 next_allowed_steps 中
3. 执行步骤 prepare 逻辑（读 issue、跑 gate、渲染产物）
4. 运行步骤 validation gate（validate_gcw_evidence 等）
5. 若 gate 失败 → 返回 ok=false + stop_reason，不写事件
6. 发布 hosted artifacts（progress comment / PR body / triage metadata）
7. 若发布失败 → 返回 ok=false + stop_reason，不写事件
8. record event via manage_gcw_workflow 等价逻辑
9. rebuild workflow.json（record 已包含，但显式返回最终 projection）
10. 返回 StepResult
```

### dry-run 行为

- 执行步骤 1–4
- 渲染 artifacts 到 `artifacts` 字段
- **跳过** 步骤 6–8 的远端写入与事件追加
- `phase_after` 等于 `phase_before`

### 平台适配器

| 适配器 | 用途 |
| --- | --- |
| `DryRunAdapter` | 无远端副作用；返回假 URL 或空 URL |
| `GitHubAdapter` | `gh issue comment`、`gh pr create/edit`、triage metadata |
| `GitLabAdapter` | `glab issue note`、MR 操作、triage labels |

适配器通过构造注入，runner 不直接调用 `subprocess`。

### 步骤注册表（首批）

| Step | phase_before（允许） | 主要 validation | 主要 publication |
| --- | --- | --- | --- |
| `gcw-issue-prepare` | `issue-opened`, `issue-clarifying` | `evaluate_issue_readiness` | triage metadata + progress comment |
| `gcw-issue-to-spec` | `ready-for-planning` | planning files exist + hashes | push branch + progress comment |
| `gcw-spec-check` | `planned` | `validate_gcw_evidence spec-check` | progress comment |
| `gcw-implement-check` | `implementing` | `validate_gcw_evidence implement-check` | progress comment |
| `gcw-pr-publish` | `ready-for-review` | `validate_gcw_evidence pr-publish` | PR/MR upsert + progress comment |
| `gcw-pr-review` | `reviewing` | CI + `verify_gcw_remote_evidence` | progress comment |

`gcw-implement` 暂不纳入首批 runner（实现工作由 agent 完成，无固定 publication 序列）；后续可扩展 handoff 记录。

## Implementation Plan

### Phase 1: 核心框架

**Task 1.1**: 定义 `StepResult` dataclass / TypedDict 与 JSON 序列化

**Task 1.2**: 实现 `gcw_step_runner.py` — phase 路由检查、步骤注册表、`run()` 骨架

**Task 1.3**: 实现 `gcw_step_adapters.py` — `DryRunAdapter`、`GitHubAdapter`（GitLab 可 Phase 2）

**Task 1.4**: 实现 `run_gcw_step.py` CLI：`--step`、`--issue-dir`、`--dry-run`、`--json`

### Phase 2: 步骤处理器

**Task 2.1**: `PrepareStepHandler` — 封装 readiness + triage + record-issue-prepare 顺序

**Task 2.2**: `ToSpecStepHandler` — 校验 planning files + spec_refs + record-issue-to-spec

**Task 2.3**: `SpecCheckStepHandler` — validate + record-spec-check

**Task 2.4**: `ImplementCheckStepHandler` — payload 生成/校验 + record-implement-check

**Task 2.5**: `PrPublishStepHandler` — render review request + PR upsert + record-pr-publish

**Task 2.6**: `PrReviewStepHandler` — remote checks + record-pr-review

### Phase 3: 测试

**Task 3.1**: 成功路径：mock adapter，完整 run 返回 `ok=true`

**Task 3.2**: dry-run：无事件追加、无 adapter 调用

**Task 3.3**: publication 失败：adapter 抛错，事件数不变

**Task 3.4**: validation 失败：gate 不通过，无 publication

**Task 3.5**: 非法 phase 路由：`next_allowed_steps` 不包含目标 step

### Phase 4: 文档与 skill 更新

**Task 4.1**: 在 `.agents/skills/gcw/scripts/README` 或 runner 模块 docstring 说明 CLI 用法

**Task 4.2**: 更新各 `gcw-*` step skill 的 Procedure，改为调用 `run_gcw_step.py`（保留原脚本作为底层能力）

**Task 4.3**: 为 future `gcw-*.yml` Actions 预留 `--json` 输出契约

## Acceptance Mapping

| Issue AC | Plan Task |
| --- | --- |
| Runner interface for 6 milestone steps | Phase 1 + Phase 2 |
| dry-run mode | Task 1.3, 3.2 |
| Events only after publication | Task 1.2 step order, 3.3 |
| Structured output fields | Task 1.1 |
| Existing scripts remain usable | adapters call existing modules |
| Unit tests (5 scenarios) | Phase 3 |
| Docs + skill updates | Phase 4 |

## Risks

- prepare 步骤依赖 `gcw-issue-prepare/scripts/`，runner 需正确设置 `sys.path` 或子进程调用
- PR publish 的 idempotent upsert 逻辑已在 skill 中演进，runner 应复用而非重写
- hosted Actions 尚未存在，runner JSON 契约需与 issue #11 之后的 Action 设计对齐

## Out of Scope

- `gcw-implement` 的代码生成逻辑（agent 职责）
- 新建 GitHub Actions workflow 文件（本 issue 打基础，不交付 CI）
- 替换 `manage_gcw_workflow.py` 的 `record-*` 子命令（runner 调用它们）
