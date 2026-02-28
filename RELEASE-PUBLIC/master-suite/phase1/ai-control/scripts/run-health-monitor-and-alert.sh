#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/health-monitor-$(date +%F).log"

STATE_FILE="${HEALTH_MONITOR_STATE_FILE:-$LOG_DIR/health-monitor-state.json}"
CONSECUTIVE_THRESHOLD="${HEALTH_MONITOR_CONSECUTIVE_DEGRADED_THRESHOLD:-2}"
MAX_NOTIFY_STATS_AGE_SECONDS="${HEALTH_MONITOR_MAX_NOTIFY_STATS_AGE_SECONDS:-3600}"
MAX_FANOUT_AGE_SECONDS="${HEALTH_MONITOR_MAX_FANOUT_AGE_SECONDS:-10800}"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${HEALTH_MONITOR_NTFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"

STAMP="$(date -Is)"
HOSTNAME_VALUE="$(hostname)"

SNAPSHOT_JSON=""
SNAPSHOT_STATUS=0
set +e
SNAPSHOT_JSON="$(docker exec telegram-n8n-bridge python3 -c "import json,telegram_to_n8n as m; users=m.load_user_registry().get('users',{}); admin=next((int(uid) for uid,rec in users.items() if isinstance(rec,dict) and rec.get('role')=='admin' and rec.get('status')=='active'),0); print(json.dumps(m.build_health_snapshot(request_user_id=admin, include_validate_probe=False), ensure_ascii=False, sort_keys=True))" 2>/dev/null)"
SNAPSHOT_STATUS=$?
set -e

IS_DEGRADED=0
REASONS=()
N8N_OK=0
USERS_ACTIVE=0
NOTIFY_STATS_AGE=-1
FANOUT_AGE=-1

if [[ $SNAPSHOT_STATUS -ne 0 || -z "$SNAPSHOT_JSON" ]]; then
  IS_DEGRADED=1
  REASONS+=("snapshot_unavailable")
else
  read -r N8N_OK USERS_ACTIVE NOTIFY_STATS_AGE FANOUT_AGE <<<"$(SNAPSHOT_JSON="$SNAPSHOT_JSON" /usr/bin/python3 - <<'PY'
import json, os
from datetime import datetime, timezone

def parse_iso(value: str) -> datetime | None:
    v = str(value or "").strip()
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None

raw = os.environ.get("SNAPSHOT_JSON", "")
obj = json.loads(raw) if raw else {}
checked = parse_iso(obj.get("checked_at"))
bridge = obj.get("bridge") if isinstance(obj.get("bridge"), dict) else {}
n8n = obj.get("n8n") if isinstance(obj.get("n8n"), dict) else {}
fanout = obj.get("last_fanout") if isinstance(obj.get("last_fanout"), dict) else {}

n8n_ok = 1 if bool(n8n.get("ok", False)) else 0
users_active = int(bridge.get("users_active", 0) or 0)

notify_age = -1
notify_updated = parse_iso(bridge.get("notify_stats_updated_at"))
if checked and notify_updated:
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    if notify_updated.tzinfo is None:
        notify_updated = notify_updated.replace(tzinfo=timezone.utc)
    notify_age = int(max(0, (checked - notify_updated).total_seconds()))

fanout_age = -1
try:
    fanout_ts = int(fanout.get("ts", 0) or 0)
except Exception:
    fanout_ts = 0
if checked and fanout_ts > 0:
    checked_ts = int(checked.timestamp())
    fanout_age = int(max(0, checked_ts - fanout_ts))

print(n8n_ok, users_active, notify_age, fanout_age)
PY
)"

  if [[ "$N8N_OK" != "1" ]]; then
    IS_DEGRADED=1
    REASONS+=("n8n_unreachable")
  fi

  if [[ "$USERS_ACTIVE" -lt 1 ]]; then
    IS_DEGRADED=1
    REASONS+=("no_active_users")
  fi

  if [[ "$NOTIFY_STATS_AGE" -lt 0 || "$NOTIFY_STATS_AGE" -gt "$MAX_NOTIFY_STATS_AGE_SECONDS" ]]; then
    IS_DEGRADED=1
    REASONS+=("notify_stats_stale")
  fi

  if [[ "$FANOUT_AGE" -lt 0 || "$FANOUT_AGE" -gt "$MAX_FANOUT_AGE_SECONDS" ]]; then
    IS_DEGRADED=1
    REASONS+=("fanout_stale")
  fi
