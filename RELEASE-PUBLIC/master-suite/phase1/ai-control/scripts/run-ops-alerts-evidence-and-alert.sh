#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ops-alerts-evidence-$(date +%F).log"

NTFY_BASE="${OPS_ALERTS_EVIDENCE_NOTIFY_BASE:-http://127.0.0.1:8091}"
NTFY_TOPIC="${OPS_ALERTS_EVIDENCE_NOTIFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"

set +e
{
  echo "[$(date -Is)] Starting ops-alerts evidence capture"
  /usr/bin/python3 ./scripts/capture-ops-alerts-evidence.py "$@"
  RC=$?
  echo "[$(date -Is)] capture_exit_code=$RC"
  exit "$RC"
} >"$LOG_FILE" 2>&1
STATUS=$?
set -e

if [[ $STATUS -eq 0 ]]; then
  echo "[OK] ops-alerts evidence capture passed ($(date -Is))" >>"$LOG_FILE"
  exit 0
fi

HOSTNAME_VALUE="$(hostname)"
FAIL_TAIL="$(tail -n 40 "$LOG_FILE" | tr -d '\r')"

MESSAGE=$(cat <<EOF
Ops-alerts evidence capture failed on ${HOSTNAME_VALUE} at $(date -Is).
Log: ${LOG_FILE}

Last log lines:
${FAIL_TAIL}
EOF
)

ENC_TITLE="$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote('Ops Alerts Evidence Failed'))
PY
)"

curl -fsS -X POST "${NTFY_URL}?title=${ENC_TITLE}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit "$STATUS"
