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


if __name__ == "__main__":
    unittest.main()
