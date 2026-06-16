from __future__ import annotations

from _bootstrap import add_repo_root

add_repo_root()

import argparse
import json
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable, Iterator

from gcw_workflow_lib import (
    WorkflowError,
    assert_projection_current,
    build_preview_event,
    find_latest_event,
    load_events,
    reduce_workflow,
)
from gcw_artifact_contracts import PROGRESS_MARKER, REVIEW_REQUEST_END, REVIEW_REQUEST_START

_overlay_event: ContextVar[dict[str, Any] | None] = ContextVar("gcw_render_overlay_event", default=None)


@contextmanager
def milestone_render_context(overlay_event: dict[str, Any] | None) -> Iterator[None]:
    token = _overlay_event.set(overlay_event)
    try:
        yield
    finally:
        _overlay_event.reset(token)


def _max_render_seq() -> int | None:
    overlay = _overlay_event.get()
    if overlay is None:
        return None
    seq = overlay.get("seq")
    return seq if isinstance(seq, int) else None


def _event_lookup(
    issue_dir: Path,
    event_name: str,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any] | None:
    overlay = _overlay_event.get()
    if overlay is not None and overlay.get("event") == event_name:
        if predicate is None or predicate(overlay):
            return overlay
    return find_latest_event(issue_dir, event_name, predicate, max_seq=_max_render_seq())


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


def _progress_header(phase: str) -> list[str]:
    return [PROGRESS_MARKER, f"GCW Status: {phase}", ""]


def _context_section(projection: dict[str, Any], owner: dict[str, Any]) -> list[str]:
    return [
        "## Context",
        f"- Issue: {projection.get('issue', '')}",
        f"- Branch: {projection.get('branch', '')}",
        f"- Owner: {owner.get('kind', '')}/{owner.get('id', '')}",
        f"- Last completed step: {projection.get('last_completed_step', '')}",
    ]


def _classification_from_triage(issue_dir: Path) -> dict[str, Any]:
    triage = _event_lookup(issue_dir, "gcw-issue-triage")
    if triage is not None:
        payload = triage.get("payload") if isinstance(triage.get("payload"), dict) else {}
        classification = payload.get("classification")
        return classification if isinstance(classification, dict) else {}
    return {}


def _triage_lines(issue_dir: Path, phase: str) -> list[str]:
    if phase == "issue-opened":
        return []
    classification = _classification_from_triage(issue_dir)

    def field(name: str, key: str) -> str:
        value = classification.get(key)
        if value is None or str(value).strip() == "":
            return f"- {name}: Not recorded"
        return f"- {name}: {value}"

    return [
        field("Type", "type"),
        field("Area", "area"),
        field("Priority", "priority"),
    ]


def _append_context_and_triage(
    lines: list[str],
    issue_dir: Path,
    phase: str,
    projection: dict[str, Any],
    owner: dict[str, Any],
) -> None:
    lines.extend(_context_section(projection, owner))
    triage_lines = _triage_lines(issue_dir, phase)
    if triage_lines:
        _append_section(lines, "## Triage", triage_lines)


def _validation_lines(validations: list[Any]) -> list[str]:
    lines: list[str] = []
    for validation in validations:
        if isinstance(validation, dict):
            command = str(validation.get("command", "")).strip()
            result = str(validation.get("result", "")).strip()
            if command and result:
                lines.append(f"- {command}: {result}")
    return lines


def _append_section(lines: list[str], title: str, body_lines: list[str]) -> None:
    if not body_lines:
        return
    lines.extend(["", title, *body_lines])


def _clarify_readiness_lines(issue_dir: Path) -> list[str]:
    clarify = _event_lookup(issue_dir, "gcw-issue-clarify")
    if clarify is None:
        return []
    payload = clarify.get("payload") if isinstance(clarify.get("payload"), dict) else {}
    gate = payload.get("gate")
    if not isinstance(gate, dict):
        return []

    lines = [f"- Profile: {gate.get('profile', 'Not recorded')}"]
    if gate.get("ok") is True:
        lines.append("- All structural checks passed")
        return lines

    for check in gate.get("checks", []):
        if not isinstance(check, dict) or check.get("ok") is True:
            continue
        check_id = str(check.get("id", "unknown"))
        message = str(check.get("message", "")).strip() or "check failed"
        lines.append(f"- Failed: {check_id}: {message}")
    if len(lines) == 1:
        lines.append("- Readiness gate did not pass")
    return lines


