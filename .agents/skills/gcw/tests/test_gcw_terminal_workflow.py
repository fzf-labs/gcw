from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".gcw" / "engine" / "runtime"))

from gcw_terminal_workflow import human_handoff_reason, select_next_run_step, should_stop_for_human_handoff  # noqa: E402


class GcwTerminalWorkflowTest(unittest.TestCase):
    def test_human_handoff_states_stop_run_loop(self) -> None:
        for phase in ("planned", "issue-clarifying", "blocked", "reviewing", "review-complete"):
            self.assertTrue(should_stop_for_human_handoff(phase))
            self.assertNotEqual(human_handoff_reason(phase), "")

    def test_select_next_run_step_prefers_implement_check_when_implementing(self) -> None:
        projection = {"phase": "implementing", "next_allowed_steps": ["gcw-implement", "gcw-implement-check"]}
        self.assertEqual(select_next_run_step(projection, ["README.md"], "/tmp/.gcw/issues/42"), "gcw-implement-check")

    def test_select_next_run_step_waits_for_worktree_changes_before_implement(self) -> None:
        projection = {"phase": "ready-for-implementation", "next_allowed_steps": ["gcw-implement"]}
        self.assertIsNone(select_next_run_step(projection, [".gcw/issues/42/workflow.json"], ".gcw/issues/42"))


if __name__ == "__main__":
    unittest.main()
