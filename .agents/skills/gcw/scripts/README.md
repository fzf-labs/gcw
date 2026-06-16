# GCW Skill Script Entrypoints

`.agents/skills/gcw/scripts` 是 GCW skill 暴露给本地 agent 或托管 workflow 的 CLI 壳层。

这里可以包含：

- `argparse` 参数解析。
- JSON stdout / stderr 输出格式。
- 对 `.gcw/engine/runtime` workflow core 的调用。
- 对 `.gcw/engine/platforms` adapter 的选择。

这里不应该包含：

- workflow 状态机核心规则。
- step handler 的深业务逻辑。
- GitHub / GitLab 平台副作用的具体实现。
- 可被 runtime 复用的 artifact 渲染、evidence 校验或 event store 逻辑。

依赖方向：

```text
.agents/skills/gcw/scripts -> .gcw/engine/runtime
.agents/skills/gcw/scripts -> .gcw/engine/platforms
```

这里的脚本应尽量薄：解析参数、调用核心模块、返回结构化结果。
