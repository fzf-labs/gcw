# Contributing to GCW

本文说明如何在本仓库贡献代码与文档。若你想**跟着走一遍 GCW 主流程**，请看 [GCW Quickstart](docs/quickstart.md)；本文侧重环境、约定与提 Issue / PR 的入口。

## 前置条件

- **Git** 与 **Python 3**（运行 GCW 脚本与测试）
- **GitHub CLI**（`gh`）已安装并登录：`gh auth login`
- IDE 中启用 GCW skills（仓库内路径：`.agents/skills/gcw/` 及各 `gcw-*` step skill）

## Skill 安装

GCW skills 随仓库提供，无需单独发布包。在 Cursor / 支持 Agent Skills 的环境中，将本仓库的 `.agents/skills/` 加入 skill 搜索路径，或按你使用的 IDE 文档把该目录链到本地 skills 目录。

常用入口：

- 编排：`/gcw <issue-number>`
- 单步：各 `gcw-issue-intake`、`gcw-issue-triage`、`gcw-issue-clarify` 等 skill

Skill 与脚本以仓库内文件为准；修改 skill 后请运行下方测试命令。

## 测试与校验

在仓库根目录执行：

```bash
# GCW 单元测试
python3 -m unittest discover -s .agents/skills/gcw/tests

# 事件日志与投影（将 <issue-id> 换成实际编号）
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py workflow \
  --issue-dir .gcw/issues/<issue-id>

# Issue 结构 readiness（GitHub Issue 或本地正文）
python3 .agents/skills/gcw-issue-clarify/scripts/evaluate_issue_readiness.py \
  --profile enhancement --platform github --repo OWNER/REPO --issue <n>
```

## GCW 分支约定

- Issue 工作分支：`gcw/issue-<n>`（例如 Issue #9 → `gcw/issue-9`）
- Spec、事件日志与 `workflow.json` 放在 **issue 分支** 的 `.gcw/issues/<n>/`
- 不要 force push issue 分支，除非维护者明确要求
- 实现与规划提交分开：规划提交仅含 spec / events；实现提交含产品代码与文档

主流程见 [README.md](README.md) 与 [docs/workflow.md](docs/workflow.md)。

## 提 Issue

请使用 GitHub 上的 **Enhancement** Issue 表单（`.github/ISSUE_TEMPLATE/`），正文结构对齐 [issue-template.md](.agents/skills/issue-create/issue-template.md)：

- `## What to build`
- `## Acceptance criteria`（至少一条 `- [ ]` 项）
- `## Notes`（可选）
- `## Blocked by`（无阻塞时写 `None - can start immediately`）

结构完整的 Issue 更容易在 `gcw-issue-clarify` 通过 readiness gate，避免长时间停在 `issue-clarifying`。

## 提 Pull Request

1. 从 `master`（或仓库默认分支）拉取最新代码
2. 在 `gcw/issue-<n>` 上完成实现并通过本地测试
3. 经 GCW 的 `gcw-implement-check` 后再发布 PR（`gcw-pr-publish`）
4. PR 描述应链回 Issue，并说明范围与风险

## 维护 GitHub Labels（维护者）

GCW triage 标签定义在 `.agents/skills/gcw-issue-triage/labels.json`。同步到 GitHub：

```bash
python3 .agents/skills/gcw-issue-triage/scripts/manage_triage_metadata.py sync \
  --platform github --repo fzf-labs/gcw
```

也可在 GitHub Actions 中手动触发 **GCW Labels Sync** workflow（`workflow_dispatch`），见 `.github/workflows/gcw-labels-sync.yml`。

## Hosted Agent（GitHub Actions）

在仓库中配置 `OPENAI_API_KEY`（Secret）、`OPENAI_API_ENDPOINT` 与 `AGENT_LOGIN`（Variables）后，可为 Issue 打上 trigger label（如 `gcw:ready-for-planning`）触发托管 agent。详见 [docs/hosted-agent.md](docs/hosted-agent.md)。

## 文档语言

Markdown 文档正文使用中文；专有名词、命令、路径与配置键保留英文。详见仓库文档规范。
