from __future__ import annotations

import subprocess

from gcw_workflow_errors import WorkflowError


def publish_issue_note(issue: str | int, repository: str, body: str) -> str:
    try:
        result = subprocess.run(
            ["glab", "issue", "note", str(issue), "-R", repository, "-m", body],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise WorkflowError(f"glab issue note failed: {detail}") from exc
    output = (result.stdout or result.stderr or "").strip()
    if output.startswith("http"):
        return output.splitlines()[0].strip()
    return f"https://gitlab.com/{repository}/-/issues/{issue}#note"