def _render_early_progress(
    issue_dir: Path,
    phase: str,
    projection: dict[str, Any],
    owner: dict[str, Any],
) -> str:
    lines = _progress_header(phase)
    _append_context_and_triage(lines, issue_dir, phase, projection, owner)
    if phase == "ready-for-planning":
        readiness_lines = _clarify_readiness_lines(issue_dir)
        _append_section(lines, "## Readiness", readiness_lines or ["- Not recorded."])
    return "\n".join(lines).rstrip() + "\n"


def _render_issue_clarifying(
    issue_dir: Path,
    projection: dict[str, Any],
    owner: dict[str, Any],
) -> str:
    lines = _progress_header("issue-clarifying")
    _append_context_and_triage(lines, issue_dir, "issue-clarifying", projection, owner)
    readiness_lines = _clarify_readiness_lines(issue_dir)
    _append_section(lines, "## Readiness", readiness_lines or ["- Not recorded."])
    question = ""
    clarify = _event_lookup(issue_dir, "gcw-clarify")
    if clarify:
        question = str(clarify.get("payload", {}).get("question", "")).strip()
    if not question:
        clarify = _event_lookup(
            issue_dir,
            "gcw-issue-clarify",
            lambda event: event.get("payload", {}).get("ready") is not True,
        )
        if clarify:
            question = str(clarify.get("payload", {}).get("question", "")).strip()
    feedback = projection.get("active_feedback") if isinstance(projection.get("active_feedback"), dict) else {}
    if not question:
        question = str(feedback.get("reason", "")).strip()
    _append_section(lines, "## Clarification", [f"- Question: {question}"] if question else ["- Question: Not recorded."])
    return "\n".join(lines).rstrip() + "\n"


def _render_planned_progress(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any]) -> str:
    lines = _progress_header("planned")
    _append_context_and_triage(lines, issue_dir, "planned", projection, owner)
    links = planning_links_markdown({}, projection)
    _append_section(lines, "## Planning files", links if links else ["- Not recorded yet."])
    return "\n".join(lines).rstrip() + "\n"


def _render_ready_for_implementation(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any]) -> str:
    lines = _progress_header("ready-for-implementation")
    _append_context_and_triage(lines, issue_dir, "ready-for-implementation", projection, owner)
    spec_check = _event_lookup(
        issue_dir,
        "gcw-spec-check",
        lambda event: event.get("payload", {}).get("gate", {}).get("ok") is True,
    )
    result = "passed"
    if spec_check:
        result = str(spec_check.get("payload", {}).get("result", "passed")).strip() or "passed"
    _append_section(lines, "## Spec gate", [f"- Result: {result}"])
    return "\n".join(lines).rstrip() + "\n"


def _render_implementing(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any]) -> str:
    lines = _progress_header("implementing")
    _append_context_and_triage(lines, issue_dir, "implementing", projection, owner)
    implement = _event_lookup(issue_dir, "gcw-implement")
    summary = str(implement.get("payload", {}).get("work_summary", "")).strip() if implement else ""
    _append_section(lines, "## Implementation", [f"- Work: {summary}"] if summary else ["- Work: In progress."])
    return "\n".join(lines).rstrip() + "\n"


def _render_ready_for_review(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any]) -> str:
    lines = _progress_header("ready-for-review")
    _append_context_and_triage(lines, issue_dir, "ready-for-review", projection, owner)
    implement_check = _event_lookup(
        issue_dir,
        "gcw-implement-check",
        lambda event: event.get("payload", {}).get("gate", {}).get("ok") is True,
    )
    payload = implement_check.get("payload", {}) if implement_check else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    validations = payload.get("validation") if isinstance(payload.get("validation"), list) else gate.get("validation", [])
    readiness_lines = ["- Gate: passed", *_validation_lines(validations if isinstance(validations, list) else [])]
    _append_section(lines, "## Readiness", readiness_lines or ["- Gate: passed"])
    risks = str(payload.get("risks", "")).strip()
    if risks:
        _append_section(lines, "## Risks", [risks])
    return "\n".join(lines).rstrip() + "\n"


