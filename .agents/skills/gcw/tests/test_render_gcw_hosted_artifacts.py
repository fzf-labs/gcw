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

    def test_render_progress_comment_includes_state_and_planning_links(self) -> None:
        result = self.run_render("progress-comment", "--issue-dir", str(COMPLETE_FIXTURE))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("<!-- gcw-progress -->\n"))
        self.assertIn("GCW Status: ready-for-review-request", result.stdout)
        self.assertIn("Last completed step: readiness-check", result.stdout)
        self.assertIn("- Review request: Not created yet", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md", result.stdout)

    def test_render_review_request_body_includes_readiness_evidence(self) -> None:
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

    def test_render_progress_comment_can_derive_planning_links_before_readiness(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/43"
        issue_dir.mkdir(parents=True)
        (issue_dir / "state.json").write_text(
            """{
  "branch": "feat/example-43",
  "evidence": {
    "planning_commit_pushed": true,
    "planning_files_exist": true,
    "progress_comment_url": "https://github.com/owner/repo/issues/43#issuecomment-1",
    "review_request_url": "",
    "self_review_recorded": false
  },
  "issue": 43,
  "last_completed_step": "publish-planning",
  "next_allowed_steps": ["implementation-gate"],
  "owner": {"id": "workflow-run-1", "kind": "github-actions"},
  "platform": "github",
  "repository": "owner/repo",
  "state": "planning"
}
""",
            encoding="utf-8",
        )

        result = self.run_render("progress-comment", "--issue-dir", str(issue_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-43/.gcw/issues/43/task_plan.md", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-43/.gcw/issues/43/findings.md", result.stdout)
        self.assertIn("https://github.com/owner/repo/blob/feat/example-43/.gcw/issues/43/progress.md", result.stdout)

    def test_render_progress_comment_includes_handoff_reason_when_present(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/44"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        state = json.loads((issue_dir / "state.json").read_text(encoding="utf-8"))
        state["evidence"]["handoff_reason"] = "Hosted apply workflow owns the next transition."
        (issue_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

        result = self.run_render("progress-comment", "--issue-dir", str(issue_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Handoff reason: Hosted apply workflow owns the next transition.", result.stdout)


    def test_render_review_request_includes_optional_scope_and_reviewer_notes(self) -> None:
        issue_dir = Path(self.tmp.name) / ".gcw/issues/42"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        evidence = json.loads((issue_dir / "readiness_evidence.json").read_text(encoding="utf-8"))
        evidence["scope"] = "Only the example module."
        evidence["reviewer_notes"] = "Focus on the state transitions."
        (issue_dir / "readiness_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

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
