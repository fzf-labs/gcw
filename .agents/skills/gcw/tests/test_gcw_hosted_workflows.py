from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import shutil
from pathlib import Path

import yaml
import json

ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPTS = ROOT / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))

from prepare_gcw_hosted_step import prepare  # noqa: E402
from gcw_executor_gate import EXECUTOR_HOSTED, EXECUTOR_LOCAL  # noqa: E402


EXPECTED_WORKFLOWS = {
    "gcw-issue-triage.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "apply_triage_from_handoff.py",
            "run_gcw_step.py --step gcw-issue-triage",
        ],
    },
    "gcw-issue-clarify.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "build_clarify_options.py",
            "run_gcw_step.py --step gcw-issue-clarify",
        ],
    },
    "gcw-issue-to-spec.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "prepare_issue_handoff_context.py",
            "gcw-run-codex",
            "finalize_gcw_hosted_step.py",
            "run_gcw_step.py --step gcw-issue-to-spec",
        ],
    },
    "gcw-spec-check.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "validate_gcw_evidence.py workflow",
            "run_gcw_step.py --step gcw-spec-check",
        ],
    },
    "gcw-implement.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "record_implement_milestone.py",
        ],
    },
    "gcw-implement-check.yml": {
        "permissions": {"contents": "write", "issues": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "gcw-run-codex",
            "run_gcw_step.py --step gcw-implement-check",
        ],
    },
    "gcw-pr-publish.yml": {
        "permissions": {"contents": "read", "issues": "write", "pull-requests": "write"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "finalize_gcw_hosted_step.py upsert-pr",
            "run_gcw_step.py --step gcw-pr-publish",
        ],
    },
    "gcw-pr-review.yml": {
        "permissions": {"contents": "write", "issues": "write", "pull-requests": "read"},
        "commands": [
            "gcw_workflow_event.py",
            "prepare_gcw_hosted_step.py",
            "validate_gcw_evidence.py workflow",
            "run_gcw_step.py --step gcw-pr-review",
        ],
    },
}

HOSTED_AGENT_WORKFLOWS = {
    "gcw-issue-triage.yml",
    "gcw-issue-clarify.yml",
    "gcw-issue-to-spec.yml",
    "gcw-implement.yml",
    "gcw-implement-check.yml",
}

CODEX_WORKFLOWS = HOSTED_AGENT_WORKFLOWS | {"gcw-pr-review.yml"}


def workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def workflow_data(name: str) -> dict:
    return yaml.safe_load(workflow_text(name))


def workflow_triggers(name: str) -> dict:
    data = workflow_data(name)
    return data.get("on") or data[True]


