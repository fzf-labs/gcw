"""Deprecated import shim for gcw-issue-clarify/scripts/readiness_lib.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "gcw-issue-clarify" / "scripts" / "readiness_lib.py"
SPEC = importlib.util.spec_from_file_location("_gcw_issue_clarify_readiness_lib", TARGET)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"cannot load {TARGET}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

globals().update({name: value for name, value in MODULE.__dict__.items() if not name.startswith("__")})
