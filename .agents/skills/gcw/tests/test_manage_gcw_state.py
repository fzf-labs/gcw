from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_state.py"


class ManageGcwStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def run_manager(self, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(MANAGER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.stderr, "")
        data = json.loads(result.stdout)
        if not data["ok"]:
            self.fail(f"command failed: {data}")
        return data

    def state(self) -> dict:
        return json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))

    def init(self, state: str = "issue-opened") -> None:
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
            "gcw/issue-42",
            "--owner-kind",
            "local",
            "--owner-id",
            "cursor-session",
            "--state",
            state,
        )

    def write_planning_files(self) -> None:
        for name in ("task_plan.md", "findings.md", "progress.md"):
            (self.issue_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    def test_main_path_reaches_reviewing(self) -> None:
        self.init()
        self.run_manager("record-issue-prepare", "--issue-dir", str(self.issue_dir), "--ready")
        self.write_planning_files()
        self.run_manager(
            "record-issue-to-spec",
            "--issue-dir",
            str(self.issue_dir),
            "--planning-commit-pushed",
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )
        self.run_manager("record-spec-check", "--issue-dir", str(self.issue_dir), "--result", "passed")
        self.run_manager("record-implement", "--issue-dir", str(self.issue_dir))
        self.run_manager("record-implement-check", "--issue-dir", str(self.issue_dir), "--passed")
        self.run_manager(
            "record-pr-publish",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
        )

        state = self.state()
        self.assertEqual(state["state"], "reviewing")
        self.assertEqual(state["last_completed_step"], "gcw-pr-publish")
        self.assertEqual(state["next_allowed_steps"], ["gcw-pr-review"])

    def test_changes_requested_preserves_feedback_source(self) -> None:
        self.init("reviewing")
        self.run_manager(
            "record-pr-review",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            "changes-requested",
            "--feedback-source",
            "human-review",
        )
        state = self.state()
        self.assertEqual(state["state"], "changes-requested")
        self.assertEqual(state["metadata"]["feedback_source"], "human-review")
        self.assertEqual(state["next_allowed_steps"], ["gcw-implement"])

    def test_block_records_resume_point(self) -> None:
        self.init("implementing")
        self.run_manager(
            "record-block",
            "--issue-dir",
            str(self.issue_dir),
            "--reason",
            "dependency unavailable",
        )
        state = self.state()
        self.assertEqual(state["state"], "blocked")
        self.assertEqual(state["metadata"]["resume_state"], "implementing")
        self.assertEqual(state["metadata"]["resume_step"], "gcw-implement")


if __name__ == "__main__":
    unittest.main()
