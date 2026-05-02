#!/usr/bin/env python3
"""Start the Brussels FastAPI predictor (wraps 03_fastapi/main.py). Run from repo root:
   12_end/.venv/bin/python 12_end/03_serve_model.py
   or: python 12_end/03_serve_model.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FASTAPI_DIR = ROOT / "03_fastapi"


def main() -> int:
    if not FASTAPI_DIR.is_dir():
        print(f"Missing directory: {FASTAPI_DIR}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(FASTAPI_DIR))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        cwd=FASTAPI_DIR,
        env=env,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
