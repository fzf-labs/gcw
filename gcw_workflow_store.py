from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from gcw_workflow_errors import WorkflowError
from gcw_workflow_contracts import VALID_EVENT_NAMES


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


def find_latest_event(
    issue_dir: Path,
    event_name: str,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    max_seq: int | None = None,
) -> dict[str, Any] | None:
    for event in reversed(load_events(issue_dir)):
        seq = event.get("seq")
        if max_seq is not None and isinstance(seq, int) and seq > max_seq:
            continue
        if event.get("event") != event_name:
            continue
        if predicate is None or predicate(event):
            return event
    return None


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


def _default_actor() -> dict[str, str]:
    kind = os.environ.get("GCW_ACTOR_KIND", "local").strip() or "local"
    actor_id = os.environ.get("GCW_ACTOR_ID", "unknown").strip() or "unknown"
    return {"kind": kind, "id": actor_id}


def append_event(
    issue_dir: Path,
    event: dict[str, Any],
    expected_last_seq: int | None = None,
    parent_projection_hash: str | None = None,
    validate_schema: bool | None = None,
) -> dict[str, Any]:
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
    event.setdefault("actor", _default_actor())
    parent.setdefault("expected_last_seq", current_last_seq)
    event.setdefault("refs", {})
    event.setdefault("payload", {})

    from gcw_workflow_validation import validate_event_schema, validate_payload

    payload_errors = validate_payload(event_name, event["payload"], issue_dir)
    if payload_errors:
        raise WorkflowError("; ".join(payload_errors))

    if validate_schema is not False:
        schema_errors = validate_event_schema(event)
        if schema_errors:
            raise WorkflowError("; ".join(schema_errors))

    path = _event_path(issue_dir, seq, event_name)
    if path.exists():
        raise WorkflowError(f"{path.name} already exists")
    write_json(path, event)
    return event

