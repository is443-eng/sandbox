#!/bin/bash
# deployme.sh
# Deploy 10_data_management/ to Posit Connect via rsconnect-python.
# Prerequisites: .env in agentpy/ with CONNECT_SERVER and CONNECT_API_KEY (see .env.example).
# School/self-hosted Connect: CONNECT_SERVER = dashboard base URL; API key from Connect Account -> API Keys.
# Optional: CONNECT_INSECURE=1 if TLS verification fails (proxy); use only when necessary.
# Run from anywhere: bash 10_data_management/agentpy/deployme.sh

set -euo pipefail
AGENTPY_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$AGENTPY_DIR/.." && pwd)"
cd "$ROOT"

if [ -f "$AGENTPY_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$AGENTPY_DIR/.env"
  set +a
fi

: "${CONNECT_SERVER:?Set CONNECT_SERVER in .env (Posit Connect URL)}"
: "${CONNECT_API_KEY:?Set CONNECT_API_KEY in .env}"

if [ -x "$AGENTPY_DIR/.venv/bin/python" ]; then
  PY="$AGENTPY_DIR/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
"$PY" -m pip install -q rsconnect-python

TITLE="${CONNECT_TITLE:-course-autonomous-agent}"

RSCONNECT_EXTRA=()
case "${CONNECT_INSECURE:-}" in
  1|true|yes) RSCONNECT_EXTRA+=(--insecure) ;;
esac

RSC="$(dirname "$PY")/rsconnect"
if [ ! -x "$RSC" ]; then
  RSC="rsconnect"
fi
"$RSC" deploy fastapi \
  "${RSCONNECT_EXTRA[@]}" \
  --title "$TITLE" \
  --server "$CONNECT_SERVER" \
  --api-key "$CONNECT_API_KEY" \
  --entrypoint app:app \
  .
