from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_state.py"
VALIDATOR = ROOT / ".agents/skills/gcw/scripts/validate_gcw_evidence.py"

DEFAULT_PROGRESS_URL = "https://github.com/owner/repo/issues/42#issuecomment-1"


class ManageGcwStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)

    def run_manager(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MANAGER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_validator(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), command, "--issue-dir", str(self.issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def assert_ok(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)

    def state_now(self) -> dict:
        return json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))

    # -- flow helpers -----------------------------------------------------

    def init_state(self, platform: str = "github", repository: str = "owner/repo") -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "init-state",
            "--issue-dir",
            str(self.issue_dir),
            "--issue",
            "42",
            "--platform",
            platform,
            "--repository",
            repository,
            "--branch",
            "feat/example-42",
            "--owner-kind",
            "local",
            "--owner-id",
            "cursor-session",
        )

    def write_planning_files(self) -> None:
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text(
            "# Progress\n\n## Local Self-Review\n\nDiff reviewed.\nValidation performed.\n",
            encoding="utf-8",
        )

    def publish_planning(
        self,
        progress_url: str = DEFAULT_PROGRESS_URL,
        planning_commit_pushed: str = "true",
    ) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-publish-planning",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            progress_url,
            "--planning-commit-pushed",
            planning_commit_pushed,
        )

    def implementation_gate(self, progress_url: str = DEFAULT_PROGRESS_URL, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-implementation-gate",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            progress_url,
            *extra,
        )

    def implement(self) -> subprocess.CompletedProcess[str]:
        return self.run_manager("record-implement", "--issue-dir", str(self.issue_dir))

    def local_self_review(self) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-local-self-review",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-section",
            "## Local Self-Review",
        )

    def readiness_evidence(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-readiness-evidence",
            "--issue-dir",
            str(self.issue_dir),
            "--base-branch",
            "main",
            "--commit-range",
            "main...feat/example-42",
            "--title",
            "feat: add example",
            "--summary",
            "Adds the example capability.",
            "--issue-link",
            "Closes #42",
            "--validation-command",
            "python3 -m unittest",
            "--validation-result",
            "passed",
            "--risks",
            "Low risk.",
            *extra,
        )

    def review_request(self) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-review-request",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
        )

    def machine_review_start(self) -> subprocess.CompletedProcess[str]:
        return self.run_manager("record-machine-review-start", "--issue-dir", str(self.issue_dir))

    def machine_review_result(self, result: str) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-machine-review-result",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            result,
        )

    def human_review_result(self, result: str) -> subprocess.CompletedProcess[str]:
        return self.run_manager(
            "record-human-review-result",
            "--issue-dir",
            str(self.issue_dir),
            "--result",
            result,
        )

    def reach_planned(self, platform: str = "github", repository: str = "owner/repo", progress_url: str = DEFAULT_PROGRESS_URL) -> None:
        self.assert_ok(self.init_state(platform, repository))
        self.write_planning_files()
        self.assert_ok(self.publish_planning(progress_url))

    def reach_ready_for_implementation(self, progress_url: str = DEFAULT_PROGRESS_URL) -> None:
        self.reach_planned(progress_url=progress_url)
        self.assert_ok(self.implementation_gate(progress_url))

    def reach_implementing(self, progress_url: str = DEFAULT_PROGRESS_URL) -> None:
        self.reach_ready_for_implementation(progress_url)
        self.assert_ok(self.implement())

    def prepare_implementing_issue(self) -> None:
        self.reach_implementing()
        self.assert_ok(self.local_self_review())

    def reach_ready_for_review(self) -> None:
        self.prepare_implementing_issue()
        self.assert_ok(self.readiness_evidence())
        self.assert_ok(self.review_request())

    def reach_human_reviewing(self) -> None:
        self.reach_ready_for_review()
        self.assert_ok(self.machine_review_start())
        self.assert_ok(self.machine_review_result("passed"))

    def reach_approved(self) -> None:
        self.reach_human_reviewing()
        self.assert_ok(self.human_review_result("approved"))

    # -- init / planning --------------------------------------------------

    def test_init_state_writes_valid_planning_state(self) -> None:
        self.assert_ok(self.init_state())

        state = self.state_now()
        self.assertEqual(state["state"], "planning")
        self.assertEqual(state["last_completed_step"], "")
        self.assertEqual(state["next_allowed_steps"], ["publish-planning"])
        self.assertFalse(state["evidence"]["planning_files_exist"])
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_publish_planning_moves_state_to_planned(self) -> None:
        self.assert_ok(self.init_state())
        self.write_planning_files()

        self.assert_ok(self.publish_planning())

        state = self.state_now()
        self.assertEqual(state["state"], "planned")
        self.assertEqual(state["last_completed_step"], "publish-planning")
        self.assertEqual(state["next_allowed_steps"], ["implementation-gate"])
        self.assertTrue(state["evidence"]["planning_files_exist"])
        self.assertTrue(state["evidence"]["planning_commit_pushed"])
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_publish_planning_fails_without_planning_files_and_keeps_state(self) -> None:
        self.assert_ok(self.init_state())

        result = self.publish_planning()

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("planning files are missing", output["errors"])
        state = self.state_now()
        self.assertEqual(state["state"], "planning")
        self.assertEqual(state["last_completed_step"], "")
        self.assertFalse(state["evidence"]["planning_files_exist"])
        self.assertFalse(state["evidence"]["planning_commit_pushed"])

    def test_record_publish_planning_fails_when_commit_not_pushed(self) -> None:
        self.assert_ok(self.init_state())
        self.write_planning_files()

        result = self.publish_planning(planning_commit_pushed="false")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("planning commit is not pushed", output["errors"])
        state = self.state_now()
        self.assertEqual(state["state"], "planning")
        self.assertFalse(state["evidence"]["planning_commit_pushed"])

    # -- implementation gate ----------------------------------------------

    def test_record_implementation_gate_writes_passing_gate_and_updates_state(self) -> None:
        self.reach_planned()

        self.assert_ok(self.implementation_gate())

        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["state_transition"], {"from": "planned", "to": "ready-for-implementation"})
        state = self.state_now()
        self.assertEqual(state["state"], "ready-for-implementation")
        self.assertEqual(state["last_completed_step"], "implementation-gate")
        self.assertEqual(state["next_allowed_steps"], ["implement"])
        validator = self.run_validator("implementation-gate")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_implementation_gate_can_move_to_issue_clarifying(self) -> None:
        self.reach_planned()

        result = self.implementation_gate(
            DEFAULT_PROGRESS_URL,
            "--issue-actionable",
            "false",
            "--clarifying-question",
            "Which rollout behavior should this use?",
        )

        self.assertNotEqual(result.returncode, 0)
        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["state_transition"], {"from": "planned", "to": "issue-clarifying"})
        state = self.state_now()
        self.assertEqual(state["state"], "issue-clarifying")
        self.assertEqual(state["evidence"]["clarifying_question"], "Which rollout behavior should this use?")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_implementation_gate_fails_when_push_evidence_is_missing(self) -> None:
        self.reach_planned()
        state = self.state_now()
        state["evidence"]["planning_commit_pushed"] = False
        (self.issue_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = self.implementation_gate()

        self.assertNotEqual(result.returncode, 0)
        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        self.assertFalse(gate["ok"])
        self.assertFalse(gate["checks"]["planning_commit_pushed"])
        self.assertEqual(self.state_now()["state"], "blocked")

    def test_record_implementation_gate_blocks_without_clarifying_question(self) -> None:
        self.reach_planned()

        result = self.implementation_gate(DEFAULT_PROGRESS_URL, "--issue-actionable", "false")

        self.assertNotEqual(result.returncode, 0)
        state = self.state_now()
        self.assertEqual(state["state"], "blocked")

    # -- implement --------------------------------------------------------

    def test_record_implement_moves_ready_for_implementation_to_implementing(self) -> None:
        self.reach_ready_for_implementation()

        self.assert_ok(self.implement())

        state = self.state_now()
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "implement")
        self.assertIn("readiness-check", state["next_allowed_steps"])
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_implement_requires_ready_for_implementation(self) -> None:
        self.reach_planned()

        result = self.implement()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state_now()["state"], "planned")

    # -- readiness / review request ---------------------------------------

    def test_record_readiness_evidence_moves_state_to_ready_for_review_request(self) -> None:
        self.prepare_implementing_issue()

        self.assert_ok(self.readiness_evidence())

        evidence = json.loads((self.issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["commit_range"], "main...feat/example-42")
        self.assertEqual(evidence["progress_comment_url"], DEFAULT_PROGRESS_URL)
        state = self.state_now()
        self.assertEqual(state["state"], "ready-for-review-request")
        self.assertEqual(state["last_completed_step"], "readiness-check")
        self.assertEqual(state["next_allowed_steps"], ["create-review-request"])
        validator = self.run_validator("readiness-check")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_readiness_evidence_records_optional_scope_and_reviewer_notes(self) -> None:
        self.prepare_implementing_issue()

        self.assert_ok(
            self.readiness_evidence(
                "--scope",
                "Only the example module; excludes CLI changes.",
                "--reviewer-notes",
                "Focus on the state transitions.",
            )
        )

        evidence = json.loads((self.issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["scope"], "Only the example module; excludes CLI changes.")
        self.assertEqual(evidence["reviewer_notes"], "Focus on the state transitions.")
        validator = self.run_validator("readiness-check")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_readiness_evidence_requires_prior_local_self_review(self) -> None:
        self.reach_implementing()

        result = self.readiness_evidence()

        self.assertNotEqual(result.returncode, 0)
        state = self.state_now()
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "implement")

    def test_record_review_request_moves_state_to_ready_for_review(self) -> None:
        self.prepare_implementing_issue()
        self.assert_ok(self.readiness_evidence())

        self.assert_ok(self.review_request())

        state = self.state_now()
        self.assertEqual(state["state"], "ready-for-review")
        self.assertEqual(state["last_completed_step"], "create-review-request")
        self.assertEqual(state["next_allowed_steps"], ["machine-review-start"])
        self.assertEqual(state["evidence"]["review_request_url"], "https://github.com/owner/repo/pull/7")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_review_request_fails_without_readiness_check(self) -> None:
        self.prepare_implementing_issue()

        result = self.review_request()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state_now()["state"], "implementing")

    # -- machine review ---------------------------------------------------

    def test_machine_review_passed_moves_to_human_reviewing(self) -> None:
        self.reach_ready_for_review()

        self.assert_ok(self.machine_review_start())
        self.assertEqual(self.state_now()["state"], "machine-reviewing")
        self.assert_ok(self.machine_review_result("passed"))

        state = self.state_now()
        self.assertEqual(state["state"], "human-reviewing")
        self.assertEqual(state["last_completed_step"], "machine-review-result")
        self.assertEqual(state["next_allowed_steps"], ["human-review-result"])
        self.assertEqual(state["evidence"]["machine_review_result"], "passed")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_machine_review_failed_moves_to_machine_review_failed(self) -> None:
        self.reach_ready_for_review()
        self.assert_ok(self.machine_review_start())

        result = self.machine_review_result("failed")

        self.assertNotEqual(result.returncode, 0)
        state = self.state_now()
        self.assertEqual(state["state"], "machine-review-failed")
        self.assertIn("address-machine-feedback", state["next_allowed_steps"])
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_address_machine_feedback_returns_to_implementing(self) -> None:
        self.reach_ready_for_review()
        self.assert_ok(self.machine_review_start())
        self.assertNotEqual(self.machine_review_result("failed").returncode, 0)

        result = self.run_manager("record-address-machine-feedback", "--issue-dir", str(self.issue_dir))

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "address-machine-feedback")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    # -- human review -----------------------------------------------------

    def test_human_review_approved_then_review_complete(self) -> None:
        self.reach_human_reviewing()

        self.assert_ok(self.human_review_result("approved"))
        approved = self.state_now()
        self.assertEqual(approved["state"], "approved")
        self.assertEqual(approved["next_allowed_steps"], ["review-complete", "implement"])

        complete = self.run_manager("record-review-complete", "--issue-dir", str(self.issue_dir))
        self.assert_ok(complete)
        state = self.state_now()
        self.assertEqual(state["state"], "review-complete")
        self.assertEqual(state["last_completed_step"], "review-complete")
        self.assertEqual(state["next_allowed_steps"], [])
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_human_review_changes_requested_loops_back_to_implementing(self) -> None:
        self.reach_human_reviewing()

        self.assert_ok(self.human_review_result("changes-requested"))
        self.assertEqual(self.state_now()["state"], "changes-requested")

        result = self.run_manager("record-address-human-feedback", "--issue-dir", str(self.issue_dir))
        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "address-human-feedback")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_human_review_closed_moves_to_review_complete(self) -> None:
        self.reach_human_reviewing()

        self.assert_ok(self.human_review_result("closed"))

        state = self.state_now()
        self.assertEqual(state["state"], "review-complete")
        self.assertEqual(state["next_allowed_steps"], [])

    def test_review_complete_requires_approved_state(self) -> None:
        self.reach_human_reviewing()

        result = self.run_manager("record-review-complete", "--issue-dir", str(self.issue_dir))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state_now()["state"], "human-reviewing")

    # -- escape transitions ----------------------------------------------

    def test_record_block_moves_current_issue_to_blocked(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-block",
            "--issue-dir",
            str(self.issue_dir),
            "--reason",
            "Waiting for API credentials.",
        )

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "blocked")
        self.assertEqual(state["last_completed_step"], "block")
        self.assertEqual(state["next_allowed_steps"], [])
        self.assertEqual(state["evidence"]["block_reason"], "Waiting for API credentials.")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_clarify_moves_current_issue_to_issue_clarifying(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-clarify",
            "--issue-dir",
            str(self.issue_dir),
            "--question",
            "Which API version should this target?",
        )

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "issue-clarifying")
        self.assertEqual(state["last_completed_step"], "clarify")
        self.assertEqual(state["next_allowed_steps"], [])
        self.assertEqual(state["evidence"]["clarifying_question"], "Which API version should this target?")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_local_self_review_marks_review_evidence(self) -> None:
        self.reach_implementing()

        self.assert_ok(self.local_self_review())

        state = self.state_now()
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "local-self-review")
        self.assertIn("readiness-check", state["next_allowed_steps"])
        self.assertTrue(state["evidence"]["self_review_recorded"])
        self.assertEqual(state["evidence"]["self_review_progress_section"], "## Local Self-Review")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_handoff_updates_owner_without_changing_state(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-handoff",
            "--issue-dir",
            str(self.issue_dir),
            "--owner-kind",
            "github-actions",
            "--owner-id",
            "workflow-run-123",
            "--reason",
            "Hosted apply workflow owns the next transition.",
        )

        self.assert_ok(result)
        state = self.state_now()
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["owner"], {"kind": "github-actions", "id": "workflow-run-123"})
        self.assertEqual(state["last_completed_step"], "ownership-handoff")
        self.assertEqual(state["evidence"]["handoff_reason"], "Hosted apply workflow owns the next transition.")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_readiness_evidence_uses_gitlab_planning_links(self) -> None:
        self.assert_ok(self.init_state(platform="gitlab", repository="group/project"))
        self.write_planning_files()
        gitlab_progress_url = "https://gitlab.com/group/project/-/issues/42#note_1"
        self.assert_ok(self.publish_planning(gitlab_progress_url))
        self.assert_ok(self.implementation_gate(gitlab_progress_url))
        self.assert_ok(self.implement())
        self.assert_ok(self.local_self_review())

        self.assert_ok(self.readiness_evidence())

        evidence = json.loads((self.issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(
            evidence["planning_links"]["task_plan"],
            "https://gitlab.com/group/project/-/blob/feat/example-42/.gcw/issues/42/task_plan.md",
        )
        self.assertEqual(
            evidence["planning_links"]["findings"],
            "https://gitlab.com/group/project/-/blob/feat/example-42/.gcw/issues/42/findings.md",
        )


if __name__ == "__main__":
    unittest.main()
