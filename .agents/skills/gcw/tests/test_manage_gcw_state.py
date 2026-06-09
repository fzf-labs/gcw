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

    def write_initial_state(self) -> None:
        result = self.run_manager(
            "init-state",
            "--issue-dir",
            str(self.issue_dir),
            "--issue",
            "42",
            "--platform",
            "github",
            "--repository",
            "owner/repo",
            "--branch",
            "feat/example-42",
            "--owner-kind",
            "local",
            "--owner-id",
            "cursor-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_state_writes_valid_planning_state(self) -> None:
        result = self.run_manager(
            "init-state",
            "--issue-dir",
            str(self.issue_dir),
            "--issue",
            "42",
            "--platform",
            "github",
            "--repository",
            "owner/repo",
            "--branch",
            "feat/example-42",
            "--owner-kind",
            "local",
            "--owner-id",
            "cursor-session",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "planning")
        self.assertEqual(state["last_completed_step"], "")
        self.assertEqual(state["next_allowed_steps"], ["create-issue-worktree", "create-planning-files", "publish-planning", "implementation-gate"])
        self.assertFalse(state["evidence"]["planning_files_exist"])
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_publish_planning_updates_planning_evidence(self) -> None:
        self.write_initial_state()
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text("# Progress\n", encoding="utf-8")

        result = self.run_manager(
            "record-publish-planning",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "planning")
        self.assertEqual(state["last_completed_step"], "publish-planning")
        self.assertEqual(state["next_allowed_steps"], ["implementation-gate"])
        self.assertTrue(state["evidence"]["planning_files_exist"])
        self.assertTrue(state["evidence"]["planning_commit_pushed"])

    def test_record_implementation_gate_writes_passing_gate_and_updates_state(self) -> None:
        self.write_initial_state()
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text("# Progress\n", encoding="utf-8")

        result = self.run_manager(
            "record-implementation-gate",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["state_transition"], {"from": "planning", "to": "implementing"})
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "implementation-gate")
        self.assertIn("readiness-check", state["next_allowed_steps"])
        validator = self.run_validator("implementation-gate")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_implementation_gate_can_move_to_clarifying(self) -> None:
        self.write_initial_state()
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text("# Progress\n", encoding="utf-8")

        result = self.run_manager(
            "record-implementation-gate",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
            "--issue-actionable",
            "false",
            "--clarifying-question",
            "Which rollout behavior should this use?",
        )

        self.assertNotEqual(result.returncode, 0)
        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["state_transition"], {"from": "planning", "to": "clarifying"})
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "clarifying")
        self.assertEqual(state["evidence"]["clarifying_question"], "Which rollout behavior should this use?")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def prepare_implementing_issue(self) -> None:
        self.write_initial_state()
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text(
            "# Progress\n\n## Local Self-Review\n\nDiff reviewed.\nValidation performed.\n",
            encoding="utf-8",
        )
        result = self.run_manager(
            "record-implementation-gate",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self_review = self.run_manager(
            "record-local-self-review",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-section",
            "## Local Self-Review",
        )
        self.assertEqual(self_review.returncode, 0, self_review.stderr)

    def prepare_implementing_issue_without_self_review(self) -> None:
        self.write_initial_state()
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text(
            "# Progress\n\n## Local Self-Review\n\nDiff reviewed.\nValidation performed.\n",
            encoding="utf-8",
        )
        result = self.run_manager(
            "record-implementation-gate",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/42#issuecomment-1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_record_readiness_evidence_writes_evidence_without_ready_transition(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
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
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads((self.issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["commit_range"], "main...feat/example-42")
        self.assertEqual(evidence["progress_comment_url"], "https://github.com/owner/repo/issues/42#issuecomment-1")
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "readiness-check")
        self.assertEqual(state["next_allowed_steps"], ["create-review-request"])
        validator = self.run_validator("readiness-check")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_readiness_evidence_requires_prior_local_self_review(self) -> None:
        self.prepare_implementing_issue_without_self_review()

        result = self.run_manager(
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
        )

        self.assertNotEqual(result.returncode, 0)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["last_completed_step"], "implementation-gate")

    def test_record_review_request_moves_state_to_ready_for_review(self) -> None:
        self.prepare_implementing_issue()
        readiness = self.run_manager(
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
        )
        self.assertEqual(readiness.returncode, 0, readiness.stderr)

        result = self.run_manager(
            "record-review-request",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "ready-for-review")
        self.assertEqual(state["last_completed_step"], "create-review-request")
        self.assertEqual(state["next_allowed_steps"], [])
        self.assertEqual(state["evidence"]["review_request_url"], "https://github.com/owner/repo/pull/7")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_review_request_fails_without_readiness_check(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-review-request",
            "--issue-dir",
            str(self.issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
        )

        self.assertNotEqual(result.returncode, 0)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "implementing")

    def test_record_block_moves_current_issue_to_blocked(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-block",
            "--issue-dir",
            str(self.issue_dir),
            "--reason",
            "Waiting for API credentials.",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "blocked")
        self.assertEqual(state["last_completed_step"], "block")
        self.assertEqual(state["next_allowed_steps"], [])
        self.assertEqual(state["evidence"]["block_reason"], "Waiting for API credentials.")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_clarify_moves_current_issue_to_clarifying(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-clarify",
            "--issue-dir",
            str(self.issue_dir),
            "--question",
            "Which API version should this target?",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "clarifying")
        self.assertEqual(state["last_completed_step"], "clarify")
        self.assertEqual(state["next_allowed_steps"], [])
        self.assertEqual(state["evidence"]["clarifying_question"], "Which API version should this target?")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_local_self_review_marks_review_evidence(self) -> None:
        self.prepare_implementing_issue()

        result = self.run_manager(
            "record-local-self-review",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-section",
            "## Local Self-Review",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
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

        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "implementing")
        self.assertEqual(state["owner"], {"kind": "github-actions", "id": "workflow-run-123"})
        self.assertEqual(state["last_completed_step"], "ownership-handoff")
        self.assertEqual(state["evidence"]["handoff_reason"], "Hosted apply workflow owns the next transition.")
        validator = self.run_validator("state")
        self.assertEqual(validator.returncode, 0, validator.stdout)

    def test_record_readiness_evidence_uses_gitlab_planning_links(self) -> None:
        result = self.run_manager(
            "init-state",
            "--issue-dir",
            str(self.issue_dir),
            "--issue",
            "42",
            "--platform",
            "gitlab",
            "--repository",
            "group/project",
            "--branch",
            "feat/example-42",
            "--owner-kind",
            "local",
            "--owner-id",
            "cursor-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text(
            "# Progress\n\n## Local Self-Review\n\nDiff reviewed.\nValidation performed.\n",
            encoding="utf-8",
        )
        gate = self.run_manager(
            "record-implementation-gate",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-comment-url",
            "https://gitlab.com/group/project/-/issues/42#note_1",
        )
        self.assertEqual(gate.returncode, 0, gate.stderr)
        self_review = self.run_manager(
            "record-local-self-review",
            "--issue-dir",
            str(self.issue_dir),
            "--progress-section",
            "## Local Self-Review",
        )
        self.assertEqual(self_review.returncode, 0, self_review.stderr)

        readiness = self.run_manager(
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
        )

        self.assertEqual(readiness.returncode, 0, readiness.stderr)
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
