from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from gcw_workflow_lib import WorkflowError, load_projection

from render_gcw_hosted_artifacts import render_progress_comment


def body_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").rstrip() + "\n"
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def render_milestone_progress_body(
    issue_dir: Path,
    milestone_event: str,
    milestone_payload: dict[str, Any],
) -> str:
    return render_progress_comment(
        argparse.Namespace(
            issue_dir=issue_dir,
            milestone_event=milestone_event,
            milestone_payload=milestone_payload,
        )
    )


def publish_github(issue: str | int, repository: str, body: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(body)
        body_file = handle.name
    try:
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue), "--repo", repository, "--body-file", body_file],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise WorkflowError(f"gh issue comment failed: {detail}") from exc
    finally:
        Path(body_file).unlink(missing_ok=True)
    url = result.stdout.strip()
    if not url:
        raise WorkflowError("gh issue comment did not return a comment URL")
    return url


def publish_gitlab(issue: str | int, repository: str, body: str) -> str:
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


def _publish_body(issue_dir: Path, body: str, *, dry_run: bool) -> dict[str, Any]:
    digest = body_hash(body)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "body": body,
            "body_hash": digest,
            "progress_comment_url": "",
        }

    projection = load_projection(issue_dir)["projection"]
    platform = str(projection.get("platform", "github"))
    repository = str(projection.get("repository", "")).strip()
    issue = projection.get("issue")
    if not repository or issue is None:
        raise WorkflowError("workflow projection is missing repository or issue")

    if platform == "gitlab":
        url = publish_gitlab(issue, repository, body)
    else:
        url = publish_github(issue, repository, body)

    return {
        "ok": True,
        "dry_run": False,
        "body": body,
        "body_hash": digest,
        "progress_comment_url": url,
    }


def publish_milestone_progress_comment(
    issue_dir: Path,
    milestone_event: str,
    milestone_payload: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    body = render_milestone_progress_body(issue_dir, milestone_event, milestone_payload)
    return _publish_body(issue_dir, body, dry_run=dry_run)


def publish_progress_comment(args: argparse.Namespace) -> dict[str, Any]:
    milestone_event = getattr(args, "milestone_event", None)
    milestone_payload = getattr(args, "milestone_payload", None)
    if milestone_event and isinstance(milestone_payload, dict):
        return publish_milestone_progress_comment(
            args.issue_dir,
            str(milestone_event),
            milestone_payload,
            dry_run=bool(args.dry_run),
        )

    body = render_progress_comment(argparse.Namespace(issue_dir=args.issue_dir))
    return _publish_body(args.issue_dir, body, dry_run=bool(args.dry_run))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render and publish a new GCW issue progress comment (never edits existing comments).",
    )
    parser.add_argument("--issue-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Render only; do not post to GitHub/GitLab.")
    parser.add_argument(
        "--milestone-event",
        default="",
        help="Milestone event name to render as if already recorded (e.g. gcw-issue-triage).",
    )
    parser.add_argument(
        "--milestone-payload-file",
        default=None,
        type=Path,
        help="JSON object with the milestone event payload used for preview rendering.",
    )
    parser.set_defaults(handler=publish_progress_comment)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.milestone_payload_file:
        payload = json.loads(args.milestone_payload_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise WorkflowError("milestone payload file must contain a JSON object")
        args.milestone_payload = payload
    else:
        args.milestone_payload = None
    try:
        result = args.handler(args)
    except (WorkflowError, ValueError) as exc:
        result = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
