from __future__ import annotations

import hashlib
from pathlib import Path


def file_sha(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def planning_shas(issue_dir: Path) -> dict[str, str]:
    return {
        "task_plan_sha": file_sha(issue_dir / "task_plan.md"),
        "findings_sha": file_sha(issue_dir / "findings.md"),
        "progress_sha": file_sha(issue_dir / "progress.md"),
    }
