from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml
import json

ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPTS = ROOT / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from prepare_gcw_hosted_step import prepare  # noqa: E402


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


class PrepareHostedStepTest(unittest.TestCase):
    def test_prepare_allows_implement_from_implementing(self) -> None:
        issue_dir = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"
        projection = json.loads((issue_dir / "workflow.json").read_text(encoding="utf-8"))
        projection["projection"]["phase"] = "implementing"
        with tempfile.TemporaryDirectory() as temp_root:
            temp_dir = Path(temp_root) / "prepare-implement"
            temp_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "workflow.json").write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")
            result = prepare("gcw-implement", temp_dir, "99", "gcw/issue-99")
            self.assertTrue(result["should_run"])
            self.assertEqual(result["issue_branch"], "gcw/issue-99")

    def test_prepare_blocks_spec_check_while_implementing(self) -> None:
        issue_dir = ROOT / ".gcw/issues/12"
        result = prepare("gcw-spec-check", issue_dir, "12", "")
        self.assertFalse(result["should_run"])
        self.assertIn("planned", result["skip_reason"])


if __name__ == "__main__":
    unittest.main()
