#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CRON_TAG="# ai-control-media-request-tracker-kpi-weekly"
CMD="$ROOT_DIR/scripts/run-media-request-tracker-kpi-weekly-rollup-and-alert.sh"
SCHEDULE="${REQTRACK_KPI_WEEKLY_CRON_SCHEDULE:-40 6 * * 1}"
ENTRY="$SCHEDULE $CMD $CRON_TAG"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(crontab -l 2>/dev/null || true) | grep -v "$CRON_TAG" >"$TMP_FILE" || true
echo "$ENTRY" >>"$TMP_FILE"
crontab "$TMP_FILE"

echo "[OK] Installed weekly cron job:"
echo "  - $ENTRY"
crontab -l | grep "$CRON_TAG" || true
