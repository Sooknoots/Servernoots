#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/telegram-chat-smoke-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${NTFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"
TEXTBOOK_WEBHOOK_VERIFY_ENABLED="${TEXTBOOK_WEBHOOK_VERIFY_ENABLED:-true}"

SMOKE_STATUS=0
TEXTBOOK_STATUS=0
RAG_WEBHOOK_STATUS=0
SMOKE_ARGS=("$@")
SMOKE_MODE="all"

for ((i=0; i<${#SMOKE_ARGS[@]}; i++)); do
  if [[ "${SMOKE_ARGS[$i]}" == "--mode" && $((i + 1)) -lt ${#SMOKE_ARGS[@]} ]]; then
    SMOKE_MODE="${SMOKE_ARGS[$((i + 1))]}"
  fi
done

set +e
{
  echo "[$(date -Is)] Starting Telegram/chat smoke suite"
  if [[ "$SMOKE_MODE" == "local" ]]; then
    echo "[$(date -Is)] Mode local: skipping rag-query health + textbook webhook verification"
    RAG_WEBHOOK_STATUS=0
    TEXTBOOK_STATUS=0
  else
    echo "[$(date -Is)] Ensuring rag-query webhook is healthy (auto-heal enabled)"
    ./scripts/ensure-rag-webhook-ready.sh
    RAG_WEBHOOK_STATUS=$?

    if [[ "$TEXTBOOK_WEBHOOK_VERIFY_ENABLED" == "true" ]]; then
      echo "[$(date -Is)] Running textbook webhook verify check"
      ./scripts/verify-textbook-webhook.sh
      TEXTBOOK_STATUS=$?
    else
      echo "[$(date -Is)] Skipping textbook webhook verify check (disabled)"
    fi
  fi

  echo "[$(date -Is)] Running Telegram/chat smoke checks"
  if [[ ${#SMOKE_ARGS[@]} -gt 0 ]]; then
    echo "[$(date -Is)] Smoke args: ${SMOKE_ARGS[*]}"
  fi
  /usr/bin/python3 ./scripts/eval-telegram-chat-smoke.py "${SMOKE_ARGS[@]}"
  SMOKE_STATUS=$?
} >"$LOG_FILE" 2>&1
set -e

if [[ $RAG_WEBHOOK_STATUS -eq 0 && $TEXTBOOK_STATUS -eq 0 && $SMOKE_STATUS -eq 0 ]]; then
  echo "[OK] Telegram/chat smoke checks passed ($(date -Is))" >>"$LOG_FILE"
  exit 0
fi

STATUS=1

HOSTNAME_VALUE="$(hostname)"
FAIL_LINES="$(grep '^\[FAIL\]' "$LOG_FILE" || true)"
FAIL_PREVIEW="$(printf '%s\n' "$FAIL_LINES" | head -n 8)"

if [[ -z "$FAIL_PREVIEW" ]]; then
  FAIL_PREVIEW="(no explicit [FAIL] lines found; inspect log for details)"
fi

MESSAGE=$(cat <<EOF
Telegram/chat smoke checks failed on ${HOSTNAME_VALUE} at $(date -Is).
Log: ${LOG_FILE}

Failed checks:
${FAIL_PREVIEW}

Status summary: rag_webhook=${RAG_WEBHOOK_STATUS} textbook_verify=${TEXTBOOK_STATUS} telegram_smoke=${SMOKE_STATUS}
EOF
)

ENC_TITLE="$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote('Telegram Chat Smoke Failed'))
PY
)"

curl -fsS -X POST "${NTFY_URL}?title=${ENC_TITLE}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit $STATUS
