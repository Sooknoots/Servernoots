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
LOG_FILE="$LOG_DIR/personalized-plex-recs-$(date +%F).log"
HEARTBEAT_FILE="${MEDIA_PERSONALIZED_HEARTBEAT_FILE:-$LOG_DIR/media-personalized-heartbeat.json}"
STATE_FILE="${MEDIA_PERSONALIZED_MONITOR_STATE_FILE:-$LOG_DIR/media-personalized-monitor-state.json}"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_ALERT_TOPIC="${MEDIA_PERSONALIZED_ALERT_TOPIC:-ops-alerts}"
NTFY_ALERT_URL="${NTFY_BASE%/}/${NTFY_ALERT_TOPIC}"
ALERT_ON_SKIP="${MEDIA_PERSONALIZED_ALERT_ON_SKIP:-true}"
ZERO_ACTIVITY_THRESHOLD="${MEDIA_PERSONALIZED_ZERO_ACTIVITY_THRESHOLD:-3}"

HOSTNAME_VALUE="$(hostname)"
STAMP="$(date -Is)"

send_alert() {
  local title="$1"
  local message="$2"
  curl -fsS -X POST "$NTFY_ALERT_URL" \
    -H "Title: $title" \
    -H "Priority: high" \
    -H "Tags: warning,robot_face" \
    -d "$message" >/dev/null 2>&1 || true
}

write_heartbeat() {
  local status="$1"
  local reason="$2"
  local users="$3"
  local notified="$4"
  local auto_requested="$5"
  local dry_run="$6"
  cat >"$HEARTBEAT_FILE" <<EOF
{
  "timestamp": "$(date -Is)",
  "status": "$status",
  "reason": "$reason",
  "users": $users,
  "notified": $notified,
  "auto_requested": $auto_requested,
  "dry_run": "$dry_run"
}
EOF
}

fail_run() {
  local reason="$1"
  local details="$2"
  {
    echo "[$(date -Is)] [FAIL] $reason"
    if [[ -n "$details" ]]; then
      echo "$details"
    fi
  } >>"$LOG_FILE"
  write_heartbeat "failed" "$reason" 0 0 0 "unknown"
  send_alert "Personalized Plex Recs Failed" "Personalized recs failed on ${HOSTNAME_VALUE} at ${STAMP}. reason=${reason}. ${details} log=${LOG_FILE}"
  exit 1
}

if [[ -z "${TAUTULLI_URL:-}" || -z "${TAUTULLI_API_KEY:-}" ]]; then
  {
    echo "[$(date -Is)] Skipping personalized plex recommendation run"
    echo "[SKIP] Missing required env: TAUTULLI_URL and/or TAUTULLI_API_KEY"
  } >>"$LOG_FILE" 2>&1
  write_heartbeat "skipped" "missing_tautulli_env" 0 0 0 "unknown"
  if [[ "$ALERT_ON_SKIP" == "true" ]]; then
    send_alert "Personalized Plex Recs Skipped" "Personalized recs skipped on ${HOSTNAME_VALUE} at ${STAMP}. reason=missing_tautulli_env log=${LOG_FILE}"
  fi
  exit 0
fi

ARGS=()
if [[ "${MEDIA_PERSONALIZED_DRY_RUN:-false}" == "true" ]]; then
  ARGS+=(--dry-run)
fi
if [[ -n "${MEDIA_PERSONALIZED_PROFILES_PATH:-}" ]]; then
  ARGS+=(--profiles "${MEDIA_PERSONALIZED_PROFILES_PATH}")
fi
if [[ -n "${MEDIA_PERSONALIZED_STATE_PATH:-}" ]]; then
  ARGS+=(--state "${MEDIA_PERSONALIZED_STATE_PATH}")
fi
if [[ -n "${MEDIA_PERSONALIZED_AUTO_REQUEST_PER_USER:-}" ]]; then
  ARGS+=(--auto-request-per-user "${MEDIA_PERSONALIZED_AUTO_REQUEST_PER_USER}")
fi

TMP_OUT="$(mktemp)"
trap 'rm -f "$TMP_OUT"' EXIT

