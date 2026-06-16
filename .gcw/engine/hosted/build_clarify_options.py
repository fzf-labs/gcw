#!/usr/bin/env python3
"""Build gcw-issue-clarify options from hosted handoff or readiness gate."""

# 中文说明：为 hosted `gcw-issue-clarify` 步骤生成本地 step runner 需要的 options。
# 流程：先重新运行 readiness gate，再合并 agent handoff 中的问题或摘要，
# 输出 clarify options JSON，供 `run_gcw_step.py --step gcw-issue-clarify` 使用。

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="enhancement")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--handoff", type=Path, default=Path(".gcw-runtime/handoff/clarify_result.json"))
    parser.add_argument("--gate-output", type=Path, default=Path("/tmp/clarify_gate.json"))
    parser.add_argument("--options-output", type=Path, default=Path("/tmp/clarify_options.json"))
    args = parser.parse_args(argv)

    subprocess.run(
        [
            "python3",
            ".agents/skills/gcw-issue-clarify/scripts/evaluate_issue_readiness.py",
            "--profile",
            args.profile,
            "--platform",
            "github",
            "--repo",
            args.repo,
            "--issue",
            args.issue,
            "--output",
            str(args.gate_output),
            "--question",
        ],
        check=True,
    )
    gate = json.loads(args.gate_output.read_text(encoding="utf-8"))
    options: dict = {"gate_file": str(args.gate_output)}

    if args.handoff.is_file():
        handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        if handoff.get("question"):
            options["question"] = handoff["question"]
        if gate.get("ok"):
            options["summary"] = handoff.get("summary") or "Hosted clarify gate passed."
        elif handoff.get("question"):
            options["question"] = handoff["question"]
        else:
            question = subprocess.check_output(
                [
                    "python3",
                    ".agents/skills/gcw-issue-clarify/scripts/evaluate_issue_readiness.py",
                    "--profile",
                    args.profile,
                    "--platform",
                    "github",
                    "--repo",
                    args.repo,
                    "--issue",
                    args.issue,
                    "--question",
                ],
                text=True,
            ).strip()
            options["question"] = question
    else:
        if gate.get("ok"):
            options["summary"] = "Hosted clarify gate passed."
        else:
            question = subprocess.check_output(
                [
                    "python3",
                    ".agents/skills/gcw-issue-clarify/scripts/evaluate_issue_readiness.py",
                    "--profile",
                    args.profile,
                    "--platform",
                    "github",
                    "--repo",
                    args.repo,
                    "--issue",
                    args.issue,
                    "--question",
                ],
                text=True,
            ).strip()
            options["question"] = question

    args.options_output.write_text(json.dumps(options, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(options, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
