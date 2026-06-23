from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gcw_workflow_errors import WorkflowError
from gcw_workflow_store import events_dir, load_events, read_json
from gcw_workflow_contracts import STATES

try:
    import jsonschema as _jsonschema_mod
    _HAS_JSONSCHEMA = True
except ImportError:
    _jsonschema_mod = None
    _HAS_JSONSCHEMA = False

_RUNTIME_DIR = Path(__file__).resolve().parent
_SCHEMA_DIR = _RUNTIME_DIR / "schemas"
_EVENT_SCHEMA_PATH = _SCHEMA_DIR / "event.schema.json"
_LABELS_PATH = _RUNTIME_DIR / "labels.json"
_READINESS_LIB_DIR = _RUNTIME_DIR / "readiness"
_GITHUB_LEGACY_LABEL_GROUPS = frozenset({"type", "priority"})


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


def _workflow_platform(issue_dir: Path) -> str:
    events = load_events(issue_dir)
    if not events:
        return "github"
    payload = events[0].get("payload") if isinstance(events[0].get("payload"), dict) else {}
    platform = str(payload.get("platform", "")).strip()
    return platform or "github"


def _triage_validation_platform(payload: dict[str, Any], issue_dir: Path) -> str:
    events = load_events(issue_dir)
    if events:
        return _workflow_platform(issue_dir)
    platform = str(payload.get("platform", "")).strip()
    return platform or "github"


def _validate_triage_payload(payload: dict[str, Any], platform: str, event_name: str = "gcw-issue-triage") -> list[str]:
    errors: list[str] = []
    classification = payload.get("classification")
    if not isinstance(classification, dict) or not classification:
        errors.append(f"{event_name} classification is required")
    else:
        for key in ("type", "priority"):
            if not str(classification.get(key, "")).strip():
                errors.append(f"{event_name} classification.{key} is required")

    labels_applied = payload.get("labels_applied")
    if not isinstance(labels_applied, list) or not labels_applied:
        errors.append(f"{event_name} labels_applied must be a non-empty array")
    if isinstance(labels_applied, list) and platform == "github":
        grouped = _load_label_groups()
        for label in labels_applied:
            name = str(label)
            for group in _GITHUB_LEGACY_LABEL_GROUPS:
                if name in grouped.get(group, []):
                    errors.append(f"{event_name} labels_applied must not include {name} on github")
    remote_sync = payload.get("remote_sync")
    if not isinstance(remote_sync, dict) or not remote_sync:
        errors.append(f"{event_name} remote_sync is required")
    else:
        sync_platform = str(remote_sync.get("platform", "")).strip()
        if sync_platform and sync_platform != platform:
            errors.append(f"{event_name} remote_sync.platform does not match workflow platform")
        labels = remote_sync.get("labels")
        if isinstance(labels_applied, list) and isinstance(labels, list):
            if sorted(str(x) for x in labels_applied) != sorted(str(x) for x in labels):
                errors.append(f"{event_name} remote_sync.labels does not match labels_applied")
    return errors


def _validate_clarify_payload(payload: dict[str, Any], event_name: str = "gcw-issue-clarify") -> list[str]:
    errors: list[str] = []
    gate = payload.get("gate")
    if not isinstance(gate, dict):
        errors.append(f"{event_name} payload.gate is required")
        return errors

    ready = payload.get("ready")
    if not isinstance(ready, bool):
        errors.append(f"{event_name} payload.ready must be boolean")
    gate_ok = gate.get("ok") is True
    if isinstance(ready, bool) and ready is not gate_ok:
        errors.append(f"{event_name} payload.ready must match gate.ok")

    if not gate_ok:
        if not str(payload.get("question", "")).strip():
            errors.append(f"{event_name} requires question when ready is false")
        gate_errors = gate.get("errors")
        if not isinstance(gate_errors, list) or not gate_errors:
            errors.append(f"{event_name} gate.errors must be non-empty when gate.ok is false")

    if _READINESS_LIB_DIR.is_dir():
        import sys

        scripts_path = str(_READINESS_LIB_DIR)
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        try:
            from readiness_lib import validate_gate_against_rubric

            errors.extend(validate_gate_against_rubric(gate))
        except ImportError:
            errors.append(f"{event_name} readiness_lib is unavailable for gate validation")
    return errors


def progress_comment_required(event_name: str, payload: dict[str, Any], phase_before: str) -> bool:
    if event_name in {
        "gcw-issue-triage",
        "gcw-issue-clarify",
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
    if event_name == "gcw-issue-triage":
        for key in ("issue", "platform", "repository", "branch"):
            if key not in payload:
                errors.append(f"gcw-issue-triage missing payload.{key}")
        owner = payload.get("owner")
        if not isinstance(owner, dict) or "kind" not in owner or "id" not in owner:
            errors.append("gcw-issue-triage payload.owner must have kind and id")
        if "platform" in payload and payload["platform"] not in ("github", "gitlab"):
            errors.append("gcw-issue-triage payload.platform must be github or gitlab")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-issue-triage requires progress_comment_url")
        classification = payload.get("classification")
        if not isinstance(classification, dict) or not classification:
            errors.append("gcw-issue-triage classification is required")
        else:
            for key in ("type", "priority"):
                if not str(classification.get(key, "")).strip():
                    errors.append(f"gcw-issue-triage classification.{key} is required")
        if not isinstance(payload.get("labels_applied"), list) or not payload.get("labels_applied"):
            errors.append("gcw-issue-triage labels_applied must be a non-empty array")
        if not isinstance(payload.get("remote_sync"), dict) or not payload.get("remote_sync"):
            errors.append("gcw-issue-triage remote_sync is required")
        if issue_dir is not None:
            errors.extend(_validate_triage_payload(payload, _triage_validation_platform(payload, issue_dir)))
    elif event_name == "gcw-issue-clarify":
        if "ready" not in payload:
            errors.append("gcw-issue-clarify missing payload.ready")
        elif not isinstance(payload["ready"], bool):
            errors.append("gcw-issue-clarify payload.ready must be boolean")
        if not isinstance(payload.get("gate"), dict):
            errors.append("gcw-issue-clarify payload.gate is required")
        if not str(payload.get("progress_comment_url", "")).strip():
            errors.append("gcw-issue-clarify requires progress_comment_url")
        if issue_dir is not None:
            errors.extend(_validate_clarify_payload(payload))
        elif isinstance(payload.get("gate"), dict):
            gate = payload["gate"]
            if payload.get("ready") is not gate.get("ok"):
                errors.append("gcw-issue-clarify payload.ready must match gate.ok")
            if payload.get("ready") is False and not str(payload.get("question", "")).strip():
                errors.append("gcw-issue-clarify requires question when ready is false")
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


def validate_event_sequence(events: list[dict[str, Any]]) -> None:
    for expected, event in enumerate(events):
        if event.get("seq") != expected:
            raise WorkflowError(f"event sequence must be continuous; expected {expected}, found {event.get('seq')}")
    if events and events[0].get("event") != "gcw-issue-triage":
        raise WorkflowError("first event must be gcw-issue-triage")


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
        return []
    try:
        schema = json.loads(_EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"event.schema.json is invalid: {exc}"]
    try:
        _jsonschema_mod.validate(event, schema)
    except _jsonschema_mod.ValidationError as exc:
        return [f"event schema validation: {exc.message}"]
    return []


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
            errors.append(f"seq {seq}: parent.expected_last_seq {expected} does not match prior seq {required_last}")
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
