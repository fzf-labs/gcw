# 托管 Runner

托管 runner 分两类：只读验证和受 ownership gate 保护的写入。

## 只读检查

这些 workflow 只做证据验证，不修改 repository、Issue 或 review request state：

```text
.github/workflows/ci.yml
.gitlab-ci.yml
.gitlab/ci/gcw-validate.yml
```

## Hosted Apply

这些入口需要手动触发，并先通过 `record-handoff` 认领 ownership。随后 ownership gate 再检查 `state.json.owner.kind` / `state.json.owner.id` 是否与 runner 身份一致：

```text
.github/workflows/gcw-hosted-apply.yml
.gitlab/ci/gcw-hosted-apply.yml
```

Hosted apply 可以：

- 执行支持的 `gcw_step.py --mode apply` 状态转换。
- 渲染 progress comment 和 review request body。
- 更新 issue progress comment 和 review request body。
- 提交 `.gcw/issues/<issue-id>/` evidence。
- 推送当前 Issue 分支。

Hosted apply 不可以：

- Force-push。
- 删除分支。
- Merge review request。
- Close issue。
- 未经显式 handoff 覆盖 ownership。

## Action Pipelines

这些入口把多个已支持的 `gcw_step.py --mode apply` 步骤串起来：

```text
.github/workflows/gcw-action-pipelines.yml
.gitlab/ci/gcw-action-pipelines.yml
```

当前支持的 pipeline：

- `issue-intake`
- `issue-clarify`
- `planning`
- `machine-review`
- `machine-feedback-loop`
- `human-feedback-loop`
- `review-complete`

Action pipeline 仍然不能 force-push、merge review request、close issue、删除分支，或在没有明确授权时修改托管平台对象。

## Ownership 规则

除非 `state.json.owner.kind` 和 `state.json.owner.id` 都与 runner 匹配，否则 hosted apply 必须 fail closed。GitHub Actions 使用 `github-actions`，GitLab CI 使用 `gitlab-ci`。

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

远程文本抓取后，使用 [validation.md](validation.md) 验证 remote artifacts。
