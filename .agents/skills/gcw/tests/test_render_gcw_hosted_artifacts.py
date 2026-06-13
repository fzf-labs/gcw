from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RENDER = ROOT / ".agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py"
MANAGER = ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"
COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class RenderGcwHostedArtifactsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_render(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RENDER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_manager(self, *args: str) -> None:
        result = subprocess.run(
            [sys.executable, str(MANAGER), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_render_progress_comment_uses_readiness_format_after_planned(self) -> None:
        result = self.run_render("progress-comment", "--issue-dir", str(COMPLETE_FIXTURE))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("<!-- gcw-progress -->\n"))
        self.assertIn("GCW Status: ready-for-review", result.stdout)
        self.assertIn("## Context", result.stdout)
        self.assertIn("## Triage", result.stdout)
        self.assertIn("- Type: enhancement", result.stdout)
        self.assertIn("- Area: area:tests", result.stdout)
        self.assertIn("- Priority: priority:p2", result.stdout)
        self.assertIn("## Readiness", result.stdout)
        self.assertIn("- Gate: passed", result.stdout)
        self.assertIn("python3 -m unittest discover -s .agents/skills/gcw/tests: passed", result.stdout)
        self.assertIn("## Risks", result.stdout)
        self.assertNotIn("## Planning files", result.stdout)
        self.assertNotIn("Review request:", result.stdout)

    def test_render_progress_comment_includes_planning_links_only_when_planned(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/43"
        issue_dir.mkdir(parents=True)
        self.run_manager(
            "init-workflow",
            "--issue-dir",
            str(issue_dir),
            "--issue",
            "43",
            "--platform",
            "github",
            "--repository",
            "owner/repo",
            "--branch",
            "feat/example-43",
            "--owner-kind",
            "github-actions",
            "--owner-id",
            "workflow-run-1",
        )
        self.run_manager("record-issue-prepare", "--issue-dir", str(issue_dir), "--ready")
        for name in ("task_plan.md", "findings.md", "progress.md"):
            (issue_dir / name).write_text(f"# {name}\n", encoding="utf-8")
        self.run_manager(
            "record-issue-to-spec",
            "--issue-dir",
            str(issue_dir),
            "--planning-commit-pushed",
            "--progress-comment-url",
            "https://github.com/owner/repo/issues/43#issuecomment-1",
        )

        result = self.run_render("progress-comment", "--issue-dir", str(issue_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-43/.gcw/issues/43/task_plan.md", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-43/.gcw/issues/43/findings.md", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-43/.gcw/issues/43/progress.md", result.stdout)
        self.assertIn("GCW Status: planned", result.stdout)
        self.assertIn("## Planning files", result.stdout)

    def test_render_progress_comment_uses_review_format_when_reviewing(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/45"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        self.run_manager(
            "record-pr-publish",
            "--issue-dir",
            str(issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
            "--body-hash",
            "sha256:body",
            "--target",
            "owner/repo#7",
        )

        result = self.run_render("progress-comment", "--issue-dir", str(issue_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GCW Status: reviewing", result.stdout)
        self.assertIn("## Review", result.stdout)
        self.assertIn("- Request: https://github.com/owner/repo/pull/7", result.stdout)
        self.assertNotIn("## Planning files", result.stdout)
        self.assertNotIn("## Readiness", result.stdout)

    def test_render_review_request_body_includes_implement_check_event_payload(self) -> None:
        result = self.run_render("review-request", "--issue-dir", str(COMPLETE_FIXTURE))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("<!-- gcw-review-request:start -->\n"))
        self.assertTrue(result.stdout.rstrip().endswith("<!-- gcw-review-request:end -->"))
        self.assertIn("feat: add example", result.stdout)
        self.assertIn("Adds the example capability.", result.stdout)
        self.assertIn("Closes #42", result.stdout)
        self.assertIn("python3 -m unittest discover -s .agents/skills/gcw/tests", result.stdout)
        self.assertIn("passed", result.stdout)
        self.assertIn("Low risk; fixture only.", result.stdout)
        self.assertIn("https://github.com/owner/repo/issues/42#issuecomment-1", result.stdout)

    def test_render_progress_comment_includes_active_feedback_when_present(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/44"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        self.run_manager(
            "record-pr-publish",
            "--issue-dir",
            str(issue_dir),
            "--review-request-url",
            "https://github.com/owner/repo/pull/7",
            "--body-hash",
            "sha256:body",
            "--target",
            "owner/repo#7",
        )
        self.run_manager(
            "record-pr-review",
            "--issue-dir",
            str(issue_dir),
            "--result",
            "changes-requested",
            "--reason",
            "Hosted apply workflow owns the next transition.",
        )

        result = self.run_render("progress-comment", "--issue-dir", str(issue_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GCW Status: changes-requested", result.stdout)
        self.assertIn("## Feedback", result.stdout)
        self.assertIn("- Reason: Hosted apply workflow owns the next transition.", result.stdout)
        self.assertIn("## Review", result.stdout)


    def test_render_review_request_includes_optional_scope_and_reviewer_notes(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        event_path = issue_dir / "events/005-gcw-implement-check.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["payload"]["scope"] = "Only the example module."
        event["payload"]["reviewer_notes"] = "Focus on the state transitions."
        event_path.write_text(json.dumps(event, indent=2), encoding="utf-8")
        self.run_manager("rebuild-projection", "--issue-dir", str(issue_dir))

        result = self.run_render("review-request", "--issue-dir", str(issue_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## Scope", result.stdout)
        self.assertIn("Only the example module.", result.stdout)
        self.assertIn("## Reviewer Notes", result.stdout)
        self.assertIn("Focus on the state transitions.", result.stdout)

    def test_merge_review_request_replaces_marked_section_and_preserves_manual_content(self) -> None:
        existing = Path(self.tmp.name) / "existing.md"
        rendered = Path(self.tmp.name) / "rendered.md"
        existing.write_text(
            "Manual intro written by a human.\n\n"
            "<!-- gcw-review-request:start -->\nOld generated body.\n<!-- gcw-review-request:end -->\n\n"
            "## Manual Release Notes\n\n- Keep me.\n",
            encoding="utf-8",
        )
        rendered.write_text(
            "<!-- gcw-review-request:start -->\nNew generated body.\n<!-- gcw-review-request:end -->\n",
            encoding="utf-8",
        )

        result = self.run_render(
            "merge-review-request",
            "--existing-file",
            str(existing),
            "--rendered-file",
            str(rendered),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Manual intro written by a human.", result.stdout)
        self.assertIn("New generated body.", result.stdout)
        self.assertNotIn("Old generated body.", result.stdout)
        self.assertIn("## Manual Release Notes", result.stdout)
        self.assertIn("- Keep me.", result.stdout)

    def test_merge_review_request_appends_generated_section_when_no_markers_exist(self) -> None:
        existing = Path(self.tmp.name) / "existing.md"
        rendered = Path(self.tmp.name) / "rendered.md"
        existing.write_text("Hand-written description without markers.\n", encoding="utf-8")
        rendered.write_text(
            "<!-- gcw-review-request:start -->\nGenerated body.\n<!-- gcw-review-request:end -->\n",
            encoding="utf-8",
        )

        result = self.run_render(
            "merge-review-request",
            "--existing-file",
            str(existing),
            "--rendered-file",
            str(rendered),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("Hand-written description without markers.\n"))
        self.assertIn("Generated body.", result.stdout)

    def test_merge_review_request_uses_rendered_body_when_existing_is_empty(self) -> None:
        existing = Path(self.tmp.name) / "existing.md"
        rendered = Path(self.tmp.name) / "rendered.md"
        existing.write_text("", encoding="utf-8")
        rendered.write_text(
            "<!-- gcw-review-request:start -->\nGenerated body.\n<!-- gcw-review-request:end -->\n",
            encoding="utf-8",
        )

        result = self.run_render(
            "merge-review-request",
            "--existing-file",
            str(existing),
            "--rendered-file",
            str(rendered),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("<!-- gcw-review-request:start -->"))
        self.assertIn("Generated body.", result.stdout)


if __name__ == "__main__":
    unittest.main()
