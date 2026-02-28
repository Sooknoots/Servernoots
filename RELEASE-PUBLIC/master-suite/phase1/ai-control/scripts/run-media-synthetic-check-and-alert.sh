#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/media-synthetic-check-$(date +%F).log"
HEARTBEAT_FILE="${MEDIA_SYNTHETIC_HEARTBEAT_FILE:-$LOG_DIR/media-synthetic-heartbeat.json}"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_ALERT_TOPIC="${NTFY_ALERT_TOPIC:-ops-alerts}"
NTFY_ALERT_URL="${NTFY_BASE%/}/${NTFY_ALERT_TOPIC}"

OVERSEERR_URL="${OVERSEERR_URL:-http://127.0.0.1:5055}"
OVERSEERR_FALLBACK_URL="${MEDIA_SYNTHETIC_OVERSEERR_FALLBACK_URL:-http://127.0.0.1:5055}"
OVERSEERR_API_KEY="${OVERSEERR_API_KEY:-}"
REQUEST_CHECK_QUERY="${MEDIA_SYNTHETIC_REQUEST_QUERY:-Sintel}"
REQUEST_CHECK_MEDIA_TYPE="${MEDIA_SYNTHETIC_REQUEST_MEDIA_TYPE:-movie}"

BRIDGE_SERVICE="${MEDIA_SYNTHETIC_BRIDGE_SERVICE:-ntfy-n8n-bridge}"
FANOUT_WAIT_SECONDS="${MEDIA_SYNTHETIC_FANOUT_WAIT_SECONDS:-120}"
ACCEPT_RESULTS_RAW="${MEDIA_SYNTHETIC_ACCEPT_RESULTS:-sent,sent_partial}"

REQUEST_REASON="pending"
FANOUT_REASON="pending"

if [[ -z "$OVERSEERR_API_KEY" ]]; then
  echo "[FAIL] OVERSEERR_API_KEY is required" | tee -a "$LOG_FILE"
  exit 1
fi

send_failure_alert() {
  local title="$1"
  local message="$2"
  curl -fsS -X POST "$NTFY_ALERT_URL" \
    -H "Title: $title" \
    -H "Priority: high" \
    -H "Tags: rotating_light,warning" \
    -d "$message" >/dev/null 2>&1 || true
}

write_heartbeat() {
  local status="$1"
  local request_reason="$2"
  local fanout_reason="$3"
  cat >"$HEARTBEAT_FILE" <<EOF
{
  "timestamp": "$(date -Is)",
  "status": "$status",
  "request_check": "$request_reason",
  "fanout_check": "$fanout_reason"
}
EOF
}

fail_run() {
  local reason="$1"
  local message="Media synthetic check failed on $(hostname) at $(date -Is): $reason. See $LOG_FILE"
  echo "[FAIL] $reason" | tee -a "$LOG_FILE"
  write_heartbeat "failed" "$REQUEST_REASON" "$FANOUT_REASON"
  send_failure_alert "Media Synthetic Check Failed" "$message"
  exit 1
}

echo "[$(date -Is)] Starting media synthetic check" | tee -a "$LOG_FILE"

echo "[$(date -Is)] Ensuring rag-query webhook is healthy (auto-heal enabled)" | tee -a "$LOG_FILE"
if ! ./scripts/ensure-rag-webhook-ready.sh >>"$LOG_FILE" 2>&1; then
  REQUEST_REASON="rag_webhook_unhealthy"
  FANOUT_REASON="not_started"
  fail_run "$REQUEST_REASON"
fi
echo "[$(date -Is)] rag-query webhook preflight passed" | tee -a "$LOG_FILE"

