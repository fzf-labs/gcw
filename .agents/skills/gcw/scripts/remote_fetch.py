from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from _bootstrap import add_repo_root

add_repo_root()

_ROOT = Path(__file__).resolve().parents[4]
_IMPL_PATH = _ROOT / ".gcw" / "engine" / "platforms" / "remote_fetch.py"
_SPEC = importlib.util.spec_from_file_location("_gcw_platform_remote_fetch", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"could not load {_IMPL_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

__all__ = [name for name in dir(_MODULE) if not name.startswith("_")]
globals().update({name: getattr(_MODULE, name) for name in __all__})
