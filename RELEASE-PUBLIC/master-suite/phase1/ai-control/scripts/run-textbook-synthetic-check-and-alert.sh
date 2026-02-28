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
LOG_FILE="$LOG_DIR/textbook-synthetic-check-$(date +%F).log"
HEARTBEAT_FILE="${TEXTBOOK_SYNTHETIC_HEARTBEAT_FILE:-$LOG_DIR/textbook-synthetic-heartbeat.json}"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_ALERT_TOPIC="${NTFY_ALERT_TOPIC:-ops-alerts}"
NTFY_ALERT_URL="${NTFY_BASE%/}/${NTFY_ALERT_TOPIC}"

TEXTBOOK_WEBHOOK_VERIFY_ENABLED="${TEXTBOOK_WEBHOOK_VERIFY_ENABLED:-true}"
TEXTBOOK_SYNTHETIC_RAG_PREFLIGHT_ENABLED="${TEXTBOOK_SYNTHETIC_RAG_PREFLIGHT_ENABLED:-true}"
TEXTBOOK_SYNTHETIC_SMOKE_MODE="${TEXTBOOK_SYNTHETIC_SMOKE_MODE:-local}"
TEXTBOOK_SYNTHETIC_CHECKS_RAW="${TEXTBOOK_SYNTHETIC_CHECKS:-textbook_pick_alias_local,textbook_untrusted_source_local,textbook_delivery_ack_retry_local}"

WEBHOOK_STATUS=0
SMOKE_STATUS=0

write_heartbeat() {
  local status="$1"
  local webhook_status="$2"
  local smoke_status="$3"
  cat >"$HEARTBEAT_FILE" <<EOF
{
  "timestamp": "$(date -Is)",
  "status": "$status",
  "webhook_verify": "$webhook_status",
  "smoke_checks": "$smoke_status"
}
EOF
}

CHECK_NAMES=()
IFS=',' read -r -a RAW_CHECKS <<<"$TEXTBOOK_SYNTHETIC_CHECKS_RAW"
for item in "${RAW_CHECKS[@]}"; do
  check_name="$(echo "$item" | tr -d '[:space:]')"
  if [[ -n "$check_name" ]]; then
    CHECK_NAMES+=("$check_name")
  fi
done

if [[ ${#CHECK_NAMES[@]} -eq 0 ]]; then
  CHECK_NAMES=("textbook_pick_alias_local" "textbook_untrusted_source_local" "textbook_delivery_ack_retry_local")
fi

SMOKE_ARGS=("--mode" "$TEXTBOOK_SYNTHETIC_SMOKE_MODE")
for check_name in "${CHECK_NAMES[@]}"; do
  SMOKE_ARGS+=("--check" "$check_name")
done

set +e
{
  echo "[$(date -Is)] Starting textbook synthetic check"
  if [[ "$TEXTBOOK_SYNTHETIC_RAG_PREFLIGHT_ENABLED" == "true" ]]; then
    echo "[$(date -Is)] Ensuring rag-query webhook is healthy (auto-heal enabled)"
    ./scripts/ensure-rag-webhook-ready.sh
  else
    echo "[$(date -Is)] Skipping rag-query webhook preflight (disabled)"
  fi

  if [[ "$TEXTBOOK_WEBHOOK_VERIFY_ENABLED" == "true" ]]; then
    echo "[$(date -Is)] Running textbook webhook verify check"
    ./scripts/verify-textbook-webhook.sh
    WEBHOOK_STATUS=$?
  else
    echo "[$(date -Is)] Skipping textbook webhook verify check (disabled)"
    WEBHOOK_STATUS=0
  fi

  echo "[$(date -Is)] Running textbook smoke checks"
  echo "[$(date -Is)] Smoke args: ${SMOKE_ARGS[*]}"
  /usr/bin/python3 ./scripts/eval-telegram-chat-smoke.py "${SMOKE_ARGS[@]}"
  SMOKE_STATUS=$?
} >"$LOG_FILE" 2>&1
set -e

if [[ $WEBHOOK_STATUS -eq 0 && $SMOKE_STATUS -eq 0 ]]; then
  echo "[OK] Textbook synthetic checks passed ($(date -Is))" >>"$LOG_FILE"
  write_heartbeat "ok" "ok" "ok"
  exit 0
fi

write_heartbeat "failed" "${WEBHOOK_STATUS}" "${SMOKE_STATUS}"

HOSTNAME_VALUE="$(hostname)"
FAIL_LINES="$(grep '^\[FAIL\]' "$LOG_FILE" || true)"
FAIL_PREVIEW="$(printf '%s\n' "$FAIL_LINES" | head -n 8)"

if [[ -z "$FAIL_PREVIEW" ]]; then
  FAIL_PREVIEW="(no explicit [FAIL] lines found; inspect log for details)"
fi

MESSAGE=$(cat <<EOF
Textbook synthetic check failed on ${HOSTNAME_VALUE} at $(date -Is).
Log: ${LOG_FILE}

Failed checks:
${FAIL_PREVIEW}

Status summary: textbook_webhook_verify=${WEBHOOK_STATUS} textbook_smoke=${SMOKE_STATUS}
EOF
)

ENC_TITLE="$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote('Textbook Synthetic Check Failed'))
PY
)"

curl -fsS -X POST "${NTFY_ALERT_URL}?title=${ENC_TITLE}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit 1
