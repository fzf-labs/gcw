from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = ROOT / ".agents/skills/gcw/schemas"


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


if __name__ == "__main__":
    unittest.main()
