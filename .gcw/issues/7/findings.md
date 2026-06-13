# Findings: P0 给事件和投影加硬校验

## 1. 现有架构概述

GCW 采用事件溯源架构：

- **事件日志** (`.gcw/issues/<id>/events/*.json`) 是唯一权威数据源
- **投影缓存** (`.gcw/issues/<id>/workflow.json`) 是从事件日志确定性推导出的缓存
- **Reducer** (`reduce_workflow`) 是将事件序列折叠为当前状态的核心函数
- **Schema** (`event.schema.json`) 是事件结构的声明式约束

关键设计原则：
- workflow.json 删除后必须能从事件日志完全重建
- 乐观并发控制通过 `parent.expected_last_seq` 实现
- 确定性哈希通过 `hash_events` 的 `sha256` 实现

## 2. 验证层次分析

### 2.1 Schema 层 (event.schema.json)

**现状**：Schema 定义了 11 种事件类型（8 主步骤 + 2 反馈循环 + 1 终态），每种事件声明了 required payload 字段。

**关键发现**：
- 所有 `additionalProperties: true` — 无法防止字段注入或拼写错误
- payload 字段无类型约束 — `issue` 可以是数字、字符串、对象甚至 null
- 无枚举约束 — `platform` 不限于 github/gitlab，`result` 不限于合法值
- `parent.expected_last_seq` 不是 required — 可以创建没有并发控制的事件
- `refs` 完全无结构定义 — 任何内容都可以塞入

### 2.2 Reducer 层 (gcw_workflow_lib.py)

**现状**：`reduce_workflow` 实现了完整的状态机，每个事件类型有前置阶段检查。

**关键发现**：
- 只验证阶段前置条件，不验证 payload 字段类型
- `gate` 只检查 `isinstance(dict)` 和 `ok is True`，不验证内部结构
- `gcw-implement-check` 的 7 个 required payload 字段完全没有被 reducer 验证
- `gcw-block` 的 `resume_phase`/`resume_step` 不验证合法性
- `append_event` 不验证事件名是否为已知类型
- `load_events` 不验证文件名与内容一致性

### 2.3 证据验证层 (validate_gcw_evidence.py)

**现状**：提供 4 个检查命令 (workflow, spec-check, implement-check, pr-publish)。

**关键发现**：
- `spec-check` 不验证 `spec_refs` hash 与实际文件内容一致
- `implement-check` 只验证 `review_request` 的 3 个子字段，不验证其他 6 个 required 字段
- `pr-publish` 不验证 `effects` 元素结构
- 缺少 review-check、block-check、clarify-check 命令
- `workflow` 检查不验证 `parent.expected_last_seq` 连续性

### 2.4 远程验证层 (verify_gcw_remote_evidence.py)

**现状**：验证远端平台产物与本地渲染结果一致。

**关键发现**：
- 不使用 `body_hash` 校验远程内容
- 全文严格比对过于脆弱，格式微差即失败
- 标记嵌套时行为不确定
- 不验证远程内容时效性

### 2.5 测试层

**现状**：6 个测试文件，覆盖正向路径。

**关键发现**：
- `test_gcw_workflow_lib.py` 只有 2 个测试用例，缺少几乎所有负向路径
- `test_validate_gcw_evidence.py` 只有正向验证
- `test_gcw_schemas.py` 不使用 jsonschema.validate 实际验证数据
- fixture 只有一种 (complete_issue)，缺少 blocked/clarifying/reviewing/corrupted 场景

## 3. workflow.json 可重建性风险

### 3.1 已有保护

- `assert_projection_current` 比较事件 hash 和投影内容
- `rebuild-projection` 命令可从事件重建投影
- `validate_event_sequence` 检查 seq 连续性

### 3.2 重建失败场景

| 场景 | 当前行为 | 影响 |
|---|---|---|
| 事件文件被删除 | `validate_event_sequence` 报 seq 不连续 | 无法重建，错误信息不明确 |
| 事件文件被手动编辑 | `assert_projection_current` 报 hash 不匹配 | 可重建但与旧投影不一致 |
| 事件文件部分写入 | `read_json` 抛 JSON 解析错误 | 无法加载事件，系统不可用 |
| workflow.json 部分写入 | `load_projection` 抛 JSON 解析错误 | 无法加载投影，但可重建 |
| 并发写入同一 seq | 两个文件同时存在，seq 重复 | `validate_event_sequence` 失败 |
| 文件名与内容不一致 | 按内容 seq 排序，hash 一致 | 调试困难但功能正常 |
| JSON 序列化差异 | 不同 Python 版本可能产生不同 hash | 误报 hash 不匹配 |

### 3.3 关键风险

最严重的风险是**事件文件部分写入**和**并发写入竞争**，因为它们会导致系统完全不可用，而不仅仅是验证失败。

## 4. 依赖关系

- Schema 硬化是其他所有硬化的基础 — payload 类型定义需要先在 schema 中声明
- Reducer 硬化依赖 Schema 定义 — 验证逻辑应与 schema 保持一致
- 证据验证硬化依赖 Reducer 硬化 — 检查逻辑应复用 reducer 的验证
- 测试硬化贯穿所有阶段 — 每个 Phase 完成后立即补充测试
- 原子性写入独立于其他硬化 — 可以并行实施

## 5. 向后兼容性考虑

硬化 schema 和 reducer 验证可能导致：
1. 现有事件文件无法通过新的 schema 验证
2. 现有测试 fixture 需要更新
3. CLI 命令的参数验证更严格

建议策略：
- 新验证以 **warning 模式** 先上线，不阻断现有流程
- 确认所有现有事件文件通过新验证后，再切换为 **error 模式**
- 为 `append_event` 添加 `--skip-validation` 选项用于紧急情况
