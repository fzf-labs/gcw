# Progress: P0 给事件和投影加硬校验

## Issue #7

**Status**: planned

## Timeline

| Phase | Status | Notes |
|---|---|---|
| Phase 1: Schema 硬化 | pending | event.schema.json + workflow_projection.schema.json |
| Phase 2: Reducer 硬化 | pending | gcw_workflow_lib.py |
| Phase 3: 原子性写入 | pending | write_json 原子化 |
| Phase 4: 证据验证硬化 | pending | validate_gcw_evidence.py |
| Phase 5: 远程验证硬化 | pending | verify_gcw_remote_evidence.py |
| Phase 6: 测试硬化 | pending | tests/ |
| Phase 7: Schema 验证集成 | pending | jsonschema 集成 |

## Blockers

None.

## Decisions

- 硬化策略：先 warning 模式，确认兼容后切换 error 模式
- 原子性写入：采用 write-to-temp + rename 模式
- 测试策略：每个 Phase 完成后立即补充对应测试