REQUEST_OK="$(OVERSEERR_URL="$OVERSEERR_URL" OVERSEERR_FALLBACK_URL="$OVERSEERR_FALLBACK_URL" OVERSEERR_API_KEY="$OVERSEERR_API_KEY" REQUEST_CHECK_QUERY="$REQUEST_CHECK_QUERY" REQUEST_CHECK_MEDIA_TYPE="$REQUEST_CHECK_MEDIA_TYPE" python3 - <<'PY'
import json, os, urllib.error, urllib.parse, urllib.request
primary = os.environ.get("OVERSEERR_URL", "http://127.0.0.1:5055").strip().rstrip("/")
fallback = os.environ.get("OVERSEERR_FALLBACK_URL", "http://127.0.0.1:5055").strip().rstrip("/")
api = os.environ.get("OVERSEERR_API_KEY", "").strip()
query = os.environ.get("REQUEST_CHECK_QUERY", "Sintel").strip()
media_type = os.environ.get("REQUEST_CHECK_MEDIA_TYPE", "movie").strip().lower()

candidates = []
if primary:
  candidates.append(primary)
if fallback and fallback not in candidates:
  candidates.append(fallback)

status_ok = False
has_match = False

for base in candidates:
  try:
    status_url = f"{base}/api/v1/status"
    status_req = urllib.request.Request(status_url, headers={"Accept": "application/json", "X-Api-Key": api})
    with urllib.request.urlopen(status_req, timeout=20) as resp:
      status_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    status_ok = bool(status_data.get("version"))

    search_url = f"{base}/api/v1/search?" + urllib.parse.urlencode({"query": query, "page": 1, "language": "en"})
    search_req = urllib.request.Request(search_url, headers={"Accept": "application/json", "X-Api-Key": api})
    with urllib.request.urlopen(search_req, timeout=20) as resp:
      search_data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    results = search_data.get("results") if isinstance(search_data, dict) else []
    if not isinstance(results, list):
      results = []
    matches = [item for item in results if isinstance(item, dict) and str(item.get("mediaType", "")).lower() == media_type]
    has_match = len(matches) > 0
    if status_ok and has_match:
      print("true")
      raise SystemExit(0)
  except Exception:
    continue

print("false")
PY
)" || true

if [[ "$REQUEST_OK" != "true" ]]; then
  REQUEST_REASON="request_path_failed"
  fail_run "$REQUEST_REASON"
fi
REQUEST_REASON="request_path_ok"
echo "[$(date -Is)] request-path check passed" | tee -a "$LOG_FILE"

SYN_ID="media-verify-$(date +%s)-$RANDOM"
SYN_TITLE="Media Ready Verification ${REQUEST_CHECK_QUERY}"
SYN_MESSAGE="${REQUEST_CHECK_QUERY} is now available in Plex. verification_run=${SYN_ID}"

PRE_MEDIA_EVENT_COUNT="$(docker compose exec -T "$BRIDGE_SERVICE" python - <<'PY' 2>/dev/null || echo "0"
import importlib.util

spec = importlib.util.spec_from_file_location('ntfy_bridge', '/app/ntfy_to_n8n.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

data = mod.load_notify_stats_state()
items = data.get('events') if isinstance(data, dict) else []
if not isinstance(items, list):
    items = []
count = sum(1 for item in items if isinstance(item, dict) and str(item.get('topic', '')) == 'media-alerts')
print(count)
PY
)"

if ! [[ "$PRE_MEDIA_EVENT_COUNT" =~ ^[0-9]+$ ]]; then
  PRE_MEDIA_EVENT_COUNT="0"
fi

if ! docker compose exec -T \
  -e SYN_TITLE="$SYN_TITLE" \
  -e SYN_MESSAGE="$SYN_MESSAGE" \
  "$BRIDGE_SERVICE" \
  python -c "import importlib.util, os; spec=importlib.util.spec_from_file_location('ntfy_bridge','/app/ntfy_to_n8n.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); mod.fanout_to_telegram(topic='media-alerts', title=os.environ.get('SYN_TITLE',''), message=os.environ.get('SYN_MESSAGE',''), priority=5)" >/dev/null 2>&1; then
  FANOUT_REASON="synthetic_fanout_invoke_failed"
  fail_run "$FANOUT_REASON"
