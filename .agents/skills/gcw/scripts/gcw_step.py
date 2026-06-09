from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATOR = SCRIPT_DIR / "validate_gcw_evidence.py"
MANAGER = SCRIPT_DIR / "manage_gcw_state.py"
REMOTE_VERIFIER = SCRIPT_DIR / "verify_gcw_remote_evidence.py"

CHECK_COMMANDS = {
    "state": (VALIDATOR, ["state"]),
    "implementation-gate": (VALIDATOR, ["implementation-gate"]),
    "readiness-check": (VALIDATOR, ["readiness-check"]),
    "create-review-request": (VALIDATOR, ["readiness-check"]),
    "remote-progress-comment": (REMOTE_VERIFIER, ["progress-comment"]),
    "remote-review-request": (REMOTE_VERIFIER, ["review-request"]),
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


def emit_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


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
    emit_json(
        {
            "ok": False,
            "step": step,
            "mode": mode,
            "errors": [f"{step} does not support {mode} mode"],
        }
    )
    return 1


def issue_dir_from_args(args: list[str]) -> Path | None:
    for index, value in enumerate(args):
        if value == "--issue-dir" and index + 1 < len(args):
            return Path(args[index + 1])
        if value.startswith("--issue-dir="):
            return Path(value.split("=", 1)[1])
    return None


def verify_apply_owner(step: str, runner_kind: str, passthrough: list[str]) -> int | None:
    issue_dir = issue_dir_from_args(passthrough)
    if issue_dir is None:
        emit_json(
            {
                "ok": False,
                "step": step,
                "mode": "apply",
                "runner_kind": runner_kind,
                "errors": ["apply mode requires --issue-dir for ownership verification"],
            }
        )
        return 1

    state_path = issue_dir / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        emit_json(
            {
                "ok": False,
                "step": step,
                "mode": "apply",
                "runner_kind": runner_kind,
                "errors": ["state.json is missing for ownership verification"],
            }
        )
        return 1
    except json.JSONDecodeError as exc:
        emit_json(
            {
                "ok": False,
                "step": step,
                "mode": "apply",
                "runner_kind": runner_kind,
                "errors": [f"state.json is not valid JSON: {exc.msg}"],
            }
        )
        return 1

    owner = state.get("owner") if isinstance(state, dict) else {}
    owner_kind = owner.get("kind") if isinstance(owner, dict) else None
    if owner_kind != runner_kind:
        emit_json(
            {
                "ok": False,
                "step": step,
                "mode": "apply",
                "runner_kind": runner_kind,
                "errors": [f"owner.kind {owner_kind or '<missing>'} does not match runner {runner_kind}"],
            }
        )
        return 1
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run GCW step contracts in check or apply mode."
    )
    parser.add_argument(
        "step",
        choices=sorted(set(CHECK_COMMANDS) | set(APPLY_COMMANDS)),
    )
    parser.add_argument("--mode", required=True, choices=("check", "apply"))
    parser.add_argument(
        "--runner-kind",
        choices=("local", "github-actions", "gitlab-ci", "manual"),
        default="local",
        help="Runner requesting apply mode. Defaults to local.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, passthrough = parser.parse_known_args(argv)

    if args.mode == "check":
        command = CHECK_COMMANDS.get(args.step)
        if command is None:
            return unsupported(args.step, args.mode)
        script, child_args = command
        return run_child(script, [*child_args, *passthrough])

    command = APPLY_COMMANDS.get(args.step)
    if command is None:
        return unsupported(args.step, args.mode)
    owner_error = verify_apply_owner(args.step, args.runner_kind, passthrough)
    if owner_error is not None:
        return owner_error
    return run_child(MANAGER, [*command, *passthrough])


if __name__ == "__main__":
    sys.exit(main())
