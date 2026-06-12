from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = ROOT / ".agents/skills/gcw/schemas"


class GcwSchemaTest(unittest.TestCase):
    def test_v1_json_schemas_are_present_and_parseable(self) -> None:
        for name in ("state.schema.json", "implementation_gate_result.schema.json", "readiness_evidence.schema.json"):
            with self.subTest(schema=name):
                schema_path = SCHEMA_DIR / name
                self.assertTrue(schema_path.is_file(), f"{name} is missing")
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["type"], "object")
                self.assertIn("required", schema)
                self.assertIn("properties", schema)

    def test_state_schema_only_allows_current_states(self) -> None:
        schema = json.loads((SCHEMA_DIR / "state.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["state"]["enum"],
            [
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
            ],
        )

    def test_spec_check_schema_uses_current_step_name(self) -> None:
        schema = json.loads((SCHEMA_DIR / "implementation_gate_result.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["step"]["const"], "spec-check")


if __name__ == "__main__":
    unittest.main()
