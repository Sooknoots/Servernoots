#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERIFY=false
if [[ "${1:-}" == "--verify" ]]; then
  VERIFY=true
fi

RAG_WORKFLOW_FILE="workflows/rag-query-webhook.json"
RAG_WORKFLOW_NAME="Day4 - RAG Query"
TEXTBOOK_WORKFLOW_FILE="workflows/textbook-fulfillment-webhook.json"
TEXTBOOK_WORKFLOW_NAME="Day7 - Textbook Fulfillment"

for wf in "$RAG_WORKFLOW_FILE" "$TEXTBOOK_WORKFLOW_FILE"; do
  if [[ ! -f "$wf" ]]; then
    echo "[FAIL] Missing $wf"
    exit 1
  fi
done

resolve_workflow_id() {
  local workflow_name="$1"
  docker exec n8n n8n list:workflow | awk -F'|' -v name="$workflow_name" '$2==name {id=$1} END {print id}'
}

publish_workflow_by_name() {
  local workflow_name="$1"
  local workflow_id
  workflow_id="$(resolve_workflow_id "$workflow_name")"
  if [[ -z "$workflow_id" ]]; then
    echo "[FAIL] Could not resolve workflow ID for '$workflow_name'"
    docker exec n8n n8n list:workflow | sed -n '1,200p'
    exit 1
  fi

  echo "[INFO] Publishing workflow $workflow_name ($workflow_id)"
  docker exec n8n n8n publish:workflow --id="$workflow_id" >/tmp/core_chat_publish.log 2>&1 || {
    echo "[FAIL] Publish failed for $workflow_name"
    tail -n 60 /tmp/core_chat_publish.log || true
    exit 1
  }
}

echo "[INFO] Publishing core chat workflows (rag-query + textbook) with one restart"

echo "[INFO] Importing RAG Query workflow from $RAG_WORKFLOW_FILE"
docker exec n8n n8n import:workflow --input=/opt/workflows/rag-query-webhook.json >/tmp/core_chat_import_rag.log 2>&1 || {
  echo "[FAIL] RAG Query workflow import failed"
  tail -n 60 /tmp/core_chat_import_rag.log || true
  exit 1
}

echo "[INFO] Importing textbook workflow from $TEXTBOOK_WORKFLOW_FILE"
docker exec n8n n8n import:workflow --input=/opt/workflows/textbook-fulfillment-webhook.json >/tmp/core_chat_import_textbook.log 2>&1 || {
  echo "[FAIL] Textbook workflow import failed"
  tail -n 60 /tmp/core_chat_import_textbook.log || true
  exit 1
}

publish_workflow_by_name "$RAG_WORKFLOW_NAME"
publish_workflow_by_name "$TEXTBOOK_WORKFLOW_NAME"

echo "[INFO] Restarting n8n once to apply webhook registration"
docker compose restart n8n >/dev/null
sleep 4

if [[ "$VERIFY" == true ]]; then
  ./scripts/verify-textbook-webhook.sh

  echo "[INFO] Verifying webhook /webhook/rag-query"
  RAG_RESP="$(curl -sS --max-time 25 -H 'Content-Type: application/json' \
    -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"user","tenant_id":"u_9001","full_name":"Smoke User","telegram_username":"smokeuser","message":"healthcheck ping"}' \
    http://127.0.0.1:5678/webhook/rag-query || true)"

  if echo "$RAG_RESP" | grep -q 'requested webhook "POST rag-query" is not registered'; then
    echo "[FAIL] rag-query webhook is not registered after publish/restart"
    echo "$RAG_RESP"
    exit 1
  fi

  if ! echo "$RAG_RESP" | grep -q '"reply"'; then
    echo "[WARN] rag-query verify response did not include reply field"
    echo "$RAG_RESP"
  else
    echo "[OK] rag-query webhook verified and reachable"
  fi
fi

echo "[OK] Core chat workflows published successfully."
