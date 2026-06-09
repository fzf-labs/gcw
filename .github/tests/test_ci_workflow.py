from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
HOSTED_APPLY = ROOT / ".github/workflows/gcw-hosted-apply.yml"
GITLAB_CI = ROOT / ".gitlab-ci.yml"
GITLAB_VALIDATE = ROOT / ".gitlab/ci/gcw-validate.yml"
GITLAB_HOSTED_APPLY = ROOT / ".gitlab/ci/gcw-hosted-apply.yml"


class CiWorkflowTest(unittest.TestCase):
    def test_ci_skips_draft_pull_requests(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", content)
        self.assertIn("ready_for_review", content)
        self.assertIn("github.event.pull_request.draft == false", content)

    def test_ci_runs_gcw_and_repository_tests(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s .agents/skills/gcw/tests", content)
        self.assertIn("python3 -m unittest discover -s .github/tests", content)
        self.assertIn("actions/checkout@v6", content)
        self.assertNotIn("actions/checkout@v4", content)

    def test_ci_validates_gcw_evidence_when_present(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("validate_gcw_evidence.py state", content)
        self.assertIn("validate_gcw_evidence.py implementation-gate", content)
        self.assertIn("validate_gcw_evidence.py readiness-check", content)

    def test_ci_validates_gcw_schema_files(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Validate GCW schemas", content)
        self.assertIn(".agents/skills/gcw/schemas", content)
        self.assertIn("*.schema.json", content)

    def test_gitlab_ci_entrypoint_includes_split_job_files(self) -> None:
        content = GITLAB_CI.read_text(encoding="utf-8")
        self.assertIn("stages:", content)
        self.assertIn("- validate", content)
        self.assertIn("- apply", content)
        self.assertIn("include:", content)
        self.assertIn("local: .gitlab/ci/gcw-validate.yml", content)
        self.assertIn("local: .gitlab/ci/gcw-hosted-apply.yml", content)
        self.assertNotIn("gcw:validate:", content)
        self.assertNotIn("gcw:hosted-apply:", content)

    def test_gitlab_ci_provides_read_only_gcw_validation_parity(self) -> None:
        validate_job = GITLAB_VALIDATE.read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s .agents/skills/gcw/tests", validate_job)
        self.assertIn("python3 -m unittest discover -s .github/tests", validate_job)
        self.assertIn("python3 -m py_compile", validate_job)
        self.assertIn("validate_gcw_evidence.py state", validate_job)
        self.assertIn("validate_gcw_evidence.py implementation-gate", validate_job)
        self.assertIn("validate_gcw_evidence.py readiness-check", validate_job)
        self.assertNotIn("git push", validate_job)
        self.assertNotIn("gh pr create", validate_job)
        self.assertNotIn("glab mr create", validate_job)

    def test_github_hosted_apply_workflow_is_manual_and_owner_gated(self) -> None:
        content = HOSTED_APPLY.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("contents: write", content)
        self.assertIn("issues: write", content)
        self.assertIn("pull-requests: write", content)
        self.assertIn("gcw_step.py", content)
        self.assertIn("--mode apply", content)
        self.assertIn("--runner-kind github-actions", content)
        self.assertIn("render_gcw_hosted_artifacts.py progress-comment", content)
        self.assertIn("render_gcw_hosted_artifacts.py review-request", content)
        self.assertIn("gh api", content)
        self.assertIn("gh pr edit", content)
        self.assertIn('git add "$GCW_ISSUE_DIR"', content)
        self.assertNotIn("git push --force", content)

    def test_gitlab_hosted_apply_job_is_manual_and_owner_gated(self) -> None:
        content = GITLAB_HOSTED_APPLY.read_text(encoding="utf-8")
        self.assertIn("gcw:hosted-apply", content)
        self.assertIn("when: manual", content)
        self.assertIn("gcw_step.py", content)
        self.assertIn("--mode apply", content)
        self.assertIn("--runner-kind gitlab-ci", content)
        self.assertIn("render_gcw_hosted_artifacts.py progress-comment", content)
        self.assertIn("render_gcw_hosted_artifacts.py review-request", content)
        self.assertIn("curl --request PUT", content)
        self.assertIn("GCW_PROGRESS_NOTE_ID", content)
        self.assertIn("GCW_MERGE_REQUEST_IID", content)
        self.assertIn('git add "$GCW_ISSUE_DIR"', content)
        self.assertNotIn("git push --force", content)


if __name__ == "__main__":
    unittest.main()
