from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from gcw_workflow_contracts import NEXT_ALLOWED_STEPS, STATES
from gcw_workflow_errors import WorkflowError
from gcw_workflow_store import find_latest_event, load_events
from gcw_workflow_validation import apply_progress_comment_url, validate_event_sequence, validate_payload


PREVIEW_PROGRESS_COMMENT_URL = "https://gcw.preview/progress-comment"


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_phase(phase: str, allowed: set[str], event_name: str) -> None:
    if phase not in allowed:
        expected = ", ".join(sorted(allowed))
        raise WorkflowError(f"{event_name} requires phase {expected}; current phase is {phase}")


def _latest_applied_effect(payload: dict[str, Any]) -> dict[str, Any] | None:
    effects = payload.get("effects")
    if not isinstance(effects, list):
        return None
    for effect in effects:
        if isinstance(effect, dict) and effect.get("status") == "applied":
            return effect
    return None


def reduce_workflow(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        raise WorkflowError("events are missing")
    validate_event_sequence(events)
    for event in events:
        event_name = str(event.get("event", ""))
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        payload_errors = validate_payload(event_name, payload)
        if payload_errors:
            raise WorkflowError(f"seq {event.get('seq', '?')}: {'; '.join(payload_errors)}")

    intake = events[0]
    payload = intake.get("payload") if isinstance(intake.get("payload"), dict) else {}
    for key in ("issue", "platform", "repository", "branch", "owner"):
        if key not in payload:
            raise WorkflowError(f"gcw-issue-intake missing payload.{key}")

    phase = "issue-opened"
    last_completed_step = "gcw-issue-intake"
    refs: dict[str, Any] = {}
    active_feedback: dict[str, Any] | None = None
    active_blocker: dict[str, Any] | None = None

    for event in events[1:]:
        event_name = str(event.get("event", ""))
        event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        last_completed_step = event_name
        phase_before = phase

        if event_name == "gcw-issue-triage":
            _require_phase(phase, {"issue-opened"}, event_name)
            phase = "issue-triaged"
        elif event_name == "gcw-issue-clarify":
            _require_phase(phase, {"issue-triaged", "issue-clarifying"}, event_name)
            if event_payload.get("ready") is True:
                phase = "ready-for-planning"
                active_feedback = None
            else:
                if not str(event_payload.get("question", "")).strip():
                    raise WorkflowError("gcw-issue-clarify requires question when ready is false")
                phase = "issue-clarifying"
                active_feedback = {
                    "source": "gcw-issue-clarify",
                    "reason": event_payload.get("question", ""),
                    "from_event_id": event.get("event_id", ""),
                }
        elif event_name == "gcw-issue-to-spec":
            _require_phase(phase, {"ready-for-planning"}, event_name)
            if event_payload.get("planning_commit_pushed") is not True:
                raise WorkflowError("gcw-issue-to-spec requires planning_commit_pushed true")
            phase = "planned"
        elif event_name == "gcw-spec-check":
            _require_phase(phase, {"planned"}, event_name)
            gate = event_payload.get("gate") if isinstance(event_payload.get("gate"), dict) else {}
            if gate.get("ok") is True:
                phase = "ready-for-implementation"
            elif event_payload.get("result") == "clarifying":
                phase = "issue-clarifying"
                active_feedback = {
                    "source": "spec-check",
                    "reason": event_payload.get("question", ""),
                    "from_event_id": event.get("event_id", ""),
                }
            else:
                phase = "blocked"
                active_blocker = {
                    "source": "spec-check",
                    "reason": event_payload.get("reason") or event_payload.get("block_reason", ""),
                    "from_event_id": event.get("event_id", ""),
                }
        elif event_name == "gcw-implement":
            _require_phase(phase, {"ready-for-implementation", "implementing", "changes-requested"}, event_name)
            phase = "implementing"
            active_feedback = None
            active_blocker = None
        elif event_name == "gcw-implement-check":
            _require_phase(phase, {"implementing"}, event_name)
            gate = event_payload.get("gate") if isinstance(event_payload.get("gate"), dict) else {}
            phase = "ready-for-review" if gate.get("ok") is True else "implementing"
        elif event_name == "gcw-pr-publish":
            _require_phase(phase, {"ready-for-review"}, event_name)
            if _latest_applied_effect(event_payload) is None:
                raise WorkflowError("gcw-pr-publish requires an applied effect")
            refs["review_request_url"] = event_payload.get("review_request_url", "")
            phase = "reviewing"
        elif event_name == "gcw-pr-review":
            _require_phase(phase, {"reviewing"}, event_name)
            result = event_payload.get("result")
            if result == "passed":
                phase = "reviewing"
            elif result == "changes-requested":
                phase = "changes-requested"
                active_feedback = {
                    "source": event_payload.get("feedback_source", "pr-review"),
                    "reason": event_payload.get("reason", ""),
                    "from_event_id": event.get("event_id", ""),
                }
            elif result == "blocked":
                phase = "blocked"
                active_blocker = {
                    "source": "pr-review",
                    "reason": event_payload.get("block_reason", ""),
                    "from_event_id": event.get("event_id", ""),
                }
            else:
                raise WorkflowError("gcw-pr-review result must be passed, changes-requested, or blocked")
        elif event_name == "gcw-block":
            _require_phase(phase, set(STATES) - {"review-complete"}, event_name)
            phase = "blocked"
            active_blocker = {
                "source": "gcw-block",
                "reason": event_payload.get("reason", ""),
                "from_event_id": event.get("event_id", ""),
                "resume_phase": event_payload.get("resume_phase", ""),
                "resume_step": event_payload.get("resume_step", ""),
            }
        elif event_name == "gcw-clarify":
            _require_phase(phase, set(STATES) - {"review-complete"}, event_name)
            phase = "issue-clarifying"
            active_feedback = {
                "source": "gcw-clarify",
                "reason": event_payload.get("question", ""),
                "from_event_id": event.get("event_id", ""),
            }
        elif event_name == "review-complete":
            _require_phase(phase, {"reviewing"}, event_name)
            phase = "review-complete"
        else:
            raise WorkflowError(f"unknown event {event_name}")

        url_errors = apply_progress_comment_url(refs, event_name, event_payload, phase_before)
        if url_errors:
            raise WorkflowError(f"seq {event.get('seq', '?')}: {'; '.join(url_errors)}")

    projection: dict[str, Any] = {
        "issue": payload["issue"],
        "platform": payload["platform"],
        "repository": payload["repository"],
        "branch": payload["branch"],
        "owner": payload["owner"],
        "phase": phase,
        "last_completed_step": last_completed_step,
        "next_allowed_steps": NEXT_ALLOWED_STEPS[phase],
        "refs": refs,
    }
    if active_feedback:
        projection["active_feedback"] = active_feedback
    if active_blocker:
        projection["active_blocker"] = active_blocker
    return projection


def build_preview_event(
    events: list[dict[str, Any]],
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    last_seq = events[-1]["seq"] if events else -1
    preview_payload = dict(payload)
    if not str(preview_payload.get("progress_comment_url", "")).strip():
        preview_payload["progress_comment_url"] = PREVIEW_PROGRESS_COMMENT_URL
    return {
        "actor": {"kind": "local", "id": "preview"},
        "at": _now(),
        "event": event_name,
        "event_id": f"preview-{last_seq + 1}-{event_name}",
        "parent": {"expected_last_seq": last_seq},
        "payload": preview_payload,
        "refs": {},
        "schema": "gcw.event/v1",
        "seq": last_seq + 1,
    }


def preview_projection_for_milestone(
    issue_dir: Path,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    events = load_events(issue_dir)
    overlay = build_preview_event(events, event_name, payload)
    return reduce_workflow(events + [overlay])
