from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / ".agents" / "skills" / "gcw" / "scripts"
sys.path.insert(0, str(ROOT / ".gcw" / "engine" / "platforms"))
sys.path.insert(0, str(ROOT / ".gcw" / "engine" / "runtime"))
sys.path.insert(0, str(SCRIPTS))

from verify_gcw_remote_evidence import (  # noqa: E402
    normalize_body,
    resolve_review_request_url,
    verify_progress_comment,
    verify_review_request,
)


VERIFY = ROOT / ".agents/skills/gcw/scripts/verify_gcw_remote_evidence.py"
RENDER = ROOT / ".agents/skills/gcw/scripts/render_gcw_hosted_artifacts.py"
COMPLETE_FIXTURE = ROOT / ".agents/skills/gcw/tests/fixtures/complete_issue"


class VerifyGcwRemoteEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)

    def run_verify(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def render_artifact(self, command: str, issue_dir: Path) -> str:
        result = subprocess.run(
            [sys.executable, str(RENDER), command, "--issue-dir", str(issue_dir)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout

    def test_progress_comment_verification_accepts_rendered_body(self) -> None:
        comment_path = self.tmp_path / "progress-comment.md"
        comment_path.write_text(self.render_artifact("progress-comment", COMPLETE_FIXTURE), encoding="utf-8")

        result = self.run_verify(
            "progress-comment",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(comment_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-progress-comment")
        self.assertTrue(output["ok"])

    def test_progress_comment_verification_rejects_mismatched_body(self) -> None:
        comment_path = self.tmp_path / "progress-comment.md"
        comment_path.write_text(
            "\n".join(
                [
                    "<!-- gcw-progress -->",
                    "GCW Status: ready-for-review",
                    "",
                    "## Context",
                    "- Issue: 42",
                    "- Branch: feat/example-42",
                    "- Owner: local/cursor-session",
                    "- Last completed step: gcw-implement-check",
                    "",
                    "## Readiness",
                    "- Gate: passed",
                    "",
                    "## Risks",
                    "completely different",
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_verify(
            "progress-comment",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(comment_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("remote progress comment does not match rendered body", output["errors"])

    def test_progress_comment_verification_rejects_unmarked_planning_links_comment(self) -> None:
        comment_path = self.tmp_path / "planning-links-comment.md"
        comment_path.write_text(
            "\n".join(
                [
                    "## GCW Planning Spec",
                    "",
                    "Planning files for issue #42 are on branch `feat/example-42`:",
                    "",
                    "- [task_plan.md](https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md)",
                    "- [findings.md](https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md)",
                    "- [progress.md](https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md)",
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_verify(
            "progress-comment",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(comment_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("remote progress comment is missing gcw progress marker", output["errors"])

    def test_progress_comment_verification_rejects_recorded_body_hash_mismatch(self) -> None:
        issue_dir = self.tmp_path / "issue"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        latest_file = sorted((issue_dir / "events").glob("*gcw-implement-check*.json"))[-1]
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        data["payload"]["progress_comment_body_hash"] = "sha256:" + "0" * 64
        latest_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"),
                "rebuild-projection",
                "--issue-dir",
                str(issue_dir),
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        comment_path = self.tmp_path / "progress-comment.md"
        comment_path.write_text(self.render_artifact("progress-comment", issue_dir), encoding="utf-8")

        result = self.run_verify(
            "progress-comment",
            "--issue-dir",
            str(issue_dir),
            "--remote-file",
            str(comment_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertTrue(any("progress comment body hash" in e for e in output["errors"]))

    def test_review_request_verification_accepts_rendered_body(self) -> None:
        body_path = self.tmp_path / "review-request.md"
        body_path.write_text(self.render_artifact("review-request", COMPLETE_FIXTURE), encoding="utf-8")

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(body_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["step"], "remote-review-request")
        self.assertTrue(output["ok"])

    def test_review_request_verification_rejects_body_hash_mismatch(self) -> None:
        issue_dir = self.tmp_path / "issue"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        body_text = self.render_artifact("review-request", issue_dir)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"),
                "record-pr-publish",
                "--issue-dir",
                str(issue_dir),
                "--review-request-url",
                "https://github.com/owner/repo/pull/7",
                "--body-hash",
                "sha256:" + "b" * 64,
                "--target",
                "owner/repo#7",
                "--progress-comment-url",
                "https://github.com/owner/repo/issues/42#issuecomment-6",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        body_path = self.tmp_path / "review-request.md"
        body_path.write_text(body_text, encoding="utf-8")

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(issue_dir),
            "--remote-file",
            str(body_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertTrue(any("body hash" in e for e in output["errors"]))

    def test_review_request_verification_rejects_body_without_markers(self) -> None:
        body_path = self.tmp_path / "review-request.md"
        body_path.write_text(
            "\n".join(
                [
                    "feat: add example",
                    "Adds the example capability.",
                    "Closes #42",
                    "## Validation",
                    "- python3 -m unittest discover -s .agents/skills/gcw/tests: passed",
                    "## Planning",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/task_plan.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/findings.md",
                    "- https://github.com/owner/repo/blob/feat/example-42/.gcw/issues/42/progress.md",
                    "## Progress Comment",
                    "https://github.com/owner/repo/issues/42#issuecomment-2",
                    "## Risks",
                    "Low risk; fixture only.",
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_verify(
            "review-request",
            "--issue-dir",
            str(COMPLETE_FIXTURE),
            "--remote-file",
            str(body_path),
        )

        self.assertNotEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertFalse(output["ok"])
        self.assertIn("remote review request is missing gcw review request markers", output["errors"])

    def test_progress_comment_verification_fetches_from_projection_url(self) -> None:
        rendered = self.render_artifact("progress-comment", COMPLETE_FIXTURE)

        def fetcher(url: str) -> str:
            self.assertEqual(url, "https://github.com/owner/repo/issues/42#issuecomment-5")
            return rendered

        args = argparse.Namespace(
            issue_dir=COMPLETE_FIXTURE,
            remote_file=None,
            fetch_url="",
            progress_comment_url="",
            fetcher=fetcher,
        )
        output = verify_progress_comment(args)
        self.assertTrue(output["ok"], output["errors"])

    def test_progress_comment_verification_reports_missing_projection_url(self) -> None:
        issue_dir = self.tmp_path / "issue"
        (issue_dir / "events").mkdir(parents=True)
        shutil.copy(
            COMPLETE_FIXTURE / "events" / "000-gcw-issue-intake.json",
            issue_dir / "events" / "000-gcw-issue-intake.json",
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"),
                "rebuild-projection",
                "--issue-dir",
                str(issue_dir),
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        args = argparse.Namespace(
            issue_dir=issue_dir,
            remote_file=None,
            fetch_url="",
            progress_comment_url="",
            fetcher=lambda _url: "unused",
        )
        output = verify_progress_comment(args)
        self.assertFalse(output["ok"])
        self.assertTrue(
            any("progress_comment_url is missing from projection refs" in error for error in output["errors"])
        )

    def test_review_request_verification_fetches_with_explicit_url(self) -> None:
        issue_dir = self.tmp_path / "issue"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        body_text = self.render_artifact("review-request", issue_dir)

        def fetcher(url: str) -> str:
            self.assertEqual(url, "https://github.com/owner/repo/pull/7")
            return body_text

        args = argparse.Namespace(
            issue_dir=issue_dir,
            remote_file=None,
            fetch_url="https://github.com/owner/repo/pull/7",
            review_request_url="",
            fetcher=fetcher,
        )
        output = verify_review_request(args)
        self.assertTrue(output["ok"], output["errors"])

    def test_resolve_review_request_url_reads_pr_publish_event(self) -> None:
        issue_dir = self.tmp_path / "issue"
        shutil.copytree(COMPLETE_FIXTURE, issue_dir)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / ".agents/skills/gcw/scripts/manage_gcw_workflow.py"),
                "record-pr-publish",
                "--issue-dir",
                str(issue_dir),
                "--review-request-url",
                "https://github.com/owner/repo/pull/99",
                "--body-hash",
                "sha256:" + "c" * 64,
                "--target",
                "owner/repo#99",
                "--progress-comment-url",
                "https://github.com/owner/repo/issues/42#issuecomment-6",
                "--rendered-from-event-id",
                "gcw-42-006-gcw-implement-check",
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        errors: list[str] = []
        args = argparse.Namespace(fetch_url="", review_request_url="")
        url = resolve_review_request_url(issue_dir, args, errors)
        self.assertEqual(url, "https://github.com/owner/repo/pull/99")


if __name__ == "__main__":
    unittest.main()
