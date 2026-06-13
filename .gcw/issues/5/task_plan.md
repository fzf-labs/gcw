# Task Plan: 端到端 GCW Quickstart

## Goal

新增 `docs/quickstart.md`，以 Issue #3 / PR #4 为真实案例，让读者在约 10–15 分钟内跟着走完 GCW 主流程（接入 → spec → 实现 → PR → review 反馈），并在 `README.md` 与 `docs/workflow.md` 中增加导航链接。

## Current Phase

Phase 4

## Phases

### Phase 1: Requirements & Discovery
- [x] 阅读 Issue #5 验收标准与 Notes
- [x] 对照 Issue #3 评论、`gcw/issue-3` 分支上的 events / spec 示例
- [x] 确认不扩展 `CONTRIBUTING.md` 等 CI 期望文档
- **Status:** complete

### Phase 2: Planning & Structure
- [x] 定义 Quickstart 章节结构（前置条件、逐步操作、观察产物、反馈闭环、深入阅读）
- [x] 为每个 GCW 步骤选定 Issue #3 上的可点击远程链接
- **Status:** complete

### Phase 3: Implementation
- [x] 撰写 `docs/quickstart.md`（中文正文，专有名词保留英文）
- [x] 更新 `README.md` 文档导航
- [x] 在 `docs/workflow.md` 增加一句指向 Quickstart 的链接
- **Status:** complete

### Phase 4: Testing & Verification
- [x] 检查所有远程链接可访问（Issue #3 评论、分支 spec、PR #4）
- [x] 确认 Quickstart 不重复 `docs/workflow.md` 步骤表全文
- [x] 运行 `python3 -m unittest discover -s .agents/skills/gcw/tests`
- **Status:** complete

### Phase 5: Delivery
- [x] 通过 `gcw-implement-check` 与 `gcw-pr-publish` 发布 PR
- [x] `gcw-pr-review` 自动检查通过（本地验证 + 远程 PR body 校验）
- **Status:** complete

## Key Questions

1. Quickstart 是否演示 Issue #5 自身作为 live 示例？——Issue 要求以 #3 / #4 为主线；#5 可作为「正在进行的第二实例」一句带过，不喧宾夺主。
2. 是否包含截图？——验收标准未要求；以可点击链接与引用 `<!-- gcw-progress -->` 块为主。

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 主线案例固定为 Issue #3 / PR #4 | Issue 明确要求，且已有完整 events 与 review 反馈素材 |
| spec / events 链接指向 `gcw/issue-3` 远程分支 | master 合并后本地可能无 `.gcw/issues/3/` |
| Quickstart 做「跟着做」，workflow 做「查手册」 | 避免两文档重复，满足 Issue 分工 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
|       |         |            |
