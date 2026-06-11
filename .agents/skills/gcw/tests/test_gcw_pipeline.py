from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PIPELINE = ROOT / ".agents/skills/gcw/scripts/gcw_pipeline.py"
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_state.py"
VALIDATOR = ROOT / ".agents/skills/gcw/scripts/validate_gcw_evidence.py"

DEFAULT_PROGRESS_URL = "https://github.com/owner/repo/issues/42#issuecomment-1"


class GcwPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def run_manager(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MANAGER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_pipeline(self, pipeline: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PIPELINE),
                pipeline,
                "--issue-dir",
                str(self.issue_dir),
                "--runner-id",
                "cursor-session",
                *args,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_validator(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), command, "--issue-dir", str(self.issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def state_now(self) -> dict:
        return json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))

    def init_state(self, state: str = "planning") -> None:
        self.assert_ok(
            self.run_manager(
                "init-state",
                "--issue-dir",
                str(self.issue_dir),
                "--issue",
                "42",
                "--platform",
                "github",
                "--repository",
                "owner/repo",
                "--branch",
                "feat/example-42",
                "--owner-kind",
                "local",
                "--owner-id",
                "cursor-session",
                "--state",
                state,
            )
        )

    def write_planning_files(self) -> None:
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text(
            "# Progress\n\n## Local Self-Review\n\nDiff reviewed.\nValidation performed.\n",
            encoding="utf-8",
        )

    def publish_planning(self) -> None:
        self.write_planning_files()
        self.assert_ok(
            self.run_manager(
                "record-publish-planning",
                "--issue-dir",
                str(self.issue_dir),
                "--progress-comment-url",
                DEFAULT_PROGRESS_URL,
                "--planning-commit-pushed",
                "true",
            )
        )

    def reach_ready_for_implementation(self) -> None:
        self.init_state()
        self.publish_planning()
        self.assert_ok(
            self.run_manager(
                "record-implementation-gate",
                "--issue-dir",
                str(self.issue_dir),
                "--progress-comment-url",
                DEFAULT_PROGRESS_URL,
            )
        )

    def reach_implementing_with_self_review(self) -> None:
        self.reach_ready_for_implementation()
        self.assert_ok(self.run_manager("record-implement", "--issue-dir", str(self.issue_dir)))
        self.assert_ok(
            self.run_manager(
                "record-local-self-review",
                "--issue-dir",
                str(self.issue_dir),
                "--progress-section",
                "## Local Self-Review",
            )
        )

    def reach_ready_for_review(self) -> None:
        self.reach_implementing_with_self_review()
        self.assert_ok(
            self.run_manager(
                "record-readiness-evidence",
                "--issue-dir",
                str(self.issue_dir),
                "--base-branch",
                "main",
                "--commit-range",
                "main...feat/example-42",
                "--title",
                "feat: add example",
                "--summary",
                "Adds the example capability.",
                "--issue-link",
                "Closes #42",
                "--validation-command",
                "python3 -m unittest",
                "--validation-result",
                "passed",
                "--risks",
                "Low risk.",
            )
        )
        self.assert_ok(
            self.run_manager(
                "record-review-request",
                "--issue-dir",
                str(self.issue_dir),
                "--review-request-url",
                "https://github.com/owner/repo/pull/7",
            )
        )

    def readiness_args(self) -> list[str]:
        return [
            "--progress-section",
            "## Local Self-Review",
            "--base-branch",
            "main",
            "--commit-range",
            "main...feat/example-42",
            "--title",
            "feat: add example",
            "--summary",
            "Adds the example capability.",
            "--issue-link",
            "Closes #42",
            "--validation-command",
            "python3 -m unittest",
            "--validation-result",
            "passed",
            "--risks",
            "Low risk.",
        ]

    def test_issue_intake_pipeline_marks_actionable_issue_ready_for_planning(self) -> None:
        self.init_state("issue-opened")

        result = self.run_pipeline(
            "issue-intake",
            "--priority",
            "P1",
            "--summary",
            "Core workflow is blocked.",
        )

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "ready-for-planning")
        self.assertEqual(state["last_completed_step"], "mark-issue-actionable")
        self.assertEqual(state["evidence"]["triage_priority"], "P1")
        self.assertEqual(state["evidence"]["triage_summary"], "Core workflow is blocked.")
        self.assertEqual(self.run_validator("state").returncode, 0)

    def test_issue_intake_pipeline_keeps_unclear_issue_in_clarification(self) -> None:
        self.init_state("issue-opened")

        result = self.run_pipeline(
            "issue-intake",
            "--priority",
            "P1",
            "--summary",
            "Needs product decision.",
            "--issue-actionable",
            "false",
            "--clarifying-question",
            "Which rollout behavior should this use?",
        )

        self.assertEqual(result.returncode, 2)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])
        self.assertTrue(output["paused"])
        state = self.state_now()
        self.assertEqual(state["state"], "issue-clarifying")
        self.assertEqual(state["evidence"]["clarifying_question"], "Which rollout behavior should this use?")
        self.assertEqual(self.run_validator("state").returncode, 0)

    def test_issue_clarify_pipeline_marks_answered_issue_ready_for_planning(self) -> None:
        self.init_state("issue-clarifying")

        result = self.run_pipeline("issue-clarify", "--issue-actionable", "true")

        self.assert_ok(result)
        self.assertEqual(self.state_now()["state"], "ready-for-planning")

    def test_issue_clarify_pipeline_keeps_unclear_issue_in_clarification_and_pauses(self) -> None:
        self.init_state("issue-clarifying")

        result = self.run_pipeline(
            "issue-clarify",
            "--issue-actionable",
            "false",
            "--clarifying-question",
            "Which rollout behavior should this use?",
        )

        self.assertEqual(result.returncode, 2)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])
        self.assertTrue(output["paused"])
        state = self.state_now()
        self.assertEqual(state["state"], "issue-clarifying")
        self.assertEqual(state["evidence"]["clarifying_question"], "Which rollout behavior should this use?")

    def test_planning_pipeline_records_worktree_planning_files_and_publish_evidence(self) -> None:
        self.init_state("ready-for-planning")
        self.write_planning_files()

        result = self.run_pipeline(
            "planning",
            "--worktree-path",
            "/tmp/gcw-worktrees/42",
            "--progress-comment-url",
            DEFAULT_PROGRESS_URL,
            "--planning-commit-pushed",
            "true",
        )

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "planned")
        self.assertEqual(state["last_completed_step"], "publish-planning")
        self.assertEqual(state["evidence"]["issue_worktree_path"], "/tmp/gcw-worktrees/42")
        self.assertTrue(state["evidence"]["planning_files_exist"])
        self.assertTrue(state["evidence"]["planning_commit_pushed"])

    def test_machine_review_pipeline_records_passing_review(self) -> None:
        self.reach_ready_for_review()

        result = self.run_pipeline("machine-review", "--machine-review-result", "passed")

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "human-reviewing")
        self.assertEqual(state["evidence"]["machine_review_result"], "passed")

    def test_machine_review_pipeline_records_failed_review_and_fails_job(self) -> None:
        self.reach_ready_for_review()

        result = self.run_pipeline("machine-review", "--machine-review-result", "failed")

        self.assertNotEqual(result.returncode, 0)
        state = self.state_now()
        self.assertEqual(state["state"], "machine-review-failed")
        self.assertEqual(state["evidence"]["machine_review_result"], "failed")
        self.assertIn("address-machine-feedback", state["next_allowed_steps"])

    def test_machine_feedback_loop_pipeline_regenerates_readiness_evidence(self) -> None:
        self.reach_ready_for_review()
        self.assert_ok(self.run_manager("record-machine-review-start", "--issue-dir", str(self.issue_dir)))
        self.assertNotEqual(
            self.run_manager(
                "record-machine-review-result",
                "--issue-dir",
                str(self.issue_dir),
                "--result",
                "failed",
            ).returncode,
            0,
        )

        result = self.run_pipeline("machine-feedback-loop", *self.readiness_args())

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "ready-for-review-request")
        self.assertEqual(state["last_completed_step"], "readiness-check")
        self.assertTrue((self.issue_dir / "readiness_evidence.json").is_file())

    def test_human_feedback_loop_pipeline_regenerates_readiness_evidence(self) -> None:
        self.reach_ready_for_review()
        self.assert_ok(self.run_manager("record-machine-review-start", "--issue-dir", str(self.issue_dir)))
        self.assert_ok(
            self.run_manager(
                "record-machine-review-result",
                "--issue-dir",
                str(self.issue_dir),
                "--result",
                "passed",
            )
        )
        self.assert_ok(
            self.run_manager(
                "record-human-review-result",
                "--issue-dir",
                str(self.issue_dir),
                "--result",
                "changes-requested",
            )
        )

        result = self.run_pipeline("human-feedback-loop", *self.readiness_args())

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "ready-for-review-request")
        self.assertEqual(state["last_completed_step"], "readiness-check")
        self.assertTrue((self.issue_dir / "readiness_evidence.json").is_file())

    def test_review_complete_pipeline_records_completion_result(self) -> None:
        self.reach_ready_for_review()
        self.assert_ok(self.run_manager("record-machine-review-start", "--issue-dir", str(self.issue_dir)))
        self.assert_ok(
            self.run_manager(
                "record-machine-review-result",
                "--issue-dir",
                str(self.issue_dir),
                "--result",
                "passed",
            )
        )
        self.assert_ok(
            self.run_manager(
                "record-human-review-result",
                "--issue-dir",
                str(self.issue_dir),
                "--result",
                "approved",
            )
        )

        result = self.run_pipeline("review-complete", "--review-complete-result", "accepted")

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "review-complete")
        self.assertEqual(state["evidence"]["review_complete_result"], "accepted")
        self.assertEqual(state["next_allowed_steps"], [])

    def test_claim_ownership_allows_hosted_pipeline_to_run(self) -> None:
        self.init_state("issue-opened")

        result = self.run_pipeline(
            "issue-intake",
            "--runner-kind",
            "github-actions",
            "--runner-id",
            "run-123:1:action-pipeline",
            "--claim-ownership",
            "--priority",
            "P1",
            "--summary",
            "Core workflow is blocked.",
        )

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["owner"], {"kind": "github-actions", "id": "run-123:1:action-pipeline"})
        self.assertEqual(state["state"], "ready-for-planning")


if __name__ == "__main__":
    unittest.main()