echo "[$(date -Is)] Starting personalized plex recommendation run" >>"$LOG_FILE"
set +e
python3 scripts/run-personalized-plex-recs.py "${ARGS[@]}" >"$TMP_OUT" 2>&1
RUN_STATUS=$?
set -e
cat "$TMP_OUT" >>"$LOG_FILE"

if [[ "$RUN_STATUS" -ne 0 ]]; then
  fail_run "runner_exit_${RUN_STATUS}" "python_exit=${RUN_STATUS}"
fi

SUMMARY_LINE="$(grep -E 'users=[0-9]+ notified=[0-9]+ auto_requested=[0-9]+ dry_run=(True|False|true|false)' "$TMP_OUT" | tail -n 1 || true)"
if [[ -z "$SUMMARY_LINE" ]]; then
  fail_run "summary_missing" "missing_expected_summary_line"
fi

read -r USERS NOTIFIED AUTO_REQUESTED DRY_RUN_FLAG <<<"$(SUMMARY_LINE="$SUMMARY_LINE" /usr/bin/python3 - <<'PY'
import os, re
line = os.environ.get("SUMMARY_LINE", "")
m = re.search(r"users=(\d+)\s+notified=(\d+)\s+auto_requested=(\d+)\s+dry_run=(True|False|true|false)", line)
if not m:
    print("0 0 0 unknown")
else:
    print(f"{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)}")
PY
)"

if [[ "$USERS" -lt 1 ]]; then
  write_heartbeat "degraded" "no_profiles" "$USERS" "$NOTIFIED" "$AUTO_REQUESTED" "$DRY_RUN_FLAG"
  send_alert "Personalized Plex Recs Degraded" "Personalized recs degraded on ${HOSTNAME_VALUE} at ${STAMP}. reason=no_profiles users=${USERS} notified=${NOTIFIED} auto_requested=${AUTO_REQUESTED} dry_run=${DRY_RUN_FLAG} log=${LOG_FILE}"
  exit 1
fi

STATE_RESULT="$(STATE_FILE="$STATE_FILE" NOTIFIED="$NOTIFIED" AUTO_REQUESTED="$AUTO_REQUESTED" THRESHOLD="$ZERO_ACTIVITY_THRESHOLD" /usr/bin/python3 - <<'PY'
import json, os, pathlib
state_path = pathlib.Path(os.environ["STATE_FILE"])
notified = int(os.environ.get("NOTIFIED", "0") or 0)
auto_requested = int(os.environ.get("AUTO_REQUESTED", "0") or 0)
threshold = max(1, int(os.environ.get("THRESHOLD", "3") or 3))

state = {}
if state_path.exists():
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state = loaded
    except Exception:
        state = {}

zero_activity = 1 if (notified == 0 and auto_requested == 0) else 0
prev = int(state.get("consecutive_zero_activity", 0) or 0)
current = prev + 1 if zero_activity else 0
alert = bool(zero_activity and current >= threshold and prev < threshold)

state["consecutive_zero_activity"] = current
state["last_notified"] = notified
state["last_auto_requested"] = auto_requested
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"{current} {'1' if alert else '0'}")
PY
)"

read -r CONSEC_ZERO SHOULD_ALERT_ZERO <<<"$STATE_RESULT"

if [[ "$SHOULD_ALERT_ZERO" == "1" ]]; then
  send_alert "Personalized Plex Recs Zero Activity" "Personalized recs saw zero activity for ${CONSEC_ZERO} consecutive runs on ${HOSTNAME_VALUE} at ${STAMP}. users=${USERS} notified=${NOTIFIED} auto_requested=${AUTO_REQUESTED} threshold=${ZERO_ACTIVITY_THRESHOLD} log=${LOG_FILE}"
fi

write_heartbeat "ok" "run_ok" "$USERS" "$NOTIFIED" "$AUTO_REQUESTED" "$DRY_RUN_FLAG"
echo "[$(date -Is)] Personalized plex recommendation run complete users=${USERS} notified=${NOTIFIED} auto_requested=${AUTO_REQUESTED} dry_run=${DRY_RUN_FLAG}" >>"$LOG_FILE"