fi

STATE_RESULT="$(STATE_FILE="$STATE_FILE" IS_DEGRADED="$IS_DEGRADED" CONSECUTIVE_THRESHOLD="$CONSECUTIVE_THRESHOLD" /usr/bin/python3 - <<'PY'
import json, os, pathlib
state_path = pathlib.Path(os.environ["STATE_FILE"])
is_degraded = int(os.environ.get("IS_DEGRADED", "0") or 0)
threshold = max(1, int(os.environ.get("CONSECUTIVE_THRESHOLD", "2") or "2"))
state = {}
if state_path.exists():
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state = loaded
    except Exception:
        state = {}

prev_count = int(state.get("consecutive_degraded", 0) or 0)
count = prev_count + 1 if is_degraded else 0
alert = bool(is_degraded and count >= threshold and prev_count < threshold)

state["consecutive_degraded"] = count
state["last_status"] = "degraded" if is_degraded else "ok"
state["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"consecutive_degraded": count, "alert": alert}, ensure_ascii=False))
PY
)"

CONSECUTIVE_DEGRADED="$(STATE_RESULT="$STATE_RESULT" /usr/bin/python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("STATE_RESULT", "{}"))
print(int(obj.get("consecutive_degraded", 0) or 0))
PY
)"
ALERT_NEEDED="$(STATE_RESULT="$STATE_RESULT" /usr/bin/python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("STATE_RESULT", "{}"))
print("1" if bool(obj.get("alert", False)) else "0")
PY
)"

REASON_TEXT="ok"
if [[ ${#REASONS[@]} -gt 0 ]]; then
  REASON_TEXT="$(IFS=','; echo "${REASONS[*]}")"
fi

{
  echo "[$STAMP] health_monitor status=$([[ "$IS_DEGRADED" == "1" ]] && echo degraded || echo ok) host=$HOSTNAME_VALUE"
  echo "snapshot_status=$SNAPSHOT_STATUS n8n_ok=$N8N_OK users_active=$USERS_ACTIVE notify_stats_age_s=$NOTIFY_STATS_AGE fanout_age_s=$FANOUT_AGE"
  echo "consecutive_degraded=$CONSECUTIVE_DEGRADED threshold=$CONSECUTIVE_THRESHOLD reasons=$REASON_TEXT"
  echo "state_file=$STATE_FILE"
} >>"$LOG_FILE"

if [[ "$IS_DEGRADED" == "1" && "$ALERT_NEEDED" == "1" ]]; then
  MESSAGE=$(cat <<EOF
Telegram health monitor degraded on ${HOSTNAME_VALUE} at ${STAMP}.

reasons=${REASON_TEXT}
consecutive_degraded=${CONSECUTIVE_DEGRADED}
threshold=${CONSECUTIVE_THRESHOLD}
n8n_ok=${N8N_OK}
users_active=${USERS_ACTIVE}
notify_stats_age_s=${NOTIFY_STATS_AGE}
fanout_age_s=${FANOUT_AGE}
log=${LOG_FILE}
EOF
)

  ENC_TITLE="$(/usr/bin/python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote('Telegram Health Degraded'))
PY
)"

  curl -fsS -X POST "${NTFY_URL}?title=${ENC_TITLE}" \
    -H "Content-Type: text/plain" \
    -d "$MESSAGE" >/dev/null 2>&1 || true
fi

if [[ "$IS_DEGRADED" == "1" ]]; then
  exit 1
fi
exit 0
