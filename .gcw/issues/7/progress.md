# Progress: P0 给事件和投影加硬校验

## Issue #7

**Status**: implementing

## Timeline

| Phase | Status | Notes |
|---|---|---|
| Phase 1: Schema 硬化 | done | additionalProperties:false, strict types, enums, patterns |
| Phase 2: Reducer 硬化 | done | validate_payload, validate_event_name, validate_events_integrity |
| Phase 3: 原子性写入 | done | write_json uses tempfile + os.replace |
| Phase 4: 证据验证硬化 | done | review-check, block-check, clarify-check; deeper payload validation |
| Phase 5: 远程验证硬化 | done | body_hash verification, marker counting, UTF-8 handling |
| Phase 6: 测试硬化 | done | 29 → 50 tests; negative/boundary tests added |
| Phase 7: Schema 验证集成 | done | jsonschema optional integration in append_event + workflow check |

## Blockers

None.

## Decisions

- 硬化策略：先 warning 模式，确认兼容后切换 error 模式
- 原子性写入：采用 write-to-temp + rename 模式
- 测试策略：每个 Phase 完成后立即补充对应测试
- Schema 验证：jsonschema 可选集成，未安装时不阻断
