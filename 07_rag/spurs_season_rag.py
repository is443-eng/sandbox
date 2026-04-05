#!/usr/bin/env python3
"""Shim: canonical CLI is 08_function_calling/spurs_season_rag.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "08_function_calling" / "spurs_season_rag.py"

if __name__ == "__main__":
    sys.argv[0] = str(_TARGET)
    runpy.run_path(str(_TARGET), run_name="__main__")
