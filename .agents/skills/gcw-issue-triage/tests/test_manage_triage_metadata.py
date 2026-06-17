from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from manage_triage_metadata import cmd_apply_metadata  # noqa: E402
from triage_lib import EXECUTOR_HOSTED, EXECUTOR_LOCAL  # noqa: E402


class ManageTriageMetadataTest(unittest.TestCase):
    def test_apply_metadata_defaults_to_local_executor(self) -> None:
        args = argparse.Namespace(
            platform="github",
            repo="owner/repo",
            issue="42",
            type="enhancement",
            priority="priority:p2",
            labels="triaged,area:workflow",
            executor="local",
        )

        stdout = io.StringIO()
        with (
            patch("manage_triage_metadata.patch_github_issue_type"),
            patch("manage_triage_metadata.set_github_priority"),
            patch("manage_triage_metadata.issue_labels_github", return_value=[]),
            patch("manage_triage_metadata.apply_github_labels") as apply_labels,
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(cmd_apply_metadata(args), 0)

        output = json.loads(stdout.getvalue())
        self.assertEqual(output["remote_sync"]["labels"], ["triaged", "area:workflow", EXECUTOR_LOCAL])
        apply_labels.assert_called_once_with("owner/repo", "42", ["triaged", "area:workflow", EXECUTOR_LOCAL], [])

    def test_apply_metadata_preserves_hosted_executor(self) -> None:
        args = argparse.Namespace(
            platform="github",
            repo="owner/repo",
            issue="42",
            type="enhancement",
            priority="priority:p2",
            labels=f"triaged,{EXECUTOR_HOSTED}",
            executor="local",
        )

        stdout = io.StringIO()
        with (
            patch("manage_triage_metadata.patch_github_issue_type"),
            patch("manage_triage_metadata.set_github_priority"),
            patch("manage_triage_metadata.issue_labels_github", return_value=[]),
            patch("manage_triage_metadata.apply_github_labels"),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(cmd_apply_metadata(args), 0)

        output = json.loads(stdout.getvalue())
        self.assertEqual(output["remote_sync"]["labels"], ["triaged", EXECUTOR_HOSTED])

    def test_apply_metadata_can_skip_executor_default(self) -> None:
        args = argparse.Namespace(
            platform="gitlab",
            repo="owner/repo",
            issue="42",
            type="enhancement",
            priority="priority:p2",
            labels="triaged,area:workflow",
            executor="none",
        )

        stdout = io.StringIO()
        with (
            patch("manage_triage_metadata.issue_labels_gitlab", return_value=[]),
            patch("manage_triage_metadata.apply_gitlab_labels") as apply_labels,
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(cmd_apply_metadata(args), 0)

        output = json.loads(stdout.getvalue())
        self.assertEqual(
            output["remote_sync"]["labels"],
            ["area:workflow", "enhancement", "priority:p2", "triaged"],
        )
        apply_labels.assert_called_once_with("owner/repo", "42", ["triaged", "area:workflow", "enhancement", "priority:p2"], [])


if __name__ == "__main__":
    unittest.main()
