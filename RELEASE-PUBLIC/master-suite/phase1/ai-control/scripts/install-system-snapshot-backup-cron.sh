#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CRON_TAG="# ai-control-system-snapshot-backup"
CMD="$ROOT_DIR/scripts/backup-system-snapshots.sh"
SCHEDULE="${BACKUP_CRON_SCHEDULE:-45 2 * * *}"
ENTRY="$SCHEDULE $CMD $CRON_TAG"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(crontab -l 2>/dev/null || true) | grep -v "$CRON_TAG" >"$TMP_FILE" || true
echo "$ENTRY" >>"$TMP_FILE"
crontab "$TMP_FILE"

echo "[OK] Installed cron job:"
echo "  - $ENTRY"
crontab -l | grep "$CRON_TAG" || true
