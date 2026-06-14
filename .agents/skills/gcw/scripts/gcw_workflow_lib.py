from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

try:
    import jsonschema as _jsonschema_mod
    _HAS_JSONSCHEMA = True
except ImportError:
    _jsonschema_mod = None
    _HAS_JSONSCHEMA = False

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
_EVENT_SCHEMA_PATH = _SCHEMA_DIR / "event.schema.json"
_LABELS_PATH = Path(__file__).resolve().parents[2] / "gcw-issue-prepare" / "labels.json"
_GITHUB_LEGACY_LABEL_GROUPS = frozenset({"type", "priority"})


STATES = (
    "issue-opened",
    "issue-clarifying",
    "ready-for-planning",
    "planned",
    "ready-for-implementation",
    "implementing",
    "ready-for-review",
    "reviewing",
    "changes-requested",
    "blocked",
    "review-complete",
)

VALID_EVENT_NAMES = frozenset({
    "gcw-issue-intake",
    "gcw-issue-prepare",
    "gcw-issue-to-spec",
    "gcw-spec-check",
    "gcw-implement",
    "gcw-implement-check",
    "gcw-pr-publish",
    "gcw-pr-review",
    "gcw-block",
    "gcw-clarify",
    "review-complete",
})

NEXT_ALLOWED_STEPS: dict[str, list[str]] = {
    "issue-opened": ["gcw-issue-prepare"],
    "issue-clarifying": ["gcw-issue-prepare"],
    "ready-for-planning": ["gcw-issue-to-spec"],
    "planned": ["gcw-spec-check"],
    "ready-for-implementation": ["gcw-implement"],
    "implementing": ["gcw-implement", "gcw-implement-check", "gcw-block", "gcw-clarify"],
    "ready-for-review": ["gcw-pr-publish"],
    "reviewing": ["gcw-pr-review"],
    "changes-requested": ["gcw-implement"],
    "blocked": [],
    "review-complete": [],
}

PLANNING_FILES = ("task_plan.md", "findings.md", "progress.md")


