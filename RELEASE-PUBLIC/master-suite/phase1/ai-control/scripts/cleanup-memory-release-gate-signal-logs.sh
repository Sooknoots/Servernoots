#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
RETENTION_DAYS="${MEMORY_RELEASE_GATE_SIGNAL_LOG_RETENTION_DAYS:-30}"
PATTERN="memory-release-gate-signal-alert-*.log"

mkdir -p "$LOG_DIR"

if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || (( RETENTION_DAYS < 1 )); then
  echo "[ERROR] MEMORY_RELEASE_GATE_SIGNAL_LOG_RETENTION_DAYS must be an integer >= 1 (got: $RETENTION_DAYS)" >&2
  exit 2
fi

CUTOFF_DAYS="$RETENTION_DAYS"
LATEST_FILE="$LOG_DIR/memory-release-gate-signal-alert-latest.log"

TOTAL_MATCHED=$(find "$LOG_DIR" -maxdepth 1 -type f -name "$PATTERN" ! -name "memory-release-gate-signal-alert-latest.log" | wc -l)
TO_DELETE=$(find "$LOG_DIR" -maxdepth 1 -type f -name "$PATTERN" ! -name "memory-release-gate-signal-alert-latest.log" -mtime "+$CUTOFF_DAYS" | wc -l)

if (( TO_DELETE > 0 )); then
  find "$LOG_DIR" -maxdepth 1 -type f -name "$PATTERN" ! -name "memory-release-gate-signal-alert-latest.log" -mtime "+$CUTOFF_DAYS" -delete
fi

REMAINING=$(find "$LOG_DIR" -maxdepth 1 -type f -name "$PATTERN" ! -name "memory-release-gate-signal-alert-latest.log" | wc -l)

echo "MEMORY_RELEASE_GATE_SIGNAL_LOG_CLEANUP=PASS"
echo "RETENTION_DAYS=$RETENTION_DAYS"
echo "TOTAL_MATCHED=$TOTAL_MATCHED"
echo "DELETED=$TO_DELETE"
echo "REMAINING=$REMAINING"
if [[ -f "$LATEST_FILE" ]]; then
  echo "LATEST_POINTER=present"
else
  echo "LATEST_POINTER=missing"
fi
