from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / ".agents/skills/gcw/scripts/validate_gcw_evidence.py"
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"


class ValidateGcwEvidenceTest(unittest.TestCase):
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
        self.assertTrue(data["ok"], data)
        return data

    def write_planning_files(self) -> None:
        for name in ("task_plan.md", "findings.md", "progress.md"):
            (self.issue_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    def init(self) -> None:
        self.run_manager(
            "init-workflow",
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
        )

    def prepare_to_spec_check(self) -> None:
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

    def implement_check_payload(self) -> dict:
        return {
            "gate": {
                "ok": True,
                "checks": [{"id": "diff_boundary", "ok": True}],
                "validation": [{"command": "pytest", "exit_code": 0, "result": "passed"}],
            },
            "review_request": {"title": "feat: example", "summary": "Adds example.", "issue_link": "Closes #42"},
            "risks": "Low.",
            "scope": "Example only.",
            "reviewer_notes": "Review transitions.",
            "self_review": {"recorded": True, "progress_section": "## Local Self-Review"},
            "spec_refs": {"task_plan_sha": "sha256:task", "findings_sha": "sha256:findings", "progress_sha": "sha256:progress"},
        }

    def prepare_to_implement_check(self) -> None:
        self.prepare_to_spec_check()
        self.run_manager("record-spec-check", "--issue-dir", str(self.issue_dir), "--result", "passed")
        self.run_manager("record-implement", "--issue-dir", str(self.issue_dir), "--work-summary", "Implemented.")
        payload_file = self.issue_dir / "implement-check-payload.json"
        payload_file.write_text(json.dumps(self.implement_check_payload()), encoding="utf-8")
        self.run_manager("record-implement-check", "--issue-dir", str(self.issue_dir), "--payload-file", str(payload_file))

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

    def test_workflow_accepts_current_projection(self) -> None:
        self.init()
        output = self.run_validate("workflow")
        self.assertTrue(output["ok"], output)

    def test_spec_check_requires_planning_files_and_links(self) -> None:
        self.prepare_to_spec_check()
        self.run_manager("record-spec-check", "--issue-dir", str(self.issue_dir), "--result", "passed")
        output = self.run_validate("spec-check")
        self.assertTrue(output["ok"], output)

    def test_implement_check_requires_event_payload(self) -> None:
        self.prepare_to_implement_check()
        output = self.run_validate("implement-check")
        self.assertTrue(output["ok"], output)

    def test_pr_publish_requires_review_request_url(self) -> None:
        self.prepare_to_implement_check()
        self.run_manager(
            "record-pr-publish",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
            "--body-hash",
            "sha256:body",
            "--target",
            "owner/repo#7",
        )
        output = self.run_validate("pr-publish")
        self.assertTrue(output["ok"], output)


if __name__ == "__main__":
    unittest.main()
