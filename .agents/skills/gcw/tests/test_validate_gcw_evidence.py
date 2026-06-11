from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / ".agents/skills/gcw/scripts/validate_gcw_evidence.py"
COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class ValidateGcwEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        self.issue_dir.mkdir(parents=True)
        self.write_complete_issue_dir()

    def write_json(self, name: str, data: dict) -> None:
        (self.issue_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_complete_issue_dir(self) -> None:
        (self.issue_dir / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
        (self.issue_dir / "findings.md").write_text("# Findings\n", encoding="utf-8")
        (self.issue_dir / "progress.md").write_text(
            "# Progress\n\n## Local Self-Review\n\nDiff reviewed.\nValidation performed.\n",
            encoding="utf-8",
        )
        self.write_json(
            "state.json",
            {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "state": "ready-for-review-request",
                "branch": "feat/example-42",
                "owner": {"kind": "local", "id": "cursor-session"},
                "last_completed_step": "readiness-check",
                "next_allowed_steps": ["create-review-request"],
                "evidence": {
                    "planning_files_exist": True,
                    "planning_commit_pushed": True,
                    "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
                    "self_review_recorded": True,
                    "review_request_url": "",
                },
            },
        )
        self.write_json(
            "implementation_gate_result.json",
            {
                "step": "implementation-gate",
                "ok": True,
                "state_transition": {"from": "planned", "to": "ready-for-implementation"},
                "checks": {
                    "planning_files_exist": True,
                    "planning_commit_pushed": True,
                    "progress_comment_linked": True,
                    "issue_actionable": True,
                },
            },
        )
        self.write_json(
            "readiness_evidence.json",
            {
                "issue": 42,
                "branch": "feat/example-42",
                "base_branch": "main",
                "commit_range": "main...feat/example-42",
                "review_request": {
                    "title": "feat: add example",
                    "summary": "Adds the example capability.",
                    "issue_link": "Closes #42",
                },
                "validation": [{"command": "python3 -m unittest", "result": "passed"}],
                "local_self_review": {"recorded": True, "progress_section": "## Local Self-Review"},
                "planning_links": {
                    "task_plan": "https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "findings": "https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "progress": "https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                },
                "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
                "risks": "Low risk; documentation-only example.",
            },
        )

    def run_validator(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), command, "--issue-dir", str(self.issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_validator_for_path(self, command: str, issue_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), command, "--issue-dir", str(issue_dir)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_checked_in_complete_fixture_passes_all_validators(self) -> None:
        for command in ("state", "implementation-gate", "readiness-check"):
            with self.subTest(command=command):
                result = self.run_validator_for_path(command, COMPLETE_FIXTURE)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_state_check_accepts_complete_state(self) -> None:
        result = self.run_validator("state")

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])
        self.assertEqual(output["step"], "state")

    def test_state_check_requires_owner_id(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        del state["owner"]["id"]
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("owner.id is missing", output["errors"])

    def test_state_check_rejects_non_string_owner_id(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["owner"]["id"] = 123
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("owner.id must be a string", output["errors"])

    def test_state_check_rejects_next_steps_outside_transition_table(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "ready-for-review"
        state["last_completed_step"] = "create-review-request"
        state["next_allowed_steps"] = ["readiness-check"]
        state["evidence"]["review_request_url"] = "https://github.com/owner/repo/pull/7"
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn(
            "next_allowed_steps contains steps not allowed from ready-for-review: readiness-check",
            output["errors"],
        )

    def test_state_check_accepts_ready_for_review_after_create_review_request(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "ready-for-review"
        state["last_completed_step"] = "create-review-request"
        state["next_allowed_steps"] = ["machine-review-start"]
        state["evidence"]["review_request_url"] = "https://github.com/owner/repo/pull/7"
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertEqual(result.returncode, 0, result.stdout)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])

    def test_state_check_requires_readiness_evidence_for_review_request_state(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "ready-for-review-request"
        state["last_completed_step"] = "readiness-check"
        state["next_allowed_steps"] = ["create-review-request"]
        self.write_json("state.json", state)
        (self.issue_dir / "readiness_evidence.json").unlink()

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("ready-for-review-request requires readiness_evidence.json", output["errors"])

    def test_state_check_rejects_planned_without_planning_files(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "planned"
        state["last_completed_step"] = "publish-planning"
        state["next_allowed_steps"] = ["implementation-gate"]
        self.write_json("state.json", state)
        (self.issue_dir / "findings.md").unlink()

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("findings.md is missing", output["errors"])

    def test_state_check_rejects_planned_without_push_evidence(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "planned"
        state["last_completed_step"] = "publish-planning"
        state["next_allowed_steps"] = ["implementation-gate"]
        state["evidence"]["planning_commit_pushed"] = False
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("planned requires evidence.planning_commit_pushed", output["errors"])

    def test_state_check_rejects_implementing_without_passing_gate(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "implementing"
        state["last_completed_step"] = "implement"
        state["next_allowed_steps"] = ["readiness-check"]
        self.write_json("state.json", state)
        (self.issue_dir / "implementation_gate_result.json").unlink()

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("implementing requires passing implementation_gate_result.json", output["errors"])

    def test_state_check_rejects_inconsistent_machine_reviewing_state(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "machine-reviewing"
        state["last_completed_step"] = "review-complete"
        state["next_allowed_steps"] = []
        state["evidence"]["review_request_url"] = "https://github.com/owner/repo/pull/7"
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn(
            "machine-reviewing requires last_completed_step machine-review-start",
            output["errors"],
        )
        self.assertIn(
            "machine-reviewing requires next_allowed_steps to include machine-review-result",
            output["errors"],
        )

    def test_state_check_rejects_approved_without_human_review_result(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "approved"
        state["last_completed_step"] = "machine-review-result"
        state["next_allowed_steps"] = ["review-complete", "implement"]
        state["evidence"]["review_request_url"] = "https://github.com/owner/repo/pull/7"
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("approved requires last_completed_step human-review-result", output["errors"])

    def test_implementation_gate_accepts_complete_evidence(self) -> None:
        result = self.run_validator("implementation-gate")

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])

    def test_implementation_gate_rejects_state_that_still_says_planned(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "planned"
        state["last_completed_step"] = "publish-planning"
        state["next_allowed_steps"] = ["implementation-gate"]
        self.write_json("state.json", state)

        result = self.run_validator("implementation-gate")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn(
            "implementation gate requires state.json state to advance beyond planned",
            output["errors"],
        )
        self.assertEqual(output["step"], "implementation-gate")

    def test_implementation_gate_accepts_clarifying_pause_evidence(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "issue-clarifying"
        state["last_completed_step"] = "implementation-gate"
        state["next_allowed_steps"] = []
        state["evidence"]["clarifying_question"] = "Which rollout behavior should this use?"
        self.write_json("state.json", state)
        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        gate["ok"] = False
        gate["state_transition"]["to"] = "issue-clarifying"
        gate["checks"]["issue_actionable"] = False
        gate["errors"] = ["implementation gate evidence is incomplete or the issue needs clarification"]
        self.write_json("implementation_gate_result.json", gate)

        result = self.run_validator("implementation-gate")

        self.assertEqual(result.returncode, 0, result.stdout)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])

    def test_implementation_gate_requires_all_planning_files(self) -> None:
        (self.issue_dir / "findings.md").unlink()

        result = self.run_validator("implementation-gate")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("findings.md is missing", output["errors"])

    def test_readiness_check_accepts_complete_evidence(self) -> None:
        result = self.run_validator("readiness-check")

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["ok"])
        self.assertEqual(output["step"], "readiness-check")

    def test_readiness_check_requires_local_self_review(self) -> None:
        evidence = json.loads((self.issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        evidence["local_self_review"]["recorded"] = False
        self.write_json("readiness_evidence.json", evidence)

        result = self.run_validator("readiness-check")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("local self-review is not recorded", output["errors"])

    def test_readiness_check_requires_v1_schema_fields(self) -> None:
        evidence = json.loads((self.issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        del evidence["commit_range"]
        del evidence["progress_comment_url"]
        self.write_json("readiness_evidence.json", evidence)

        result = self.run_validator("readiness-check")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("commit_range is missing", output["errors"])
        self.assertIn("progress_comment_url is missing", output["errors"])

    def test_readiness_check_requires_passing_implementation_gate_for_implementing_state(self) -> None:
        (self.issue_dir / "implementation_gate_result.json").unlink()

        result = self.run_validator("readiness-check")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn(
            "implementation gate: implementation_gate_result.json is missing",
            output["errors"],
        )

    def test_readiness_check_rejects_valid_but_non_passing_gate(self) -> None:
        gate = json.loads((self.issue_dir / "implementation_gate_result.json").read_text(encoding="utf-8"))
        gate["ok"] = False
        gate["state_transition"]["to"] = "issue-clarifying"
        gate["checks"]["issue_actionable"] = False
        gate["errors"] = ["implementation gate evidence is incomplete or the issue needs clarification"]
        self.write_json("implementation_gate_result.json", gate)

        result = self.run_validator("readiness-check")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("readiness-check requires passing implementation gate", output["errors"])

    def test_readiness_check_requires_ready_for_review_request_state(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "implementing"
        state["last_completed_step"] = "local-self-review"
        state["next_allowed_steps"] = ["readiness-check"]
        self.write_json("state.json", state)

        result = self.run_validator("readiness-check")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("readiness-check must leave state.json state as ready-for-review-request", output["errors"])

    def test_readiness_check_requires_readiness_check_completion(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["last_completed_step"] = "something-else"
        self.write_json("state.json", state)

        result = self.run_validator("readiness-check")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("ready-for-review-request requires last_completed_step readiness-check", output["errors"])

    def test_implementation_gate_rejects_ready_for_review_without_review_request(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "ready-for-review"
        state["last_completed_step"] = "create-review-request"
        state["next_allowed_steps"] = []
        state["evidence"]["review_request_url"] = ""
        self.write_json("state.json", state)

        result = self.run_validator("implementation-gate")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("ready-for-review requires state.json evidence.review_request_url", output["errors"])

    def test_state_check_rejects_review_complete_without_completion_result(self) -> None:
        state = json.loads((self.issue_dir / "state.json").read_text(encoding="utf-8"))
        state["state"] = "review-complete"
        state["last_completed_step"] = "review-complete"
        state["next_allowed_steps"] = []
        state["evidence"]["review_request_url"] = "https://github.com/owner/repo/pull/7"
        self.write_json("state.json", state)

        result = self.run_validator("state")

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("review-complete requires state.json evidence.review_complete_result", output["errors"])


if __name__ == "__main__":
    unittest.main()
