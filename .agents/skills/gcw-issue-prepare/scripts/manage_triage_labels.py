#!/usr/bin/env python3
"""Backward-compatible wrapper around manage_triage_metadata."""

from __future__ import annotations

from manage_triage_metadata import main

if __name__ == "__main__":
    raise SystemExit(main())
