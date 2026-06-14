#!/usr/bin/env python3
"""Evaluate GCW issue readiness against a structural rubric profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from readiness_lib import evaluate_readiness, fetch_issue_body, gate_to_question


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate issue readiness for gcw-issue-clarify.")
    parser.add_argument("--profile", default="enhancement")
    parser.add_argument("--body-file", type=Path, default=None)
    parser.add_argument("--platform", choices=("github", "gitlab"), default=None)
    parser.add_argument("--repo", default="")
    parser.add_argument("--issue", default="")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--question", action="store_true", help="Print gate_to_question to stderr")
    return parser


def resolve_body(args: argparse.Namespace) -> str:
    if args.body_file is not None:
        return args.body_file.read_text(encoding="utf-8")
    if args.platform and args.repo and args.issue:
        return fetch_issue_body(args.platform, args.repo, args.issue)
    raise SystemExit("provide --body-file or --platform --repo --issue")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    body = resolve_body(args)
    gate = evaluate_readiness(body, profile=args.profile)
    output = json.dumps(gate, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    if args.question:
        question = gate_to_question(gate)
        if question:
            print(question, file=sys.stderr)
    return 0 if gate.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
