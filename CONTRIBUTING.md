# 贡献指南

命名 workflow package、状态、证据文件、测试和文档时，请沿用 [CONTEXT.md](CONTEXT.md) 中定义的项目术语。

## 开发流程

1. 检查当前分支和工作树。
2. 新增或修改工作流行为前，先补充对应的行为测试。
3. 将确定性检查放在 `.agents/skills/gcw/scripts/`，方便本地 agent 和 hosted runner 共用。
4. 当术语、状态转换、runner 权限或验证方式变化时，同步更新主文档。
5. 运行 [docs/validation.md](docs/validation.md) 中的验证命令。

## 文档约定

优先维护这几份主文档：

- `CONTEXT.md`：术语与边界。
- `docs/workflow.md`：状态流、步骤和 Action 流水线。
- `docs/evidence.md`：证据文件与 schema。
- `docs/hosted-runners.md`：托管写入边界。
- `docs/validation.md`：本地和 CI 验证。

如果新内容可以放进现有主文档，就不要再新增带项目专名的长篇设计文档。

## 提交信息

提交信息使用简短的祈使句，风格与现有历史一致，例如：

```text
Add hosted GCW apply workflow support
Split GitLab CI job definitions
```
