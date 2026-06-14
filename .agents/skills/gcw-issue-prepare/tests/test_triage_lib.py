from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from triage_lib import (  # noqa: E402
    expected_remote_sync,
    github_issue_type,
    github_priority_value,
    labels_for_platform,
    load_labels,
    validate_labels_applied_for_platform,
)


class TriageLibTest(unittest.TestCase):
    def test_github_mappings(self) -> None:
        self.assertEqual(github_issue_type("enhancement"), "Feature")
        self.assertEqual(github_issue_type("bug"), "Bug")
        self.assertEqual(github_priority_value("priority:p0"), "Urgent")
        self.assertEqual(github_priority_value("priority:p3"), "Low")

    def test_github_label_filter(self) -> None:
        labels = labels_for_platform(load_labels(), "github")
        self.assertIn("triaged", labels)
        self.assertNotIn("enhancement", labels)
        self.assertNotIn("priority:p0", labels)

    def test_gitlab_label_filter(self) -> None:
        labels = labels_for_platform(load_labels(), "gitlab")
        self.assertIn("enhancement", labels)
        self.assertIn("priority:p0", labels)

    def test_validate_github_labels_applied(self) -> None:
        errors = validate_labels_applied_for_platform(
            "github",
            ["triaged", "enhancement", "area:workflow"],
        )
        self.assertTrue(any("enhancement" in err for err in errors))

    def test_expected_remote_sync_github(self) -> None:
        expected = expected_remote_sync(
            "github",
            {"type": "enhancement", "priority": "priority:p0"},
            ["triaged", "area:workflow"],
        )
        self.assertEqual(expected["issue_type"], "Feature")
        self.assertEqual(expected["priority"], "Urgent")
        self.assertEqual(expected["labels"], ["triaged", "area:workflow"])

    def test_expected_remote_sync_gitlab(self) -> None:
        expected = expected_remote_sync(
            "gitlab",
            {"type": "enhancement", "priority": "priority:p0"},
            ["triaged", "area:workflow"],
        )
        self.assertEqual(
            expected["labels"],
            ["area:workflow", "enhancement", "priority:p0", "triaged"],
        )


if __name__ == "__main__":
    unittest.main()
