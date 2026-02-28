#!/usr/bin/env bash
set -euo pipefail

CRON_TAG="# ai-control-personalized-plex-recs"

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

(crontab -l 2>/dev/null || true) | grep -v "$CRON_TAG" >"$TMP_FILE" || true
crontab "$TMP_FILE"

echo "[OK] Removed cron job tag: $CRON_TAG"
if crontab -l 2>/dev/null | grep -q "$CRON_TAG"; then
  echo "[WARN] Matching entries still present"
  crontab -l | grep "$CRON_TAG" || true
  exit 1
fi
echo "[OK] No matching cron entries remain"
