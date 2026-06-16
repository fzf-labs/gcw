<!-- gcw-review-request:start -->
Add GitLab CI support for hosted GCW

## Summary

Adds a GitLab CI template, CLI install flag, hosted-step label handling, implement milestone handoff support, tests, and documentation.

## Issue

Closes #21

## Validation

- npm test: passed
- python3 -m unittest discover -s .agents/skills/gcw/tests: passed
- python .agents/skills/gcw/scripts/validate_gcw_evidence.py workflow --issue-dir .gcw/issues/21: passed

## Scope

GitLab CI hosted GCW template, CLI packaging/install path, hosted script support, tests, documentation, and Issue #21 GCW artifacts.

## Planning

- Task plan: https://github.com/fzf-labs/gcw/blob/gcw/issue-21/.gcw/issues/21/task_plan.md
- Findings: https://github.com/fzf-labs/gcw/blob/gcw/issue-21/.gcw/issues/21/findings.md
- Progress: https://github.com/fzf-labs/gcw/blob/gcw/issue-21/.gcw/issues/21/progress.md

## Progress Comment

https://github.com/fzf-labs/gcw/issues/21#issuecomment-4719839183

## Risks

GitLab CI template is covered by static/unit tests but has not been executed in a live GitLab project in this pass.

## Reviewer Notes

Review .gitlab-ci.yml token/branch assumptions and the GitLab v1 local-agent handoff model.

<!-- gcw-review-request:end -->
