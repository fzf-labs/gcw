# GCW 工作流

GCW 的完整流程从一个已经存在的 Issue 开始，不是从写代码开始。Issue 可以由人直接在 GitHub/GitLab 平台创建，也可以由 agent 预先创建；GCW 主流程负责接入这个 Issue、分类、讨论清楚，并判断是否可以开发。进入 GCW 文件化阶段后，稳定事实会追加写入 Issue 分支中的 `.gcw/issues/<issue-id>/events/`；`workflow.json` 只是由事件日志通过 reducer 生成的投影缓存，删除后必须能重建。在文件化之前，状态可以由 Issue 评论、label 或 agent 上下文承载。之后才进入实现、review request、PR review、人审和审查结束。

GCW 由人、agent、Action 三方协作推进：

- **人**：在 GitHub/GitLab 上做判断和关键决策。
- **agent**：Codex、Cursor、Claude Code 等 AI 编码工具，承担需要判断和代码能力的工作；可跑在本地 IDE，也可在 Action 里运行。
- **Action**：GitHub Actions / GitLab CI 等托管流水线，跑在远端 runner 上，由平台事件触发。

本文把三个层次拆开说明：

- **步骤**：人、agent 或 Action 可以承载或执行的具体动作。
- **状态**：由 `events/` 事件日志通过 reducer 推导，并缓存到 `workflow.json` 的稳定阶段。
- **Action 流水线**：可以合并到同一个自动化入口中连续执行的步骤组。

## 主流程

```text
已有 Issue
  -> gcw-issue-intake
  -> gcw-issue-prepare
  -> gcw-issue-to-spec
  -> gcw-spec-check
  -> gcw-implement
  -> gcw-implement-check
  -> gcw-pr-publish
  -> gcw-pr-review
  -> 等待 GitHub/GitLab 上的人类审查和结束结果
```

spec files 不是直接上传到 Issue。它们会提交到 Issue 分支中的 `.gcw/issues/<issue-id>/`，推送到远程分支，然后通过 Issue 评论链接到这些文件。当前 spec files 包含 `task_plan.md`、`findings.md` 和 `progress.md`。

如果 `gcw-spec-check` 发现 Issue 仍不清楚，会回到 `issue-clarifying`；已生成的 spec files 作为草稿保留，澄清后重新执行 `gcw-issue-to-spec` 更新。

## 步骤拆解

下表的 `Action` 指上文约定的托管流水线；它既能直接执行机械步骤，也能在流水线内启动 agent。当 agent 跑在本地时，它与远端 Action 通过 repo / issue / PR 交接，而不是被 Action 直接驱动。`执行方` 表示承担判断、内容生成或平台操作的主体；`Action 角色` 表示该步骤是否需要托管流水线入口，以及流水线承担的自动化范围。`GitHub Action 文件` 表示目标 GitHub Actions workflow 文件名，期望和步骤名称一致。目标步骤统一使用 `gcw-` 前缀。

