# Task Plan: P0 给事件和投影加硬校验

## Issue
- **Number**: 7
- **Title**: P0 给事件和投影加硬校验，所有 payload、transition、required fields 都能被机器验证，workflow.json 可重建。
- **Priority**: P0
- **Area**: area:workflow

## Goal

为 GCW 事件和投影系统添加硬校验，确保：
1. 所有事件 payload 的字段类型、结构、枚举值都能被机器验证
2. 所有状态转换都能被机器验证（只能从合法前置阶段转换到合法目标阶段）
3. workflow.json 可从事件日志确定性重建，且重建结果可验证

## Current State Analysis

### 现有验证层

| 层 | 文件 | 当前能力 | 缺陷 |
|---|---|---|---|
| JSON Schema | `event.schema.json` | 声明 required 字段 | `additionalProperties:true` 允许任意字段；无 payload 类型约束；无枚举约束 |
| Reducer | `gcw_workflow_lib.py:reduce_workflow` | 阶段前置检查 + 部分布尔检查 | 不验证 payload 字段类型和结构；不验证事件名合法性 |
| CLI 验证 | `validate_gcw_evidence.py` | 4 个检查命令 | 不验证 spec_refs hash；不验证 effects 结构；缺少 review/block/clarify 检查 |
| 远程验证 | `verify_gcw_remote_evidence.py` | 进度评论和 review request 比对 | 不使用 body_hash 校验；全文比对过于脆弱 |
| 测试 | `tests/` | 正向路径覆盖 | 无负向测试；无边界测试；fixture 单一 |

### 关键缺陷（Top 10）

1. **P0**: Schema `additionalProperties:true` 允许任意字段注入
2. **P0**: `reduce_workflow` 不验证 payload 字段类型和结构
3. **P0**: 并发写入无原子性保护
4. **P1**: `append_event` 不验证事件名称合法性
5. **P1**: 远程验证不使用 `body_hash` 校验
6. **P1**: 测试只覆盖正向路径，无负向/边界测试
7. **P1**: `write_json` 非原子写入，可能留下损坏文件
8. **P2**: Schema 不验证 payload 字段类型和枚举值
9. **P2**: `load_events` 不验证文件名与内容一致性
10. **P2**: `hash_events` 跨语言/版本不确定性

## Implementation Plan

### Phase 1: Schema 硬化 (event.schema.json + workflow_projection.schema.json)

**Task 1.1**: 将顶层和所有嵌套对象的 `additionalProperties` 改为 `false`（或严格定义的属性集）

**Task 1.2**: 为每个事件类型的 payload 添加完整的类型和结构约束：
- `gcw-issue-intake`: `issue` (string), `platform` (enum: github/gitlab), `repository` (string), `branch` (string), `owner` (object with kind enum + id string)
- `gcw-issue-prepare`: `ready` (boolean), `question` (string, required when ready=false), `summary` (string), `classification` (object with type/area/priority), `labels_applied` (array of strings)
- `gcw-issue-to-spec`: `planning_commit_pushed` (boolean), `progress_comment_url` (string), `spec_refs` (object with task_plan_sha/findings_sha/progress_sha, all string with sha256: prefix)
- `gcw-spec-check`: `gate` (object with ok:boolean, checks:array, errors:array), `result` (enum), `question` (string), `reason` (string)
- `gcw-implement`: `work_summary` (string, minLength:1), `feedback_source` (enum), `feedback_ref` (string)
- `gcw-implement-check`: `gate` (object with ok:boolean, checks:array of {id:string, ok:boolean}, validation:array of {command:string, exit_code:integer, result:string}), `review_request` (object with title/summary/issue_link), `risks` (string), `scope` (string), `reviewer_notes` (string), `self_review` (object), `spec_refs` (object with sha256 hashes)
- `gcw-pr-publish`: `review_request_url` (string, format:uri), `rendered_from_event_id` (string), `body_hash` (string, pattern: sha256:), `effects` (array of effect objects)
- `gcw-pr-review`: `result` (enum: passed/changes-requested/blocked), `feedback_source` (enum), `reason` (string)
- `gcw-block`: `reason` (string, minLength:1), `resume_phase` (enum from STATES), `resume_step` (enum from step names)
- `gcw-clarify`: `question` (string, minLength:1), `source_phase` (enum from STATES)
- `review-complete`: `result` (enum: merged/closed/accepted/rejected)

**Task 1.3**: 为 `actor.kind` 添加枚举约束 (local, github-actions, gitlab-ci, manual)

**Task 1.4**: 为 `at` 添加 format: date-time 约束

