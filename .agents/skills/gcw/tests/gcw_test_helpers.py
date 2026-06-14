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


PROGRESS_COMMENT_BASE = "https://github.com/owner/repo/issues/42#issuecomment"


def progress_comment_url(seq: int) -> str:
    return f"{PROGRESS_COMMENT_BASE}-{seq}"
