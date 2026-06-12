from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / ".agents/skills/gcw/scripts/validate_gcw_evidence.py"


class ValidateGcwEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def write_state(self, **overrides: object) -> dict:
        state = {
            "issue": 42,
            "platform": "github",
            "repository": "owner/repo",
            "state": "planned",
            "branch": "gcw/issue-42",
            "owner": {"kind": "local", "id": "cursor-session"},
            "last_completed_step": "gcw-issue-to-spec",
            "next_allowed_steps": ["gcw-spec-check"],
            "evidence": {
                "planning_files_exist": True,
                "planning_commit_pushed": True,
                "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
                "spec_check_passed": False,
                "implement_check_passed": False,
                "self_review_recorded": False,
                "review_request_url": "",
            },
            "metadata": {},
        }
        state.update(overrides)
        (self.issue_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        return state

    def write_planning_files(self) -> None:
        for name in ("task_plan.md", "findings.md", "progress.md"):
            (self.issue_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    def write_readiness(self) -> None:
        readiness = {
            "issue": 42,
            "branch": "gcw/issue-42",
            "base_branch": "main",
            "commit_range": "main...gcw/issue-42",
            "review_request": {
                "title": "feat: example",
                "summary": "Adds example.",
                "issue_link": "Closes #42",
            },
            "validation": [{"command": "pytest", "result": "passed"}],
            "local_self_review": {"recorded": True, "progress_section": "## Local Self-Review"},
            "planning_links": {
                "task_plan": "https://github.com/owner/repo/blob/gcw/issue-42/.gcw/issues/42/task_plan.md",
                "findings": "https://github.com/owner/repo/blob/gcw/issue-42/.gcw/issues/42/findings.md",
                "progress": "https://github.com/owner/repo/blob/gcw/issue-42/.gcw/issues/42/progress.md",
            },
            "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
            "risks": "Low.",
        }
        (self.issue_dir / "readiness_evidence.json").write_text(json.dumps(readiness, indent=2), encoding="utf-8")

    def run_validate(self, command: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), command, "--issue-dir", str(self.issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def test_state_accepts_current_contract(self) -> None:
        self.write_state()
        output = self.run_validate("state")
        self.assertTrue(output["ok"], output)

    def test_spec_check_requires_planning_files_and_links(self) -> None:
        self.write_state()
        self.write_planning_files()
        output = self.run_validate("spec-check")
        self.assertTrue(output["ok"], output)

    def test_implement_check_requires_readiness_evidence(self) -> None:
        state = self.write_state(
            state="ready-for-review",
            last_completed_step="gcw-implement-check",
            next_allowed_steps=["gcw-pr-publish"],
        )
        state["evidence"]["implement_check_passed"] = True
        state["evidence"]["self_review_recorded"] = True
        (self.issue_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        self.write_readiness()
        output = self.run_validate("implement-check")
        self.assertTrue(output["ok"], output)

    def test_pr_publish_requires_review_request_url(self) -> None:
        state = self.write_state(
            state="reviewing",
            last_completed_step="gcw-pr-publish",
            next_allowed_steps=["gcw-pr-review"],
        )
        state["evidence"]["review_request_url"] = "https://github.com/owner/repo/pull/7"
        (self.issue_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        output = self.run_validate("pr-publish")
        self.assertTrue(output["ok"], output)


if __name__ == "__main__":
    unittest.main()
