from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
STEP = ROOT / ".agents/skills/gcw/scripts/gcw_step.py"
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_state.py"
COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class GcwStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def run_step(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(STEP), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_manager(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MANAGER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write_initial_state_and_planning_files(self) -> None:
        result = self.run_manager(
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
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text("# Progress\n", encoding="utf-8")

    def test_check_mode_dispatches_to_validator(self) -> None:
        result = self.run_step("state", "--mode", "check", "--issue-dir", str(COMPLETE_FIXTURE))

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "state")
        self.assertTrue(output["ok"])

    def test_check_mode_dispatches_remote_progress_verification(self) -> None:
        remote_file = self.issue_dir / "progress-comment.md"
        remote_file.write_text(
            "\n".join(
                [
                    "Planning files:",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_step(
            "remote-progress-comment",
            "--mode",
            "check",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(remote_file),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-progress-comment")
        self.assertTrue(output["ok"])

    def test_apply_mode_dispatches_to_state_manager(self) -> None:
        self.write_initial_state_and_planning_files()

        result = self.run_step(
            "implementation-gate",
            "--mode",
            "apply",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])
        self.assertEqual(output["state"]["state"], "ready-for-implementation")

    def test_apply_mode_rejects_non_owner_runner(self) -> None:
        self.write_initial_state_and_planning_files()

        result = self.run_step(
            "implementation-gate",
            "--mode",
            "apply",
            "--runner-kind",
            "github-actions",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertEqual(output["step"], "implementation-gate")
        self.assertIn("owner.kind local does not match runner github-actions", output["errors"])

    def test_unsupported_apply_mode_fails_closed(self) -> None:
        result = self.run_step("state", "--mode", "apply", "--issue-dir", str(COMPLETE_FIXTURE))

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("does not support apply mode", output["errors"][0])

    def test_apply_mode_dispatches_new_review_step_and_fails_closed(self) -> None:
        self.write_initial_state_and_planning_files()

        result = self.run_step(
            "review-complete",
            "--mode",
            "apply",
            "--issue-dir",
            str(self.issue_dir),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("review-complete requires approved state", output["errors"])


if __name__ == "__main__":
    unittest.main()