def _render_reviewing(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any], refs: dict[str, Any]) -> str:
    lines = _progress_header("reviewing")
    _append_context_and_triage(lines, issue_dir, "reviewing", projection, owner)
    review_request_url = str(refs.get("review_request_url", "")).strip()
    review_lines = [f"- Request: {review_request_url}"] if review_request_url else ["- Request: Not created yet."]
    pr_review = _event_lookup(issue_dir, "gcw-pr-review")
    if pr_review:
        result = str(pr_review.get("payload", {}).get("result", "")).strip()
        if result:
            review_lines.append(f"- Automatic review: {result}")
    _append_section(lines, "## Review", review_lines)
    return "\n".join(lines).rstrip() + "\n"


def _render_changes_requested(
    issue_dir: Path,
    projection: dict[str, Any],
    owner: dict[str, Any],
    refs: dict[str, Any],
) -> str:
    lines = _progress_header("changes-requested")
    _append_context_and_triage(lines, issue_dir, "changes-requested", projection, owner)
    review_request_url = str(refs.get("review_request_url", "")).strip()
    review_lines = [f"- Request: {review_request_url}"] if review_request_url else ["- Request: Not recorded."]
    _append_section(lines, "## Review", review_lines)
    feedback = projection.get("active_feedback") if isinstance(projection.get("active_feedback"), dict) else {}
    source = str(feedback.get("source", "")).strip()
    reason = str(feedback.get("reason", "")).strip()
    feedback_lines: list[str] = []
    if source:
        feedback_lines.append(f"- Source: {source}")
    if reason:
        feedback_lines.append(f"- Reason: {reason}")
    _append_section(lines, "## Feedback", feedback_lines or ["- Reason: Not recorded."])
    return "\n".join(lines).rstrip() + "\n"


def _render_blocked(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any]) -> str:
    lines = _progress_header("blocked")
    _append_context_and_triage(lines, issue_dir, "blocked", projection, owner)
    blocker = projection.get("active_blocker") if isinstance(projection.get("active_blocker"), dict) else {}
    reason = str(blocker.get("reason", "")).strip()
    resume_phase = str(blocker.get("resume_phase", "")).strip()
    resume_step = str(blocker.get("resume_step", "")).strip()
    blocker_lines = []
    if reason:
        blocker_lines.append(f"- Reason: {reason}")
    if resume_phase and resume_step:
        blocker_lines.append(f"- Resume: {resume_step} at {resume_phase}")
    _append_section(lines, "## Blocker", blocker_lines or ["- Reason: Not recorded."])
    return "\n".join(lines).rstrip() + "\n"


def _render_review_complete(issue_dir: Path, projection: dict[str, Any], owner: dict[str, Any]) -> str:
    lines = _progress_header("review-complete")
    _append_context_and_triage(lines, issue_dir, "review-complete", projection, owner)
    complete = _event_lookup(issue_dir, "review-complete")
    outcome = str(complete.get("payload", {}).get("result", "")).strip() if complete else ""
    _append_section(lines, "## Outcome", [f"- Result: {outcome}"] if outcome else ["- Result: Not recorded."])
    return "\n".join(lines).rstrip() + "\n"


