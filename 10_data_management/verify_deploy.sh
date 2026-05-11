#!/usr/bin/env bash
# Quick check against a live deploy. Usage:
#   export AGENT_PUBLIC_URL='https://…share.connect.posit.cloud'   # no trailing slash
#   ./verify_deploy.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -z "${AGENT_PUBLIC_URL:-}" ]]; then
  echo "Set AGENT_PUBLIC_URL to the deployed base URL (no trailing slash)." >&2
  exit 1
fi
BASE="${AGENT_PUBLIC_URL%/}"
echo "GET ${BASE}/health"
curl -sS -f "${BASE}/health" | python3 -m json.tool
echo
echo "For POST /hooks/agent and viewer-auth flows, run: cd agentpy && python testme.py"
echo "(with AGENT_PUBLIC_URL and optionally CONNECT_VIEWER_KEY in agentpy/.env)"
