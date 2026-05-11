#!/bin/bash
# Verify rsconnect can reach Posit Connect (same .env as deployme.sh).
# Run: cd agentpy && ./detailsme.sh
set -euo pipefail
AGENTPY_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$AGENTPY_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${CONNECT_SERVER:?Set CONNECT_SERVER in .env}"
: "${CONNECT_API_KEY:?Set CONNECT_API_KEY in .env}"

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

EXTRA=()
case "${CONNECT_INSECURE:-}" in
  1|true|yes) EXTRA+=(--insecure) ;;
esac

"$RSC" details --server "$CONNECT_SERVER" --api-key "$CONNECT_API_KEY" "${EXTRA[@]}"
