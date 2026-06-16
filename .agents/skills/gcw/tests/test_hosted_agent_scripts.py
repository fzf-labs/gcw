from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from finalize_gcw_hosted_step import commit_push, has_changes  # noqa: E402
from gcw_executor_gate import EXECUTOR_HOSTED, EXECUTOR_LOCAL  # noqa: E402
from gcw_workflow_event import comment_requests_step, resolve, should_run_event  # noqa: E402
from prepare_issue_handoff_context import issue_branch, prepare as prepare_handoff  # noqa: E402
from validate_handoff_json import validate  # noqa: E402


class GcwWorkflowEventTest(unittest.TestCase):
    def test_comment_requests_explicit_step_command(self) -> None:
        self.assertTrue(comment_requests_step("@gcw-bot /gcw issue-to-spec", "gcw-bot", "gcw-issue-to-spec"))
        self.assertTrue(comment_requests_step("@gcw-bot /gcw to-spec", "gcw-bot", "gcw-issue-to-spec"))
        self.assertFalse(comment_requests_step("@gcw-bot /gcw implement", "gcw-bot", "gcw-issue-to-spec"))

    def test_comment_requests_legacy_mention_for_compatibility(self) -> None:
        self.assertTrue(comment_requests_step("@gcw-bot please continue", "gcw-bot", "gcw-issue-to-spec"))

    def test_should_run_on_trigger_label(self) -> None:
        ok, reason = should_run_event(
            "gcw-issue-to-spec",
            {
                "event_name": "issues",
                "action": "labeled",
                "issue": {
                    "labels": [
                        {"name": "gcw:ready-for-planning"},
                        {"name": EXECUTOR_HOSTED},
                    ],
                    "assignees": [{"login": "gcw-bot"}],
                },
                "label": {"name": "gcw:ready-for-planning"},
                "pull_request": None,
            },
            "gcw-bot",
        )
        self.assertTrue(ok)
        self.assertIn("gcw:ready-for-planning", reason)

    def test_should_not_run_without_executor_hosted(self) -> None:
        ok, reason = should_run_event(
            "gcw-issue-to-spec",
            {
                "event_name": "issues",
                "action": "labeled",
                "issue": {
                    "labels": [{"name": "gcw:ready-for-planning"}, {"name": EXECUTOR_LOCAL}],
                    "assignees": [{"login": "gcw-bot"}],
                },
                "label": {"name": "gcw:ready-for-planning"},
                "pull_request": None,
            },
            "gcw-bot",
        )
        self.assertFalse(ok)
        self.assertIn(EXECUTOR_LOCAL, reason)

    @patch("gcw_workflow_event.fetch_issue_labels_github", return_value=["gcw:executor-hosted"])
    def test_dispatch_resolve_requires_executor_hosted(self, _fetch) -> None:
        result = resolve(
            step="gcw-issue-to-spec",
            event_name="workflow_dispatch",
            event_path="",
            dispatch_issue_number="12",
            dispatch_issue_branch="",
            dispatch_dry_run="false",
            agent_login="",
            repo="owner/repo",
        )
        self.assertTrue(result["should_trigger"])
        self.assertEqual(result["issue_number"], "12")
        self.assertNotIn("execution_mode", result)

    @patch("gcw_workflow_event.fetch_issue_labels_github", return_value=["gcw:executor-local"])
    def test_dispatch_resolve_blocks_without_executor_hosted(self, _fetch) -> None:
        result = resolve(
            step="gcw-issue-to-spec",
            event_name="workflow_dispatch",
            event_path="",
            dispatch_issue_number="12",
            dispatch_issue_branch="",
            dispatch_dry_run="false",
            agent_login="",
            repo="owner/repo",
        )
        self.assertFalse(result["should_trigger"])
        self.assertIn(EXECUTOR_LOCAL, result["trigger_reason"])


class ValidateHandoffJsonTest(unittest.TestCase):
    def test_validate_triage_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "triage_result.json"
            path.write_text(
                json.dumps(
                    {
                        "classification_type": "enhancement",
                        "classification_priority": "priority:p2",
                        "labels_applied": ["triaged"],
                    }
                ),
                encoding="utf-8",
            )
            data = validate("triage_result.json", path)
            self.assertEqual(data["classification_type"], "enhancement")


class PrepareHandoffTest(unittest.TestCase):
    def test_issue_branch_default(self) -> None:
        self.assertEqual(issue_branch("9", ""), "gcw/issue-9")

    @patch("prepare_issue_handoff_context.fetch_comments")
    @patch("prepare_issue_handoff_context.fetch_issue")
    def test_prepare_to_spec_context(self, fetch_issue, fetch_comments) -> None:
        fetch_issue.return_value = {
            "title": "Test",
            "body": "Body",
            "labels": [],
            "assignees": [],
            "html_url": "https://example.test/1",
        }
        fetch_comments.return_value = []
        issue_dir = ROOT / ".gcw/issues/12"
        with tempfile.TemporaryDirectory() as temp_dir:
            result = prepare_handoff(
                repo="fzf-labs/gcw",
                issue_number="12",
                step="gcw-issue-to-spec",
                issue_dir=issue_dir,
                issue_branch_input="",
                output_dir=Path(temp_dir),
            )
            self.assertTrue(result["issue_context"])
            context = json.loads(Path(result["issue_context"]).read_text(encoding="utf-8"))
            self.assertEqual(context["step"], "gcw-issue-to-spec")
            self.assertIn("gcw-issue-to-spec", context["skill_paths"][-1])


class FinalizeHostedStepTest(unittest.TestCase):
    def test_has_changes_false_on_clean_tree(self) -> None:
        self.assertFalse(has_changes(["README.md"]))


if __name__ == "__main__":
    unittest.main()
