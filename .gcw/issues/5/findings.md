# Findings & Decisions

## Requirements

- 新增 `docs/quickstart.md`，端到端演示 GCW 主流程
- 以 Issue #3（添加 `README.md`）与 PR #4 为贯穿示例
- 覆盖 `/gcw` 接入至 `gcw-pr-review`，含 `changes-requested` 反馈闭环
- 各阶段提供可点击远程链接（Issue、PR、分支上 spec / events）
- 更新 `README.md` 与 `docs/workflow.md` 互相导航
- 说明前置条件（已有 Issue、`gh`、GCW skills；`gcw-issue-intake` 无 Action）

## Research Findings

- Issue #3 评论含 `planned`、`ready-for-implementation`、`changes-requested` 三类 `<!-- gcw-progress -->` 块
- `gcw/issue-3` 分支保留 `.gcw/issues/3/events/`（000–007）与 `workflow.json` 投影
- PR #4 已合并；`changes-requested` 来自 CI `validate` 失败（缺 `CONTRIBUTING.md` 等，超出 #3 scope）
- 当前 `README.md` 仅链接 `docs/workflow.md`，无 Quickstart 入口
- Issue #5 标签：`documentation`；Blocked by：无

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Quickstart 按 GCW 8 步组织章节 | 与主流程示意一致，读者可按步骤跳转 |
| 每步列出「执行」「观察」「状态」三要素 | 满足「跟着做一遍」而非纯理论 |
| 不补齐 CONTRIBUTING 等缺失文档 | Issue Notes 明确排除 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
|       |            |

## Resources

- Issue #5: https://github.com/fzf-labs/gcw/issues/5
- Issue #3: https://github.com/fzf-labs/gcw/issues/3
- PR #4: https://github.com/fzf-labs/gcw/pull/4
- 示例分支: `gcw/issue-3`
- `docs/workflow.md` — 步骤、状态、Action 流水线详解
