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
LOG_FILE="$LOG_DIR/media-request-tracker-kpi-weekly-$(date +%F).log"

REQTRACK_KPI_WEEKLY_WINDOW_HOURS="${REQTRACK_KPI_WEEKLY_WINDOW_HOURS:-168}"

ARGS=(
  --kpi-report
  --kpi-window-hours "$REQTRACK_KPI_WEEKLY_WINDOW_HOURS"
  --emit-kpi-ntfy
)

{
  echo "[$(date -Is)] Starting reqtrack weekly KPI rollup"
  ./scripts/reqtrack "${ARGS[@]}"
  echo "[$(date -Is)] Reqtrack weekly KPI rollup complete"
} >>"$LOG_FILE" 2>&1
