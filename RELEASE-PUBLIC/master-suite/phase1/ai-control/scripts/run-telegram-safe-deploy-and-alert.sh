#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/telegram-safe-deploy-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${NTFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"
MODE="${TELEGRAM_SAFE_DEPLOY_CRON_MODE:-gate}"

STATUS=0
set +e
{
  echo "[$(date -Is)] Telegram scheduled safe run started (mode=${MODE})"
  if [[ "$MODE" == "deploy" ]]; then
    ./scripts/deploy-telegram-bridges-safe.sh
    STATUS=$?
  else
    ./scripts/run-telegram-release-gate.sh
    STATUS=$?
  fi
  echo "[$(date -Is)] Telegram scheduled safe run finished (status=${STATUS})"
} >>"$LOG_FILE" 2>&1
set -e

if [[ $STATUS -eq 0 ]]; then
  echo "[OK] Telegram scheduled safe run passed ($(date -Is))" >>"$LOG_FILE"
  exit 0
fi

HOSTNAME_VALUE="$(hostname)"
FAIL_LINES="$(grep '^\[FAIL\]' "$LOG_FILE" || true)"
FAIL_PREVIEW="$(printf '%s\n' "$FAIL_LINES" | tail -n 8)"
if [[ -z "$FAIL_PREVIEW" ]]; then
  FAIL_PREVIEW="(no explicit [FAIL] lines found; inspect log for details)"
fi

MESSAGE=$(cat <<EOF
Telegram scheduled safe run failed on ${HOSTNAME_VALUE} at $(date -Is).
Mode: ${MODE}
Log: ${LOG_FILE}

Failure preview:
${FAIL_PREVIEW}
EOF
)

ENC_TITLE="$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote('Telegram Safe Deploy Failed'))
PY
)"

curl -fsS -X POST "${NTFY_URL}?title=${ENC_TITLE}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit $STATUS
