# 验证

GCW 尽量使用确定性验证。本地 agent、GitHub Actions 和 GitLab CI 应调用同一组脚本。

## 必需的本地检查

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

统一 runner 也提供同样的检查：

```bash
python3 .agents/skills/gcw/scripts/gcw_step.py state --mode check --issue-dir .gcw/issues/<issue-id>
python3 .agents/skills/gcw/scripts/gcw_step.py readiness-check --mode check --issue-dir .gcw/issues/<issue-id>
```

review 阶段的状态转换也可以通过同一 runner 做状态校验，例如 `machine-review-start`、`human-review-result` 和 `review-complete`。

## Remote Artifact Verification

使用平台客户端抓取 issue progress comment 文本或 review request body 文本，写入临时文件后运行：

```bash
python3 .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py progress-comment --issue-dir .gcw/issues/<issue-id> --remote-file /tmp/progress-comment.md
python3 .agents/skills/gcw/scripts/verify_gcw_remote_evidence.py review-request --issue-dir .gcw/issues/<issue-id> --remote-file /tmp/review-request.md
```

该检查会将托管平台上的文本与 `readiness_evidence.json` 比较，并报告缺失的 planning links、validation、issue link、progress comment URL 或 risks。

## CI

GitHub Actions 使用 `.github/workflows/ci.yml`。

GitLab CI 使用 `.gitlab-ci.yml` 作为入口，并 include：

```text
.gitlab/ci/gcw-validate.yml
.gitlab/ci/gcw-hosted-apply.yml
```
