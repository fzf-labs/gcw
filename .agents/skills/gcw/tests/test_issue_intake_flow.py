from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_state.py"


class GcwIssueIntakeFlowTest(unittest.TestCase):
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

    def init_issue_opened(self) -> None:
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
            "--state",
            "issue-opened",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_state_can_start_in_issue_opened(self) -> None:
        self.init_issue_opened()
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "issue-opened")
        self.assertEqual(state["last_completed_step"], "")
        self.assertEqual(state["next_allowed_steps"], ["triage-issue"])

    def test_record_triage_issue_moves_to_issue_triaging(self) -> None:
        self.init_issue_opened()

        result = self.run_manager(
            "record-triage-issue",
            "--issue-dir",
            str(self.issue_dir),
            "--priority",
            "P1",
            "--summary",
            "Core workflow broken.",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "issue-triaging")
        self.assertEqual(state["last_completed_step"], "triage-issue")
        self.assertEqual(state["next_allowed_steps"], ["discuss-issue", "mark-issue-actionable"])
        self.assertTrue(state["evidence"]["triage_recorded"])
        self.assertEqual(state["evidence"]["triage_priority"], "P1")
        self.assertEqual(state["evidence"]["triage_summary"], "Core workflow broken.")

    def reach_issue_triaging(self) -> None:
        self.init_issue_opened()
        result = self.run_manager(
            "record-triage-issue",
            "--issue-dir",
            str(self.issue_dir),
            "--priority",
            "P1",
            "--summary",
            "Core workflow broken.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_record_discuss_issue_moves_to_issue_clarifying(self) -> None:
        self.reach_issue_triaging()

        result = self.run_manager(
            "record-discuss-issue",
            "--issue-dir",
            str(self.issue_dir),
            "--question",
            "Which runner should own the first write?",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "issue-clarifying")
        self.assertEqual(state["last_completed_step"], "discuss-issue")
        self.assertEqual(state["next_allowed_steps"], ["discuss-issue", "mark-issue-actionable"])
        self.assertEqual(state["evidence"]["clarifying_question"], "Which runner should own the first write?")

    def reach_issue_clarifying(self) -> None:
        self.reach_issue_triaging()
        result = self.run_manager(
            "record-discuss-issue",
            "--issue-dir",
            str(self.issue_dir),
            "--question",
            "Which runner should own the first write?",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_record_mark_issue_actionable_moves_to_ready_for_planning(self) -> None:
        self.reach_issue_clarifying()

        result = self.run_manager(
            "record-mark-issue-actionable",
            "--issue-dir",
            str(self.issue_dir),
            "--issue-actionable",
            "true",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "ready-for-planning")
        self.assertEqual(state["last_completed_step"], "mark-issue-actionable")
        self.assertEqual(state["next_allowed_steps"], ["create-issue-worktree", "create-planning-files"])
        self.assertTrue(state["evidence"]["issue_actionable"])

    def test_record_mark_issue_actionable_requires_question_when_not_actionable(self) -> None:
        self.reach_issue_clarifying()

        result = self.run_manager(
            "record-mark-issue-actionable",
            "--issue-dir",
            str(self.issue_dir),
            "--issue-actionable",
            "false",
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("clarifying question is required when the issue is not actionable", output["errors"])
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "issue-clarifying")
        self.assertEqual(state["last_completed_step"], "discuss-issue")

    def reach_ready_for_planning(self) -> None:
        self.reach_issue_clarifying()
        result = self.run_manager(
            "record-mark-issue-actionable",
            "--issue-dir",
            str(self.issue_dir),
            "--issue-actionable",
            "true",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_record_create_issue_worktree_records_evidence(self) -> None:
        self.reach_ready_for_planning()

        result = self.run_manager(
            "record-create-issue-worktree",
            "--issue-dir",
            str(self.issue_dir),
            "--worktree-path",
            str(self.issue_dir.parent / "worktree"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "ready-for-planning")
        self.assertEqual(state["last_completed_step"], "create-issue-worktree")
        self.assertEqual(state["next_allowed_steps"], ["create-planning-files"])
        self.assertTrue(state["evidence"]["issue_worktree_created"])
        self.assertEqual(state["evidence"]["issue_worktree_path"], str(self.issue_dir.parent / "worktree"))

    def test_record_create_planning_files_moves_to_planning(self) -> None:
        self.reach_ready_for_planning()
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text("# Progress\n", encoding="utf-8")

        result = self.run_manager(
            "record-create-planning-files",
            "--issue-dir",
            str(self.issue_dir),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "planning")
        self.assertEqual(state["last_completed_step"], "create-planning-files")
        self.assertEqual(state["next_allowed_steps"], ["publish-planning"])
        self.assertTrue(state["evidence"]["planning_files_exist"])


if __name__ == "__main__":
    unittest.main()
