from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gcw_step_adapters import RecordingAdapter
from gcw_step_runner import GcwStepRunner, SUPPORTED_STEPS


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class GcwStepRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        shutil.copytree(FIXTURE, self.issue_dir)

    def event_count(self) -> int:
        events_dir = self.issue_dir / "events"
        return len(list(events_dir.glob("*.json"))) if events_dir.is_dir() else 0

    def copy_planned_fixture(self) -> None:
        shutil.rmtree(self.issue_dir)
        self.issue_dir.mkdir(parents=True)
        shutil.copytree(FIXTURE / "events", self.issue_dir / "events")
        for name in ("task_plan.md", "findings.md", "progress.md"):
            shutil.copy2(FIXTURE / name, self.issue_dir / name)
        for path in sorted((self.issue_dir / "events").glob("*.json")):
            if path.name.startswith(("003-", "004-", "005-")):
                path.unlink()
        from gcw_workflow_lib import write_projection

        write_projection(self.issue_dir)

    def test_supported_steps_cover_milestone_list(self) -> None:
        expected = {
            "gcw-issue-prepare",
            "gcw-issue-to-spec",
            "gcw-spec-check",
            "gcw-implement-check",
            "gcw-pr-publish",
            "gcw-pr-review",
        }
        self.assertEqual(set(SUPPORTED_STEPS), expected)

    def test_illegal_phase_routing(self) -> None:
        self.copy_planned_fixture()
        runner = GcwStepRunner(adapter=RecordingAdapter())
        result = runner.run("gcw-pr-publish", self.issue_dir)
        self.assertFalse(result.ok)
        self.assertEqual(result.stop_reason, "illegal_phase")
        self.assertEqual(result.phase_before, "planned")
        self.assertEqual(result.phase_after, "planned")
        self.assertEqual(self.event_count(), 3)

    def test_dry_run_does_not_append_events(self) -> None:
        self.copy_planned_fixture()
        runner = GcwStepRunner(adapter=RecordingAdapter())
        before = self.event_count()
        result = runner.run("gcw-spec-check", self.issue_dir, dry_run=True, options={"result": "passed"})
        self.assertTrue(result.ok)
        self.assertEqual(result.phase_before, "planned")
        self.assertEqual(result.phase_after, "planned")
        self.assertIn("progress_comment_body", result.artifacts)
        self.assertEqual(self.event_count(), before)
        self.assertEqual(len(RecordingAdapter().published_urls), 0)

    def test_validation_failure_without_publication(self) -> None:
        self.copy_planned_fixture()
        (self.issue_dir / "task_plan.md").unlink()
        adapter = RecordingAdapter()
        runner = GcwStepRunner(adapter=adapter)
        before = self.event_count()
        result = runner.run("gcw-spec-check", self.issue_dir, options={"result": "passed"})
        self.assertFalse(result.ok)
        self.assertEqual(result.stop_reason, "validation_failed")
        self.assertEqual(self.event_count(), before)
        self.assertEqual(adapter.published_urls, [])

    def test_publication_failure_does_not_append_events(self) -> None:
        self.copy_planned_fixture()
        adapter = RecordingAdapter(fail_on="progress_comment")
        runner = GcwStepRunner(adapter=adapter)
        before = self.event_count()
        result = runner.run("gcw-spec-check", self.issue_dir, options={"result": "passed"})
        self.assertFalse(result.ok)
        self.assertEqual(result.stop_reason, "publication_failed")
        self.assertEqual(self.event_count(), before)

    def test_successful_spec_check_run(self) -> None:
        self.copy_planned_fixture()
        adapter = RecordingAdapter()
        runner = GcwStepRunner(adapter=adapter)
        result = runner.run("gcw-spec-check", self.issue_dir, options={"result": "passed"})
        self.assertTrue(result.ok)
        self.assertEqual(result.phase_before, "planned")
        self.assertEqual(result.phase_after, "ready-for-implementation")
        self.assertEqual(result.stop_reason, None)
        self.assertTrue(result.validation)
        self.assertEqual(self.event_count(), 4)
        self.assertEqual(len(adapter.published_urls), 1)

    def test_prepare_step_requires_gate_file(self) -> None:
        shutil.rmtree(self.issue_dir)
        self.issue_dir.mkdir(parents=True)
        intake = {
            "actor": {"id": "cursor-session", "kind": "local"},
            "at": "2026-06-14T00:00:00Z",
            "event": "gcw-issue-intake",
            "event_id": "gcw-42-000-gcw-issue-intake",
            "parent": {"expected_last_seq": -1},
            "payload": {
                "branch": "feat/example-42",
                "issue": "42",
                "owner": {"id": "cursor-session", "kind": "local"},
                "platform": "github",
                "repository": "owner/repo",
            },
            "refs": {"branch": "feat/example-42", "issue": "42"},
            "schema": "gcw.event/v1",
            "seq": 0,
        }
        events_dir = self.issue_dir / "events"
        events_dir.mkdir(parents=True)
        (events_dir / "000-gcw-issue-intake.json").write_text(json.dumps(intake) + "\n", encoding="utf-8")
        from gcw_workflow_lib import write_projection

        write_projection(self.issue_dir)
        runner = GcwStepRunner(adapter=RecordingAdapter())
        result = runner.run("gcw-issue-prepare", self.issue_dir, options={})
        self.assertFalse(result.ok)
        self.assertEqual(result.stop_reason, "blocked")


if __name__ == "__main__":
    unittest.main()
