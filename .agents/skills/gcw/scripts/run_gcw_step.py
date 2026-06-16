"""CLI entrypoint for the unified GCW step runner.

Executes one milestone step end-to-end: validate projection routing, run step
gates, publish hosted artifacts, then record the workflow event.

Supported steps: gcw-issue-triage, gcw-issue-clarify, gcw-issue-to-spec,
gcw-spec-check, gcw-implement-check, gcw-pr-publish, gcw-pr-review.

Example::

    python run_gcw_step.py --step gcw-spec-check \\
        --issue-dir .gcw/issues/42 --dry-run
"""

from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from base import DryRunAdapter, GitHubAdapter
from gcw_steps import SUPPORTED_STEPS, GcwStepRunner, StepResult
from gcw_workflow_lib import WorkflowError


def emit(result: dict[str, Any]) -> int:
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def run_step(args: argparse.Namespace) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if args.options_file:
        options = json.loads(Path(args.options_file).read_text(encoding="utf-8"))
        if not isinstance(options, dict):
            raise WorkflowError("options file must contain a JSON object")

    if args.adapter == "github":
        adapter = GitHubAdapter()
    else:
        adapter = DryRunAdapter() if args.dry_run else GitHubAdapter()

    runner = GcwStepRunner(adapter=adapter)
    result: StepResult = runner.run(args.step, args.issue_dir, dry_run=args.dry_run, options=options)
    return {"ok": result.ok, **result.to_dict()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one GCW milestone step end-to-end with structured JSON output.",
    )
    parser.add_argument("--step", required=True, choices=SUPPORTED_STEPS)
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Render and validate without remote writes or events.")
    parser.add_argument(
        "--adapter",
        choices=("dry-run", "github"),
        default="github",
        help="Platform adapter (dry-run uses DryRunAdapter even when --dry-run is false).",
    )
    parser.add_argument(
        "--options-file",
        type=Path,
        default=None,
        help="JSON file with step-specific options (gate_file, payload_file, review_request_url, etc.).",
    )
    parser.set_defaults(handler=run_step)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.adapter == "dry-run":
        args.dry_run = True
    try:
        return emit(args.handler(args))
    except WorkflowError as exc:
        return emit({"ok": False, "errors": [str(exc)]})


if __name__ == "__main__":
    sys.exit(main())
