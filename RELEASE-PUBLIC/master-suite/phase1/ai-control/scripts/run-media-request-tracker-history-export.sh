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
LOG_FILE="$LOG_DIR/media-request-tracker-history-export-$(date +%F).log"

REQTRACK_EXPORT_FORMAT="${REQTRACK_EXPORT_FORMAT:-ndjson}"
REQTRACK_EXPORT_WINDOW_HOURS="${REQTRACK_EXPORT_WINDOW_HOURS:-168}"
REQTRACK_EXPORT_LIMIT="${REQTRACK_EXPORT_LIMIT:-1000}"
REQTRACK_EXPORT_DIR="${REQTRACK_EXPORT_DIR:-$LOG_DIR}"
REQTRACK_EXPORT_FILE="${REQTRACK_EXPORT_FILE:-$REQTRACK_EXPORT_DIR/media-request-tracker-history-$(date +%F).${REQTRACK_EXPORT_FORMAT}}"

ARGS=(
  --kpi-report
  --kpi-window-hours "${REQTRACK_KPI_WINDOW_HOURS:-24}"
  --export-history-format "$REQTRACK_EXPORT_FORMAT"
  --export-history-file "$REQTRACK_EXPORT_FILE"
  --export-history-window-hours "$REQTRACK_EXPORT_WINDOW_HOURS"
  --export-history-limit "$REQTRACK_EXPORT_LIMIT"
)

if [[ "${REQTRACK_EXPORT_EMIT_KPI_NTFY:-false}" == "true" ]]; then
  ARGS+=(--emit-kpi-ntfy)
fi

{
  echo "[$(date -Is)] Starting reqtrack history export"
  ./scripts/reqtrack "${ARGS[@]}"
  echo "[$(date -Is)] Reqtrack history export complete"
} >>"$LOG_FILE" 2>&1
