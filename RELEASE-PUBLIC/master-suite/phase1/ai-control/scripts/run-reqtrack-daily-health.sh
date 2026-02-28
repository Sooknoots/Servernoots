#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

if [[ -f .env.secrets ]]; then
  set -a
  source .env.secrets
  set +a
fi

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/reqtrack-daily-health-$(date +%F).log"

run_step() {
  local label="$1"
  shift
  echo "[$(date -Is)] step=${label} start" | tee -a "$LOG_FILE"
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[$(date -Is)] step=${label} ok" | tee -a "$LOG_FILE"
    return 0
  fi
  echo "[$(date -Is)] step=${label} fail" | tee -a "$LOG_FILE"
  return 1
}

tracker_status=ok
kpi_status=ok
dashboard_status=ok

run_step tracker ./scripts/run-media-request-tracker-and-alert.sh || tracker_status=fail
run_step kpi ./scripts/run-media-request-tracker-kpi-and-alert.sh || kpi_status=fail
run_step dashboard ./scripts/render-media-request-tracker-dashboard-status.sh || dashboard_status=fail

overall=ok
if [[ "$tracker_status" != "ok" || "$kpi_status" != "ok" || "$dashboard_status" != "ok" ]]; then
  overall=degraded
fi

echo "[$(date -Is)] reqtrack_daily_health overall=${overall} tracker=${tracker_status} kpi=${kpi_status} dashboard=${dashboard_status} log=${LOG_FILE}" | tee -a "$LOG_FILE"

if [[ "$overall" == "ok" ]]; then
  exit 0
fi
exit 1
