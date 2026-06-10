# Git Collaboration Workflow

Git Collaboration Workflow（GCW）是一套面向人机协作开发的工作流包。它连接本地 Git 开发与 GitHub/GitLab 协作流程，让 coding agent 能围绕一个 GitHub/GitLab Issue 持续推进，直到创建 review request、通过机审并完成人类审查。

GCW 的核心价值是：统一术语、持久化规划信息、产出机器可读证据，并为 CI 上的托管执行环境（hosted runner）提供清晰的安全边界。

## 从这里开始

- 阅读 [CONTEXT.md](CONTEXT.md) 了解项目术语。
- 阅读 [docs/overview.md](docs/overview.md) 了解项目整体。
- 阅读 [docs/workflow.md](docs/workflow.md) 了解从 Issue 接入到人类审查结束的完整流程、状态和 Action 流水线边界。
- 阅读 [docs/evidence.md](docs/evidence.md) 了解 GCW 如何记录状态、实现前检查和审查准备证据，包括 `state.json`、implementation gate 和 readiness evidence。
- 使用 GitHub Actions 或 GitLab CI 执行写入操作前，先阅读 [docs/hosted-runners.md](docs/hosted-runners.md) 了解 apply 模式。
- 修改脚本、skill 或 CI 前，先阅读 [docs/validation.md](docs/validation.md)。

## 仓库结构

```text
.agents/skills/      coding agent 使用的 workflow packages
.github/workflows/   GitHub Actions workflows
.gitlab-ci.yml       GitLab CI 入口文件
.gitlab/ci/          GitLab CI job 定义
docs/                项目设计、操作说明、验证说明、路线图和 ADR
```

## 本地验证

提交或发布改动前运行：

```bash
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m unittest discover -s .agents/skills/gcw/tests
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m unittest discover -s .github/tests
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m py_compile .agents/skills/gcw/scripts/*.py
```

## 安全边界

GCW 的托管写操作受 ownership gate 保护，也就是先检查谁拥有当前分支的写入权。只有当 `state.json.owner.kind` 和 `state.json.owner.id` 都与 hosted runner 的 `--runner-kind` / `--runner-id` 匹配，或已经完成显式 handoff 后，hosted runner 才能执行状态转换。

Force-push、删除分支、合并、关闭 Issue、编辑他人创建的内容，都必须先获得明确的人类批准。
