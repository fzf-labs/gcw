# Plan — Issue #21: GitLab CI Support For GCW Hosted Actions

## Goal

为 GCW hosted execution 增加 GitLab CI 支持，使 GitLab 项目可以像当前 GitHub Actions 路径一样配置、触发、校验和记录 GCW 托管步骤，同时保持现有 GitHub 行为不回退。

## Current Phase

Phase 1 — 规划完成，等待 `gcw-spec-check`

## Phases

### Phase 1 — 现状梳理与边界确认

- [x] 确认 Issue #21 已完成 intake、triage、clarify。
- [x] 确认分类为 `enhancement` / `area:workflow` / `priority:p2`。
- [x] 确认 readiness gate 已通过，当前状态为 `ready-for-planning`。
- [x] 将已知事实、约束和风险写入 `findings.md`。
- **Status:** complete

### Phase 2 — GitLab CI 模板设计

- [ ] 设计 GitLab CI 入口文件，例如 `.gitlab-ci.yml` 或可包含的 GCW CI 模板。
- [ ] 为已有 hosted GCW 步骤建立 GitLab job 映射，覆盖当前 GitHub Actions 中支持的 `gcw-*` 步骤。
- [ ] 保留 `gcw-issue-intake` 为人工或本地 agent 入口，不新增 hosted intake job。
- [ ] 明确 GitLab CI 变量、token 权限、分支策略和 artifact 传递方式。
- **Status:** pending

### Phase 3 — 平台适配与共享脚本

- [ ] 复用现有 GCW workflow event log、projection、progress comment 和 evidence validation 机制。
- [ ] 将 GitHub 专用操作抽象或分支处理为 GitLab 等价实现。
- [ ] 使用 `glab` 或 GitLab API 完成 issue comment、labels、branch push、MR publish 和远端证据读取。
- [ ] 保证 GitHub path 继续通过现有 tests 和 workflows。
- **Status:** pending

### Phase 4 — 测试覆盖

- [ ] 扩展 hosted workflow 测试，验证 GitLab CI 模板结构、必需 job、变量和脚本调用。
- [ ] 覆盖共享 hosted step 行为，确保 GitHub/GitLab 分支不会互相回退。
- [ ] 补充 GitLab metadata / remote evidence 的单元测试或 fixture。
- **Status:** pending

### Phase 5 — 文档同步

- [ ] 更新 `docs/hosted-agent.md`，说明 GitLab CI 配置、触发方式、必需变量和权限。
- [ ] 更新 `docs/workflow.md` 或 quickstart 中与 hosted Action 相关的 GitHub-only 表述。
- [ ] 更新相关 GCW skill 说明，明确 GitHub Actions 与 GitLab CI 均属于 hosted pipeline。
- **Status:** pending

## Acceptance Criteria

- [ ] 仓库模板包含 GitLab CI 配置，覆盖当前支持 hosted execution 的 GCW 步骤。
- [ ] GitLab CI jobs 遵守与 GitHub hosted path 等价的 executor label/run gate 和 workflow phase gate。
- [ ] GitLab 平台操作使用 `glab` 或 GitLab API，支持 issue comment、labels、branch push、MR publish 和 remote evidence verification。
- [ ] 现有 GitHub Actions 路径不回退，相关测试继续通过。
- [ ] 新增或扩展测试覆盖 GitLab CI template shape 和共享 hosted step 行为。
- [ ] 文档说明 GitLab CI 的配置、触发、权限和与 GitHub Actions 的差异。

## Out Of Scope

- 不实现 `gcw-issue-intake` 的 hosted CI 入口。
- 不引入新的 LLM provider 或替换现有 local agent 工作方式。
- 不改变 GCW event log / `workflow.json` 的核心状态模型。
- 不要求一次性支持 GitLab 之外的其他 CI 平台。

## Key Questions

1. GitLab CI 配置应作为根级 `.gitlab-ci.yml` 模板生成，还是作为可 include 的 `dist/templates/repo` 文件提供？
2. `glab` 在 CI runner 中的认证变量名和最小权限应如何文档化？
3. GitLab label、issue 和 MR metadata 与 GitHub Issue Type / Priority 的差异是否需要新的 adapter 契约？

## Decisions Made

- GitLab support 应作为与 GitHub hosted path 对等的纵向 slice，而不是只补文档。
- 继续复用 `.gcw/issues/<issue-id>/events/` 和 `workflow.json`，避免为 GitLab 增加第二套状态模型。
- 当前 issue 的实现阶段必须同时覆盖模板、平台适配、测试和文档，才能满足端到端可验证目标。

## Risks

- GitLab CI 权限模型和 token scope 与 GitHub Actions 不同，可能需要明确 project access token 或 CI job token 的边界。
- `glab` 命令输出和错误模型与 `gh` 不完全一致，脚本需要稳定 JSON 契约。
- GitHub Issue Type / Priority 是原生字段，而 GitLab 当前 GCW model 依赖 labels；测试需覆盖这种差异。
