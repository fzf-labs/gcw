from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
STEP_RUNNER = SCRIPT_DIR / "gcw_step.py"

PIPELINES = (
    "issue-intake",
    "issue-clarify",
    "planning",
    "machine-review",
    "machine-feedback-loop",
    "human-feedback-loop",
    "review-complete",
)
READINESS_REQUIRED_ARGS = (
    "base_branch",
    "commit_range",
    "title",
    "summary",
    "issue_link",
    "validation_command",
    "validation_result",
    "risks",
)


def emit_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected a boolean value")


def non_empty(args: argparse.Namespace, names: tuple[str, ...], pipeline: str) -> list[str]:
    errors: list[str] = []
    for name in names:
        value = getattr(args, name)
        if not str(value).strip():
            option = name.replace("_", "-")
            errors.append(f"{pipeline} requires --{option}")
    return errors


def maybe_extend(command: list[str], option: str, value: str) -> None:
    if value:
        command.extend([option, value])


def readiness_step_args(args: argparse.Namespace) -> list[str]:
    command = [
        "--issue-dir",
        str(args.issue_dir),
        "--base-branch",
        args.base_branch,
        "--commit-range",
        args.commit_range,
        "--title",
        args.title,
        "--summary",
        args.summary,
        "--issue-link",
        args.issue_link,
        "--validation-command",
        args.validation_command,
        "--validation-result",
        args.validation_result,
        "--risks",
        args.risks,
    ]
    maybe_extend(command, "--scope", args.scope)
    maybe_extend(command, "--reviewer-notes", args.reviewer_notes)
    return command


def pipeline_steps(args: argparse.Namespace) -> tuple[list[tuple[str, list[str]]], bool, list[str]]:
    issue_arg = ["--issue-dir", str(args.issue_dir)]
    pause_after_success = False
    errors: list[str] = []

    if args.pipeline == "issue-intake":
        errors.extend(non_empty(args, ("priority", "summary"), args.pipeline))
        if not args.issue_actionable and not args.clarifying_question:
            errors.append("issue-intake requires --clarifying-question when --issue-actionable is false")
        steps = [
            (
                "triage-issue",
                [
                    *issue_arg,
                    "--priority",
                    args.priority,
                    "--summary",
                    args.summary,
                ],
            ),
            (
                "mark-issue-actionable",
                [
                    *issue_arg,
                    "--issue-actionable",
                    str(args.issue_actionable).lower(),
                    "--clarifying-question",
                    args.clarifying_question,
                ],
            ),
        ]
        pause_after_success = not args.issue_actionable
        return steps, pause_after_success, errors

    if args.pipeline == "issue-clarify":
        if not args.issue_actionable and not args.clarifying_question:
            errors.append("issue-clarify requires --clarifying-question when --issue-actionable is false")
        if args.issue_actionable:
            steps = [
                (
                    "mark-issue-actionable",
                    [*issue_arg, "--issue-actionable", "true"],
                )
            ]
        else:
            steps = [
                (
                    "discuss-issue",
                    [*issue_arg, "--question", args.clarifying_question],
                )
            ]
            pause_after_success = True
        return steps, pause_after_success, errors

    if args.pipeline == "planning":
        errors.extend(non_empty(args, ("progress_comment_url",), args.pipeline))
        steps = [
            (
                "create-issue-worktree",
                [
                    *issue_arg,
                    "--worktree-path",
                    args.worktree_path,
                ],
            ),
            ("create-planning-files", issue_arg),
            (
                "publish-planning",
                [
                    *issue_arg,
                    "--progress-comment-url",
                    args.progress_comment_url,
                    "--planning-commit-pushed",
                    str(args.planning_commit_pushed).lower(),
                ],
            ),
        ]
        return steps, pause_after_success, errors

    if args.pipeline == "machine-review":
        steps = [
            ("machine-review-start", issue_arg),
            (
                "machine-review-result",
                [
                    *issue_arg,
                    "--result",
                    args.machine_review_result,
                ],
            ),
        ]
        return steps, pause_after_success, errors

    if args.pipeline == "machine-feedback-loop":
        errors.extend(non_empty(args, READINESS_REQUIRED_ARGS, args.pipeline))
        steps = [
            ("address-machine-feedback", issue_arg),
            (
                "local-self-review",
                [
                    *issue_arg,
                    "--progress-section",
                    args.progress_section,
                ],
            ),
            ("readiness-check", readiness_step_args(args)),
        ]
        return steps, pause_after_success, errors

    if args.pipeline == "human-feedback-loop":
        errors.extend(non_empty(args, READINESS_REQUIRED_ARGS, args.pipeline))
        steps = [
            ("address-human-feedback", issue_arg),
            (
                "local-self-review",
                [
                    *issue_arg,
                    "--progress-section",
                    args.progress_section,
                ],
            ),
            ("readiness-check", readiness_step_args(args)),
        ]
        return steps, pause_after_success, errors

    if args.pipeline == "review-complete":
        steps = [
            (
                "review-complete",
                [
                    *issue_arg,
                    "--result",
                    args.review_complete_result,
                ],
            )
        ]
        return steps, pause_after_success, errors

    return [], pause_after_success, [f"unsupported pipeline: {args.pipeline}"]


