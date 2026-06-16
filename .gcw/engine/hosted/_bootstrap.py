# 中文说明：为 `.gcw/engine/hosted` 下的可执行脚本定位仓库内 `.gcw/engine/runtime`。
# 流程：从当前文件向上查找仓库根目录，确认 runtime 合约文件存在后，把
# `.gcw/engine/runtime` 加入 `sys.path`，让 hosted helper 能导入共享状态机与契约模块。

from __future__ import annotations

import sys
from pathlib import Path


def add_repo_root() -> None:
    for candidate in Path(__file__).resolve().parents:
        runtime = candidate / ".gcw" / "engine" / "runtime"
        platforms = candidate / ".gcw" / "engine" / "platforms"
        if (runtime / "gcw_workflow_contracts.py").is_file() and (runtime / "gcw_artifact_contracts.py").is_file():
            for path in (platforms, runtime):
                path_text = str(path)
                if path_text not in sys.path:
                    sys.path.insert(0, path_text)
            return
