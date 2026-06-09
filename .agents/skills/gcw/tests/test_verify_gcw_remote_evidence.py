from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VERIFY = ROOT / ".agents/skills/gcw/scripts/verify_gcw_remote_evidence.py"
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

    def test_progress_comment_verification_accepts_linked_planning_evidence(self) -> None:
        comment_path = self.tmp_path / "progress-comment.md"
        comment_path.write_text(
            "\n".join(
                [
                    "GCW status: implementing",
                    "Planning files:",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                    "Latest checkpoint: readiness-check",
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

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-progress-comment")
        self.assertTrue(output["ok"])

    def test_review_request_verification_accepts_complete_body(self) -> None:
        body_path = self.tmp_path / "review-request.md"
        body_path.write_text(
            "\n".join(
                [
                    "feat: add example",
                    "Adds the example capability.",
                    "Closes #42",
                    "Validation:",
                    "- python3 -m unittest discover -s .agents/skills/gcw/tests: passed",
                    "Planning:",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                    "Progress comment: https://github.com/owner/repo/issues/42#issuecomment-1",
                    "Risks: Low risk; fixture only.",
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

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-review-request")
        self.assertTrue(output["ok"])


if __name__ == "__main__":
    unittest.main()
