# GCW Platform Adapters

`.gcw/engine/platforms` 集中 GitHub / GitLab 远端平台副作用。

这里可以包含：

- GitHub issue comment、label / metadata、PR 查询和更新。
- GitLab issue note、metadata、MR 查询和更新。
- remote evidence 读取和比对所需的远端 fetch 操作。
- dry-run / recording adapter 等测试或本地执行 adapter。

这里不应该包含：

- workflow phase transition。
- event log append / projection rebuild。
- hosted CI output 写入逻辑。

依赖方向：

```text
.gcw/engine/platforms -> .gcw/engine/runtime 的基础 contract / error 类型
```

`.gcw/engine/runtime` 的核心状态机不应该直接 shell out 到平台 CLI；需要远端副作用时通过这里的 adapter 完成。
