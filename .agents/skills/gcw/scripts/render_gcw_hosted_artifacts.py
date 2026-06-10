from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROGRESS_MARKER = "<!-- gcw-progress -->"
REVIEW_REQUEST_START = "<!-- gcw-review-request:start -->"
REVIEW_REQUEST_END = "<!-- gcw-review-request:end -->"


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def planning_link(platform: str, repository: str, branch: str, issue: Any, filename: str) -> str:
    if platform == "gitlab":
        return f"https://gitlab.com/{repository}/-/blob/{branch}/.gcw/issues/{issue}/{filename}"
    return f"https://github.com/{repository}/blob/{branch}/.gcw/issues/{issue}/{filename}"


def planning_links_from_state(state: dict[str, Any]) -> dict[str, str]:
    issue = state.get("issue")
    repository = state.get("repository")
    branch = state.get("branch")
    if not issue or not repository or not branch:
        return {}
    platform = str(state.get("platform", "github"))
    return {
        "task_plan": planning_link(platform, str(repository), str(branch), issue, "task_plan.md"),
        "findings": planning_link(platform, str(repository), str(branch), issue, "findings.md"),
        "progress": planning_link(platform, str(repository), str(branch), issue, "progress.md"),
    }


def planning_links_markdown(evidence: dict[str, Any], state: dict[str, Any] | None = None) -> list[str]:
    links = evidence.get("planning_links") if isinstance(evidence.get("planning_links"), dict) else {}
    if not links and state is not None:
        links = planning_links_from_state(state)
    rows: list[str] = []
    for label, key in (("Task plan", "task_plan"), ("Findings", "findings"), ("Progress", "progress")):
        value = links.get(key)
        if value:
            rows.append(f"- {label}: {value}")
    return rows


def render_progress_comment(args: argparse.Namespace) -> str:
    state = load_json(args.issue_dir / "state.json")
    readiness = load_json(args.issue_dir / "readiness_evidence.json")
    evidence = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    owner = state.get("owner") if isinstance(state.get("owner"), dict) else {}
    handoff_reason = evidence.get("handoff_reason", "")
    review_request_url = str(evidence.get("review_request_url", "")).strip()
    lines = [
        PROGRESS_MARKER,
        f"GCW Status: {state.get('state', 'unknown')}",
        "",
        f"- Issue: {state.get('issue', '')}",
        f"- Branch: {state.get('branch', '')}",
        f"- Owner: {owner.get('kind', '')}/{owner.get('id', '')}",
        f"- Last completed step: {state.get('last_completed_step', '')}",
        f"- Review request: {review_request_url or 'Not created yet'}",
    ]
    if handoff_reason:
        lines.append(f"- Handoff reason: {handoff_reason}")
    lines.extend(["", "Planning files:"])
    links = planning_links_markdown(readiness, state)
    lines.extend(links if links else ["- Not recorded yet."])
    if readiness.get("risks"):
        lines.extend(["", f"Risks: {readiness['risks']}"])
    return "\n".join(lines).rstrip() + "\n"


def render_review_request(args: argparse.Namespace) -> str:
    readiness = load_json(args.issue_dir / "readiness_evidence.json")
    review_request = readiness.get("review_request") if isinstance(readiness.get("review_request"), dict) else {}
    validations = readiness.get("validation") if isinstance(readiness.get("validation"), list) else []
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
    links = planning_links_markdown(readiness)
    lines.extend(links if links else ["- Not recorded."])
    lines.extend(
        [
            "",
            "## Progress Comment",
            "",
            str(readiness.get("progress_comment_url", "")).strip(),
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
    end = existing.find(REVIEW_REQUEST_END)
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
    print(args.handler(args), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
