# 贡献指南

命名 workflow packages、状态、证据文件、测试和文档时，使用 [CONTEXT.md](CONTEXT.md) 中的项目术语。

## 开发流程

1. 检查当前分支和工作树。
2. 修改工作流行为前，先新增或更新行为测试。
3. 将可确定性检查放在 `.agents/skills/gcw/scripts/`，方便本地 agent 和 hosted runner 复用。
4. 当术语、状态转换、runner 权限或验证方式变化时，同步更新 `docs/` 下的聚焦文档。
5. 运行 [docs/validation.md](docs/validation.md) 中的验证命令。

## 文档命名

使用稳定的读者意图命名：

- `docs/overview.md`：项目整体形态。
- `docs/concepts.md`：GCW 核心概念。
- `docs/workflow.md`：状态流和步骤。
- `docs/evidence.md`：Issue 目录和 JSON 证据。
- `docs/hosted-runners.md`：GitHub Actions 和 GitLab CI 权限。
- `docs/validation.md`：本地和 CI 验证。
- `docs/roadmap.md`：阶段状态和未来工作。

如果已有聚焦文档能承载内容，不要新增带项目专名的长篇设计文档。

## 提交信息

使用简短的祈使句，风格与现有历史一致，例如：

```text
Add hosted GCW apply workflow support
Split GitLab CI job definitions
```