| 顺序 | 步骤 | GitHub Action 文件 | 目标 | 执行方 | Action 角色 | 完成后的状态 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `gcw-issue-intake` | 无 | 接入已经存在的 GitHub/GitLab Issue，记录 Issue URL、编号和初始上下文，并初始化 GCW 状态。 | 人 / agent | 不需要：Issue 接入由人或 agent 发起，不由托管流水线自动接入 | `issue-opened` | Issue 创建属于流程外前置动作，可以由人或 agent 完成 |
| 2 | `gcw-issue-prepare` | `gcw-issue-prepare.yml` | 分类 Issue、补充讨论并检查信息是否足以进入 spec 编写。 | 人 / agent / Action | 需要：收集上下文、运行 agent 分类和整理澄清问题、记录讨论和状态；不能替代关键业务判断 | `ready-for-planning` 或 `issue-clarifying` | 关键业务答案必须来自人类或可信来源，不能由 Action 猜测 |
| 3 | `gcw-issue-to-spec` | `gcw-issue-to-spec.yml` | 创建隔离 worktree，将 Issue 生成 spec files，提交并推送，然后在 Issue 评论中链接。 | agent / Action | 建议有：运行 agent 生成 spec，或接收本地 agent 产物并完成推送和 Issue 评论 | `planned` | spec files 包含 `task_plan.md`、`findings.md` 和 `progress.md` |
| 4 | `gcw-spec-check` | `gcw-spec-check.yml` | 检查 spec files 是否已生成并推送、Issue 评论是否已链接、内容是否足以进入实现。 | agent / Action | 应该有：作为进入实现前的远端 gate | `ready-for-implementation`、`issue-clarifying` 或 `blocked` | 这是实现前的 spec 硬门槛 |
| 5 | `gcw-implement` | `gcw-implement.yml` | 按计划修改代码、补测试、更新必要文档。 | agent / Action | 可以有：在 runner 内运行 agent，或记录本地 agent 通过 repo / issue / PR 的交接 | `implementing` | 表示实现阶段内的一次推进；实现是否足以进入 review 由 `gcw-implement-check` 判定。PR review 或人审反馈修复也回到这里 |
| 6 | `gcw-implement-check` | `gcw-implement-check.yml` | 创建 review request 前检查 diff、提交边界、风险、验证结果和 spec files，并追加用于 PR/MR 渲染的 `gcw-implement-check` 事件 payload。 | agent / Action | 应该有：作为创建或更新 review request 前的远端 gate | `ready-for-review` | 把实现自查和 review request 证据收敛成一个主步骤 |
| 7 | `gcw-pr-publish` | `gcw-pr-publish.yml` | 幂等地创建或更新 review request：PR/MR 不存在则创建并写入完整 summary、Issue link、验证结果和风险说明，已存在则推送更新。 | agent / Action | 建议有：承载 PR/MR 创建或更新、Issue link 和 summary 发布 | `reviewing` | 首次提交与反馈修改都走它 |
| 8 | `gcw-pr-review` | `gcw-pr-review.yml` | 触发 CI、静态检查、remote artifact verification、可选 AI review，并汇总 PR review 结果。 | Action | 必须有：承载 CI、静态检查、remote artifact verification 和 AI review 汇总 | `reviewing`、`changes-requested` 或 `blocked` | 只覆盖自动 PR review；自动检查通过后仍处于 `reviewing`，继续等待平台人审 |

人类审查和 `review-complete` 状态不作为本流程的步骤拆解项；它们发生在 GitHub 或 GitLab 上，由 reviewer、merge 策略或平台事件产生。

`gcw-block` 和 `gcw-clarify` 不是主步骤；它们是反馈循环动作。`gcw-block` 可以从任意非终态阶段切到 `blocked`，并在 metadata 中记录 `resume_state` / `resume_step`；阻塞解除后回到这个恢复点。`gcw-clarify` 可以从需要补充 Issue 信息的阶段切到 `issue-clarifying`。

首次提交与反馈修改都以 `gcw-implement` -> `gcw-implement-check` -> `gcw-pr-publish` -> `gcw-pr-review` 收尾；区别在于反馈修改从 `changes-requested` 回到 `implementing`，再重新走这条收尾链路。`gcw-pr-publish` 幂等：首次创建 review request、之后推送更新都走它。

当前 GitHub Actions 实现仍有聚合入口；目标上应拆成上表所列的 workflow 文件。`gcw-issue-intake` 没有对应 Action 文件。

## 状态拆解

