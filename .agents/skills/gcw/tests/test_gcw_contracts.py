from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))

from gcw_workflow_contracts import (  # noqa: E402
    HOSTED_STEP_PHASES,
    MAIN_STEP_ORDER,
    NEXT_ALLOWED_STEPS,
    PLANNING_FILES,
    REPEATABLE_WHILE_PHASE,
    STATES,
    STEP_TRIGGER_LABELS,
    VALIDATE_COMMANDS,
    VALID_EVENT_NAMES,
)


class GcwWorkflowContractsTest(unittest.TestCase):
    def test_main_step_order_is_canonical(self) -> None:
        self.assertEqual(
            MAIN_STEP_ORDER,
            (
                "gcw-issue-intake",
                "gcw-issue-triage",
                "gcw-issue-clarify",
                "gcw-issue-to-spec",
                "gcw-spec-check",
                "gcw-implement",
                "gcw-implement-check",
                "gcw-pr-publish",
                "gcw-pr-review",
            ),
        )

    def test_hosted_step_contracts_cover_the_main_flow(self) -> None:
        for step in ("gcw-issue-triage", "gcw-issue-clarify", "gcw-issue-to-spec", "gcw-spec-check", "gcw-implement", "gcw-implement-check", "gcw-pr-publish", "gcw-pr-review"):
            self.assertIn(step, HOSTED_STEP_PHASES)
            self.assertIn(step, STEP_TRIGGER_LABELS)

    def test_phase_and_step_tables_stay_aligned(self) -> None:
        self.assertEqual(NEXT_ALLOWED_STEPS["issue-opened"], ["gcw-issue-triage"])
        self.assertEqual(NEXT_ALLOWED_STEPS["reviewing"], ["gcw-pr-review"])
        self.assertEqual(REPEATABLE_WHILE_PHASE["gcw-implement"], ("implementing", "changes-requested", "ready-for-implementation"))
        self.assertEqual(VALIDATE_COMMANDS["gcw-pr-review"], "review-check")

    def test_domain_constants_remain_available(self) -> None:
        self.assertIn("blocked", STATES)
        self.assertIn("review-complete", STATES)
        self.assertIn("review-complete", VALID_EVENT_NAMES)
        self.assertEqual(PLANNING_FILES, ("task_plan.md", "findings.md", "progress.md"))


if __name__ == "__main__":
    unittest.main()
