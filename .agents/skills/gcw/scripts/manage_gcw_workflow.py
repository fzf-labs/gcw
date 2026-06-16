#!/usr/bin/env python3
from __future__ import annotations

import sys

from _bootstrap import add_repo_root

add_repo_root()

from gcw_workflow_commands import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
