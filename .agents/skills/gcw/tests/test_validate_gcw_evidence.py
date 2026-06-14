from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gcw_test_helpers import (
    clarify_record_cli_args,
    file_sha,
    planning_shas,
    prepare_record_cli_args,
    progress_comment_url,
    triage_record_cli_args,
)


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / ".agents/skills/gcw/scripts/validate_gcw_evidence.py"
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"

_FAKE_SHA = "sha256:" + "a" * 64


def _file_sha(path: Path) -> str:
    return file_sha(path)


class ValidateGcwEvidenceTest(unittest.TestCase):
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
        self.assertTrue(data["ok"], data)
        return data

    def write_planning_files(self) -> None:
        for name in ("task_plan.md", "findings.md", "progress.md"):
            (self.issue_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    def _planning_shas(self) -> dict[str, str]:
        return {
            "task_plan_sha": _file_sha(self.issue_dir / "task_plan.md"),
            "findings_sha": _file_sha(self.issue_dir / "findings.md"),
            "progress_sha": _file_sha(self.issue_dir / "progress.md"),
        }

    def init(self) -> None:
        self.run_manager(
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

    def prepare_to_spec_check(self) -> None:
        self.init()
        self.run_manager(*triage_record_cli_args(self.issue_dir, seq=0))
        self.run_manager(*clarify_record_cli_args(self.issue_dir, seq=1, ready=True))
        self.write_planning_files()
        shas = self._planning_shas()
        self.run_manager(
            "record-issue-to-spec",
            "--issue-dir",
            str(self.issue_dir),
            "--planning-commit-pushed",
            "--progress-comment-url",
            progress_comment_url(2),
            "--task-plan-sha",
            shas["task_plan_sha"],
            "--findings-sha",
            shas["findings_sha"],
            "--progress-sha",
            shas["progress_sha"],
        )

    def implement_check_payload(self) -> dict:
        shas = self._planning_shas()
        return {
            "gate": {
                "ok": True,
                "checks": [{"id": "diff_boundary", "ok": True}],
                "validation": [{"command": "pytest", "exit_code": 0, "result": "passed"}],
            },
            "review_request": {"title": "feat: example", "summary": "Adds example.", "issue_link": "Closes #42"},
            "risks": "Low.",
            "scope": "Example only.",
            "reviewer_notes": "Review transitions.",
            "self_review": {"recorded": True, "progress_section": "## Local Self-Review"},
            "spec_refs": shas,
        }

    def prepare_to_implement_check(self) -> None:
        self.prepare_to_spec_check()
        self.run_manager(
            "record-spec-check",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            "passed",
            "--progress-comment-url",
            progress_comment_url(3),
        )
        self.run_manager(
            "record-implement",
            "--issue-dir",
            str(self.issue_dir),
            "--work-summary",
            "Implemented.",
            "--progress-comment-url",
            progress_comment_url(4),
        )
        payload_file = self.issue_dir / "implement-check-payload.json"
        payload_file.write_text(json.dumps(self.implement_check_payload()), encoding="utf-8")
        self.run_manager(
            "record-implement-check",
            "--issue-dir",
            str(self.issue_dir),
            "--payload-file",
            str(payload_file),
            "--progress-comment-url",
            progress_comment_url(5),
        )

    def _record_pr_publish(self) -> None:
        self.run_manager(
            "record-pr-publish",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
            "--body-hash",
            _FAKE_SHA,
            "--target",
            "owner/repo#7",
            "--rendered-from-event-id",
            "gcw-42-006-gcw-implement-check",
            "--progress-comment-url",
            progress_comment_url(6),
        )

    def run_validate(self, command: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), command, "--issue-dir", str(self.issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def test_workflow_accepts_current_projection(self) -> None:
        self.init()
        output = self.run_validate("workflow")
        self.assertTrue(output["ok"], output)

    def test_triage_check_accepts_issue_triaged(self) -> None:
        self.init()
        self.run_manager(*triage_record_cli_args(self.issue_dir, seq=0))
        output = self.run_validate("triage-check")
        self.assertTrue(output["ok"], output)

    def test_issue_clarify_check_accepts_ready_and_not_ready(self) -> None:
        self.init()
        self.run_manager(*triage_record_cli_args(self.issue_dir, seq=0))
        self.run_manager(*clarify_record_cli_args(self.issue_dir, seq=1, ready=False))
        output = self.run_validate("issue-clarify-check")
        self.assertTrue(output["ok"], output)

    def test_spec_check_requires_planning_files_and_links(self) -> None:
        self.prepare_to_spec_check()
        self.run_manager(
            "record-spec-check",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            "passed",
            "--progress-comment-url",
            progress_comment_url(3),
        )
        output = self.run_validate("spec-check")
        self.assertTrue(output["ok"], output)

    def test_implement_check_requires_event_payload(self) -> None:
        self.prepare_to_implement_check()
        output = self.run_validate("implement-check")
        self.assertTrue(output["ok"], output)

    def test_implement_check_rejects_stale_progress_comment_body_hash(self) -> None:
        self.prepare_to_implement_check()
        latest_file = list((self.issue_dir / "events").glob("*gcw-implement-check*.json"))[0]
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        data["payload"]["progress_comment_body_hash"] = "sha256:" + "0" * 64
        latest_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.run_manager("rebuild-projection", "--issue-dir", str(self.issue_dir))
        output = self.run_validate("implement-check")
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("progress_comment_body_hash" in e for e in output["errors"]))

    def test_pr_publish_requires_review_request_url(self) -> None:
        self.prepare_to_implement_check()
        self._record_pr_publish()
        output = self.run_validate("pr-publish")
        self.assertTrue(output["ok"], output)

    def test_workflow_rejects_invalid_payload(self) -> None:
        self.init()
        events_dir = self.issue_dir / "events"
        intake_file = list(events_dir.glob("*gcw-issue-intake*.json"))[0]
        data = json.loads(intake_file.read_text(encoding="utf-8"))
        del data["payload"]["platform"]
        intake_file.write_text(json.dumps(data), encoding="utf-8")
        output = self.run_validate("workflow")
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("platform" in e for e in output["errors"]))

    def test_workflow_rejects_broken_parent_chain(self) -> None:
        self.init()
        events_dir = self.issue_dir / "events"
        intake_file = list(events_dir.glob("*gcw-issue-intake*.json"))[0]
        data = json.loads(intake_file.read_text(encoding="utf-8"))
        data["parent"]["expected_last_seq"] = 0
        intake_file.write_text(json.dumps(data), encoding="utf-8")
        output = self.run_validate("workflow")
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("expected_last_seq" in e for e in output["errors"]))

    def test_spec_check_rejects_stale_spec_refs_hashes(self) -> None:
        self.prepare_to_spec_check()
        self.run_manager(
            "record-spec-check",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            "passed",
            "--progress-comment-url",
            progress_comment_url(3),
        )
        (self.issue_dir / "task_plan.md").write_text("# changed\n", encoding="utf-8")
        output = self.run_validate("spec-check")
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("task_plan_sha" in e for e in output["errors"]))

    def test_implement_check_rejects_stale_spec_refs_hashes(self) -> None:
        self.prepare_to_implement_check()
        (self.issue_dir / "findings.md").write_text("# changed findings\n", encoding="utf-8")
        output = self.run_validate("implement-check")
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("findings_sha" in e for e in output["errors"]))

    def test_rebuild_projection_rejects_invalid_event_log(self) -> None:
        self.init()
        events_dir = self.issue_dir / "events"
        intake_file = list(events_dir.glob("*gcw-issue-intake*.json"))[0]
        data = json.loads(intake_file.read_text(encoding="utf-8"))
        del data["payload"]["platform"]
        intake_file.write_text(json.dumps(data), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(MANAGER), "rebuild-projection", "--issue-dir", str(self.issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("platform" in e for e in output["errors"]))

    def test_implement_check_validates_self_review(self) -> None:
        self.prepare_to_implement_check()
        latest_file = list((self.issue_dir / "events").glob("*gcw-implement-check*.json"))[0]
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        data["payload"]["self_review"]["recorded"] = False
        latest_file.write_text(json.dumps(data), encoding="utf-8")
        self.run_manager("rebuild-projection", "--issue-dir", str(self.issue_dir))
        output = self.run_validate("implement-check")
        self.assertFalse(output["ok"], output)

    def test_implement_check_validates_spec_refs(self) -> None:
        self.prepare_to_implement_check()
        latest_file = list((self.issue_dir / "events").glob("*gcw-implement-check*.json"))[0]
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        data["payload"]["spec_refs"]["task_plan_sha"] = "sha256:" + "c" * 64
        latest_file.write_text(json.dumps(data), encoding="utf-8")
        self.run_manager("rebuild-projection", "--issue-dir", str(self.issue_dir))
        output = self.run_validate("implement-check")
        self.assertFalse(output["ok"], output)

    def test_pr_publish_validates_effects_structure(self) -> None:
        self.prepare_to_implement_check()
        self._record_pr_publish()
        latest_file = list((self.issue_dir / "events").glob("*gcw-pr-publish*.json"))[0]
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        data["payload"]["effects"][0]["status"] = "pending"
        latest_file.write_text(json.dumps(data), encoding="utf-8")
        output = self.run_validate("pr-publish")
        self.assertFalse(output["ok"], output)
        self.assertTrue(any("applied effect" in e for e in output["errors"]))

    def test_review_check_command(self) -> None:
        self.prepare_to_implement_check()
        self._record_pr_publish()
        self.run_manager(
            "record-pr-review",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            "passed",
            "--progress-comment-url",
            progress_comment_url(7),
        )
        output = self.run_validate("review-check")
        self.assertTrue(output["ok"], output)

    def test_block_check_command(self) -> None:
        self.prepare_to_implement_check()
        self.run_manager(
            "record-block",
            "--issue-dir",
            str(self.issue_dir),
            "--reason",
            "Blocked by dependency",
            "--resume-phase",
            "implementing",
            "--resume-step",
            "gcw-implement",
            "--progress-comment-url",
            progress_comment_url(7),
        )
        output = self.run_validate("block-check")
        self.assertTrue(output["ok"], output)

    def test_clarify_check_command(self) -> None:
        self.init()
        self.run_manager(
            "record-clarify",
            "--issue-dir",
            str(self.issue_dir),
            "--question",
            "Need more details",
            "--source-phase",
            "issue-opened",
            "--progress-comment-url",
            progress_comment_url(8),
        )
        output = self.run_validate("clarify-check")
        self.assertTrue(output["ok"], output)


if __name__ == "__main__":
    unittest.main()