**Task 1.5**: 为 `event_id` 添加 pattern 约束

**Task 1.6**: 将 `parent.expected_last_seq` 设为 required

**Task 1.7**: 为 `refs` 添加属性定义 (issue, branch)

**Task 1.8**: 同步硬化 `workflow_projection.schema.json`

### Phase 2: Reducer 硬化 (gcw_workflow_lib.py)

**Task 2.1**: 在 `append_event` 中添加事件名合法性验证（必须为已知事件类型）

**Task 2.2**: 在 `reduce_workflow` 中为每个事件类型添加 payload 字段类型验证

**Task 2.3**: 添加 `validate_payload(event_name, payload)` 函数，在 reducer 处理前验证 payload 结构

**Task 2.4**: 验证 `gcw-block` 的 `resume_phase` 和 `resume_step` 合法性

**Task 2.5**: 验证 `gcw-clarify` 的 `source_phase` 合法性

**Task 2.6**: 验证 `review-complete` 的 `result` 值合法性

**Task 2.7**: 在 `load_events` 中添加文件名与内容一致性验证

**Task 2.8**: 添加 `validate_event_integrity(event)` 函数，验证单个事件的内部一致性

### Phase 3: 原子性写入保护

**Task 3.1**: 将 `write_json` 改为先写临时文件再 rename 的原子写入模式

**Task 3.2**: 在 `append_event` 和 `write_projection` 中使用原子写入

### Phase 4: 证据验证硬化 (validate_gcw_evidence.py)

**Task 4.1**: 添加 `spec-check` 对 `spec_refs` hash 与实际文件内容的一致性验证

**Task 4.2**: 添加 `implement-check` 对 `self_review`、`spec_refs`、`gate.checks`、`gate.validation` 的结构验证

**Task 4.3**: 添加 `pr-publish` 对 `effects` 结构和 `body_hash` 格式的验证

**Task 4.4**: 添加 `review-check` 命令

**Task 4.5**: 添加 `block-check` 命令

**Task 4.6**: 添加 `clarify-check` 命令

**Task 4.7**: 在 `workflow` 检查中添加 `parent.expected_last_seq` 连续性验证

### Phase 5: 远程验证硬化 (verify_gcw_remote_evidence.py)

**Task 5.1**: 使用 `body_hash` 校验远程内容与事件记录的一致性

**Task 5.2**: 添加结构化比对替代全文严格比对

**Task 5.3**: 添加标记嵌套/重复检测

### Phase 6: 测试硬化

**Task 6.1**: 为 `test_gcw_workflow_lib.py` 添加负向测试：
- 非法状态转换
- 事件序列不连续
- 首事件非 intake
- payload 字段缺失/类型错误
- 未知事件类型
- 乐观并发冲突
- 文件已存在

**Task 6.2**: 为 `test_validate_gcw_evidence.py` 添加负向测试

**Task 6.3**: 为 `test_gcw_schemas.py` 添加 jsonschema.validate 实际验证测试

**Task 6.4**: 添加多样化 fixture（blocked, clarifying, reviewing, review_complete, corrupted）

**Task 6.5**: 为 `test_verify_gcw_remote_evidence.py` 添加边界测试

**Task 6.6**: 为 `test_manage_gcw_state.py` 添加错误路径测试

### Phase 7: Schema 验证集成

**Task 7.1**: 在 `append_event` 中集成 jsonschema 验证（使用硬化后的 schema）

**Task 7.2**: 在 `validate_gcw_evidence.py workflow` 检查中集成 schema 验证

**Task 7.3**: 确保 `rebuild-projection` 命令在重建前验证所有事件

## Execution Order

1. Phase 1 (Schema 硬化) — 基础，其他层依赖
2. Phase 3 (原子性写入) — 独立，可并行
3. Phase 2 (Reducer 硬化) — 依赖 Phase 1 的 schema 定义
4. Phase 7 (Schema 验证集成) — 依赖 Phase 1 + Phase 2
5. Phase 4 (证据验证硬化) — 依赖 Phase 2
6. Phase 5 (远程验证硬化) — 依赖 Phase 4
7. Phase 6 (测试硬化) — 贯穿所有 Phase，每个 Phase 完成后立即补充对应测试

## Risk Assessment

- **Breaking change**: 硬化 schema 可能导致现有事件文件无法通过验证。需要确保向后兼容或提供迁移路径。
- **Performance**: jsonschema 验证可能增加事件追加延迟。对于小规模事件日志影响可忽略。
- **Complexity**: 完整的 payload 类型验证增加代码量，需要权衡验证深度与维护成本。
