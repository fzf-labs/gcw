from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class GcwContractDocSyncTest(unittest.TestCase):
    def test_contract_docs_are_in_sync(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render-gcw-contract-docs.py"), "--check"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

    def test_public_docs_do_not_describe_intake_as_a_main_step(self) -> None:
        public_contracts = [
            ROOT / "README.md",
            ROOT / "docs" / "workflow.md",
            ROOT / "docs" / "hosted-agent.md",
            ROOT / "docs" / "quickstart.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / ".agents" / "skills" / "gcw" / "SKILL.md",
            ROOT / ".agents" / "skills" / "gcw-issue-triage" / "SKILL.md",
            ROOT / ".agents" / "skills" / "gcw-issue-to-spec" / "SKILL.md",
        ]
        forbidden = ("gcw-issue-intake", "issue-opened", "000-gcw-issue-intake", "init-workflow")
        for path in public_contracts:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, msg=f"{path.relative_to(ROOT)} contains {token}")


if __name__ == "__main__":
    unittest.main()
