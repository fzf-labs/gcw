# GCW Runtime

`.gcw/engine/runtime` 是 GCW 的 workflow core，负责描述和执行平台无关的业务规则。

这里可以包含：

- workflow contracts、状态机、phase transition 和 projection rebuild。
- event log 的读取、追加、校验和 hash。
- step runner、step handler、milestone payload 和本地 evidence 校验。
- progress comment、review request 等 artifact 的渲染契约。
- hosted phase gate、executor gate 和幂等策略中的纯规则部分。

这里不应该包含：

- 对 `.agents/` 目录的 import 或硬编码依赖。
- 对 `gh`、`glab`、`git` 的直接 `subprocess` 调用。
- GitHub Actions output、GitLab CI env file、runner 环境变量等 CI glue。

依赖方向：

```text
.gcw/engine/runtime -> Python 标准库
.gcw/engine/runtime -> .gcw/engine/platforms 的抽象类型（仅在确有 adapter seam 时）
```

调用方包括 `.gcw/engine/hosted` 和 `.agents/skills/gcw/scripts`。
