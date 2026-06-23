#!/usr/bin/env python3
"""Print a structured GCW hosted skip summary for workflow logs."""

from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

import argparse
import sys

from gcw_skip_diagnostics import format_skip_summary


def parse_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report a structured GCW hosted skip summary.")
    parser.add_argument("--step", default="")
    parser.add_argument("--skip-gate", default="")
    parser.add_argument("--skip-reason", default="")
    parser.add_argument("--phase", default="")
    parser.add_argument("--env-file", default="", help="GitHub/GitLab prepare output (key=value lines).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    step = args.step.strip()
    skip_gate = args.skip_gate.strip()
    skip_reason = args.skip_reason.strip()
    phase = args.phase.strip()
    if args.env_file:
        env = parse_env_file(args.env_file)
        step = step or env.get("step", "")
        skip_gate = skip_gate or env.get("skip_gate", "")
        skip_reason = skip_reason or env.get("skip_reason", "")
        phase = phase or env.get("phase", "")
    if not step:
        print("report_gcw_skip: missing --step", file=sys.stderr)
        return 1
    print(
        format_skip_summary(
            step=step,
            skip_gate=skip_gate,
            skip_reason=skip_reason,
            phase=phase,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
