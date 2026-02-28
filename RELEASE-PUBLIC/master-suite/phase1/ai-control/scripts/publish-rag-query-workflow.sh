#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WORKFLOW_FILE="workflows/rag-query-webhook.json"
WORKFLOW_NAME="Day4 - RAG Query"
VERIFY=false

if [[ "${1:-}" == "--verify" ]]; then
  VERIFY=true
fi

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "[FAIL] Missing $WORKFLOW_FILE"
  exit 1
fi

echo "[INFO] Importing RAG Query workflow from $WORKFLOW_FILE"
docker exec n8n n8n import:workflow --input=/opt/workflows/rag-query-webhook.json >/tmp/rag_query_wf_import.log 2>&1 || {
  echo "[FAIL] Workflow import failed"
  tail -n 60 /tmp/rag_query_wf_import.log || true
  exit 1
}

WORKFLOW_ID="$(docker exec n8n n8n list:workflow | awk -F'|' -v name="$WORKFLOW_NAME" '$2==name {id=$1} END {print id}')"
if [[ -z "$WORKFLOW_ID" ]]; then
  echo "[FAIL] Could not resolve workflow ID for '$WORKFLOW_NAME'"
  docker exec n8n n8n list:workflow | sed -n '1,200p'
  exit 1
fi

echo "[INFO] Publishing workflow $WORKFLOW_NAME ($WORKFLOW_ID)"
docker exec n8n n8n publish:workflow --id="$WORKFLOW_ID" >/tmp/rag_query_wf_publish.log 2>&1 || {
  echo "[FAIL] Workflow publish failed"
  tail -n 60 /tmp/rag_query_wf_publish.log || true
  exit 1
}

echo "[INFO] Restarting n8n to apply webhook registration"
docker compose restart n8n >/dev/null
sleep 4

if [[ "$VERIFY" == true ]]; then
  echo "[INFO] Verifying webhook /webhook/rag-query"
  RESP="$(curl -sS --max-time 25 -H 'Content-Type: application/json' \
    -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"user","tenant_id":"u_9001","full_name":"Smoke User","telegram_username":"smokeuser","message":"healthcheck ping"}' \
    http://127.0.0.1:5678/webhook/rag-query || true)"

  if echo "$RESP" | grep -q 'requested webhook "POST rag-query" is not registered'; then
    echo "[FAIL] rag-query webhook is not registered after publish/restart"
    echo "$RESP"
    exit 1
  fi

  if ! echo "$RESP" | grep -q '"reply"'; then
    echo "[WARN] Verify response did not include reply field"
    echo "$RESP"
  else
    echo "[OK] rag-query webhook verified and reachable"
  fi
fi

echo "[OK] RAG Query workflow imported, published, and n8n restarted."
