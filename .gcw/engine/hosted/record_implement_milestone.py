#!/usr/bin/env python3
"""Record gcw-implement milestone from hosted or handoff inputs."""

# 中文说明：把 hosted `gcw-implement` 的实现进展记录成 GCW workflow 事件。
# 流程：从参数或 `implement_summary.json` 取 work summary，先发布进度评论，
# 再调用 `manage_gcw_workflow.py record-implement` 写入事件日志和更新 projection。

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def resolve_work_summary(work_summary: str, handoff_summary: Path) -> str:
    summary = work_summary.strip()
    if summary:
        return summary
    data = json.loads(handoff_summary.read_text(encoding="utf-8"))
    return str(data.get("work_summary", "")).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-dir", type=Path, required=True)
    parser.add_argument("--handoff-summary", type=Path, default=Path(".gcw-runtime/handoff/implement_summary.json"))
    parser.add_argument("--work-summary", default="")
    parser.add_argument("--feedback-source", default="")
    parser.add_argument("--feedback-ref", default="")
    args = parser.parse_args(argv)

    work_summary = resolve_work_summary(args.work_summary, args.handoff_summary)
    if not work_summary:
        print("work_summary is required", file=sys.stderr)
        return 1

    payload_path = Path("/tmp/implement_milestone.json")
    payload_path.write_text(json.dumps({"work_summary": work_summary}) + "\n", encoding="utf-8")
    result = subprocess.check_output(
        [
            "python3",
            ".agents/skills/gcw/scripts/publish_progress_comment.py",
            "--issue-dir",
            str(args.issue_dir),
            "--milestone-event",
            "gcw-implement",
            "--milestone-payload-file",
            str(payload_path),
        ],
        text=True,
    )
    url = json.loads(result)["progress_comment_url"]
    cmd = [
        "python3",
        ".agents/skills/gcw/scripts/manage_gcw_workflow.py",
        "record-implement",
        "--issue-dir",
        str(args.issue_dir),
        "--work-summary",
        work_summary,
        "--progress-comment-url",
        url,
    ]
    if args.feedback_source.strip():
        cmd.extend(["--feedback-source", args.feedback_source.strip()])
    if args.feedback_ref.strip():
        cmd.extend(["--feedback-ref", args.feedback_ref.strip()])
    subprocess.run(cmd, check=True)
    print(json.dumps({"work_summary": work_summary, "progress_comment_url": url}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
