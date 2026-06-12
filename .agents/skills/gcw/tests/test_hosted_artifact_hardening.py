from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RENDER = ROOT / ".agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py"
VERIFY = ROOT / ".agents/skills/gcw/scripts/verify_gcw_remote_evidence.py"
COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class HostedArtifactHardeningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_render(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RENDER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_verify(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_merge_review_request_replaces_section_even_with_marker_text_in_manual_content(self) -> None:
        existing = Path(self.tmp.name) / "existing.md"
        rendered = Path(self.tmp.name) / "rendered.md"
        existing.write_text(
            "Manual intro with marker text <!-- gcw-review-request:end --> in the prose.\n\n"
            "<!-- gcw-review-request:start -->\n"
            "Old generated body.\n"
            "<!-- gcw-review-request:end -->\n\n"
            "Manual outro that should stay.\n",
            encoding="utf-8",
        )
        rendered.write_text(
            "<!-- gcw-review-request:start -->\n"
            "New generated body.\n"
            "<!-- gcw-review-request:end -->\n",
            encoding="utf-8",
        )

        result = self.run_render(
            "merge-review-request",
            "--existing-file",
            str(existing),
            "--rendered-file",
            str(rendered),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Manual intro with marker text <!-- gcw-review-request:end --> in the prose.", result.stdout)
        self.assertIn("New generated body.", result.stdout)
        self.assertNotIn("Old generated body.", result.stdout)
        self.assertIn("Manual outro that should stay.", result.stdout)

    def test_render_progress_comment_reports_malformed_json(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        issue_dir.mkdir(parents=True)
        (issue_dir / "state.json").write_text(
            """{
  "issue": 42,
  "platform": "github",
  "repository": "owner/repo",
  "state": "planned",
  "branch": "feat/example-42",
  "owner": {"kind": "local", "id": "cursor-session"},
  "last_completed_step": "gcw-issue-to-spec",
  "next_allowed_steps": ["gcw-spec-check"],
  "evidence": {
    "planning_files_exist": false,
    "planning_commit_pushed": false,
    "implement_check_passed": false,
    "progress_comment_url": "",
    "self_review_recorded": false,
    "spec_check_passed": false,
    "review_request_url": ""
  }
}
""",
            encoding="utf-8",
        )
        (issue_dir / "readiness_evidence.json").write_text("{not valid json", encoding="utf-8")

        result = self.run_render("progress-comment", "--issue-dir", str(issue_dir))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("readiness_evidence.json is not valid JSON", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_verify_review_request_reports_malformed_json(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/42-verify"
        issue_dir.mkdir(parents=True)
        for name in ("state.json", "task_plan.md", "findings.md", "progress.md", "implementation_gate_result.json"):
            source = COMPLETE_FIXTURE / name
            target = issue_dir / name
            if source.is_file():
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        (issue_dir / "readiness_evidence.json").write_text("{not valid json", encoding="utf-8")
        remote_file = Path(self.tmp.name) / "remote-review.md"
        remote_file.write_text("<!-- gcw-review-request:start -->\nGenerated body.\n<!-- gcw-review-request:end -->\n", encoding="utf-8")

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(issue_dir),
            "--remote-file",
            str(remote_file),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertTrue(
            any("readiness_evidence.json is not valid JSON" in error for error in output["errors"])
        )

    def test_verify_review_request_finds_generated_section_after_marker_text(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/42-verify-marker"
        issue_dir.mkdir(parents=True)
        for name in ("state.json", "task_plan.md", "findings.md", "progress.md", "implementation_gate_result.json", "readiness_evidence.json"):
            source = COMPLETE_FIXTURE / name
            target = issue_dir / name
            if source.is_file():
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        rendered = subprocess.run(
            [sys.executable, str(RENDER), "review-request", "--issue-dir", str(COMPLETE_FIXTURE)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        remote_file = Path(self.tmp.name) / "remote-review-marker.md"
        remote_file.write_text(
            "Manual intro mentioning <!-- gcw-review-request:end --> before the generated section.\n"
            f"{rendered}\n"
            "Manual outro after the generated section.\n",
            encoding="utf-8",
        )

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(issue_dir),
            "--remote-file",
            str(remote_file),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])


if __name__ == "__main__":
    unittest.main()
