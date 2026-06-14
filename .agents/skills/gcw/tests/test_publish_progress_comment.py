from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/tests"))

from publish_progress_comment import publish_progress_comment  # noqa: E402

COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class PublishProgressCommentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)
        for name in ("events", "task_plan.md", "findings.md", "progress.md"):
            src = COMPLETE_FIXTURE / name
            dst = self.issue_dir / name
            if src.is_dir():
                import shutil

                shutil.copytree(src, dst)
            elif src.is_file():
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        workflow = json.loads((COMPLETE_FIXTURE / "workflow.json").read_text(encoding="utf-8"))
        (self.issue_dir / "workflow.json").write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")

    @mock.patch("publish_progress_comment.subprocess.run")
    def test_publish_creates_github_comment_only(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = mock.Mock(stdout="https://github.com/owner/repo/issues/42#issuecomment-9\n", returncode=0)
        output = publish_progress_comment(argparse.Namespace(issue_dir=self.issue_dir, dry_run=False))
        self.assertTrue(output["ok"])
        self.assertEqual(output["progress_comment_url"], "https://github.com/owner/repo/issues/42#issuecomment-9")
        self.assertTrue(output["body_hash"].startswith("sha256:"))
        command = run_mock.call_args[0][0]
        self.assertEqual(command[:4], ["gh", "issue", "comment", "42"])
        self.assertIn("--body-file", command)

    def test_dry_run_renders_without_posting(self) -> None:
        output = publish_progress_comment(argparse.Namespace(issue_dir=self.issue_dir, dry_run=True))
        self.assertTrue(output["ok"])
        self.assertTrue(output["dry_run"])
        self.assertIn("<!-- gcw-progress -->", output["body"])
        self.assertEqual(output["progress_comment_url"], "")


if __name__ == "__main__":
    unittest.main()
