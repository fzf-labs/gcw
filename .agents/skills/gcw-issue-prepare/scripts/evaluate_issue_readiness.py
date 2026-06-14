#!/usr/bin/env python3
"""Deprecated wrapper for gcw-issue-clarify/scripts/evaluate_issue_readiness.py."""

from __future__ import annotations

import sys
from pathlib import Path

CLARIFY_SCRIPTS = Path(__file__).resolve().parents[2] / "gcw-issue-clarify" / "scripts"
sys.path.insert(0, str(CLARIFY_SCRIPTS))

from evaluate_issue_readiness import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
