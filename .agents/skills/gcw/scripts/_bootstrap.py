from __future__ import annotations

import sys
from pathlib import Path


def add_repo_root() -> None:
    for candidate in Path(__file__).resolve().parents:
        runtime = candidate / ".gcw" / "runtime"
        if (runtime / "gcw_workflow_contracts.py").is_file() and (runtime / "gcw_artifact_contracts.py").is_file():
            root_text = str(runtime)
            if root_text not in sys.path:
                sys.path.insert(0, root_text)
            return