| 状态 | 含义 | 允许的典型下一步 |
| --- | --- | --- |
| `issue-opened` | Issue 已被 GCW 接入，但还没有完成分类和可执行性判断。 | `gcw-issue-prepare` |
| `issue-clarifying` | Issue 信息不足或边界不清，需要通过评论继续讨论。 | `gcw-issue-prepare` |
| `ready-for-planning` | Issue 已经讨论清楚，可以开始从 Issue 生成 spec files。 | `gcw-issue-to-spec` |
| `planned` | spec files 已提交并推送，Issue 评论已经链接到远程文件。 | `gcw-spec-check` |
| `ready-for-implementation` | 实现前检查通过，可以开始开发。 | `gcw-implement` |
| `implementing` | agent 正在实现功能、修复问题、补测试，或处理 PR review / 人审反馈。 | `gcw-implement`、`gcw-implement-check`，也可通过反馈动作进入 `blocked` 或 `issue-clarifying` |
| `ready-for-review` | 分支已经通过实现自查，且最新 `gcw-implement-check` 事件 payload 完整，具备创建或更新 review request 的条件。 | `gcw-pr-publish`（幂等：首次创建，已有则更新） |
| `reviewing` | PR/MR 已创建或更新，正在经历自动检查或等待人类 reviewer 审查。 | `gcw-pr-review`；平台要求修改 -> `changes-requested`；平台审查结束 -> `review-complete` |
| `changes-requested` | PR review 或人类 reviewer 要求修改。通过 metadata 区分反馈来源。 | `gcw-implement` |
| `blocked` | 当前无法继续推进，例如缺权限、缺依赖、外部服务不可用或需要人类决策。 | 阻塞解除后按 metadata 中的 `resume_state` / `resume_step` 回到恢复点 |
| `review-complete` | 人类审查已经结束，结果已记录。这个状态可以代表已合并、已关闭、已接受不合并、拒绝，或明确终止。 | 无 |

`reviewing` 只说明 review request 已经进入审查过程。自动 PR review 通过后仍保持 `reviewing`，直到平台人审事件产生 `review-complete` 或 `changes-requested`。当进入 `changes-requested` 时，应通过 metadata 区分反馈来源，例如 `feedback_source: pr-review` 或 `feedback_source: human-review`。

## Action 流水线

主步骤是最小拆解单位；除 `gcw-issue-intake` 外，需要 Action 的主步骤对应一个同名 workflow 文件。Action 流水线把连续的主步骤合并到同一个自动化入口中编排执行：Action 负责触发、串联和记录，并在流水线内运行 agent（或与本地 agent 通过 repo / issue / PR 交接）；agent 指 Codex、Cursor、Claude Code 等工具，负责需要判断和代码能力的工作；人负责无法被自动化替代的关键决策。下表 Action 列描述流水线的托管流水线职责，和步骤表中的 `Action 角色` 保持一致；“运行 agent”指在流水线内启动 agent，若 agent 跑在本地，则替换为通过 repo / issue / PR 交接。产出状态列只列流水线的最终或停顿状态，不列中间状态。

| 流水线 | 包含主步骤 | 人 | agent | Action | 产出状态 |
| --- | --- | --- | --- | --- | --- |
| 接入与准备 | `gcw-issue-intake`、`gcw-issue-prepare` | 创建或确认 Issue，回答关键业务问题 | 接入、分类、起草讨论与检查 | 不执行 `gcw-issue-intake`；准备阶段负责收集上下文、运行 agent 分类和整理澄清问题、记录讨论和状态 | `ready-for-planning` 或 `issue-clarifying` |
| 规划 | `gcw-issue-to-spec`、`gcw-spec-check` | spec 信息不足时补充澄清 | 生成 spec files、自检内容 | 运行 agent 生成 spec、推送分支、校验硬门槛 | `ready-for-implementation`、`issue-clarifying` 或 `blocked` |
| 实现 | `gcw-implement`、`gcw-implement-check`、`gcw-pr-publish` | 必要时介入决策 | 写代码、补测试、自查、发 review request | 可运行 agent 实现或接收本地 agent 交接；必须承担检查 gate，并建议承担 PR/MR 发布 | `reviewing` |
| 审查 | `gcw-pr-review` | 根据自动检查结果继续平台人审；平台事件可要求修改或结束审查 | 按反馈修复时回到实现流水线 | 跑 CI、静态检查、AI review 并汇总结果 | 自动检查产出 `reviewing`、`changes-requested` 或 `blocked`；平台事件可产出 `review-complete` 或 `changes-requested` |

流水线只是编排粒度，不改变主步骤的状态语义；任意流水线遇到硬门槛或需要人类判断时都会停下，把控制权交回人，或进入 `issue-clarifying` / `blocked`。
