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
from gcw_test_helpers import write_readiness_gate_file, write_remote_sync_file


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
            if int(path.name.split("-", 1)[0]) > 3:
                path.unlink()
        from gcw_workflow_lib import write_projection

        write_projection(self.issue_dir)

    def test_supported_steps_cover_milestone_list(self) -> None:
        expected = {
            "gcw-issue-triage",
            "gcw-issue-clarify",
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
        self.assertEqual(self.event_count(), 4)

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
        self.assertEqual(self.event_count(), 5)
        self.assertEqual(len(adapter.published_urls), 1)

    def test_triage_step_requires_remote_sync_file(self) -> None:
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
        result = runner.run(
            "gcw-issue-triage",
            self.issue_dir,
            options={
                "classification_type": "enhancement",
                "classification_priority": "priority:p2",
                "labels_applied": ["triaged", "area:tests"],
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.stop_reason, "blocked")

    def test_triage_dry_run_renders_post_record_phase(self) -> None:
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
        remote_sync_file = write_remote_sync_file(self.issue_dir / "remote-sync.json", ["triaged", "area:tests"])
        runner = GcwStepRunner(adapter=RecordingAdapter())
        result = runner.run(
            "gcw-issue-triage",
            self.issue_dir,
            dry_run=True,
            options={
                "classification_type": "enhancement",
                "classification_area": "area:tests",
                "classification_priority": "priority:p2",
                "labels_applied": ["triaged", "area:tests"],
                "remote_sync_file": str(remote_sync_file),
            },
        )
        self.assertTrue(result.ok)
        body = result.artifacts["progress_comment_body"]
        self.assertIn("GCW Status: issue-triaged", body)
        self.assertIn("Last completed step: gcw-issue-triage", body)
        self.assertNotIn("GCW Status: issue-opened", body)

    def test_clarify_dry_run_renders_ready_for_planning(self) -> None:
        shutil.rmtree(self.issue_dir)
        self.issue_dir.mkdir(parents=True)
        events_dir = self.issue_dir / "events"
        events_dir.mkdir(parents=True)
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
        triage = {
            "actor": {"id": "cursor-session", "kind": "local"},
            "at": "2026-06-14T00:00:01Z",
            "event": "gcw-issue-triage",
            "event_id": "gcw-42-001-gcw-issue-triage",
            "parent": {"expected_last_seq": 0},
            "payload": {
                "classification": {"type": "enhancement", "area": "area:tests", "priority": "priority:p2"},
                "labels_applied": ["triaged", "area:tests"],
                "remote_sync": {
                    "platform": "github",
                    "issue_type": "Feature",
                    "priority": "Medium",
                    "labels": ["triaged", "area:tests"],
                },
                "progress_comment_url": "https://github.com/test/repo/issues/1#issuecomment-1",
            },
            "refs": {"branch": "feat/example-42", "issue": "42"},
            "schema": "gcw.event/v1",
            "seq": 1,
        }
        (events_dir / "000-gcw-issue-intake.json").write_text(json.dumps(intake) + "\n", encoding="utf-8")
        (events_dir / "001-gcw-issue-triage.json").write_text(json.dumps(triage) + "\n", encoding="utf-8")
        from gcw_workflow_lib import write_projection

        write_projection(self.issue_dir)
        gate_file = write_readiness_gate_file(self.issue_dir / "clarify-gate.json", ready=True)
        runner = GcwStepRunner(adapter=RecordingAdapter())
        result = runner.run(
            "gcw-issue-clarify",
            self.issue_dir,
            dry_run=True,
            options={"gate_file": str(gate_file), "ready": True, "summary": "scope clear"},
        )
        self.assertTrue(result.ok)
        body = result.artifacts["progress_comment_body"]
        self.assertIn("GCW Status: ready-for-planning", body)
        self.assertIn("Last completed step: gcw-issue-clarify", body)


if __name__ == "__main__":
    unittest.main()
