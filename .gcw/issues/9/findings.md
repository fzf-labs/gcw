# Findings & Decisions

## Requirements

- 新增 `CONTRIBUTING.md`：skill 安装、测试命令、GCW 分支约定
- 新增 `.github/ISSUE_TEMPLATE/` GitHub Issue Form，对齐 `issue-template.md`
- Issue Form 创建的 Issue 能通过 `evaluate_issue_readiness.py --profile enhancement`
- （可选）`labels.json` 一键 sync 的 CI job

## Research Findings

- 仓库当前无 `.github/` 目录；Issue 只能在 GitHub UI 用空白正文创建
- `docs/quickstart.md` 已覆盖 GCW 端到端演示，但前置条件未集中说明 skill 安装与本地测试命令
- PR #4 合并时 CI 曾因缺 `CONTRIBUTING.md` 失败（见 Issue #5 findings），本 Issue 直接补齐
- `.agents/skills/issue-create/issue-template.md` 定义标准四节结构，prepare gate `enhancement` profile 与之对齐
- `.agents/skills/gcw-issue-prepare/scripts/manage_triage_metadata.py sync` 已可同步 `labels.json` 到 GitHub；无现成 Action workflow
- 常用测试命令：`python3 -m unittest discover -s .agents/skills/gcw/tests`（见 Issue #5 实现记录）

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 使用 GitHub Issue **Form**（`.yml`）而非纯 markdown 模板 | Form 可强制必填字段，减少空 Issue |
| Form 输出 markdown 含 `## What to build` 等二级标题 | 与 structural gate 正则/解析一致 |
| `CONTRIBUTING.md` 链接 skill 目录 `.agents/skills/`，不复制 skill 正文 | 单一来源；skill 更新时少漂移 |
| Labels sync 采用可选 `workflow_dispatch` | 满足「可选」范围，低风险 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Issue 初稿仅标题重复，prepare gate 失败 | 已补充结构化正文并通过 gate |

## Resources

- Issue #9: https://github.com/fzf-labs/gcw/issues/9
- `docs/quickstart.md` — GCW 端到端上手
- `.agents/skills/issue-create/issue-template.md` — Issue 正文模板
- `.agents/skills/gcw-issue-prepare/labels.json` — triage label 定义
- GitHub docs: [Creating issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
