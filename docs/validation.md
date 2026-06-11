# 验证

GCW 尽量把验证收敛到同一组脚本。文件与 schema 契约见 [evidence.md](evidence.md)。

## 本地检查

```bash
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m unittest discover -s .agents/skills/gcw/tests
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m unittest discover -s .github/tests
PYTHONPYCACHEPREFIX=/tmp/gcw-pycache python3 -m py_compile .agents/skills/gcw/scripts/*.py
```

## Evidence Checks

```bash
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py state --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py implementation-gate --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py readiness-check --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/validate_gcw_evidence.py create-review-request --issue-dir .gcw/issues/<issue-id>
```

`readiness-check` 是 `create-review-request` 的前置检查。`create-review-request` validator 使用的是同一套 preflight contract，只是换成消费它的 step 名称。

统一 runner 也提供同样的检查：

```bash
python3 .agents/skills/gcw/scripts/gcw_step.py state --mode check --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/gcw_step.py readiness-check --mode check --issue-dir .gcw/issues/<issue-id>
```

review 阶段的状态转换也可以通过同一 runner 做状态校验，例如 `machine-review-start`、`human-review-result` 和 `review-complete`。

## Remote Artifact Verification

抓取平台上的 progress comment 或 review request body 后，再用：

```bash
python3 .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py progress-comment --issue-dir .gcw/issues/<issue-id> --remote-file /tmp/progress-comment.md
python3 .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py review-request --issue-dir .gcw/issues/<issue-id> --remote-file /tmp/review-request.md
```

该检查会把远程文本与 `readiness_evidence.json` 比较，报告缺失的 planning links、validation、issue link、progress comment URL 或 risks。

## CI

GitHub Actions 使用 `.github/workflows/ci.yml`。

GitLab CI 使用 `.gitlab-ci.yml` 作为入口，并 include：

```text
.gitlab/ci/gcw-validate.yml
.gitlab/ci/gcw-hosted-apply.yml
.gitlab/ci/gcw-action-pipelines.yml
```
