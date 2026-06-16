from __future__ import annotations

import sys
from pathlib import Path


def add_repo_root() -> None:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "gcw_workflow_contracts.py").is_file() and (candidate / "gcw_artifact_contracts.py").is_file():
            root = candidate
            root_text = str(root)
            if root_text not in sys.path:
                sys.path.insert(0, root_text)
            return