def _render_progress_for_projection(
    issue_dir: Path,
    projection: dict[str, Any],
    overlay: dict[str, Any] | None = None,
) -> str:
    owner = projection.get("owner") if isinstance(projection.get("owner"), dict) else {}
    refs = projection.get("refs") if isinstance(projection.get("refs"), dict) else {}
    phase = str(projection.get("phase", "unknown"))

    with milestone_render_context(overlay):
        if phase == "issue-clarifying":
            return _render_issue_clarifying(issue_dir, projection, owner)
        if phase == "planned":
            return _render_planned_progress(issue_dir, projection, owner)
        if phase == "ready-for-implementation":
            return _render_ready_for_implementation(issue_dir, projection, owner)
        if phase == "implementing":
            return _render_implementing(issue_dir, projection, owner)
        if phase == "ready-for-review":
            return _render_ready_for_review(issue_dir, projection, owner)
        if phase == "reviewing":
            return _render_reviewing(issue_dir, projection, owner, refs)
        if phase == "changes-requested":
            return _render_changes_requested(issue_dir, projection, owner, refs)
        if phase == "blocked":
            return _render_blocked(issue_dir, projection, owner)
        if phase == "review-complete":
            return _render_review_complete(issue_dir, projection, owner)
        return _render_early_progress(issue_dir, phase, projection, owner)


def render_progress_comment(args: argparse.Namespace) -> str:
    issue_dir = args.issue_dir
    milestone_event = getattr(args, "milestone_event", None)
    milestone_payload = getattr(args, "milestone_payload", None)
    overlay: dict[str, Any] | None = None

    if milestone_event and isinstance(milestone_payload, dict):
        events = load_events(issue_dir)
        overlay = build_preview_event(events, str(milestone_event), milestone_payload)
        projection = reduce_workflow(events + [overlay])
    else:
        current = assert_projection_current(issue_dir)
        if not current["ok"]:
            raise ValueError("; ".join(current["errors"]))
        projection = current["projection"]

    return _render_progress_for_projection(issue_dir, projection, overlay)


def render_recorded_progress_comment(issue_dir: Path, event: dict[str, Any]) -> str:
    seq = event.get("seq")
    if not isinstance(seq, int):
        raise ValueError("recorded event is missing integer seq")
    events = load_events(issue_dir)
    prior_events = [
        candidate
        for candidate in events
        if isinstance(candidate.get("seq"), int) and candidate["seq"] < seq
    ]
    projection = reduce_workflow(prior_events + [event])
    return _render_progress_for_projection(issue_dir, projection, event)


def render_review_request(args: argparse.Namespace) -> str:
    current = assert_projection_current(args.issue_dir)
    if not current["ok"]:
        raise ValueError("; ".join(current["errors"]))
    latest_ready = _event_lookup(args.issue_dir, "gcw-implement-check", lambda event: event.get("payload", {}).get("gate", {}).get("ok") is True)
    if latest_ready is None:
        raise ValueError("passing gcw-implement-check event is missing")
    readiness = latest_ready.get("payload", {})
    review_request = readiness.get("review_request") if isinstance(readiness.get("review_request"), dict) else {}
    gate = readiness.get("gate") if isinstance(readiness.get("gate"), dict) else {}
    validations = readiness.get("validation") if isinstance(readiness.get("validation"), list) else gate.get("validation", [])
    projection = current["projection"]
    issue_id = projection.get("issue")
    issue_link = str(review_request.get("issue_link", "")).strip()
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
    ]
    if issue_link:
        lines.append(issue_link)
    if issue_id is not None:
        closes = f"Closes #{issue_id}"
        if closes.casefold() not in issue_link.casefold():
            if issue_link:
                lines.append("")
            lines.append(closes)
    if not issue_link and issue_id is None:
        lines.append("- Not recorded.")
    lines.extend(
        [
            "",
            "## Validation",
            "",
        ]
    )
    if validations:
        for validation in validations:
            if isinstance(validation, dict):
                lines.append(f"- {validation.get('command', '')}: {validation.get('result', '')}")
    else:
        lines.append("- Not recorded.")
    if readiness.get("scope"):
        lines.extend(["", "## Scope", "", str(readiness["scope"]).strip()])
    lines.extend(["", "## Planning", ""])
    links = planning_links_markdown(readiness, projection)
    lines.extend(links if links else ["- Not recorded."])
    lines.extend(
        [
            "",
            "## Progress Comment",
            "",
            str(projection.get("refs", {}).get("progress_comment_url", "")).strip(),
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
