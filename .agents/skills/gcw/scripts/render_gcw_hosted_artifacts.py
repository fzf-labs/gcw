from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gcw_workflow_lib import WorkflowError, assert_projection_current, find_latest_event


PROGRESS_MARKER = "<!-- gcw-progress -->"
REVIEW_REQUEST_START = "<!-- gcw-review-request:start -->"
REVIEW_REQUEST_END = "<!-- gcw-review-request:end -->"


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        return {}
    return data


def planning_link(platform: str, repository: str, branch: str, issue: Any, filename: str) -> str:
    if platform == "gitlab":
        return f"https://gitlab.com/{repository}/-/blob/{branch}/.gcw/issues/{issue}/{filename}"
    return f"https://github.com/{repository}/blob/{branch}/.gcw/issues/{issue}/{filename}"


def planning_links_from_projection(projection: dict[str, Any]) -> dict[str, str]:
    issue = projection.get("issue")
    repository = projection.get("repository")
    branch = projection.get("branch")
    if not issue or not repository or not branch:
        return {}
    platform = str(projection.get("platform", "github"))
    return {
        "task_plan": planning_link(platform, str(repository), str(branch), issue, "task_plan.md"),
        "findings": planning_link(platform, str(repository), str(branch), issue, "findings.md"),
        "progress": planning_link(platform, str(repository), str(branch), issue, "progress.md"),
    }


def planning_links_markdown(evidence: dict[str, Any], projection: dict[str, Any] | None = None) -> list[str]:
    links = evidence.get("planning_links") if isinstance(evidence.get("planning_links"), dict) else {}
    if not links and projection is not None:
        links = planning_links_from_projection(projection)
    rows: list[str] = []
    for label, key in (("Task plan", "task_plan"), ("Findings", "findings"), ("Progress", "progress")):
        value = links.get(key)
        if value:
            rows.append(f"- {label}: {value}")
    return rows


def render_progress_comment(args: argparse.Namespace) -> str:
    current = assert_projection_current(args.issue_dir)
    if not current["ok"]:
        raise ValueError("; ".join(current["errors"]))
    projection = current["projection"]
    owner = projection.get("owner") if isinstance(projection.get("owner"), dict) else {}
    refs = projection.get("refs") if isinstance(projection.get("refs"), dict) else {}
    review_request_url = str(refs.get("review_request_url", "")).strip()
    latest_ready = find_latest_event(args.issue_dir, "gcw-implement-check", lambda event: event.get("payload", {}).get("gate", {}).get("ok") is True)
    readiness = latest_ready.get("payload", {}) if latest_ready else {}
    lines = [
        PROGRESS_MARKER,
        f"GCW Status: {projection.get('phase', 'unknown')}",
        "",
        f"- Issue: {projection.get('issue', '')}",
        f"- Branch: {projection.get('branch', '')}",
        f"- Owner: {owner.get('kind', '')}/{owner.get('id', '')}",
        f"- Last completed step: {projection.get('last_completed_step', '')}",
        f"- Review request: {review_request_url or 'Not created yet'}",
    ]
    active_feedback = projection.get("active_feedback") if isinstance(projection.get("active_feedback"), dict) else {}
    active_blocker = projection.get("active_blocker") if isinstance(projection.get("active_blocker"), dict) else {}
    if active_feedback.get("reason"):
        lines.append(f"- Active feedback: {active_feedback['reason']}")
    if active_blocker.get("reason"):
        lines.append(f"- Active blocker: {active_blocker['reason']}")
    lines.extend(["", "Planning files:"])
    links = planning_links_markdown(readiness, projection)
    lines.extend(links if links else ["- Not recorded yet."])
    if readiness.get("risks"):
        lines.extend(["", f"Risks: {readiness['risks']}"])
    return "\n".join(lines).rstrip() + "\n"


