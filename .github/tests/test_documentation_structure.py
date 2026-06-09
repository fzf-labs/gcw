from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DocumentationStructureTest(unittest.TestCase):
    def test_guiding_documentation_uses_focused_names(self) -> None:
        expected_paths = [
            "README.md",
            "CONTRIBUTING.md",
            "CONTEXT.md",
            "docs/overview.md",
            "docs/concepts.md",
            "docs/workflow.md",
            "docs/evidence.md",
            "docs/hosted-runners.md",
            "docs/validation.md",
            "docs/roadmap.md",
            "docs/adr/0001-commit-planning-files.md",
        ]
        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_old_executable_workflow_document_name_is_removed(self) -> None:
        self.assertFalse((ROOT / "docs/gcw-executable-workflow.md").exists())

    def test_repository_markdown_does_not_link_old_workflow_name(self) -> None:
        offenders = []
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if "gcw-executable-workflow.md" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