def run_step(step: str, step_args: list[str], args: argparse.Namespace) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(STEP_RUNNER),
            step,
            "--mode",
            "apply",
            "--runner-kind",
            args.runner_kind,
            "--runner-id",
            args.runner_id,
            *step_args,
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    parsed_stdout: Any
    try:
        parsed_stdout = json.loads(result.stdout) if result.stdout else None
    except json.JSONDecodeError:
        parsed_stdout = result.stdout
    return {
        "step": step,
        "returncode": result.returncode,
        "stdout": parsed_stdout,
        "stderr": result.stderr,
    }


def claim_ownership(args: argparse.Namespace) -> dict[str, Any]:
    owner_kind = args.owner_kind or args.runner_kind
    owner_id = args.owner_id or args.runner_id
    reason = args.handoff_reason or f"{args.pipeline} pipeline taking ownership."
    return run_step(
        "handoff",
        [
            "--issue-dir",
            str(args.issue_dir),
            "--owner-kind",
            owner_kind,
            "--owner-id",
            owner_id,
            "--reason",
            reason,
        ],
        args,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run owner-gated GCW Action pipelines.")
    parser.add_argument("pipeline", choices=PIPELINES)
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument(
        "--runner-kind",
        choices=("local", "github-actions", "gitlab-ci", "manual"),
        default="local",
    )
    parser.add_argument("--runner-id", required=True)
    parser.add_argument("--claim-ownership", action="store_true")
    parser.add_argument("--owner-kind", choices=("local", "github-actions", "gitlab-ci", "manual"), default="")
    parser.add_argument("--owner-id", default="")
    parser.add_argument("--handoff-reason", default="")

    parser.add_argument("--priority", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--issue-actionable", type=parse_bool, default=True)
    parser.add_argument("--clarifying-question", default="")

    parser.add_argument("--worktree-path", default="")
    parser.add_argument("--progress-comment-url", default="")
    parser.add_argument("--planning-commit-pushed", type=parse_bool, default=False)

    parser.add_argument("--machine-review-result", choices=("passed", "failed"), default="passed")

    parser.add_argument("--progress-section", default="## Local Self-Review")
    parser.add_argument("--base-branch", default="")
    parser.add_argument("--commit-range", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--issue-link", default="")
    parser.add_argument("--validation-command", default="")
    parser.add_argument("--validation-result", default="")
    parser.add_argument("--risks", default="")
    parser.add_argument("--scope", default="")
    parser.add_argument("--reviewer-notes", default="")

    parser.add_argument("--review-complete-result", choices=("merged", "closed", "accepted"), default="merged")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    steps, pause_after_success, errors = pipeline_steps(args)
    if errors:
        emit_json({"ok": False, "pipeline": args.pipeline, "errors": errors, "steps": []})
        return 1

    results: list[dict[str, Any]] = []
    if args.claim_ownership:
        handoff_result = claim_ownership(args)
        results.append(handoff_result)
        if handoff_result["returncode"] != 0:
            emit_json(
                {
                    "ok": False,
                    "pipeline": args.pipeline,
                    "errors": ["ownership handoff failed"],
                    "steps": results,
                }
            )
            return 1

    for step, step_args in steps:
        step_result = run_step(step, step_args, args)
        results.append(step_result)
        if step_result["returncode"] != 0:
            emit_json(
                {
                    "ok": False,
                    "pipeline": args.pipeline,
                    "errors": [f"{step} failed"],
                    "steps": results,
                }
            )
            return 1

    if pause_after_success:
        emit_json(
            {
                "ok": False,
                "pipeline": args.pipeline,
                "errors": ["issue requires clarification before the pipeline can continue"],
                "steps": results,
            }
        )
        return 1

    emit_json({"ok": True, "pipeline": args.pipeline, "steps": results})
    return 0


if __name__ == "__main__":
    sys.exit(main())
