#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/user-rag-snapshot-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${NTFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"
SNAPSHOT_ROOT="${ROOT_DIR}/snapshots/user-rag"
MAX_BYTES="${USER_RAG_SNAPSHOT_MAX_BYTES:-53687091200}"
WARN_PCT="${USER_RAG_SNAPSHOT_WARN_PCT:-90}"

bytes_to_human() {
  python3 - "$1" <<'PY'
import sys
n=float(sys.argv[1])
units=['B','KiB','MiB','GiB','TiB']
i=0
while n>=1024 and i < len(units)-1:
    n/=1024
    i+=1
print(f"{n:.2f} {units[i]}")
PY
}

send_alert() {
  local title="$1"
  local message="$2"
  local enc_title
  enc_title="$(python3 - "$title" <<'PY'
import urllib.parse
import sys
print(urllib.parse.quote(sys.argv[1]))
PY
)"

  curl -fsS -X POST "${NTFY_URL}?title=${enc_title}" \
    -H "Content-Type: text/plain" \
    -d "$message" >/dev/null 2>&1 || true
}

current_usage_bytes() {
  mkdir -p "$SNAPSHOT_ROOT"
  du -sb "$SNAPSHOT_ROOT" | awk '{print $1}'
}

prune_oldest_until_cap() {
  local usage
  usage="$(current_usage_bytes)"
  local deleted=0

  while [[ "$usage" -gt "$MAX_BYTES" ]]; do
    local oldest
    oldest="$(find "$SNAPSHOT_ROOT" -mindepth 1 -maxdepth 1 -type d | sort | head -n 1 || true)"
    [[ -n "$oldest" ]] || break
    echo "[retention] removing oldest snapshot dir: $oldest" >>"$LOG_FILE"
    rm -rf -- "$oldest"
    deleted=$((deleted + 1))
    usage="$(current_usage_bytes)"
  done

  echo "$deleted"
}

set +e
./scripts/snapshot-user-rag-state.sh >>"$LOG_FILE" 2>&1
STATUS=$?
set -e

DELETED_DIRS="$(prune_oldest_until_cap)"
USAGE_BYTES="$(current_usage_bytes)"
USAGE_PCT=$(( USAGE_BYTES * 100 / MAX_BYTES ))

USAGE_HUMAN="$(bytes_to_human "$USAGE_BYTES")"
MAX_HUMAN="$(bytes_to_human "$MAX_BYTES")"

HOSTNAME_VALUE="$(hostname)"
STAMP="$(date -Is)"

if [[ $STATUS -eq 0 ]]; then
  TITLE="User RAG Snapshot OK"
  MESSAGE="User/role + tenant RAG snapshot succeeded on ${HOSTNAME_VALUE} at ${STAMP}. usage=${USAGE_HUMAN}/${MAX_HUMAN} (${USAGE_PCT}%), pruned_dirs=${DELETED_DIRS}."
else
  TITLE="User RAG Snapshot Failed"
  MESSAGE="User/role + tenant RAG snapshot failed on ${HOSTNAME_VALUE} at ${STAMP}. usage=${USAGE_HUMAN}/${MAX_HUMAN} (${USAGE_PCT}%), pruned_dirs=${DELETED_DIRS}. Check ${LOG_FILE}."
fi

send_alert "$TITLE" "$MESSAGE"

if [[ "$USAGE_PCT" -ge "$WARN_PCT" ]]; then
  send_alert "User RAG Snapshot Capacity Warning" \
    "User/role + tenant snapshot storage is near cap on ${HOSTNAME_VALUE}: ${USAGE_HUMAN}/${MAX_HUMAN} (${USAGE_PCT}%)."
fi

if [[ "$USAGE_BYTES" -gt "$MAX_BYTES" ]]; then
  send_alert "User RAG Snapshot Capacity Critical" \
    "Snapshot storage remains over cap after pruning on ${HOSTNAME_VALUE}: ${USAGE_HUMAN}/${MAX_HUMAN} (${USAGE_PCT}%). Immediate cleanup required."
  exit 1
fi

exit $STATUS
