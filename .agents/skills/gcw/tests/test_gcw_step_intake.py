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


class GcwStepIntakeTest(unittest.TestCase):
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

    def test_apply_mode_dispatches_triage_issue(self) -> None:
        self.init_issue_opened()

        result = self.run_step(
            "triage-issue",
            "--mode",
            "apply",
            "--runner-id",
            "cursor-session",
            "--issue-dir",
            str(self.issue_dir),
            "--priority",
            "P1",
            "--summary",
            "Core workflow broken.",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "issue-triaging")

    def test_check_mode_reports_triage_issue_step(self) -> None:
        self.init_issue_opened()
        apply_result = self.run_step(
            "triage-issue",
            "--mode",
            "apply",
            "--runner-id",
            "cursor-session",
            "--issue-dir",
            str(self.issue_dir),
            "--priority",
            "P1",
            "--summary",
            "Core workflow broken.",
        )
        self.assertEqual(apply_result.returncode, 0, apply_result.stderr)

        result = self.run_step(
            "triage-issue",
            "--mode",
            "check",
            "--issue-dir",
            str(self.issue_dir),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "triage-issue")
        self.assertTrue(output["ok"])


if __name__ == "__main__":
    unittest.main()
