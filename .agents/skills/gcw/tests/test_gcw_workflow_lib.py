from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".gcw" / "runtime"))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/tests"))

from gcw_workflow_lib import (  # noqa: E402
    WorkflowError,
    append_event,
    assert_projection_current,
    load_events,
    reduce_workflow,
    validate_event_log,
    validate_events_integrity,
    validate_parent_chain,
    validate_payload,
    write_projection,
)


from gcw_test_helpers import clarify_event_payload, progress_comment_url, triage_event_payload  # noqa: E402


_FAKE_SHA = "sha256:" + "a" * 64


class GcwWorkflowLibTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def append(self, event: str, payload: dict, **refs: object) -> None:
        append_event(
            self.issue_dir,
            {
                "event": event,
                "actor": {"kind": "local", "id": "cursor-session"},
                "refs": {
                    "issue": 42,
                    "branch": "gcw/issue-42",
                    "base_branch": "main",
                    **refs,
                },
                "payload": payload,
            },
        )

    def test_reducer_projects_main_path_to_reviewing(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        self.append(
            "gcw-issue-triage",
            triage_event_payload(progress_comment_url=progress_comment_url(0)),
        )
        self.append(
            "gcw-issue-clarify",
            clarify_event_payload(ready=True, progress_comment_url=progress_comment_url(1)),
        )
        self.append(
            "gcw-issue-to-spec",
            {
                "planning_commit_pushed": True,
                "progress_comment_url": progress_comment_url(2),
                "spec_refs": {"task_plan_sha": _FAKE_SHA, "findings_sha": _FAKE_SHA, "progress_sha": _FAKE_SHA},
            },
        )
        self.append(
            "gcw-spec-check",
            {
                "gate": {"ok": True, "checks": [], "errors": []},
                "progress_comment_url": progress_comment_url(3),
            },
        )
        self.append(
            "gcw-implement",
            {"work_summary": "Implemented example.", "progress_comment_url": progress_comment_url(4)},
        )
        self.append(
            "gcw-implement-check",
            {
                "gate": {
                    "ok": True,
                    "checks": [{"id": "diff_boundary", "ok": True}],
                    "validation": [{"command": "python3 -m unittest", "exit_code": 0, "result": "passed"}],
                },
                "review_request": {"title": "feat: example", "summary": "Adds example.", "issue_link": "Closes #42"},
                "risks": "Low.",
                "scope": "Example only.",
                "reviewer_notes": "Review state transitions.",
                "self_review": {"recorded": True, "progress_section": "## Local Self-Review"},
                "spec_refs": {"task_plan_sha": _FAKE_SHA, "findings_sha": _FAKE_SHA, "progress_sha": _FAKE_SHA},
                "progress_comment_url": progress_comment_url(5),
            },
            code_head_sha="code-1",
        )
        self.append(
            "gcw-pr-publish",
            {
                "review_request_url": "https://github.com/owner/repo/pull/7",
                "rendered_from_event_id": "gcw-42-006-gcw-implement-check",
                "body_hash": _FAKE_SHA,
                "progress_comment_url": progress_comment_url(6),
                "effects": [
                    {
                        "kind": "github_pr_upsert",
                        "operation_id": "gcw-42-pr-publish-006",
                        "target": "owner/repo#7",
                        "body_hash": _FAKE_SHA,
                        "remote_updated_at": "2026-06-13T08:05:00Z",
                        "status": "applied",
                    }
                ],
            },
        )

        projection = reduce_workflow(load_events(self.issue_dir))

        self.assertEqual(projection["phase"], "reviewing")
        self.assertEqual(projection["last_completed_step"], "gcw-pr-publish")
        self.assertEqual(projection["next_allowed_steps"], ["gcw-pr-review"])
        self.assertEqual(projection["refs"]["review_request_url"], "https://github.com/owner/repo/pull/7")
        self.assertEqual(projection["refs"]["progress_comment_url"], progress_comment_url(6))

    def test_reducer_projects_issue_triaged_to_clarify(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        self.append(
            "gcw-issue-triage",
            triage_event_payload(progress_comment_url=progress_comment_url(0)),
        )

        projection = reduce_workflow(load_events(self.issue_dir))

        self.assertEqual(projection["phase"], "issue-triaged")
        self.assertEqual(projection["last_completed_step"], "gcw-issue-triage")
        self.assertEqual(projection["next_allowed_steps"], ["gcw-issue-clarify"])
        self.assertEqual(projection["refs"]["progress_comment_url"], progress_comment_url(0))

    def test_reducer_loops_issue_clarifying_through_clarify(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        self.append("gcw-issue-triage", triage_event_payload(progress_comment_url=progress_comment_url(0)))
        self.append("gcw-issue-clarify", clarify_event_payload(ready=False, progress_comment_url=progress_comment_url(1)))

        projection = reduce_workflow(load_events(self.issue_dir))
        self.assertEqual(projection["phase"], "issue-clarifying")
        self.assertEqual(projection["next_allowed_steps"], ["gcw-issue-clarify"])

        self.append("gcw-issue-clarify", clarify_event_payload(ready=True, progress_comment_url=progress_comment_url(2)))
        projection = reduce_workflow(load_events(self.issue_dir))
        self.assertEqual(projection["phase"], "ready-for-planning")
        self.assertEqual(projection["next_allowed_steps"], ["gcw-issue-to-spec"])
        self.assertNotIn("active_feedback", projection)

    def test_unknown_issue_event_is_rejected(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        with self.assertRaises(WorkflowError):
            self.append("gcw-unknown-event", {"ready": True})

    def test_reducer_tracks_latest_progress_comment_url(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        self.append(
            "gcw-issue-triage",
            triage_event_payload(progress_comment_url=progress_comment_url(0)),
        )
        self.append(
            "gcw-issue-clarify",
            clarify_event_payload(ready=True, progress_comment_url=progress_comment_url(1)),
        )
        self.append(
            "gcw-issue-to-spec",
            {
                "planning_commit_pushed": True,
                "progress_comment_url": progress_comment_url(2),
                "spec_refs": {"task_plan_sha": _FAKE_SHA, "findings_sha": _FAKE_SHA, "progress_sha": _FAKE_SHA},
            },
        )
        projection = reduce_workflow(load_events(self.issue_dir))
        self.assertEqual(projection["refs"]["progress_comment_url"], progress_comment_url(2))
        self.append(
            "gcw-spec-check",
            {
                "gate": {"ok": True, "checks": [], "errors": []},
                "progress_comment_url": progress_comment_url(3),
            },
        )
        projection = reduce_workflow(load_events(self.issue_dir))
        self.assertEqual(projection["refs"]["progress_comment_url"], progress_comment_url(3))

    def test_projection_is_rebuildable_cache(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )

        write_projection(self.issue_dir)
        (self.issue_dir / "workflow.json").unlink()
        rebuilt = write_projection(self.issue_dir)

        self.assertEqual(rebuilt["projection"]["phase"], "issue-opened")
        self.assertTrue(assert_projection_current(self.issue_dir)["ok"])


    def test_reducer_rejects_unknown_event(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        with self.assertRaises(WorkflowError):
            self.append("gcw-unknown-event", {})

    def test_reducer_rejects_invalid_phase_transition(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        self.append("gcw-implement", {"work_summary": "Invalid transition."})
        with self.assertRaises(WorkflowError):
            reduce_workflow(load_events(self.issue_dir))

    def test_reducer_rejects_empty_events(self) -> None:
        with self.assertRaises(WorkflowError):
            reduce_workflow([])

    def test_reducer_rejects_first_event_not_intake(self) -> None:
        events = [
            {
                "seq": 0,
                "event": "gcw-unknown-event",
                "payload": {"ready": True},
                "refs": {},
                "actor": {"kind": "local", "id": "cursor-session"},
            }
        ]
        with self.assertRaises(WorkflowError):
            reduce_workflow(events)

    def test_reducer_rejects_discontinuous_seq(self) -> None:
        events = [
            {
                "seq": 0,
                "event": "gcw-issue-intake",
                "payload": {
                    "issue": 42,
                    "platform": "github",
                    "repository": "owner/repo",
                    "branch": "gcw/issue-42",
                    "owner": {"kind": "local", "id": "cursor-session"},
                },
                "refs": {},
                "actor": {"kind": "local", "id": "cursor-session"},
            },
            {
                "seq": 3,
                "event": "gcw-unknown-event",
                "payload": {"ready": True},
                "refs": {},
                "actor": {"kind": "local", "id": "cursor-session"},
            },
        ]
        with self.assertRaises(WorkflowError):
            reduce_workflow(events)

    def test_append_event_rejects_duplicate_seq(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        events_dir = self.issue_dir / "events"
        existing_file = list(events_dir.glob("*.json"))[0]
        with self.assertRaises(WorkflowError):
            append_event(
                self.issue_dir,
                {
                    "event": "gcw-issue-intake",
                    "actor": {"kind": "local", "id": "cursor-session"},
                    "refs": {"issue": 42, "branch": "gcw/issue-42", "base_branch": "main"},
                    "payload": {
                        "issue": 42,
                        "platform": "github",
                        "repository": "owner/repo",
                        "branch": "gcw/issue-42",
                        "owner": {"kind": "local", "id": "cursor-session"},
                    },
                },
                expected_last_seq=-1,
            )

    def test_validate_payload_rejects_missing_fields(self) -> None:
        errors = validate_payload("gcw-issue-intake", {})
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("issue" in e for e in errors))
        self.assertTrue(any("platform" in e for e in errors))
        self.assertTrue(any("repository" in e for e in errors))
        self.assertTrue(any("branch" in e for e in errors))

    def test_validate_payload_rejects_invalid_platform(self) -> None:
        errors = validate_payload(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "svn",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        self.assertTrue(any("platform" in e for e in errors))

    def test_validate_payload_requires_triage_type_and_priority(self) -> None:
        errors = validate_payload(
            "gcw-issue-triage",
            {
                "classification": {"area": "area:tests"},
                "labels_applied": ["triaged", "area:tests"],
                "remote_sync": {
                    "platform": "github",
                    "issue_type": "Feature",
                    "priority": "Medium",
                    "labels": ["triaged", "area:tests"],
                },
                "progress_comment_url": progress_comment_url(0),
            },
        )

        self.assertTrue(any("classification.type is required" in error for error in errors))
        self.assertTrue(any("classification.priority is required" in error for error in errors))

    def test_validate_parent_chain_detects_mismatch(self) -> None:
        events = [
            {
                "seq": 0,
                "event": "gcw-issue-intake",
                "parent": {"expected_last_seq": -1},
                "payload": {
                    "issue": 42,
                    "platform": "github",
                    "repository": "owner/repo",
                    "branch": "gcw/issue-42",
                    "owner": {"kind": "local", "id": "cursor-session"},
                },
            },
            {
                "seq": 1,
                "event": "gcw-unknown-event",
                "parent": {"expected_last_seq": -1},
                "payload": {"ready": True},
            },
        ]
        errors = validate_parent_chain(events)
        self.assertTrue(any("seq 1" in e and "expected_last_seq" in e for e in errors))

    def test_validate_event_log_rejects_invalid_payload(self) -> None:
        self.append(
            "gcw-issue-intake",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
            },
        )
        events_dir = self.issue_dir / "events"
        intake_file = list(events_dir.glob("*.json"))[0]
        intake_file.write_text(
            intake_file.read_text(encoding="utf-8").replace('"platform": "github"', '"platform": "svn"'),
            encoding="utf-8",
        )
        errors = validate_event_log(self.issue_dir)
        self.assertTrue(any("platform" in e for e in errors))

    def test_validate_events_integrity_detects_filename_mismatch(self) -> None:
        events_dir = self.issue_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        mismatch_file = events_dir / "005-gcw-unknown-event.json"
        mismatch_file.write_text(
            '{"seq": 3, "event": "gcw-issue-intake", "payload": {}, "refs": {}, "actor": {"kind": "local", "id": "test"}}',
            encoding="utf-8",
        )
        errors = validate_events_integrity(self.issue_dir)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("filename" in e.lower() for e in errors))


if __name__ == "__main__":
    unittest.main()
