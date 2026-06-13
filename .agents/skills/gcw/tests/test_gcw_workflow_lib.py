from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))

from gcw_workflow_lib import (  # noqa: E402
    append_event,
    assert_projection_current,
    load_events,
    reduce_workflow,
    write_projection,
)


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
        self.append("gcw-issue-prepare", {"ready": True})
        self.append(
            "gcw-issue-to-spec",
            {
                "planning_commit_pushed": True,
                "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
                "spec_refs": {"task_plan_sha": "sha256:task", "findings_sha": "sha256:findings", "progress_sha": "sha256:progress"},
            },
        )
        self.append("gcw-spec-check", {"gate": {"ok": True, "checks": [], "errors": []}})
        self.append("gcw-implement", {"work_summary": "Implemented example."})
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
                "spec_refs": {"task_plan_sha": "sha256:task", "findings_sha": "sha256:findings", "progress_sha": "sha256:progress"},
            },
            code_head_sha="code-1",
        )
        self.append(
            "gcw-pr-publish",
            {
                "review_request_url": "https://github.com/owner/repo/pull/7",
                "rendered_from_event_id": "gcw-42-005-gcw-implement-check",
                "body_hash": "sha256:body",
                "effects": [
                    {
                        "kind": "github_pr_upsert",
                        "operation_id": "gcw-42-pr-publish-006",
                        "target": "owner/repo#7",
                        "body_hash": "sha256:body",
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


if __name__ == "__main__":
    unittest.main()
