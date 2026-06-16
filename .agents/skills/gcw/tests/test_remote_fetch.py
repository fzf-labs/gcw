from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".gcw" / "engine" / "platforms"))

from remote_fetch import RemoteFetchError, detect_platform, fetch_github, fetch_gitlab, fetch_url


class RemoteFetchTest(unittest.TestCase):
    def test_detect_platform_github(self) -> None:
        self.assertEqual(
            detect_platform("https://github.com/owner/repo/issues/1#issuecomment-2"),
            "github",
        )

    def test_detect_platform_gitlab(self) -> None:
        self.assertEqual(
            detect_platform("https://gitlab.com/group/project/-/merge_requests/3"),
            "gitlab",
        )

    def test_detect_platform_rejects_unknown_host(self) -> None:
        with self.assertRaises(RemoteFetchError):
            detect_platform("https://example.com/issues/1")

    def test_fetch_github_issue_comment(self) -> None:
        def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            self.assertEqual(cmd[:2], ["gh", "api"])
            self.assertIn("repos/owner/repo/issues/comments/99", cmd[2])
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"body": "<!-- gcw-progress -->\nHello\n"}),
                stderr="",
            )

        body = fetch_github(
            "https://github.com/owner/repo/issues/1#issuecomment-99",
            runner=runner,
        )
        self.assertIn("gcw-progress", body)

    def test_fetch_github_pull_request(self) -> None:
        def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            self.assertIn("repos/owner/repo/pulls/7", cmd[2])
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"body": "<!-- gcw-review-request:start -->\nPR\n<!-- gcw-review-request:end -->\n"}),
                stderr="",
            )

        body = fetch_github("https://github.com/owner/repo/pull/7", runner=runner)
        self.assertIn("gcw-review-request:start", body)

    def test_fetch_github_rejects_unsupported_shape(self) -> None:
        with self.assertRaises(RemoteFetchError) as ctx:
            fetch_github("https://github.com/owner/repo/commits/main")
        self.assertIn("unsupported github URL shape", str(ctx.exception))

    def test_fetch_github_maps_authentication_errors(self) -> None:
        def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(1, cmd, stderr="HTTP 401: Bad credentials")

        with self.assertRaises(RemoteFetchError) as ctx:
            fetch_github("https://github.com/owner/repo/pull/7", runner=runner)
        self.assertIn("authentication required", str(ctx.exception))

    def test_fetch_gitlab_issue_note(self) -> None:
        def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            self.assertEqual(cmd[:2], ["glab", "api"])
            self.assertIn("projects/group%2Fproject/issues/4/notes/55", cmd[2])
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"body": "<!-- gcw-progress -->\nNote\n"}),
                stderr="",
            )

        body = fetch_gitlab(
            "https://gitlab.com/group/project/-/issues/4#note_55",
            runner=runner,
        )
        self.assertIn("gcw-progress", body)

    def test_fetch_gitlab_merge_request(self) -> None:
        def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            self.assertEqual(cmd[:4], ["glab", "mr", "view", "9"])
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"description": "<!-- gcw-review-request:start -->\nMR\n<!-- gcw-review-request:end -->\n"}),
                stderr="",
            )

        body = fetch_gitlab("https://gitlab.com/group/project/-/merge_requests/9", runner=runner)
        self.assertIn("gcw-review-request:start", body)

    def test_fetch_url_uses_injected_fetcher(self) -> None:
        seen: list[str] = []

        def fetcher(url: str) -> str:
            seen.append(url)
            return "injected"

        body = fetch_url("https://github.com/owner/repo/pull/1", fetcher=fetcher)
        self.assertEqual(body, "injected")
        self.assertEqual(seen, ["https://github.com/owner/repo/pull/1"])


if __name__ == "__main__":
    unittest.main()
