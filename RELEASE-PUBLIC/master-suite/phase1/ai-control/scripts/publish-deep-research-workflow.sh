#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

read_env_var() {
  local key="$1"
  local file="$2"
  if [[ ! -f "$file" ]]; then
    return 1
  fi
  local line
  line="$(grep -E "^${key}=" "$file" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 1
  fi
  printf '%s' "${line#*=}"
}

WORKFLOW_FILE="workflows/deep-research-webhook.json"
WORKFLOW_NAME="Day8 - Deep Research"
VERIFY=false

if [[ "${1:-}" == "--verify" ]]; then
  VERIFY=true
fi

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "[FAIL] Missing $WORKFLOW_FILE"
  exit 1
fi

echo "[INFO] Importing deep-research workflow from $WORKFLOW_FILE"
docker exec n8n n8n import:workflow --input=/opt/workflows/deep-research-webhook.json >/tmp/deep_research_wf_import.log 2>&1 || {
  echo "[FAIL] Workflow import failed"
  tail -n 60 /tmp/deep_research_wf_import.log || true
  exit 1
}

WORKFLOW_ID="$(docker exec n8n n8n list:workflow | awk -F'|' -v name="$WORKFLOW_NAME" '$2==name {id=$1} END {print id}')"
if [[ -z "$WORKFLOW_ID" ]]; then
  echo "[FAIL] Could not resolve workflow ID for '$WORKFLOW_NAME'"
  docker exec n8n n8n list:workflow | sed -n '1,200p'
  exit 1
fi

echo "[INFO] Publishing workflow $WORKFLOW_NAME ($WORKFLOW_ID)"
docker exec n8n n8n publish:workflow --id="$WORKFLOW_ID" >/tmp/deep_research_wf_publish.log 2>&1 || {
  echo "[FAIL] Workflow publish failed"
  tail -n 60 /tmp/deep_research_wf_publish.log || true
  exit 1
}

echo "[INFO] Recreating n8n to apply webhook + env updates"
docker compose up -d --force-recreate n8n >/dev/null
sleep 4

if [[ "$VERIFY" == true ]]; then
  echo "[INFO] Verifying webhook /webhook/deep-research"
  NEXTCLOUD_BASE="${RESEARCH_NEXTCLOUD_BASE_URL:-$(read_env_var RESEARCH_NEXTCLOUD_BASE_URL "$ROOT_DIR/.env.secrets" || read_env_var RESEARCH_NEXTCLOUD_BASE_URL "$ROOT_DIR/.env" || echo http://nextcloud)}"
  NEXTCLOUD_USER="${RESEARCH_NEXTCLOUD_USER:-$(read_env_var RESEARCH_NEXTCLOUD_USER "$ROOT_DIR/.env.secrets" || read_env_var RESEARCH_NEXTCLOUD_USER "$ROOT_DIR/.env" || read_env_var NEXTCLOUD_ADMIN_USER "$ROOT_DIR/.env" || echo admin)}"
  NEXTCLOUD_PASSWORD="${RESEARCH_NEXTCLOUD_PASSWORD:-$(read_env_var RESEARCH_NEXTCLOUD_PASSWORD "$ROOT_DIR/.env.secrets" || read_env_var NEXTCLOUD_ADMIN_PASSWORD "$ROOT_DIR/.env.secrets" || read_env_var RESEARCH_NEXTCLOUD_PASSWORD "$ROOT_DIR/.env" || read_env_var NEXTCLOUD_ADMIN_PASSWORD "$ROOT_DIR/.env" || true)}"
  NEXTCLOUD_FOLDER="${RESEARCH_NEXTCLOUD_FOLDER:-$(read_env_var RESEARCH_NEXTCLOUD_FOLDER "$ROOT_DIR/.env.secrets" || read_env_var RESEARCH_NEXTCLOUD_FOLDER "$ROOT_DIR/.env" || echo research-reports)}"

  docker exec -u www-data nextcloud php occ config:system:set trusted_domains 2 --value=nextcloud >/tmp/deep_research_trusted_domain.log 2>&1 || true
  curl -sS --max-time 20 -u "${NEXTCLOUD_USER}:${NEXTCLOUD_PASSWORD}" -X MKCOL "${NEXTCLOUD_BASE}/remote.php/dav/files/${NEXTCLOUD_USER}/${NEXTCLOUD_FOLDER}" >/tmp/deep_research_mkcol.log 2>&1 || true

  START_PAYLOAD="$(jq -n \
    --arg base "$NEXTCLOUD_BASE" \
    --arg user "$NEXTCLOUD_USER" \
    --arg pass "$NEXTCLOUD_PASSWORD" \
    --arg folder "$NEXTCLOUD_FOLDER" \
    '{source:"telegram",action:"start",run_id:"rr-verify-001",chat_id:700,user_id:9001,role:"user",tenant_id:"u_9001",query:"Summarize resilience improvements for week 1",nextcloud_base_url:$base,nextcloud_user:$user,nextcloud_password:$pass,nextcloud_folder:$folder,delivery:{channel:"telegram",mode:"nextcloud_link",link_ttl_seconds:86400},timestamp:1730000000}')"

  START_RESP="$(curl -sS --max-time 25 -H 'Content-Type: application/json' \
    -d "$START_PAYLOAD" \
    http://127.0.0.1:5678/webhook/deep-research || true)"

  if echo "$START_RESP" | grep -q 'requested webhook "POST deep-research" is not registered'; then
    echo "[FAIL] deep-research webhook is not registered after publish/restart"
    echo "$START_RESP"
    exit 1
  fi

  if ! echo "$START_RESP" | jq -e '.run_id and (.status == "ready") and ((.report_url // "") | length > 0) and ((.error // "") == "")' >/dev/null 2>&1; then
    echo "[FAIL] Verify start response missing expected ready/report_url fields"
    echo "$START_RESP"
    exit 1
  fi

  RUN_ID="$(echo "$START_RESP" | jq -r '.run_id')"
  REPORT_URL_HINT="$(echo "$START_RESP" | jq -r '.report_url // ""')"
  REPORT_TITLE_HINT="$(echo "$START_RESP" | jq -r '.report_title // ""')"
  LINK_EXPIRES_HINT="$(echo "$START_RESP" | jq -r '.link_expires_at // 0')"
  STATUS_RESP="$(curl -sS --max-time 25 -H 'Content-Type: application/json' \
    -d "{\"source\":\"telegram\",\"action\":\"status\",\"run_id\":\"${RUN_ID}\",\"chat_id\":700,\"user_id\":9001,\"role\":\"user\",\"tenant_id\":\"u_9001\",\"report_url_hint\":\"${REPORT_URL_HINT}\",\"report_title_hint\":\"${REPORT_TITLE_HINT}\",\"link_expires_at_hint\":${LINK_EXPIRES_HINT},\"timestamp\":1730000001}" \
    http://127.0.0.1:5678/webhook/deep-research || true)"

  if ! echo "$STATUS_RESP" | jq -e '.run_id and (.status == "ready") and ((.report_url // "") | length > 0) and ((.error // "") == "")' >/dev/null 2>&1; then
    echo "[FAIL] Verify status response missing expected ready/report_url fields"
    echo "$STATUS_RESP"
    exit 1
  fi

  echo "[OK] deep-research webhook verified and reachable"
fi

echo "[OK] Deep Research workflow imported, published, and n8n restarted."
