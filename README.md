# Git Collaboration Workflow

Git Collaboration Workflow（GCW）是一套面向 agent-assisted development 的工作流包。它用于协调本地 Git 开发和 GitHub/GitLab 上的协作流程，让 coding agent 能从 Issue 接入开始，一路推进到 Ready for Review。

GCW 提供统一术语、持久化规划文件、机器可读证据，以及 hosted runner 可执行的安全契约。

## 从这里开始

- 阅读 [CONTEXT.md](CONTEXT.md) 了解项目术语。
- 阅读 [docs/overview.md](docs/overview.md) 了解项目整体形态。
- 阅读 [docs/workflow.md](docs/workflow.md) 了解 review-ready loop。
- 阅读 [docs/evidence.md](docs/evidence.md) 了解 `state.json`、implementation gate 和 readiness evidence。
- 阅读 [docs/hosted-runners.md](docs/hosted-runners.md) 再使用 GitHub Actions 或 GitLab CI 的 apply 模式。
- 阅读 [docs/validation.md](docs/validation.md) 再修改脚本、skill 或 CI。

## 仓库结构

```text
.agents/skills/      coding agent 使用的 workflow packages
.github/workflows/   GitHub Actions workflows
.gitlab-ci.yml       GitLab CI 入口文件
.gitlab/ci/          GitLab CI job 定义
docs/                项目设计、操作、验证、路线图和 ADR
```

## 本地验证

提交或发布改动前运行：

```bash
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m unittest discover -s .agents/skills/gcw/tests
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m unittest discover -s .github/tests
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m py_compile .agents/skills/gcw/scripts/*.py
```

## 安全边界

GCW 将 hosted write operation 视为 ownership-gated。Hosted runner 只有在 `state.json.owner.kind` 与当前 runner 匹配时，或在完成显式 handoff 后，才可以 apply 状态转换。

Force-push、删除分支、合并、关闭 Issue、编辑他人创建的内容，都需要明确的人类批准。
