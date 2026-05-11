#!/bin/bash
# manifestme.sh
# Write manifest.json for Posit Connect deployment of this FastAPI app.
# Bundle root is 10_data_management/ (entrypoint app:app).
# Use a Python 3.12 (or 3.11) venv when running this so manifest.json matches Connect runtimes
# (see ../.python-version); avoid 3.14-only manifests if the server has no 3.14.
# Run from anywhere: bash 10_data_management/agentpy/manifestme.sh
# Or: cd 10_data_management/agentpy && ./manifestme.sh

set -euo pipefail
AGENTPY_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(cd "$AGENTPY_DIR/.." && pwd)"

# Prefer project venv so manifest Python version matches local dev (and Connect-supported runtimes).
if [ -x "$AGENTPY_DIR/.venv/bin/python" ]; then
  PY="$AGENTPY_DIR/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
"$PY" -m pip install -q rsconnect-python
RSC="$(dirname "$PY")/rsconnect"
if [ ! -x "$RSC" ]; then
  RSC="rsconnect"
fi
"$RSC" write-manifest fastapi --entrypoint app:app --overwrite .
