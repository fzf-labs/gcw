from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from readiness_lib import (  # noqa: E402
    evaluate_readiness,
    gate_to_question,
    parse_markdown_sections,
    validate_gate_against_rubric,
)


class ReadinessLibTest(unittest.TestCase):
    def test_parse_markdown_sections(self) -> None:
        body = (FIXTURES / "issue_ready.md").read_text(encoding="utf-8")
        sections = parse_markdown_sections(body)
        self.assertIn("What to build", sections)
        self.assertIn("Acceptance criteria", sections)
        self.assertTrue(sections["What to build"])

    def test_evaluate_ready_issue(self) -> None:
        body = (FIXTURES / "issue_ready.md").read_text(encoding="utf-8")
        gate = evaluate_readiness(body, profile="enhancement")
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["profile"], "enhancement")
        self.assertEqual(len(gate["checks"]), 4)
        self.assertEqual(gate["errors"], [])

    def test_evaluate_needs_info_issue(self) -> None:
        body = (FIXTURES / "issue_needs_info.md").read_text(encoding="utf-8")
        gate = evaluate_readiness(body, profile="enhancement")
        self.assertFalse(gate["ok"])
        self.assertTrue(any("has_acceptance_criteria" in error for error in gate["errors"]))
        self.assertTrue(any("body_not_placeholder" in error for error in gate["errors"]))

    def test_gate_to_question_lists_failures(self) -> None:
        body = (FIXTURES / "issue_needs_info.md").read_text(encoding="utf-8")
        gate = evaluate_readiness(body, profile="enhancement")
        question = gate_to_question(gate)
        self.assertIn("acceptance", question.casefold())

    def test_validate_gate_against_rubric_rejects_mismatch(self) -> None:
        gate = {
            "ok": True,
            "rubric_version": "prepare-readiness/v1",
            "profile": "enhancement",
            "checks": [{"id": "has_what_to_build", "ok": True, "source": "structural"}],
            "errors": [],
        }
        errors = validate_gate_against_rubric(gate)
        self.assertTrue(any("missing ids" in error for error in errors))


class EvaluateIssueReadinessCliTest(unittest.TestCase):
    def test_cli_writes_gate_file(self) -> None:
        script = SCRIPTS / "evaluate_issue_readiness.py"
        output = FIXTURES / "gate_output.json"
        if output.exists():
            output.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--profile",
                "enhancement",
                "--body-file",
                str(FIXTURES / "issue_ready.md"),
                "--output",
                str(output),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        gate = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(gate["ok"])
        output.unlink()


if __name__ == "__main__":
    unittest.main()
