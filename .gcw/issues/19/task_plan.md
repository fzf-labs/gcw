# Plan — Issue #19: npm global installer for GCW

## Goal

将 GCW 发布为 npm 包 `@fzf-labs/gcw`，让用户可以通过全局 `gcw` 命令在其他仓库初始化 GCW 所需的 repo-local assets。

目标使用方式：

```bash
npm install -g @fzf-labs/gcw
cd <target-repo>
gcw init
```

初始化后，目标仓库应包含 GCW skills、Python runtime，以及可选的 GitHub hosted workflow assets；现有 Python GCW 核心逻辑不在本 issue 中重写为 Node。

## Phases

### Phase 1 — npm CLI package foundation

- [x] 新增 npm package manifest，包名为 `@fzf-labs/gcw`，并通过 `bin` 暴露全局 `gcw` 命令。
- [x] 新增 Node shebang CLI 入口，支持 `--version`、`init`、`doctor`。
- [x] 新增 package build/pack 脚本，确保发布包只包含 CLI 与 template assets。

### Phase 2 — repo-local template installation

- [x] 构建发布模板目录，包含必需的 `.agents/skills/gcw*`、`.agents/skills/planning-with-files` 与 `.gcw/runtime`。
- [x] 实现 `gcw init`，默认复制必需 assets 到当前仓库。
- [x] 支持 `--target <path>`、`--dry-run`、`--force`，默认不覆盖已有文件。
- [x] 支持 `--with-github-actions` 复制 `.github/workflows/gcw-*.yml`、`.github/actions/gcw-*` 与 `.github/scripts/`。

### Phase 3 — environment checks

- [x] 实现 `gcw doctor`，检查当前目录是否是 Git repo、GCW assets 是否已初始化、`python3` 是否可用。
- [x] 在检测到 GitHub/GitLab 使用场景时提示 `gh` / `glab` 可用性。
- [x] 输出清晰的人类可读结果，并使用非零 exit code 表示硬失败。

### Phase 4 — tests and documentation

- [x] 添加 CLI 测试覆盖 `--version`、`init --dry-run`、临时目录真实初始化、默认跳过已有文件、`--force` 覆盖行为。
- [x] 添加 package content 检查，确保 npm tarball 包含 templates 且不包含 `.gcw/issues/`。
- [ ] 继续运行现有 GCW Python 测试，避免破坏 workflow scripts。
- [x] 更新 `README.md`、`CONTRIBUTING.md`、`docs/quickstart.md`，说明 npm 安装与 `gcw init` 用法。

## Acceptance Criteria

- [ ] `npm install -g @fzf-labs/gcw` 后可执行 `gcw --version`。
- [ ] `gcw init` 在目标仓库写入必需 GCW assets，且默认不覆盖已有文件。
- [ ] `gcw init --with-github-actions` 会额外安装 hosted workflow assets。
- [ ] `gcw doctor` 能报告 repo 初始化状态与关键依赖状态。
- [ ] CLI tests、package dry-run 检查、现有 Python workflow tests 通过。
- [ ] 文档说明 npm scope、安装方式、初始化方式、发布前检查与 npm scope 权限要求。

## Out of Scope

- 不实现完整 Node 版 GCW workflow runner。
- 不把所有 `gcw-*` step 变成 Node 子命令。
- 不自动发布 npm 包；本 issue 只准备可 pack/publish 的工程结构与文档。
- 不改动 `.gcw/issues/<id>/` 运行时状态格式。

## Implementation Notes

- 参考 Trellis 的分发模型：npm 包提供 `bin` CLI 与 templates，初始化时把 assets 落到目标仓库。
- GCW 运行时仍按 repo-shaped layout 执行：目标仓库中的 `.agents/skills/gcw/scripts/_bootstrap.py` 查找目标仓库的 `.gcw/runtime/`。
- 发布包应避免包含当前开发仓库的 issue 状态文件，只复制 runtime、skills、workflow templates 与 CLI 所需文件。
- 如果 npm organization `@fzf-labs` 尚未配置发布权限，先用 `npm pack` 和本地 tarball 安装验证。
