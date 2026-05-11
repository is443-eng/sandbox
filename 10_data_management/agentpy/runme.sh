#!/bin/bash
# runme.sh
# Run the agent FastAPI app locally with uvicorn (same as README quick start).
# Run from anywhere: bash 10_data_management/agentpy/runme.sh
# Or: cd 10_data_management/agentpy && ./runme.sh

set -euo pipefail
AGENTPY_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(cd "$AGENTPY_DIR/.." && pwd)"

if [ -x "$AGENTPY_DIR/.venv/bin/python" ]; then
  PY="$AGENTPY_DIR/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
PORT="${PORT:-8000}"
"$PY" -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
# Open http://localhost:${PORT}/docs/ in browser (override: PORT=8001 bash agentpy/runme.sh)
