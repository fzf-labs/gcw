#!/usr/bin/env python3
"""Validate and expose codex handoff JSON artifacts for hosted GCW steps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_SCHEMAS: dict[str, set[str]] = {
    "triage_result.json": {
        "classification_type",
        "classification_priority",
        "labels_applied",
    },
    "clarify_result.json": {
        "ready",
    },
    "implement_summary.json": {
        "work_summary",
    },
    "implement-check-payload.json": {
        "gate",
    },
    "pr_review_summary.json": {
        "result",
    },
}


def validate(name: str, path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"missing handoff file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object")
    required = _SCHEMAS.get(name, set())
    missing = sorted(key for key in required if key not in data)
    if missing:
        raise ValueError(f"{name} missing keys: {', '.join(missing)}")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate hosted GCW handoff JSON.")
    parser.add_argument("--name", required=True, help="Artifact name, e.g. triage_result.json")
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--print-field", default="", help="Print a single field value")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = validate(args.name, args.path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.print_field:
        value = data.get(args.print_field, "")
        if isinstance(value, (dict, list)):
            print(json.dumps(value))
        else:
            print(value)
        return 0
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
