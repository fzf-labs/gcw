# 贡献指南

命名 workflow package、状态、证据文件、测试和文档时，请沿用 [CONTEXT.md](CONTEXT.md) 中定义的项目术语。

## 开发流程

1. 检查当前分支和工作树。
2. 新增或修改工作流行为前，先补充对应的行为测试。
3. 将确定性检查放在 `.agents/skills/gcw/scripts/`，方便本地 agent 和 hosted runner 共用。
4. 当术语、状态转换、runner 权限或验证方式变化时，同步更新 `docs/` 下的对应文档。
5. 运行 [docs/validation.md](docs/validation.md) 中的验证命令。

## 文档命名

文档名称应表达读者意图，而不是当前实现细节：

- `docs/overview.md`：项目整体。
- `docs/concepts.md`：GCW 核心概念。
- `docs/workflow.md`：状态流和步骤。
- `docs/evidence.md`：Issue 目录和 JSON 证据。
- `docs/hosted-runners.md`：GitHub Actions 和 GitLab CI 权限。
- `docs/validation.md`：本地和 CI 验证。
- `docs/roadmap.md`：阶段状态和未来工作。

如果新内容可以放进现有文档，不要再新增带项目专名的长篇设计文档。

## 提交信息

提交信息使用简短的祈使句，风格与现有历史一致，例如：

```text
Add hosted GCW apply workflow support
Split GitLab CI job definitions
```
