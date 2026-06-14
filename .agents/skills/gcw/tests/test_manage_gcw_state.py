from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcw_test_helpers import file_sha, planning_shas


ROOT = Path(__file__).resolve().parents[4]
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"


_FAKE_BODY_HASH = "sha256:" + "a" * 64


class ManageGcwStateTest(unittest.TestCase):
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
        if not data["ok"]:
            self.fail(f"command failed: {data}")
        return data

    def workflow(self) -> dict:
        return json.loads((self.issue_dir / "workflow.json").read_text(encoding="utf-8"))

    def events(self) -> list[dict]:
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.issue_dir / "events").glob("*.json"))
        ]

    def record_issue_to_spec(self) -> None:
        shas = planning_shas(self.issue_dir)
        self.run_manager(
            "record-issue-to-spec",
            "--issue-dir",
            str(self.issue_dir),
            "--planning-commit-pushed",
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
            "--task-plan-sha",
            shas["task_plan_sha"],
            "--findings-sha",
            shas["findings_sha"],
            "--progress-sha",
            shas["progress_sha"],
        )

    def init(self, state: str = "issue-opened") -> None:
        result = self.run_manager(
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
        if state != "issue-opened":
            self.run_manager("record-issue-prepare", "--issue-dir", str(self.issue_dir), "--ready")
        if state == "implementing":
            self.write_planning_files()
            self.record_issue_to_spec()
            self.run_manager("record-spec-check", "--issue-dir", str(self.issue_dir), "--result", "passed")
            self.run_manager("record-implement", "--issue-dir", str(self.issue_dir), "--work-summary", "Started work.")
        elif state == "reviewing":
            self.write_planning_files()
            self.record_issue_to_spec()
            self.run_manager("record-spec-check", "--issue-dir", str(self.issue_dir), "--result", "passed")
            self.run_manager("record-implement", "--issue-dir", str(self.issue_dir), "--work-summary", "Implemented.")
            payload = self.issue_dir / "implement-check-payload.json"
            payload.write_text(json.dumps(self.implement_check_payload()), encoding="utf-8")
            self.run_manager("record-implement-check", "--issue-dir", str(self.issue_dir), "--payload-file", str(payload))
            self.run_manager(
                "record-pr-publish",
                "--issue-dir",
                str(self.issue_dir),
                "--review-request-url",
                "https://github.com/owner/repo/pull/7",
                "--body-hash",
                _FAKE_BODY_HASH,
                "--target",
                "owner/repo#7",
            )
        self.assertTrue(result["ok"])

    def write_planning_files(self) -> None:
        for name in ("task_plan.md", "findings.md", "progress.md"):
            (self.issue_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    def implement_check_payload(self) -> dict:
        shas = planning_shas(self.issue_dir)
        return {
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
            "spec_refs": shas,
        }

    def test_main_path_reaches_reviewing(self) -> None:
        self.init()
        self.run_manager("record-issue-prepare", "--issue-dir", str(self.issue_dir), "--ready")
        self.write_planning_files()
        self.record_issue_to_spec()
        self.run_manager("record-spec-check", "--issue-dir", str(self.issue_dir), "--result", "passed")
        self.run_manager("record-implement", "--issue-dir", str(self.issue_dir), "--work-summary", "Implemented.")
        payload = self.issue_dir / "implement-check-payload.json"
        payload.write_text(json.dumps(self.implement_check_payload()), encoding="utf-8")
        self.run_manager("record-implement-check", "--issue-dir", str(self.issue_dir), "--payload-file", str(payload))
        self.run_manager(
            "record-pr-publish",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
            "--body-hash",
            _FAKE_BODY_HASH,
            "--target",
            "owner/repo#7",
        )

        projection = self.workflow()["projection"]
        self.assertEqual(projection["phase"], "reviewing")
        self.assertEqual(projection["last_completed_step"], "gcw-pr-publish")
        self.assertEqual(projection["next_allowed_steps"], ["gcw-pr-review"])
        self.assertEqual(self.events()[-1]["payload"]["effects"][0]["status"], "applied")

    def test_changes_requested_preserves_feedback_source(self) -> None:
        self.init("reviewing")
        self.run_manager(
            "record-pr-review",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            "changes-requested",
            "--feedback-source",
            "human-review",
        )
        projection = self.workflow()["projection"]
        self.assertEqual(projection["phase"], "changes-requested")
        self.assertEqual(projection["active_feedback"]["source"], "human-review")
        self.assertEqual(projection["next_allowed_steps"], ["gcw-implement"])

    def test_block_records_resume_point(self) -> None:
        self.init("implementing")
        self.run_manager(
            "record-block",
            "--issue-dir",
            str(self.issue_dir),
            "--reason",
            "dependency unavailable",
        )
        projection = self.workflow()["projection"]
        self.assertEqual(projection["phase"], "blocked")
        self.assertEqual(projection["active_blocker"]["resume_phase"], "implementing")
        self.assertEqual(projection["active_blocker"]["resume_step"], "gcw-implement")


if __name__ == "__main__":
    unittest.main()
