from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
HOSTED_APPLY = ROOT / ".github/workflows/gcw-hosted-apply.yml"
ACTION_PIPELINES = ROOT / ".github/workflows/gcw-action-pipelines.yml"
GITLAB_CI = ROOT / ".gitlab-ci.yml"
GITLAB_VALIDATE = ROOT / ".gitlab/ci/gcw-validate.yml"
GITLAB_HOSTED_APPLY = ROOT / ".gitlab/ci/gcw-hosted-apply.yml"
GITLAB_ACTION_PIPELINES = ROOT / ".gitlab/ci/gcw-action-pipelines.yml"


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
        self.assertIn("local: .gitlab/ci/gcw-action-pipelines.yml", content)
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
        self.assertIn("handoff --mode apply", content)
        self.assertIn("--mode apply", content)
        self.assertIn("--runner-kind github-actions", content)
        self.assertIn("--runner-id \"$GITHUB_RUN_ID:$GITHUB_RUN_ATTEMPT:$GITHUB_JOB\"", content)
        self.assertIn("scope:", content)
        self.assertIn("reviewer_notes:", content)
        self.assertIn("INPUT_SCOPE", content)
        self.assertIn("INPUT_REVIEWER_NOTES", content)
        self.assertIn("--scope \"$INPUT_SCOPE\"", content)
        self.assertIn("--reviewer-notes \"$INPUT_REVIEWER_NOTES\"", content)
        self.assertIn("machine-review-start", content)
        self.assertIn("machine-review-result", content)
        self.assertIn("address-machine-feedback", content)
        self.assertIn("human-review-result", content)
        self.assertIn("address-human-feedback", content)
        self.assertIn("review-complete", content)
        self.assertIn("machine_review_result", content)
        self.assertIn("human_review_result", content)
        self.assertIn("review_complete_result", content)
        self.assertIn("render_gcw_hosted_artifacts.py progress-comment", content)
        self.assertIn("render_gcw_hosted_artifacts.py review-request", content)
        self.assertIn("gh api", content)
        self.assertIn("gh pr edit", content)
        self.assertIn('git add "$GCW_ISSUE_DIR"', content)
        self.assertNotIn("git push --force", content)

    def test_github_action_pipelines_workflow_is_manual_and_owner_gated(self) -> None:
        content = ACTION_PIPELINES.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertIn("contents: write", content)
        self.assertIn("issues: write", content)
        self.assertIn("pull-requests: write", content)
        self.assertIn("gcw_pipeline.py", content)
        self.assertIn("--claim-ownership", content)
        self.assertIn("--runner-kind github-actions", content)
        self.assertIn("--runner-id \"$GITHUB_RUN_ID:$GITHUB_RUN_ATTEMPT:$GITHUB_JOB\"", content)
        for pipeline in (
            "issue-intake",
            "issue-clarify",
            "planning",
            "machine-review",
            "machine-feedback-loop",
            "human-feedback-loop",
            "review-complete",
        ):
            self.assertIn(pipeline, content)
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
        self.assertIn("handoff --mode apply", content)
        self.assertIn("--mode apply", content)
        self.assertIn("--runner-kind gitlab-ci", content)
        self.assertIn("--runner-id \"${CI_PIPELINE_ID}:${CI_JOB_ID}\"", content)
        self.assertIn("GCW_SCOPE", content)
        self.assertIn("GCW_REVIEWER_NOTES", content)
        self.assertIn("--scope \"${GCW_SCOPE:-}\"", content)
        self.assertIn("--reviewer-notes \"${GCW_REVIEWER_NOTES:-}\"", content)
        self.assertIn("machine-review-start", content)
        self.assertIn("machine-review-result", content)
        self.assertIn("address-machine-feedback", content)
        self.assertIn("human-review-result", content)
        self.assertIn("address-human-feedback", content)
        self.assertIn("review-complete", content)
        self.assertIn("GCW_MACHINE_REVIEW_RESULT", content)
        self.assertIn("GCW_HUMAN_REVIEW_RESULT", content)
        self.assertIn("GCW_REVIEW_COMPLETE_RESULT", content)
        self.assertIn("render_gcw_hosted_artifacts.py progress-comment", content)
        self.assertIn("render_gcw_hosted_artifacts.py review-request", content)
        self.assertIn("curl --request PUT", content)
        self.assertIn("GCW_PROGRESS_NOTE_ID", content)
        self.assertIn("GCW_MERGE_REQUEST_IID", content)
        self.assertIn('git add "$GCW_ISSUE_DIR"', content)
        self.assertNotIn("git push --force", content)

    def test_gitlab_action_pipelines_job_is_manual_and_owner_gated(self) -> None:
        content = GITLAB_ACTION_PIPELINES.read_text(encoding="utf-8")
        self.assertIn("gcw:action-pipeline", content)
        self.assertIn("when: manual", content)
        self.assertIn("gcw_pipeline.py", content)
        self.assertIn("--claim-ownership", content)
        self.assertIn("--runner-kind gitlab-ci", content)
        self.assertIn("--runner-id \"${CI_PIPELINE_ID}:${CI_JOB_ID}\"", content)
        for pipeline in (
            "issue-intake",
            "issue-clarify",
            "planning",
            "machine-review",
            "machine-feedback-loop",
            "human-feedback-loop",
            "review-complete",
        ):
            self.assertIn(pipeline, content)
        self.assertIn("render_gcw_hosted_artifacts.py progress-comment", content)
        self.assertIn("render_gcw_hosted_artifacts.py review-request", content)
        self.assertIn("curl --request PUT", content)
        self.assertIn("GCW_PROGRESS_NOTE_ID", content)
        self.assertIn("GCW_MERGE_REQUEST_IID", content)
        self.assertIn('git add "$GCW_ISSUE_DIR"', content)
        self.assertNotIn("git push --force", content)


if __name__ == "__main__":
    unittest.main()
