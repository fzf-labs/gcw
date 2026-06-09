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


if __name__ == "__main__":
    unittest.main()
