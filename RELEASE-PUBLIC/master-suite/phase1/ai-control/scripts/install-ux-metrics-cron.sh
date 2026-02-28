#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CRON_TAG="# ai-control-ux-metrics"
CMD="$ROOT_DIR/scripts/run-ux-metrics-and-alert.sh"
ENTRY="20 6 * * * $CMD $CRON_TAG"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(crontab -l 2>/dev/null || true) | grep -v "$CRON_TAG" >"$TMP_FILE" || true
echo "$ENTRY" >>"$TMP_FILE"
crontab "$TMP_FILE"

echo "[OK] Installed cron job:"
echo "  - $ENTRY"
crontab -l | grep "$CRON_TAG" || true
