#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reqtrack-command-contract-$(date +%F).log"

TRACKER_SCRIPT="$ROOT_DIR/scripts/track-stale-media-requests.py"
DRILL_STATE="${REQTRACK_CONTRACT_DRILL_STATE:-/tmp/reqtrack-command-contract-state.json}"
NTFY_BASE="${REQTRACK_CONTRACT_NTFY_BASE:-http://127.0.0.1:8091}"
ADMIN_TOPIC="${REQTRACK_CONTRACT_ADMIN_TOPIC:-reqtrack-contract-admin}"
USER_TOPIC="${REQTRACK_CONTRACT_USER_TOPIC:-reqtrack-contract-user}"

if ! command -v jq >/dev/null 2>&1; then
  echo "[FAIL] jq is required for reqtrack command-contract smoke"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[FAIL] python3 is required for reqtrack command-contract smoke"
  exit 1
fi

cleanup() {
  rm -f "$DRILL_STATE" /tmp/reqtrack-contract-run1.json /tmp/reqtrack-contract-run2.json /tmp/reqtrack-contract-run3.json
}
trap cleanup EXIT

rm -f "$DRILL_STATE"

{
  echo "[$(date -Is)] Reqtrack command-contract smoke started"

  echo "[$(date -Is)] CLI contract: incident list JSON"
  python3 "$TRACKER_SCRIPT" --incident-action list --incident-filter active --json \
    | jq -e '.count >= 0 and ((.incidents | type) == "array")' >/dev/null

  echo "[$(date -Is)] CLI contract: KPI JSON (24h + 168h)"
  python3 "$TRACKER_SCRIPT" --kpi-report --kpi-window-hours 24 --json \
    | jq -e '.kpi.window_hours == 24 and ((.kpi.totals | type) == "object")' >/dev/null
  python3 "$TRACKER_SCRIPT" --kpi-report --kpi-window-hours 168 --json \
    | jq -e '.kpi.window_hours == 168 and ((.kpi.totals | type) == "object")' >/dev/null

  echo "[$(date -Is)] CLI contract: incident action roundtrip (ack/snooze/unsnooze/close)"
  python3 "$TRACKER_SCRIPT" \
    --dry-drill --dry-drill-stateful --emit-ntfy \
    --ntfy-base "$NTFY_BASE" --admin-topic "$ADMIN_TOPIC" --user-topic "$USER_TOPIC" \
    --state-file "$DRILL_STATE" --json \
    | tee /tmp/reqtrack-contract-run1.json \
    | jq -e '.stale_count == 2 and .notify_candidate_count == 2 and ((.items | length) == 2)' >/dev/null

  INCIDENT_KEY="$(jq -r '.items[0].incident.key // empty' /tmp/reqtrack-contract-run1.json)"
  if [[ -z "$INCIDENT_KEY" ]]; then
    echo "[FAIL] Could not resolve incident key from dry drill"
    exit 1
  fi

  python3 "$TRACKER_SCRIPT" --incident-action ack --incident-key "$INCIDENT_KEY" --incident-by contract --incident-note smoke --state-file "$DRILL_STATE" --json \
    | jq -e '.ok == true and .incident.acked == true' >/dev/null
  python3 "$TRACKER_SCRIPT" --incident-action snooze --incident-key "$INCIDENT_KEY" --incident-by contract --snooze-minutes 30 --incident-note smoke --state-file "$DRILL_STATE" --json \
    | jq -e '.ok == true and (.incident.snoozed_until > 0)' >/dev/null
  python3 "$TRACKER_SCRIPT" --incident-action unsnooze --incident-key "$INCIDENT_KEY" --incident-by contract --incident-note smoke --state-file "$DRILL_STATE" --json \
    | jq -e '.ok == true and (.incident.snoozed_until == 0)' >/dev/null
  python3 "$TRACKER_SCRIPT" --incident-action close --incident-key "$INCIDENT_KEY" --incident-by contract --incident-note smoke --state-file "$DRILL_STATE" --json \
    | jq -e '.ok == true and .incident.status == "resolved"' >/dev/null

  echo "[$(date -Is)] Telegram contract: /reqtrack command handling"
  if docker ps --format '{{.Names}}' | grep -q '^telegram-n8n-bridge$'; then
    docker exec -i telegram-n8n-bridge python - <<'PY'
import importlib.util
import json

path='/app/bridge/telegram_to_n8n.py'
try:
    open(path).close()
except Exception:
    path='/app/telegram_to_n8n.py'

spec=importlib.util.spec_from_file_location('bridge_mod', path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

messages=[]
def fake_send(chat_id, text):
    messages.append((chat_id, text))

mod.send_message = fake_send
mod.USER_REGISTRY = {'users': {'42': {'role':'admin','status':'active','telegram_username':'opsadmin'}}}

checks = [
    ('/reqtrack state', 'text'),
    ('/reqtrack list active', 'text'),
    ('/reqtrack kpi json', 'json'),
    ('/reqtrack kpiweekly json', 'json'),
]

for cmd, mode in checks:
    messages.clear()
    handled = mod.handle_reqtrack_command(chat_id=999, user_id=42, text=cmd)
    if not handled or not messages:
        raise SystemExit(f'contract_fail: no response for {cmd}')
    reply = str(messages[-1][1])
    if mode == 'json':
        obj = json.loads(reply)
        if not isinstance(obj, dict) or 'kpi' not in obj:
            raise SystemExit(f'contract_fail: malformed json payload for {cmd}')
print('telegram_contract=ok')
PY
  else
    echo "[WARN] telegram-n8n-bridge is not running; skipping Telegram contract checks"
  fi

  echo "[$(date -Is)] Reqtrack command-contract smoke passed"
} | tee "$LOG_FILE"

echo "log_file=$LOG_FILE"
