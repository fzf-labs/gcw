# 托管 Runner

托管 runner 让 GitHub Actions 或 GitLab CI 可以检查证据，并在明确拥有权限时应用 GCW 状态转换。这里的应用状态转换，就是把本地证据写回 GCW 状态文件或托管平台内容。

## 只读检查

这些 workflow 只做证据验证，不修改 repository、Issue 或 review request state：

```text
.github/workflows/ci.yml
.gitlab-ci.yml
.gitlab/ci/gcw-validate.yml
```

## Hosted Apply

这些入口需要手动触发，并受 ownership gate 保护。workflow 会先用 `record-handoff` 认领当前 run 的 ownership，然后 ownership gate 再检查当前 runner 是否拥有写入权，以及 runner 身份是否与 `state.json` 中记录的一致：

```text
.github/workflows/gcw-hosted-apply.yml
.gitlab/ci/gcw-hosted-apply.yml
```

Hosted apply 可以：

- 执行支持的 `gcw_step.py --mode apply` 状态转换。
- 根据本地 evidence 渲染 progress comment 和 review request body。
- 更新 issue progress comment 和 review request body。
- 提交变更后的 `.gcw/issues/<issue-id>/` evidence。
- 推送当前 Issue 分支。

Hosted apply 不可以：

- Force-push。
- 删除分支。
- Merge review request。
- Close issue。
- 未经显式 handoff 覆盖 ownership。
- 未经明确批准编辑他人内容。

## Ownership 规则

除非 `state.json.owner.kind` 和 `state.json.owner.id` 都与 runner 匹配，否则 hosted apply 必须 fail closed，也就是直接失败并拒绝写入：

- GitHub Actions 使用 `github-actions`。
- GitLab CI 使用 `gitlab-ci`。

Hosted runner 接管后续写入前，先使用 `record-handoff`：

```bash
python3 .agents/skills/gcw/scripts/manage_gcw_state.py record-handoff \
  --issue-dir .gcw/issues/<issue-id> \
  --owner-kind github-actions \
  --owner-id <runner-or-session-id> \
  --reason <handoff-reason>
```

## 远程产物更新

Hosted workflow 通过以下命令渲染 progress comment 和 review request body：

```bash
python3 .agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py progress-comment --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py review-request --issue-dir .gcw/issues/<issue-id>
```

Progress comment 渲染结果以 `<!-- gcw-progress -->` marker 开头，与 `issue-manage` 的 `gcw-progress-upsert` 定位规则保持一致，整条评论是生成内容，可以整体替换。

Review request 渲染结果包裹在 `<!-- gcw-review-request:start -->` 与 `<!-- gcw-review-request:end -->` marker 之间。更新已有 review request 前，hosted workflow 必须先抓取现有 body，再用 `merge-review-request` 合并，避免覆盖 marker 区域之外的人工内容：

```bash
python3 .agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py merge-review-request \
  --existing-file /tmp/existing-body.md \
  --rendered-file /tmp/rendered-body.md
```

合并规则：marker 区域内的生成内容被替换；marker 之外的人工内容原样保留；现有 body 没有 marker 时，生成内容追加到人工内容之后。

抓取托管平台上的文本后，使用 [validation.md](validation.md) 验证 remote artifacts。