class HostedWorkflowYamlTest(unittest.TestCase):
    def test_all_expected_workflow_files_exist(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            self.assertTrue((WORKFLOWS / name).is_file(), msg=name)

    def test_workflows_use_workflow_dispatch_inputs(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            dispatch = workflow_triggers(name)["workflow_dispatch"]
            self.assertIn("issue_number", dispatch["inputs"], msg=name)
            self.assertIn("issue_branch", dispatch["inputs"], msg=name)
            self.assertIn("dry_run", dispatch["inputs"], msg=name)
            self.assertNotIn("execution_mode", dispatch["inputs"], msg=name)

    def test_workflows_are_hosted_agent_only(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            text = workflow_text(name)
            self.assertNotIn("execution_mode", text, msg=name)
            self.assertNotIn("local-handoff", text, msg=name)

    def test_workflows_declare_event_triggers(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            triggers = workflow_triggers(name)
            self.assertIn("issues", triggers, msg=name)
            self.assertIn("issue_comment", triggers, msg=name)

    def test_workflows_declare_permissions_and_required_commands(self) -> None:
        for name, expected in EXPECTED_WORKFLOWS.items():
            data = workflow_data(name)
            self.assertEqual(data["permissions"], expected["permissions"], msg=name)
            text = workflow_text(name)
            for command in expected["commands"]:
                self.assertIn(command, text, msg=f"{name}: {command}")

    def test_shared_setup_action_is_used(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            self.assertIn("./.github/actions/gcw-setup", workflow_text(name), msg=name)

    def test_hosted_agent_workflows_include_codex_action(self) -> None:
        for name in HOSTED_AGENT_WORKFLOWS:
            self.assertIn("gcw-run-codex", workflow_text(name), msg=name)

    def test_issue_event_workflows_gate_executor_labels_in_job_if(self) -> None:
        for name in EXPECTED_WORKFLOWS:
            text = workflow_text(name)
            self.assertIn("contains(github.event.issue.labels.*.name, 'gcw:executor-hosted')", text, msg=name)
            self.assertIn("!contains(github.event.issue.labels.*.name, 'gcw:executor-local')", text, msg=name)

    def test_codex_workflows_upload_handoff_artifacts(self) -> None:
        for name in CODEX_WORKFLOWS:
            text = workflow_text(name)
            self.assertIn("actions/upload-artifact@", text, msg=name)
            self.assertIn(".gcw-runtime/handoff", text, msg=name)

    def test_pr_review_uses_preflight_job_before_review_work(self) -> None:
        data = workflow_data("gcw-pr-review.yml")
        jobs = data["jobs"]
        self.assertIn("preflight", jobs)
        self.assertIn("pr-review", jobs)
        self.assertEqual(jobs["pr-review"]["needs"], "preflight")
        self.assertIn("needs.preflight.outputs.should_trigger == 'true'", jobs["pr-review"]["if"])

    def test_triage_workflow_splits_preflight_classify_finalize(self) -> None:
        data = workflow_data("gcw-issue-triage.yml")
        jobs = data["jobs"]
        self.assertIn("preflight", jobs)
        self.assertIn("classify", jobs)
        self.assertIn("finalize", jobs)
        self.assertEqual(jobs["classify"]["needs"], "preflight")
        self.assertEqual(jobs["finalize"]["needs"], ["preflight", "classify"])


class PrepareHostedStepTest(unittest.TestCase):
    def test_prepare_allows_implement_from_implementing(self) -> None:
        issue_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((issue_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "implementing"
        projection["projection"]["last_completed_step"] = "gcw-implement"
        projection["projection"]["next_allowed_steps"] = ["gcw-implement", "gcw-implement-check"]
        with tempfile.TemporaryDirectory() as temp_root:
            temp_dir = Path(temp_root) / "prepare-implement"
            temp_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            shutil.copytree(issue_dir / "events", temp_dir / "events")
            result = prepare("gcw-implement", temp_dir, "99", "gcw/issue-99", issue_labels=[EXECUTOR_HOSTED])
            self.assertTrue(result["should_run"])
            self.assertEqual(result["issue_branch"], "gcw/issue-99")

    def test_prepare_blocks_spec_check_while_implementing(self) -> None:
        issue_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((issue_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "implementing"
        projection["projection"]["last_completed_step"] = "gcw-implement"
        with tempfile.TemporaryDirectory() as temp_root:
            temp_dir = Path(temp_root) / "prepare-spec-check"
            temp_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            shutil.copytree(issue_dir / "events", temp_dir / "events")
            result = prepare("gcw-spec-check", temp_dir, "99", "", issue_labels=[EXECUTOR_HOSTED])
            self.assertFalse(result["should_run"])
            self.assertIn("superseded", result["skip_reason"])

    def test_prepare_blocks_without_executor_hosted(self) -> None:
        issue_dir = ROOT / ".gcw/issues/12"
        result = prepare(
            "gcw-spec-check",
            issue_dir,
            "12",
            "",
            issue_labels=[EXECUTOR_LOCAL],
        )
        self.assertFalse(result["should_run"])
        self.assertIn(EXECUTOR_LOCAL, result["skip_reason"])

    def test_prepare_allows_implement_with_executor_hosted(self) -> None:
        fixture_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((fixture_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "ready-for-implementation"
        projection["projection"]["last_completed_step"] = "gcw-spec-check"
        projection["projection"]["next_allowed_steps"] = ["gcw-implement"]
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            result = prepare(
                "gcw-implement",
                issue_dir,
                "17",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
            self.assertTrue(result["should_run"])
            self.assertEqual(result["executor_gate"], EXECUTOR_HOSTED)

    def test_prepare_pr_review_verify_only_when_already_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            shutil.copytree(ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue", issue_dir)
            from manage_gcw_workflow import main as manage_main  # noqa: E402

            def run_manager(*args: str) -> None:
                manage_main(list(args))

            run_manager(
                "record-pr-publish",
                "--issue-dir",
                str(issue_dir),
                "--review-request-url",
                "https://github.com/owner/repo/pull/7",
                "--body-hash",
                "sha256:" + "a" * 64,
                "--target",
                "owner/repo#7",
                "--progress-comment-url",
                "https://github.com/owner/repo/issues/42#issuecomment-6",
            )
            run_manager(
                "record-pr-review",
                "--issue-dir",
                str(issue_dir),
                "--result",
                "passed",
                "--progress-comment-url",
                "https://github.com/owner/repo/issues/42#issuecomment-7",
            )
            result = prepare(
                "gcw-pr-review",
                issue_dir,
                "42",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
        self.assertTrue(result["should_run"])
        self.assertEqual(result["run_mode"], "verify-only")
        self.assertEqual(result["validate_command"], "review-check")
        self.assertFalse(result["record_step"])

    def test_prepare_skips_completed_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            issue_dir = Path(temp_root) / "issue"
            shutil.copytree(ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue", issue_dir)
            from manage_gcw_workflow import main as manage_main  # noqa: E402

            manage_main(
                [
                    "record-pr-publish",
                    "--issue-dir",
                    str(issue_dir),
                    "--review-request-url",
                    "https://github.com/owner/repo/pull/7",
                    "--body-hash",
                    "sha256:" + "a" * 64,
                    "--target",
                    "owner/repo#7",
                    "--progress-comment-url",
                    "https://github.com/owner/repo/issues/42#issuecomment-6",
                ]
            )
            result = prepare(
                "gcw-pr-publish",
                issue_dir,
                "42",
                "",
                issue_labels=[EXECUTOR_HOSTED],
            )
        self.assertFalse(result["should_run"])
        self.assertIn("already completed", result["skip_reason"])


if __name__ == "__main__":
    unittest.main()
