#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WORKFLOW_FILE="workflows/textbook-fulfillment-webhook.json"
WORKFLOW_NAME="Day7 - Textbook Fulfillment"
VERIFY=false

if [[ "${1:-}" == "--verify" ]]; then
  VERIFY=true
fi

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "[FAIL] Missing $WORKFLOW_FILE"
  exit 1
fi

echo "[INFO] Importing textbook workflow from $WORKFLOW_FILE"
docker exec n8n n8n import:workflow --input=/opt/workflows/textbook-fulfillment-webhook.json >/tmp/textbook_wf_import.log 2>&1 || {
  echo "[FAIL] Workflow import failed"
  tail -n 60 /tmp/textbook_wf_import.log || true
  exit 1
}

WORKFLOW_ID="$(docker exec n8n n8n list:workflow | awk -F'|' -v name="$WORKFLOW_NAME" '$2==name {id=$1} END {print id}')"
if [[ -z "$WORKFLOW_ID" ]]; then
  echo "[FAIL] Could not resolve workflow ID for '$WORKFLOW_NAME'"
  docker exec n8n n8n list:workflow | sed -n '1,200p'
  exit 1
fi

echo "[INFO] Publishing workflow $WORKFLOW_NAME ($WORKFLOW_ID)"
docker exec n8n n8n publish:workflow --id="$WORKFLOW_ID" >/tmp/textbook_wf_publish.log 2>&1 || {
  echo "[FAIL] Workflow publish failed"
  tail -n 60 /tmp/textbook_wf_publish.log || true
  exit 1
}

echo "[INFO] Restarting n8n to apply webhook registration"
docker compose restart n8n >/dev/null
sleep 4

if [[ "$VERIFY" == true ]]; then
  echo "[INFO] Verifying webhook /webhook/textbook-fulfillment"
  RESP="$(curl -sS --max-time 20 -H 'Content-Type: application/json' \
    -d '{"textbook_request":"test textbook details","delivery_email":"student@example.edu","lawful_sources_only":true,"user_id":"1"}' \
    http://127.0.0.1:5678/webhook/textbook-fulfillment || true)"

  if echo "$RESP" | grep -q 'requested webhook "POST textbook-fulfillment" is not registered'; then
    echo "[FAIL] Webhook still not registered after publish/restart"
    echo "$RESP"
    exit 1
  fi

  if ! echo "$RESP" | grep -q 'Textbook fulfillment queued for'; then
    echo "[WARN] Verification response did not match expected queued message"
    echo "$RESP"
  else
    echo "[OK] Webhook verified and reachable"
  fi
fi

echo "[OK] Textbook workflow imported, published, and n8n restarted."
