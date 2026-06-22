# GCW Quickstart

本文用仓库内真实案例 **[Issue #3](https://github.com/fzf-labs/gcw/issues/3)**（添加 `README.md`）与 **[PR #4](https://github.com/fzf-labs/gcw/pull/4)**，演示如何从已有 Issue 启动 GCW、走完 spec、实现、发布 PR，以及处理 review 反馈。

Quickstart 侧重「跟着做一遍」；步骤表、状态机与 Action 流水线细节见 [GCW 工作流](workflow.md)。

## 前置条件

- 平台上已有一个可执行的 Issue（GitHub 或 GitLab）
- 本地已安装并登录 `gh`（GitHub）或 `glab`（GitLab）
- IDE 中已启用 GCW skills（`/gcw` 或各 `gcw-*` step skill）
- 了解：spec files 写在 issue 分支的 `.gcw/issues/<issue-id>/`，通过 Issue 评论链接，而不是写入 Issue 正文

如果是在其他项目中首次使用 GCW，可以先安装 CLI 并初始化 repo-local assets：

```bash
npm install -g @fzf-labs/gcw
cd <target-repo>
gcw init
gcw doctor
```

需要 hosted workflow assets 时，按平台使用 `gcw init --with-github-actions` 或 `gcw init --with-gitlab-ci`。这会额外安装 `.gcw/engine/hosted` 与 `.gcw/engine/platforms`，供托管 runner 调用共享 GCW workflow core。初始化后再按 IDE 文档启用目标仓库的 `.agents/skills/`。

如果你想完全走终端入口，而不是从 IDE skill 开始，可以先熟悉这四个正式命令：

```bash
gcw status 3
gcw next 3
gcw step gcw-spec-check 3
gcw run 3
```

- `gcw status <issue-number>`：检查当前 workflow state。
- `gcw next <issue-number>`：看当前 phase 最先允许的步骤。
- `gcw step <step-name> <issue-number>`：只执行一步。
- `gcw run <issue-number>`：自动推进直到 `planned`、`issue-clarifying`、`blocked`、`reviewing` 或 `review-complete`。

**关于 Action**：`gcw-issue-intake` 没有对应 Action workflow；其余步骤支持 **Hosted agent execution**（runner 内 `openai/codex-action` + 事件触发）。见 [Hosted Agent](hosted-agent.md)。

## 示例 Issue 一览

| 资源 | 链接 |
| --- | --- |
| 示例 Issue | [fzf-labs/gcw#3](https://github.com/fzf-labs/gcw/issues/3) |
| 示例 PR | [PR #4](https://github.com/fzf-labs/gcw/pull/4)（已合并） |
| 示例分支 | [`gcw/issue-3`](https://github.com/fzf-labs/gcw/tree/gcw/issue-3) |
| Spec files | [`task_plan.md`](https://github.com/fzf-labs/gcw/blob/gcw/issue-3/.gcw/issues/3/task_plan.md)、[`findings.md`](https://github.com/fzf-labs/gcw/blob/gcw/issue-3/.gcw/issues/3/findings.md)、[`progress.md`](https://github.com/fzf-labs/gcw/blob/gcw/issue-3/.gcw/issues/3/progress.md) |
| 事件日志 | [`.gcw/issues/3/events/`](https://github.com/fzf-labs/gcw/tree/gcw/issue-3/.gcw/issues/3/events) |
| 状态投影 | [`workflow.json`](https://github.com/fzf-labs/gcw/blob/gcw/issue-3/.gcw/issues/3/workflow.json) |

> **提示**：PR 合并后 `master` 上可能没有 `.gcw/issues/3/`；对照示例时请打开远程分支 `gcw/issue-3`，不要假设本地路径存在。

## 如何读每一步

每个步骤列出三列：

- **执行**：你在 IDE 里输入的命令或 skill
- **观察**：平台上应出现的产物
- **状态**：`workflow.json` 投影中的 `phase`（或由 Issue 评论中的 `<!-- gcw-progress -->` 块反映）

进度评论以 HTML 注释 `<!-- gcw-progress -->` 开头，便于人与 agent 在 Issue 时间线中定位 GCW 状态。**每个主步骤完成时新发一条评论，禁止编辑旧评论**；`workflow.json` 的 `refs.progress_comment_url` 始终指向最新一条。首条结构化进度评论在 `gcw-issue-triage` 完成时发出；`gcw-issue-intake` 只写本地 GCW 事件，不发 Issue 评论。

每种 `GCW Status` 只展示该阶段相关的段落，而不是把所有字段塞进同一条评论：

| `GCW Status` | 评论段落 |
| --- | --- |
| `issue-opened` | `## Context` |
| `ready-for-planning` 及之后 | `## Context`、`## Triage`（Type / Area / Priority） |
| `ready-for-planning` | 另含 `## Readiness`（structural gate 摘要） |
| `issue-clarifying` | `## Context`、`## Triage`、`## Readiness`、`## Clarification` |
| `planned` | `## Context`、`## Triage`、`## Planning files` |
| `ready-for-implementation` | `## Context`、`## Triage`、`## Spec gate` |
| `implementing` | `## Context`、`## Triage`、`## Implementation` |
| `ready-for-review` | `## Context`、`## Triage`、`## Readiness`、`## Risks` |
| `reviewing` | `## Context`、`## Triage`、`## Review` |
| `changes-requested` | `## Context`、`## Triage`、`## Review`、`## Feedback` |
| `blocked` | `## Context`、`## Triage`、`## Blocker` |
| `review-complete` | `## Context`、`## Triage`、`## Outcome` |

例如 Issue #3 上的三条评论：

- [`planned`](https://github.com/fzf-labs/gcw/issues/3#issuecomment-4697976894)
- [`ready-for-implementation`](https://github.com/fzf-labs/gcw/issues/3#issuecomment-4697978196)
- [`changes-requested`](https://github.com/fzf-labs/gcw/issues/3#issuecomment-4698106204)

## 步骤 1：`gcw-issue-intake`

| | |
| --- | --- |
| **执行** | 在 Cursor 等 IDE 中：`/gcw 3`，或终端执行 `gcw run 3`，或运行 `gcw-issue-intake` skill |
| **观察** | 创建/切换 `gcw/issue-3`；出现 `.gcw/issues/3/events/000-gcw-issue-intake.json` 与 `workflow.json`；尚无 spec files |
| **状态** | `issue-opened` |

Intake 读取 Issue、创建 issue 分支并持久化第一条事件；不创建 `task_plan.md` / `findings.md` / `progress.md`，也不发进度评论。

## 步骤 2：`gcw-issue-triage`

| | |
| --- | --- |
| **执行** | 继续 `/gcw 3`，或让 `gcw run 3` 自动继续，或显式执行 `gcw step gcw-issue-triage 3` |
| **观察** | Issue 上出现 triage 标签/字段（如 `triaged`、`area:*`、本地执行时的 `gcw:executor-local`、Issue Type、Priority）；首条 `<!-- gcw-progress -->` 评论；`events/001-gcw-issue-triage.json` |
| **状态** | `issue-triaged` |

Triage 只负责分类与远端 metadata 同步，不判断需求是否清楚。

## 步骤 3：`gcw-issue-clarify`

| | |
| --- | --- |
| **执行** | 继续 `/gcw 3`，或让 `gcw run 3` 自动继续，或显式执行 `gcw step gcw-issue-clarify 3` |
| **观察** | 新发 `<!-- gcw-progress -->` 评论；`events/002-gcw-issue-clarify.json` 包含 readiness gate |
| **状态** | `ready-for-planning` 或 `issue-clarifying` |

Clarify 运行 structural readiness gate。信息不足时停在 `issue-clarifying`；澄清问题写入 `gcw-progress` 的 `## Clarification` 段落。

## 步骤 4：`gcw-issue-to-spec`

| | |
| --- | --- |
| **执行** | `gcw run 3` 会在 ready-for-planning 时继续推进到这里；也可显式执行 `gcw step gcw-issue-to-spec 3` |
| **观察** | 分支上有 `.gcw/issues/3/task_plan.md` 等；[进度评论](https://github.com/fzf-labs/gcw/issues/3#issuecomment-4697976894) 显示 `GCW Status: planned` |
| **状态** | `planned` |

## 步骤 5：`gcw-spec-check`

| | |
| --- | --- |
| **执行** | `gcw-spec-check`：校验 spec 已推送、评论已链接、内容可实施 |
| **观察** | `events/004-gcw-spec-check.json`；[新发进度评论](https://github.com/fzf-labs/gcw/issues/3#issuecomment-4697978196) 为 `ready-for-implementation` |
| **状态** | `ready-for-implementation` |

未通过则回到 `issue-clarifying`，spec 草稿保留。

## 步骤 6：`gcw-implement`

| | |
| --- | --- |
| **执行** | `gcw-implement`：按 `task_plan.md` 修改代码与文档、补测试 |
| **观察** | 根目录出现 `README.md` 等实现提交；`events/005-gcw-implement.json` |
| **状态** | `implementing` |

Issue #3 的交付物是 [README.md](https://github.com/fzf-labs/gcw/blob/gcw/issue-3/README.md)。
如果实现已经收口，继续执行 `gcw run 3` 会自动推进到 `gcw-implement-check` 和 `gcw-pr-publish`，直到停在 `reviewing`。

## 步骤 7：`gcw-implement-check`

| | |
| --- | --- |
| **执行** | `gcw-implement-check`：检查 diff 边界、验证结果、风险，写入 implement-check 事件 payload |
| **观察** | `events/006-gcw-implement-check.json` 含 `gate.ok: true` |
| **状态** | `ready-for-review` |

## 步骤 8：`gcw-pr-publish`

| | |
| --- | --- |
| **执行** | `gcw-pr-publish`：幂等创建或更新 PR |
| **观察** | [PR #4](https://github.com/fzf-labs/gcw/pull/4) 创建，body 含 Issue 链接与 summary |
| **状态** | `reviewing` |

## 步骤 9：`gcw-pr-review`

| | |
| --- | --- |
| **执行** | `gcw-pr-review`（主要由 Action 执行）：触发 CI、静态检查、汇总 review |
| **观察** | PR checks 结果；`events/008-gcw-pr-review.json` |
| **状态** | `reviewing`、`changes-requested` 或 `blocked` |

自动检查通过后仍为 `reviewing`，继续等待人类 reviewer。

在 GitHub hosted workflow 中，这一步会先跑仓库单测和 evidence validation，再进入 review 记录与可选 AI review 汇总。

## Review 反馈闭环

Issue #3 在自动 review 后进入 `changes-requested`。[对应评论](https://github.com/fzf-labs/gcw/issues/3#issuecomment-4698106204) 片段：

```markdown
<!-- gcw-progress -->
GCW Status: changes-requested
...
- Feedback source: pr-review
Automatic review: CI `validate` failed. ...
```

| | |
| --- | --- |
| **含义** | CI 失败要求修改，但失败项（如 `CONTRIBUTING.md`）超出 Issue #3 范围 |
| **下一步** | 从 `changes-requested` 回到 `gcw-implement`，修复范围内问题后重走 `implement-check` → `pr-publish` → `pr-review` |
| **收尾** | PR #4 最终合并 → 平台侧 `review-complete` |

反馈修复与首次实现走同一条收尾链，区别仅在于起始状态为 `changes-requested`，且应保留 `feedback_source` 元数据。

## 本地复现（可选）

```bash
git fetch origin gcw/issue-3
git checkout gcw/issue-3
cat .gcw/issues/3/workflow.json
ls .gcw/issues/3/events/
```

对新 Issue（例如 [#5](https://github.com/fzf-labs/gcw/issues/5)）重复：`/gcw 5`。

## 深入阅读

- [GCW 工作流](workflow.md) — 完整步骤、状态与 Action 流水线
- [README](../README.md) — 项目概览与协作分工
