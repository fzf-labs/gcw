from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
GITLAB_CI = ROOT / ".gitlab-ci.yml"


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

    def test_gitlab_ci_provides_read_only_gcw_validation_parity(self) -> None:
        content = GITLAB_CI.read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s .agents/skills/gcw/tests", content)
        self.assertIn("python3 -m unittest discover -s .github/tests", content)
        self.assertIn("python3 -m py_compile", content)
        self.assertIn("validate_gcw_evidence.py state", content)
        self.assertIn("validate_gcw_evidence.py implementation-gate", content)
        self.assertIn("validate_gcw_evidence.py readiness-check", content)
        self.assertNotIn("git push", content)
        self.assertNotIn("gh pr create", content)
        self.assertNotIn("glab mr create", content)


if __name__ == "__main__":
    unittest.main()
