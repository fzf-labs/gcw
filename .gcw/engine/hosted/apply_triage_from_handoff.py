#!/usr/bin/env python3
"""Apply triage metadata from hosted handoff or dispatch inputs."""

# 中文说明：把 hosted agent 产出的 triage handoff JSON 应用回 GitHub Issue。
# 流程：读取 `.gcw-runtime/handoff/triage_result.json`，整理类型、优先级与标签，
# 再委托 `manage_triage_metadata.py apply-metadata` 同步远端 issue metadata。

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def load_handoff(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = list(data.get("labels_applied") or [])
    area = str(data.get("classification_area", "")).strip()
    if area:
        labels.append(area)
    return {
        "classification_type": data["classification_type"],
        "classification_priority": data["classification_priority"],
        "labels": ",".join(str(x) for x in labels if str(x).strip()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", type=Path, default=Path(".gcw-runtime/handoff/triage_result.json"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--output", type=Path, default=Path("/tmp/triage_remote_sync.json"))
    args = parser.parse_args(argv)

    triage = load_handoff(args.handoff)
    type_value = triage["classification_type"]
    priority = triage["classification_priority"]
    labels = triage["labels"]

    with args.output.open("w", encoding="utf-8") as handle:
        subprocess.run(
            [
                "python3",
                ".agents/skills/gcw-issue-triage/scripts/manage_triage_metadata.py",
                "apply-metadata",
                "--platform",
                "github",
                "--repo",
                args.repo,
                "--issue",
                args.issue,
                "--type",
                type_value,
                "--priority",
                priority,
                "--labels",
                labels,
                "--executor",
                "none",
            ],
            check=True,
            stdout=handle,
        )
    print(json.dumps({"classification_type": type_value, "classification_priority": priority, "labels": labels}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