def render_review_request(args: argparse.Namespace) -> str:
    current = assert_projection_current(args.issue_dir)
    if not current["ok"]:
        raise ValueError("; ".join(current["errors"]))
    latest_ready = find_latest_event(args.issue_dir, "gcw-implement-check", lambda event: event.get("payload", {}).get("gate", {}).get("ok") is True)
    if latest_ready is None:
        raise ValueError("passing gcw-implement-check event is missing")
    readiness = latest_ready.get("payload", {})
    review_request = readiness.get("review_request") if isinstance(readiness.get("review_request"), dict) else {}
    gate = readiness.get("gate") if isinstance(readiness.get("gate"), dict) else {}
    validations = readiness.get("validation") if isinstance(readiness.get("validation"), list) else gate.get("validation", [])
    lines = [
        REVIEW_REQUEST_START,
        str(review_request.get("title", "")).strip(),
        "",
        "## Summary",
        "",
        str(review_request.get("summary", "")).strip(),
        "",
        "## Issue",
        "",
        str(review_request.get("issue_link", "")).strip(),
        "",
        "## Validation",
        "",
    ]
    if validations:
        for validation in validations:
            if isinstance(validation, dict):
                lines.append(f"- {validation.get('command', '')}: {validation.get('result', '')}")
    else:
        lines.append("- Not recorded.")
    if readiness.get("scope"):
        lines.extend(["", "## Scope", "", str(readiness["scope"]).strip()])
    lines.extend(["", "## Planning", ""])
    links = planning_links_markdown(readiness, current["projection"])
    lines.extend(links if links else ["- Not recorded."])
    lines.extend(
        [
            "",
            "## Progress Comment",
            "",
            str(current["projection"].get("refs", {}).get("progress_comment_url", "")).strip(),
            "",
            "## Risks",
            "",
            str(readiness.get("risks", "")).strip(),
        ]
    )
    if readiness.get("reviewer_notes"):
        lines.extend(["", "## Reviewer Notes", "", str(readiness["reviewer_notes"]).strip()])
    lines.extend(["", REVIEW_REQUEST_END])
    return "\n".join(lines).rstrip() + "\n"


def merge_review_request_body(existing: str, rendered: str) -> str:
    """Replace the generated section between markers, preserving hand-written content outside it."""
    rendered = rendered.strip("\n")
    start = existing.find(REVIEW_REQUEST_START)
    end = existing.find(REVIEW_REQUEST_END, start + len(REVIEW_REQUEST_START)) if start != -1 else -1
    if start != -1 and end != -1 and end >= start:
        end_index = end + len(REVIEW_REQUEST_END)
        merged = existing[:start] + rendered + existing[end_index:]
        return merged.strip("\n") + "\n"
    if not existing.strip():
        return rendered + "\n"
    return existing.rstrip("\n") + "\n\n" + rendered + "\n"


def merge_review_request(args: argparse.Namespace) -> str:
    rendered = args.rendered_file.read_text(encoding="utf-8")
    existing = args.existing_file.read_text(encoding="utf-8") if args.existing_file.is_file() else ""
    return merge_review_request_body(existing, rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render hosted GCW artifact bodies from local evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    progress_parser = subparsers.add_parser("progress-comment")
    progress_parser.add_argument("--issue-dir", required=True, type=Path)
    progress_parser.set_defaults(handler=render_progress_comment)

    review_parser = subparsers.add_parser("review-request")
    review_parser.add_argument("--issue-dir", required=True, type=Path)
    review_parser.set_defaults(handler=render_review_request)

    merge_parser = subparsers.add_parser(
        "merge-review-request",
        help="Merge a rendered review request body into an existing body, preserving manual content.",
    )
    merge_parser.add_argument("--existing-file", required=True, type=Path)
    merge_parser.add_argument("--rendered-file", required=True, type=Path)
    merge_parser.set_defaults(handler=merge_review_request)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        print(args.handler(args), end="")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
