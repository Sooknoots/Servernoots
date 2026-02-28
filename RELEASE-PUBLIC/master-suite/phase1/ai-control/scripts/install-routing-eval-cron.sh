#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CRON_TAG="# ai-control-routing-eval"
CMD="$ROOT_DIR/scripts/run-routing-eval-and-alert.sh"
ENTRY_1="15 3 * * * $CMD $CRON_TAG"
ENTRY_2="15 12 * * * $CMD $CRON_TAG"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(crontab -l 2>/dev/null || true) | grep -v "$CRON_TAG" >"$TMP_FILE" || true
echo "$ENTRY_1" >>"$TMP_FILE"
echo "$ENTRY_2" >>"$TMP_FILE"
crontab "$TMP_FILE"

echo "[OK] Installed cron jobs:"
echo "  - $ENTRY_1"
echo "  - $ENTRY_2"
crontab -l | grep "$CRON_TAG" || true
