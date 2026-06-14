# Task Plan: 开发者上手与 Issue 模板标准化

## Issue

- **Number**: 9
- **Title**: 开发者上手与 Issue 模板标准化（P2）
- **Priority**: P2
- **Area**: area:workflow
- **Type**: documentation

## Goal

为新贡献者补齐上手路径，并把 GitHub Issue 创建体验与 GCW `issue-create` 模板对齐，减少 `gcw-issue-prepare` 因结构不完整而频繁进入 `needs-info`。

## Current Phase

Phase 5

## Phases

### Phase 1: Requirements & Discovery

- [x] 阅读 Issue #9 正文与验收标准
- [x] 对照 `docs/quickstart.md`、`issue-template.md`、现有 triage 脚本
- [x] 确认仓库尚无 `.github/`、`CONTRIBUTING.md`
- **Status:** complete

### Phase 2: CONTRIBUTING.md

- [x] 新增 `CONTRIBUTING.md`，与 `docs/quickstart.md` 互补而非重复
- [x] 覆盖：skill 安装路径、常用测试命令、GCW 分支约定（`gcw/issue-<n>`）、提 Issue / PR 基本要求
- [x] 在 `README.md` 增加指向 `CONTRIBUTING.md` 的链接
- **Status:** complete

### Phase 3: GitHub Issue Form

- [x] 新增 `.github/ISSUE_TEMPLATE/config.yml`（禁用空白 Issue）
- [x] 新增 Issue Form（YAML），字段映射 `issue-template.md` 四节
- [x] fixture + 单元测试验证 `enhancement` readiness profile
- **Status:** complete

### Phase 4: Labels sync（可选）

- [x] 新增 `workflow_dispatch` job：`.github/workflows/gcw-labels-sync.yml`
- [x] 在 `CONTRIBUTING.md` 文档化手动 sync 与 Actions 触发方式
- **Status:** complete

### Phase 5: Testing & Verification

- [x] `python3 -m unittest discover -s .agents/skills/gcw/tests`
- [x] `python3 -m unittest discover -s .agents/skills/gcw-issue-prepare/tests`
- [x] Issue Form fixture 通过 readiness gate
- **Status:** complete

### Phase 6: Delivery

- [ ] `gcw-implement-check` → `gcw-pr-publish` → `gcw-pr-review`
- **Status:** in progress

## Key Questions

1. Issue Form 用单一「Enhancement」模板还是再分 Bug / Documentation？——首期单一表单对齐 `enhancement` profile 即可。
2. Labels sync CI 是否本 PR 必做？——已实现可选 `workflow_dispatch`。

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `CONTRIBUTING.md` 偏「贡献约定」，Quickstart 偏「跟一遍 GCW」 | Issue Notes 要求互补、避免双份步骤 |
| Issue Form 正文以 `issue-template.md` 为单一来源 | 与 prepare gate 和 agent `issue-create` 一致 |
| Readiness 自测使用现有 `evaluate_issue_readiness.py` | 验收标准已明确；无需新 gate 脚本 |

## Out of Scope

- 重写 `docs/workflow.md` 全文
- GitLab 侧 Issue 模板
- 修改 prepare gate rubric 本身