class WorkflowError(ValueError):
    """Raised when GCW event history cannot be reduced into a valid projection."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{path.name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"{path.name} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, sort_keys=True) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".gcw-tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def events_dir(issue_dir: Path) -> Path:
    return issue_dir / "events"


def projection_path(issue_dir: Path) -> Path:
    return issue_dir / "workflow.json"


def _event_path(issue_dir: Path, seq: int, event_name: str) -> Path:
    return events_dir(issue_dir) / f"{seq:03d}-{event_name}.json"


def load_events(issue_dir: Path) -> list[dict[str, Any]]:
    directory = events_dir(issue_dir)
    if not directory.is_dir():
        return []
    events = [read_json(path) for path in sorted(directory.glob("*.json"))]
    return sorted(events, key=lambda item: int(item.get("seq", -1)))


def hash_events(events: list[dict[str, Any]]) -> str:
    encoded = json.dumps(events, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _issue_from_event(event: dict[str, Any]) -> Any:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    refs = event.get("refs") if isinstance(event.get("refs"), dict) else {}
    return refs.get("issue") or payload.get("issue") or "unknown"


def _validate_event_name(event_name: str) -> None:
    if event_name not in VALID_EVENT_NAMES:
        raise WorkflowError(f"unknown event {event_name}")


def _validate_event_integrity(event: dict[str, Any], path: Path | None = None) -> list[str]:
    errors: list[str] = []
    event_name = event.get("event", "")
    seq = event.get("seq")
    if path is not None:
        expected_name_prefix = f"{seq:03d}-"
        if not path.name.startswith(expected_name_prefix):
            errors.append(f"{path.name}: filename seq does not match content seq {seq}")
        if event_name and event_name not in path.name:
            errors.append(f"{path.name}: filename event name does not match content event '{event_name}'")
    return errors


def _load_label_groups() -> dict[str, list[str]]:
    if not _LABELS_PATH.is_file():
        return {}
    data = json.loads(_LABELS_PATH.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    grouped: dict[str, list[str]] = {}
    if not isinstance(labels, dict):
        return grouped
    for name, meta in labels.items():
        if isinstance(meta, dict):
            grouped.setdefault(str(meta.get("group", "")), []).append(str(name))
    return grouped


def _intake_platform(issue_dir: Path) -> str:
    intake_path = events_dir(issue_dir) / "000-gcw-issue-intake.json"
    if not intake_path.is_file():
        return "github"
    try:
        intake = read_json(intake_path)
    except WorkflowError:
        return "github"
    payload = intake.get("payload") if isinstance(intake.get("payload"), dict) else {}
    platform = str(payload.get("platform", "")).strip()
    return platform or "github"


def _validate_prepare_payload(payload: dict[str, Any], platform: str) -> list[str]:
    errors: list[str] = []
    labels_applied = payload.get("labels_applied")
    if isinstance(labels_applied, list) and platform == "github":
        grouped = _load_label_groups()
        for label in labels_applied:
            name = str(label)
            for group in _GITHUB_LEGACY_LABEL_GROUPS:
                if name in grouped.get(group, []):
                    errors.append(
                        f"gcw-issue-prepare labels_applied must not include {name} on github"
                    )
    remote_sync = payload.get("remote_sync")
    if isinstance(remote_sync, dict):
        sync_platform = str(remote_sync.get("platform", ""))
        if sync_platform and sync_platform != platform:
            errors.append("gcw-issue-prepare remote_sync.platform does not match intake platform")
        labels = remote_sync.get("labels")
        if isinstance(labels_applied, list) and isinstance(labels, list):
            if sorted(str(x) for x in labels_applied) != sorted(str(x) for x in labels):
                errors.append("gcw-issue-prepare remote_sync.labels does not match labels_applied")
    return errors


def progress_comment_required(event_name: str, payload: dict[str, Any], phase_before: str) -> bool:
    if event_name in {
        "gcw-issue-prepare",
        "gcw-issue-to-spec",
        "gcw-spec-check",
        "gcw-pr-publish",
        "gcw-pr-review",
        "gcw-block",
        "gcw-clarify",
        "review-complete",
    }:
        return True
    if event_name == "gcw-implement":
        return phase_before in ("ready-for-implementation", "changes-requested")
    if event_name == "gcw-implement-check":
        gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
        return gate.get("ok") is True
    return False


def apply_progress_comment_url(
    refs: dict[str, Any],
    event_name: str,
    payload: dict[str, Any],
    phase_before: str,
) -> list[str]:
    errors: list[str] = []
    url = str(payload.get("progress_comment_url", "")).strip()
    if progress_comment_required(event_name, payload, phase_before) and not url:
        errors.append(f"{event_name} requires progress_comment_url")
    if url:
        refs["progress_comment_url"] = url
    return errors


def validate_payload(event_name: str, payload: dict[str, Any], issue_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if event_name == "gcw-issue-intake":
        for key in ("issue", "platform", "repository", "branch"):
            if key not in payload:
                errors.append(f"gcw-issue-intake missing payload.{key}")
        owner = payload.get("owner")
        if not isinstance(owner, dict) or "kind" not in owner or "id" not in owner:
            errors.append("gcw-issue-intake payload.owner must have kind and id")
        if "platform" in payload and payload["platform"] not in ("github", "gitlab"):
            errors.append("gcw-issue-intake payload.platform must be github or gitlab")
    elif event_name == "gcw-issue-prepare":
        if "ready" not in payload:
            errors.append("gcw-issue-prepare missing payload.ready")
        elif not isinstance(payload["ready"], bool):
            errors.append("gcw-issue-prepare payload.ready must be boolean")
        if payload.get("ready") is False and not str(payload.get("question", "")).strip():
            errors.append("gcw-issue-prepare requires question when ready is false")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-issue-prepare requires progress_comment_url")
        if issue_dir is not None:
            errors.extend(_validate_prepare_payload(payload, _intake_platform(issue_dir)))
    elif event_name == "gcw-issue-to-spec":
        if payload.get("planning_commit_pushed") is not True:
            errors.append("gcw-issue-to-spec requires planning_commit_pushed true")
        spec_refs = payload.get("spec_refs")
        if not isinstance(spec_refs, dict):
            errors.append("gcw-issue-to-spec payload.spec_refs must be an object")
        elif not all(k in spec_refs for k in ("task_plan_sha", "findings_sha", "progress_sha")):
            errors.append("gcw-issue-to-spec payload.spec_refs missing required sha fields")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-issue-to-spec requires progress_comment_url")
    elif event_name == "gcw-spec-check":
        gate = payload.get("gate")
        if not isinstance(gate, dict):
            errors.append("gcw-spec-check payload.gate must be an object")
        elif "ok" not in gate:
            errors.append("gcw-spec-check payload.gate missing ok")
        elif not isinstance(gate["ok"], bool):
            errors.append("gcw-spec-check payload.gate.ok must be boolean")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-spec-check requires progress_comment_url")
    elif event_name == "gcw-implement":
        if not str(payload.get("work_summary", "")).strip():
            errors.append("gcw-implement payload.work_summary is required and non-empty")
    elif event_name == "gcw-implement-check":
        for key in ("gate", "review_request", "risks", "scope", "reviewer_notes", "self_review", "spec_refs"):
            if key not in payload:
                errors.append(f"gcw-implement-check payload missing {key}")
        gate = payload.get("gate")
        if isinstance(gate, dict) and "ok" not in gate:
            errors.append("gcw-implement-check payload.gate missing ok")
        review_request = payload.get("review_request")
        if isinstance(review_request, dict):
            for key in ("title", "summary", "issue_link"):
                if not str(review_request.get(key, "")).strip():
                    errors.append(f"gcw-implement-check payload.review_request.{key} is required")
        gate = payload.get("gate")
        if isinstance(gate, dict) and gate.get("ok") is True:
            if not str(payload.get("progress_comment_url", "")).strip():
                errors.append("gcw-implement-check requires progress_comment_url when gate.ok is true")
    elif event_name == "gcw-pr-publish":
        if not str(payload.get("review_request_url", "")).strip():
            errors.append("gcw-pr-publish payload.review_request_url is required")
        effects = payload.get("effects")
        if not isinstance(effects, list) or not effects:
            errors.append("gcw-pr-publish payload.effects must be a non-empty array")
        elif not any(isinstance(e, dict) and e.get("status") == "applied" for e in effects):
            errors.append("gcw-pr-publish requires an applied effect")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-pr-publish requires progress_comment_url")
    elif event_name == "gcw-pr-review":
        result = payload.get("result")
        if result not in ("passed", "changes-requested", "blocked"):
            errors.append("gcw-pr-review payload.result must be passed, changes-requested, or blocked")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-pr-review requires progress_comment_url")
    elif event_name == "gcw-block":
        for key in ("reason", "resume_phase", "resume_step"):
            if not str(payload.get(key, "")).strip():
                errors.append(f"gcw-block payload.{key} is required")
        resume_phase = payload.get("resume_phase", "")
        if resume_phase and resume_phase not in STATES:
            errors.append(f"gcw-block payload.resume_phase '{resume_phase}' is not a valid state")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-block requires progress_comment_url")
    elif event_name == "gcw-clarify":
        for key in ("question", "source_phase"):
            if not str(payload.get(key, "")).strip():
                errors.append(f"gcw-clarify payload.{key} is required")
        source_phase = payload.get("source_phase", "")
        if source_phase and source_phase not in STATES:
            errors.append(f"gcw-clarify payload.source_phase '{source_phase}' is not a valid state")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-clarify requires progress_comment_url")
    elif event_name == "review-complete":
        result = payload.get("result")
        if result not in ("merged", "closed", "accepted", "rejected"):
            errors.append("review-complete payload.result must be merged, closed, accepted, or rejected")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("review-complete requires progress_comment_url")
    return errors


def validate_parent_chain(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for event in events:
        seq = event.get("seq")
        parent = event.get("parent") if isinstance(event.get("parent"), dict) else {}
        expected = parent.get("expected_last_seq")
        if expected is None:
            errors.append(f"seq {seq}: parent.expected_last_seq is required")
            continue
        required_last = int(seq) - 1 if seq is not None else None
        if required_last is not None and int(expected) != required_last:
            errors.append(
                f"seq {seq}: parent.expected_last_seq {expected} does not match prior seq {required_last}"
            )
    return errors


def validate_event_log(issue_dir: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_events_integrity(issue_dir))
    try:
        events = load_events(issue_dir)
    except WorkflowError as exc:
        errors.append(str(exc))
        return errors
    try:
        validate_event_sequence(events)
    except WorkflowError as exc:
        errors.append(str(exc))
    errors.extend(validate_parent_chain(events))
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_name = str(event.get("event", ""))
        for err in validate_payload(event_name, payload, issue_dir):
            errors.append(f"seq {event.get('seq', '?')} {event_name}: {err}")
        for err in validate_event_schema(event):
            errors.append(f"seq {event.get('seq', '?')} {event_name}: {err}")
    return errors


def append_event(
    issue_dir: Path,
    event: dict[str, Any],
    expected_last_seq: int | None = None,
    parent_projection_hash: str | None = None,
    validate_schema: bool | None = None,
) -> dict[str, Any]:
    if validate_schema is None:
        validate_schema = _HAS_JSONSCHEMA
    existing = load_events(issue_dir)
    current_last_seq = existing[-1]["seq"] if existing else -1
    parent = event.setdefault("parent", {})
    if expected_last_seq is None:
        expected_last_seq = parent.get("expected_last_seq")
    if expected_last_seq is not None and int(expected_last_seq) != current_last_seq:
        raise WorkflowError(f"expected last seq {expected_last_seq}, found {current_last_seq}")
    if parent_projection_hash is not None:
        parent["parent_projection_hash"] = parent_projection_hash

    seq = current_last_seq + 1
    event_name = str(event["event"])
    _validate_event_name(event_name)
    event["schema"] = event.get("schema", "gcw.event/v1")
    event["seq"] = seq
    event["event_id"] = event.get("event_id", f"gcw-{_issue_from_event(event)}-{seq:03d}-{event_name}")
    event["at"] = event.get("at", _now())
    event.setdefault("actor", {"kind": "local", "id": "unknown"})
    parent.setdefault("expected_last_seq", current_last_seq)
    event.setdefault("refs", {})
    event.setdefault("payload", {})

    payload_errors = validate_payload(event_name, event["payload"])
    if payload_errors:
        raise WorkflowError("; ".join(payload_errors))

    if validate_schema:
        schema_errors = validate_event_schema(event)
        if schema_errors:
            raise WorkflowError("; ".join(schema_errors))

    path = _event_path(issue_dir, seq, event_name)
    if path.exists():
        raise WorkflowError(f"{path.name} already exists")
    write_json(path, event)
    return event


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


def validate_event_sequence(events: list[dict[str, Any]]) -> None:
    for expected, event in enumerate(events):
        if event.get("seq") != expected:
            raise WorkflowError(f"event sequence must be continuous; expected {expected}, found {event.get('seq')}")
    if events and events[0].get("event") != "gcw-issue-intake":
        raise WorkflowError("first event must be gcw-issue-intake")


def validate_events_integrity(issue_dir: Path) -> list[str]:
    directory = events_dir(issue_dir)
    if not directory.is_dir():
        return ["events directory is missing"]
    errors: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            event = read_json(path)
        except WorkflowError as exc:
            errors.append(str(exc))
            continue
        errors.extend(_validate_event_integrity(event, path))
    return errors


def validate_event_schema(event: dict[str, Any]) -> list[str]:
    if not _HAS_JSONSCHEMA:
        return []
    if not _EVENT_SCHEMA_PATH.is_file():
        return ["event.schema.json not found"]
    try:
        schema = json.loads(_EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"event.schema.json is invalid: {exc}"]
    try:
        _jsonschema_mod.validate(event, schema)
    except _jsonschema_mod.ValidationError as exc:
        return [f"event schema validation: {exc.message}"]
    return []


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

        if event_name == "gcw-issue-prepare":
            _require_phase(phase, {"issue-opened", "issue-clarifying"}, event_name)
            if event_payload.get("ready") is True:
                phase = "ready-for-planning"
            else:
                if not str(event_payload.get("question", "")).strip():
                    raise WorkflowError("gcw-issue-prepare requires question when ready is false")
                phase = "issue-clarifying"
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


def build_projection(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "gcw.workflow_projection/v1",
        "generated_from": {
            "last_seq": events[-1]["seq"] if events else -1,
            "events_hash": hash_events(events),
            "generated_at": _now(),
        },
        "projection": reduce_workflow(events),
    }


def write_projection(issue_dir: Path) -> dict[str, Any]:
    projection = build_projection(load_events(issue_dir))
    write_json(projection_path(issue_dir), projection)
    return projection


def load_projection(issue_dir: Path) -> dict[str, Any]:
    path = projection_path(issue_dir)
    if not path.is_file():
        raise WorkflowError("workflow.json is missing")
    return read_json(path)


def assert_projection_current(issue_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        events = load_events(issue_dir)
        expected = build_projection(events)
        actual = load_projection(issue_dir)
    except WorkflowError as exc:
        return {"ok": False, "errors": [str(exc)]}

    if actual.get("generated_from", {}).get("events_hash") != expected["generated_from"]["events_hash"]:
        errors.append("workflow.json generated_from.events_hash does not match events")
    if actual.get("projection") != expected["projection"]:
        errors.append("workflow.json projection does not match reduced events")
    return {"ok": not errors, "errors": errors, "projection": expected["projection"]}


def find_latest_event(
    issue_dir: Path,
    event_name: str,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any] | None:
    for event in reversed(load_events(issue_dir)):
        if event.get("event") != event_name:
            continue
        if predicate is None or predicate(event):
            return event
    return None
