"""Shim: canonical implementation is 08_function_calling/spurs_season_store.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_08 = Path(__file__).resolve().parent.parent / "08_function_calling"
_PATH = _08 / "spurs_season_store.py"
_spec = importlib.util.spec_from_file_location("spurs_season_store_canonical", _PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

for _name in dir(_mod):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_mod, _name)
