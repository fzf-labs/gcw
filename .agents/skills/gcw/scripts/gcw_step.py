from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR = SCRIPT_DIR / "validate_gcw_evidence.py"
MANAGER = SCRIPT_DIR / "manage_gcw_state.py"

CHECK_COMMANDS = {
    "state": ["state"],
    "implementation-gate": ["implementation-gate"],
    "readiness-check": ["readiness-check"],
    "create-review-request": ["readiness-check"],
}

APPLY_COMMANDS = {
    "implementation-gate": ["record-implementation-gate"],
    "readiness-check": ["record-readiness-evidence"],
    "create-review-request": ["record-review-request"],
    "block": ["record-block"],
    "clarify": ["record-clarify"],
    "local-self-review": ["record-local-self-review"],
    "handoff": ["record-handoff"],
}


def run_child(script: Path, args: list[str]) -> int:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def unsupported(step: str, mode: str) -> int:
    print(
        json.dumps(
            {
                "ok": False,
                "step": step,
                "mode": mode,
                "errors": [f"{step} does not support {mode} mode"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run GCW step contracts in check or apply mode."
    )
    parser.add_argument(
        "step",
        choices=sorted(set(CHECK_COMMANDS) | set(APPLY_COMMANDS)),
    )
    parser.add_argument("--mode", required=True, choices=("check", "apply"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, passthrough = parser.parse_known_args(argv)

    if args.mode == "check":
        command = CHECK_COMMANDS.get(args.step)
        if command is None:
            return unsupported(args.step, args.mode)
        return run_child(VALIDATOR, [*command, *passthrough])

    command = APPLY_COMMANDS.get(args.step)
    if command is None:
        return unsupported(args.step, args.mode)
    return run_child(MANAGER, [*command, *passthrough])


if __name__ == "__main__":
    sys.exit(main())
