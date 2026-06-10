from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VERIFY = ROOT / ".agents/skills/gcw/scripts/verify_gcw_remote_evidence.py"
RENDER = ROOT / ".agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py"
COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class VerifyGcwRemoteEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)

    def run_verify(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def render_artifact(self, command: str, issue_dir: Path) -> str:
        result = subprocess.run(
            [sys.executable, str(RENDER), command, "--issue-dir", str(issue_dir)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout

    def test_progress_comment_verification_accepts_rendered_body(self) -> None:
        comment_path = self.tmp_path / "progress-comment.md"
        comment_path.write_text(self.render_artifact("progress-comment", COMPLETE_FIXTURE), encoding="utf-8")

        result = self.run_verify(
            "progress-comment",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(comment_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-progress-comment")
        self.assertTrue(output["ok"])

    def test_progress_comment_verification_rejects_mismatched_body(self) -> None:
        comment_path = self.tmp_path / "progress-comment.md"
        comment_path.write_text(
            "\n".join(
                [
                    "<!-- gcw-progress -->",
                    "GCW Status: ready-for-review",
                    "",
                    "- Issue: 42",
                    "- Branch: feat/example-42",
                    "- Owner: local/cursor-session",
                    "- Last completed step: readiness-check",
                    "- Review request: https://github.com/owner/repo/pull/7",
                    "",
                    "Planning files:",
                    "- Task plan: https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "- Findings: https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "- Progress: https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                    "",
                    "Risks: completely different",
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_verify(
            "progress-comment",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(comment_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("remote progress comment does not match rendered body", output["errors"])

    def test_review_request_verification_accepts_rendered_body(self) -> None:
        body_path = self.tmp_path / "review-request.md"
        body_path.write_text(self.render_artifact("review-request", COMPLETE_FIXTURE), encoding="utf-8")

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(body_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-review-request")
        self.assertTrue(output["ok"])

    def test_review_request_verification_rejects_body_without_markers(self) -> None:
        body_path = self.tmp_path / "review-request.md"
        body_path.write_text(
            "\n".join(
                [
                    "feat: add example",
                    "Adds the example capability.",
                    "Closes #42",
                    "## Validation",
                    "- python3 -m unittest discover -s .agents/skills/gcw/tests: passed",
                    "## Planning",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                    "## Progress Comment",
                    "https://github.com/owner/repo/issues/42#issuecomment-1",
                    "## Risks",
                    "Low risk; fixture only.",
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(body_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("remote review request is missing gcw review request markers", output["errors"])


if __name__ == "__main__":
    unittest.main()
