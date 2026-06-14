from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = ROOT / ".agents/skills/gcw/schemas"


def _load_event_schema() -> dict:
    return json.loads((SCHEMA_DIR / "event.schema.json").read_text(encoding="utf-8"))


def _make_valid_event(overrides: dict | None = None) -> dict:
    event = {
        "schema": "gcw.event/v1",
        "seq": 0,
        "event": "gcw-issue-intake",
        "event_id": "gcw-42-000-gcw-issue-intake",
        "at": "2026-06-14T00:00:00Z",
        "actor": {"kind": "local", "id": "cursor-session"},
        "parent": {"expected_last_seq": -1},
        "refs": {"issue": 42, "branch": "gcw/issue-42", "base_branch": "main"},
        "payload": {
            "issue": 42,
            "platform": "github",
            "repository": "owner/repo",
            "branch": "gcw/issue-42",
            "owner": {"kind": "local", "id": "cursor-session"},
        },
    }
    if overrides:
        event.update(overrides)
    return event


class GcwSchemaTest(unittest.TestCase):
    def test_v1_json_schemas_are_present_and_parseable(self) -> None:
        for name in ("event.schema.json", "workflow_projection.schema.json"):
            with self.subTest(schema=name):
                schema_path = SCHEMA_DIR / name
                self.assertTrue(schema_path.is_file(), f"{name} is missing")
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["type"], "object")
                self.assertIn("required", schema)
                self.assertIn("properties", schema)

    def test_event_schema_uses_typed_event_payload_contracts(self) -> None:
        schema = json.loads((SCHEMA_DIR / "event.schema.json").read_text(encoding="utf-8"))
        event_names = {
            branch["properties"]["event"]["const"]
            for branch in schema["oneOf"]
            if "event" in branch.get("properties", {})
        }

        self.assertIn("gcw-issue-intake", event_names)
        self.assertIn("gcw-implement-check", event_names)
        self.assertIn("gcw-pr-publish", event_names)
        self.assertIn("gcw-pr-review", event_names)

    def test_projection_schema_is_generated_cache_only(self) -> None:
        schema = json.loads((SCHEMA_DIR / "workflow_projection.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["required"], ["schema", "generated_from", "projection"])
        self.assertEqual(schema["properties"]["schema"]["const"], "gcw.workflow_projection/v1")
        self.assertIn("events_hash", schema["properties"]["generated_from"]["required"])

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_event_schema_rejects_unknown_event_name(self) -> None:
        schema = _load_event_schema()
        event = _make_valid_event({"event": "gcw-unknown-event"})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(event, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_event_schema_rejects_additional_properties(self) -> None:
        schema = _load_event_schema()
        event = _make_valid_event({"extra_field": "should_fail"})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(event, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_event_schema_rejects_invalid_platform(self) -> None:
        schema = _load_event_schema()
        event = _make_valid_event()
        event["payload"]["platform"] = "svn"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(event, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_projection_schema_rejects_additional_properties(self) -> None:
        schema = json.loads((SCHEMA_DIR / "workflow_projection.schema.json").read_text(encoding="utf-8"))
        projection = {
            "schema": "gcw.workflow_projection/v1",
            "generated_from": {
                "last_seq": 0,
                "events_hash": "sha256:" + "a" * 64,
                "generated_at": "2026-06-14T00:00:00Z",
            },
            "projection": {
                "issue": 42,
                "platform": "github",
                "repository": "owner/repo",
                "branch": "gcw/issue-42",
                "owner": {"kind": "local", "id": "cursor-session"},
                "phase": "issue-opened",
                "last_completed_step": "gcw-issue-intake",
                "next_allowed_steps": ["gcw-issue-triage"],
                "refs": {},
            },
            "extra_field": "should_fail",
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(projection, schema)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_event_schema_all_event_types_have_payload_contracts(self) -> None:
        schema = _load_event_schema()
        expected_events = {
            "gcw-issue-intake",
            "gcw-issue-triage",
            "gcw-issue-clarify",
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
        }
        one_of_events = {
            branch["properties"]["event"]["const"]
            for branch in schema["oneOf"]
            if "event" in branch.get("properties", {})
        }
        self.assertEqual(one_of_events, expected_events)

    @unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
    def test_triage_event_schema_requires_type_and_priority(self) -> None:
        schema = _load_event_schema()
        event = _make_valid_event(
            {
                "seq": 1,
                "event": "gcw-issue-triage",
                "event_id": "gcw-42-001-gcw-issue-triage",
                "parent": {"expected_last_seq": 0},
                "payload": {
                    "classification": {"area": "area:tests"},
                    "labels_applied": ["triaged", "area:tests"],
                    "remote_sync": {
                        "platform": "github",
                        "issue_type": "Feature",
                        "priority": "Medium",
                        "labels": ["triaged", "area:tests"],
                    },
                    "progress_comment_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
                },
            }
        )

        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(event, schema)


if __name__ == "__main__":
    unittest.main()
