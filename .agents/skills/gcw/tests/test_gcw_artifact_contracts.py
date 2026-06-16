from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".agents/skills/gcw/scripts"))

from gcw_artifact_contracts import (  # noqa: E402
    PROGRESS_MARKER,
    REVIEW_REQUEST_END,
    REVIEW_REQUEST_START,
    body_hash,
    count_markers,
    extract_marked_body,
    normalize_body,
)


class GcwArtifactContractsTest(unittest.TestCase):
    def test_body_hash_normalizes_line_endings(self) -> None:
        self.assertEqual(body_hash("hello\r\nworld"), body_hash("hello\nworld"))

    def test_normalize_body_trims_to_single_trailing_newline(self) -> None:
        self.assertEqual(normalize_body("hello\r\nworld\r\n"), "hello\nworld\n")

    def test_marker_helpers_round_trip_marked_body(self) -> None:
        text = (
            "intro\n"
            f"{PROGRESS_MARKER}\n"
            "status body\n"
            f"{REVIEW_REQUEST_START}\n"
            "generated\n"
            f"{REVIEW_REQUEST_END}\n"
        )
        self.assertEqual(count_markers(text, PROGRESS_MARKER), 1)
        self.assertEqual(count_markers(text, REVIEW_REQUEST_START), 1)
        self.assertEqual(count_markers(text, REVIEW_REQUEST_END), 1)
        self.assertEqual(
            extract_marked_body(text, REVIEW_REQUEST_START, REVIEW_REQUEST_END),
            f"{REVIEW_REQUEST_START}\n"
            "generated\n"
            f"{REVIEW_REQUEST_END}",
        )


if __name__ == "__main__":
    unittest.main()
