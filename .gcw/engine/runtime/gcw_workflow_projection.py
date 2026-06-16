from __future__ import annotations

from pathlib import Path
from typing import Any

from gcw_workflow_errors import WorkflowError
from gcw_workflow_reducer import reduce_workflow
from gcw_workflow_store import hash_events, load_events, projection_path, write_json


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    from gcw_workflow_store import read_json

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