fi
echo "[$(date -Is)] synthetic fanout invoked: $SYN_ID" | tee -a "$LOG_FILE"

FANOUT_FOUND="false"
FANOUT_RESULT=""
FANOUT_REASON_RAW=""
FANOUT_EVENT_COUNT="$PRE_MEDIA_EVENT_COUNT"

for _ in $(seq 1 "$FANOUT_WAIT_SECONDS"); do
  PARSED_FIELDS="$(docker compose exec -T -e PRE_MEDIA_EVENT_COUNT="$PRE_MEDIA_EVENT_COUNT" "$BRIDGE_SERVICE" python - <<'PY' 2>/dev/null || echo "false|||$PRE_MEDIA_EVENT_COUNT"
import importlib.util
import os

spec = importlib.util.spec_from_file_location('ntfy_bridge', '/app/ntfy_to_n8n.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

try:
  pre_count = int(os.environ.get("PRE_MEDIA_EVENT_COUNT", "0"))
except Exception:
  pre_count = 0

data = mod.load_notify_stats_state()
items = data.get("events") if isinstance(data, dict) else []
if not isinstance(items, list):
  items = []

media_items = [
  item for item in items
  if isinstance(item, dict) and str(item.get("topic", "")) == "media-alerts"
]
count = len(media_items)

found = "false"
result = ""
reason = ""
if count > pre_count and media_items:
  latest = media_items[-1]
  found = "true"
  result = str(latest.get("result", ""))
  reason = str(latest.get("reason", "")).replace("|", "/")

print(f"{found}|{result}|{reason}|{count}")
PY
)"

IFS='|' read -r FANOUT_FOUND FANOUT_RESULT FANOUT_REASON_RAW FANOUT_EVENT_COUNT <<< "$PARSED_FIELDS"
FANOUT_FOUND="${FANOUT_FOUND:-false}"
FANOUT_RESULT="${FANOUT_RESULT:-}"
FANOUT_REASON_RAW="${FANOUT_REASON_RAW:-}"
FANOUT_EVENT_COUNT="${FANOUT_EVENT_COUNT:-$PRE_MEDIA_EVENT_COUNT}"
  if [[ "$FANOUT_FOUND" == "true" ]]; then
    break
  fi
  sleep 1
done

if [[ "$FANOUT_FOUND" != "true" ]]; then
  FANOUT_REASON="fanout_timeout:pre=${PRE_MEDIA_EVENT_COUNT}:seen=${FANOUT_EVENT_COUNT}"
  fail_run "$FANOUT_REASON"
fi

if [[ "$FANOUT_RESULT" == "failed" ]]; then
  FANOUT_REASON="fanout_failed:${FANOUT_REASON_RAW:-send_error}"
  fail_run "$FANOUT_REASON"
fi

RESULT_ACCEPTED="false"
IFS=',' read -r -a ACCEPT_RESULTS <<<"$ACCEPT_RESULTS_RAW"
for item in "${ACCEPT_RESULTS[@]}"; do
  value="$(echo "$item" | tr -d '[:space:]')"
  if [[ -n "$value" && "$FANOUT_RESULT" == "$value" ]]; then
    RESULT_ACCEPTED="true"
    break
  fi
done

if [[ "$RESULT_ACCEPTED" != "true" ]]; then
  FANOUT_REASON="fanout_not_delivered:${FANOUT_RESULT}:${FANOUT_REASON_RAW:-none}"
  fail_run "$FANOUT_REASON"
fi

FANOUT_REASON="fanout_processed:${FANOUT_RESULT}:${FANOUT_REASON_RAW:-none}"
write_heartbeat "ok" "$REQUEST_REASON" "$FANOUT_REASON"

echo "[$(date -Is)] media fanout check passed: result=$FANOUT_RESULT reason=${FANOUT_REASON_RAW:-none}" | tee -a "$LOG_FILE"
echo "[$(date -Is)] heartbeat written: $HEARTBEAT_FILE" | tee -a "$LOG_FILE"
exit 0
