#!/usr/bin/env python3
"""Deprecated wrapper for gcw-issue-triage/scripts/manage_triage_metadata.py."""

from __future__ import annotations

import sys
from pathlib import Path

TRIAGE_SCRIPTS = Path(__file__).resolve().parents[2] / "gcw-issue-triage" / "scripts"
sys.path.insert(0, str(TRIAGE_SCRIPTS))

from manage_triage_metadata import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
