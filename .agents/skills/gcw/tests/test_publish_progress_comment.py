from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".gcw" / "runtime"))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/tests"))

from publish_progress_comment import publish_progress_comment  # noqa: E402
from gcw_test_helpers import READINESS_GATE_OK, clarify_event_payload, triage_event_payload  # noqa: E402

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

    def test_milestone_clarify_preview_uses_post_record_phase(self) -> None:
        intake_only = Path(self.tmp.name) / ".gcw/issues/44"
        intake_only.mkdir(parents=True)
        intake = {
            "actor": {"id": "cursor-session", "kind": "local"},
            "at": "2026-06-14T00:00:00Z",
            "event": "gcw-issue-intake",
            "event_id": "gcw-44-000-gcw-issue-intake",
            "parent": {"expected_last_seq": -1},
            "payload": {
                "branch": "feat/example-44",
                "issue": "44",
                "owner": {"id": "cursor-session", "kind": "local"},
                "platform": "github",
                "repository": "owner/repo",
            },
            "refs": {"branch": "feat/example-44", "issue": "44"},
            "schema": "gcw.event/v1",
            "seq": 0,
        }
        events_dir = intake_only / "events"
        events_dir.mkdir(parents=True)
        (events_dir / "000-gcw-issue-intake.json").write_text(json.dumps(intake) + "\n", encoding="utf-8")
        triage = {
            "actor": {"id": "cursor-session", "kind": "local"},
            "at": "2026-06-14T00:00:01Z",
            "event": "gcw-issue-triage",
            "event_id": "gcw-44-001-gcw-issue-triage",
            "parent": {"expected_last_seq": 0},
            "payload": triage_event_payload(progress_comment_url="https://github.com/owner/repo/issues/44#issuecomment-1"),
            "refs": {"branch": "feat/example-44", "issue": "44"},
            "schema": "gcw.event/v1",
            "seq": 1,
        }
        (events_dir / "001-gcw-issue-triage.json").write_text(json.dumps(triage) + "\n", encoding="utf-8")
        from gcw_workflow_lib import write_projection

        write_projection(intake_only)

        payload = clarify_event_payload(ready=True, progress_comment_url="")
        payload["gate"] = READINESS_GATE_OK
        output = publish_progress_comment(
            argparse.Namespace(
                issue_dir=intake_only,
                dry_run=True,
                milestone_event="gcw-issue-clarify",
                milestone_payload=payload,
            )
        )
        self.assertTrue(output["ok"])
        self.assertIn("GCW Status: ready-for-planning", output["body"])
        self.assertIn("Last completed step: gcw-issue-clarify", output["body"])
        self.assertNotIn("GCW Status: issue-triaged", output["body"])


if __name__ == "__main__":
    unittest.main()
