#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
TRACKER_SCRIPT="$ROOT_DIR/scripts/track-stale-media-requests.py"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reqtrack-release-gate-$(date +%F).log"

DRILL_STATE="${REQTRACK_RELEASE_GATE_DRILL_STATE:-/tmp/reqtrack-release-gate-state.json}"
KEEP_DRILL_STATE="${REQTRACK_RELEASE_GATE_KEEP_DRILL_STATE:-false}"
KPI_WINDOW_HOURS="${REQTRACK_RELEASE_GATE_KPI_WINDOW_HOURS:-24}"
NTFY_BASE="${REQTRACK_RELEASE_GATE_NTFY_BASE:-http://127.0.0.1:8091}"
ADMIN_TOPIC="${REQTRACK_RELEASE_GATE_ADMIN_TOPIC:-reqtrack-release-gate-admin}"
USER_TOPIC="${REQTRACK_RELEASE_GATE_USER_TOPIC:-reqtrack-release-gate-user}"

if ! command -v jq >/dev/null 2>&1; then
  echo "[FAIL] jq is required for reqtrack release gate"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[FAIL] python3 is required for reqtrack release gate"
  exit 1
fi

cleanup() {
  if [[ "$KEEP_DRILL_STATE" != "true" ]]; then
    rm -f "$DRILL_STATE"
  fi
}
trap cleanup EXIT

rm -f "$DRILL_STATE"

{
  echo "[$(date -Is)] Reqtrack release gate started"
  echo "[$(date -Is)] Check 1/4: incident list JSON contract"
  python3 "$TRACKER_SCRIPT" --incident-action list --incident-filter all --json \
    | jq -e '.count >= 0 and ((.incidents | type) == "array")' >/dev/null
  python3 "$TRACKER_SCRIPT" --incident-action list --incident-filter all --json \
    | jq '{count, sample_incidents:(.incidents[:2])}'

  echo "[$(date -Is)] Check 2/4: KPI JSON contract (daily + weekly wrapper)"
  python3 "$TRACKER_SCRIPT" --kpi-report --kpi-window-hours "$KPI_WINDOW_HOURS" --json \
    | jq -e '.kpi.window_hours >= 1 and ((.kpi.totals | type) == "object") and (.kpi.totals.incidents_total >= 0)' >/dev/null
  python3 "$TRACKER_SCRIPT" --kpi-report --kpi-window-hours "$KPI_WINDOW_HOURS" --json \
    | jq '{window_hours:.kpi.window_hours, totals:.kpi.totals, stale_summary:.kpi.stale_summary}'

  python3 "$TRACKER_SCRIPT" --kpi-report --kpi-window-hours 168 --json \
    | jq -e '.kpi.window_hours >= 1 and ((.kpi.totals | type) == "object") and (.kpi.totals.incidents_total >= 0)' >/dev/null
  python3 "$TRACKER_SCRIPT" --kpi-report --kpi-window-hours 168 --json \
    | jq '{window_hours:.kpi.window_hours, totals:.kpi.totals, stale_summary:.kpi.stale_summary}'

  echo "[$(date -Is)] Check 3/4: stateful dry drill progression (dedupe markers via isolated ntfy topics)"
  python3 "$TRACKER_SCRIPT" --dry-drill --dry-drill-stateful --emit-ntfy --ntfy-base "$NTFY_BASE" --admin-topic "$ADMIN_TOPIC" --user-topic "$USER_TOPIC" --state-file "$DRILL_STATE" --json \
    | tee /tmp/reqtrack-release-gate-run1.json \
    | jq -e '.stale_count == 2 and .notify_candidate_count == 2 and ((.items | length) == 2) and .ntfy.admin.sent == true and .ntfy.user.sent == true' >/dev/null
  jq '{run:"run1", stale_count, notify_candidate_count, items:[.items[]|{id:.request_id,age:.age_minutes,level:.incident.current_level,notified:.incident.should_notify}]}' /tmp/reqtrack-release-gate-run1.json

  python3 "$TRACKER_SCRIPT" --dry-drill --dry-drill-stateful --emit-ntfy --ntfy-base "$NTFY_BASE" --admin-topic "$ADMIN_TOPIC" --user-topic "$USER_TOPIC" --state-file "$DRILL_STATE" --json \
    | tee /tmp/reqtrack-release-gate-run2.json \
    | jq -e '.stale_count == 2 and .notify_candidate_count == 0 and ((.items | length) == 2)' >/dev/null
  jq '{run:"run2", stale_count, notify_candidate_count, items:[.items[]|{id:.request_id,age:.age_minutes,level:.incident.current_level,notified:.incident.should_notify}]}' /tmp/reqtrack-release-gate-run2.json

  python3 "$TRACKER_SCRIPT" --dry-drill --dry-drill-stateful --emit-ntfy --ntfy-base "$NTFY_BASE" --admin-topic "$ADMIN_TOPIC" --user-topic "$USER_TOPIC" --state-file "$DRILL_STATE" --dry-drill-admin-age-minutes 130 --dry-drill-user-age-minutes 140 --json \
    | tee /tmp/reqtrack-release-gate-run3.json \
    | jq -e '.stale_count == 2 and .notify_candidate_count == 2 and ((.items | length) == 2) and ([.items[].incident.current_level] | min) >= 2 and .ntfy.admin.sent == true and .ntfy.user.sent == true' >/dev/null
  jq '{run:"run3", stale_count, notify_candidate_count, items:[.items[]|{id:.request_id,age:.age_minutes,level:.incident.current_level,notified:.incident.should_notify}]}' /tmp/reqtrack-release-gate-run3.json

  echo "[$(date -Is)] Check 4/4: state file integrity"
  jq -e '.incidents | type == "object" and ((keys | length) >= 2)' "$DRILL_STATE" >/dev/null
  jq '{state_file: input_filename, incident_keys: (keys | length)}' "$DRILL_STATE"

  rm -f /tmp/reqtrack-release-gate-run1.json /tmp/reqtrack-release-gate-run2.json /tmp/reqtrack-release-gate-run3.json
  echo "[$(date -Is)] Reqtrack release gate passed"
} | tee "$LOG_FILE"

echo "log_file=$LOG_FILE"