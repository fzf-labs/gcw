# GCW Hosted Entrypoints

`.gcw/engine/hosted` 放置 GitHub Actions / GitLab CI 调用的 hosted runner glue。

这里可以包含：

- 解析 GitHub Actions event payload、workflow dispatch inputs、GitLab CI variables。
- 准备 hosted agent handoff 文件。
- 写入 GitHub Actions output 或 GitLab CI env file。
- 调用 `.gcw/engine/runtime` 的 workflow core 和 `.gcw/engine/platforms` 的平台 adapter。
- 处理 hosted runner 的 git commit / push / review request 收尾动作。

这里不应该包含：

- workflow 状态机规则。
- event payload schema 的业务校验规则。
- step runner 的核心编排逻辑。

依赖方向：

```text
.gcw/engine/hosted -> .gcw/engine/runtime
.gcw/engine/hosted -> .gcw/engine/platforms
```

GitHub workflow 和 GitLab CI 只能直接调用这里的脚本，不直接调用 `.gcw/engine/runtime`。
