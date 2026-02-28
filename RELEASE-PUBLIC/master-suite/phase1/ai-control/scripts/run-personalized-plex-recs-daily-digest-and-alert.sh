#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
TODAY="$(date +%F)"
SOURCE_LOG="$LOG_DIR/personalized-plex-recs-${TODAY}.log"
DIGEST_LOG="$LOG_DIR/personalized-plex-recs-digest-${TODAY}.log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${MEDIA_PERSONALIZED_DIGEST_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"
WINDOW_HOURS="${MEDIA_PERSONALIZED_DIGEST_WINDOW_HOURS:-24}"
HOSTNAME_VALUE="$(hostname)"

if [[ ! -f "$SOURCE_LOG" ]]; then
  {
    echo "[$(date -Is)] Personalized digest skipped: source log missing"
    echo "source_log=$SOURCE_LOG"
  } >>"$DIGEST_LOG"
  exit 0
fi

SUMMARY="$(SOURCE_LOG="$SOURCE_LOG" WINDOW_HOURS="$WINDOW_HOURS" python3 - <<'PY'
import json
import os
import re
from datetime import datetime, timedelta

source_log = os.environ.get("SOURCE_LOG", "")
window_hours = int(os.environ.get("WINDOW_HOURS", "24") or "24")
cutoff = datetime.now() - timedelta(hours=window_hours)

summary_re = re.compile(r"users=(\d+)\s+notified=(\d+)\s+auto_requested=(\d+)\s+dry_run=(True|False|true|false)")
ts_re = re.compile(r"^\[(.*?)\]")

runs = 0
notified_total = 0
auto_requested_total = 0
dry_run_count = 0
max_users = 0
failures = 0
skips = 0
zero_activity = 0

with open(source_log, "r", encoding="utf-8", errors="ignore") as fh:
    for raw in fh:
        line = raw.strip()
        if not line:
            continue
        ts_match = ts_re.match(line)
        if ts_match:
            try:
                ts = datetime.fromisoformat(ts_match.group(1).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                ts = None
            if ts is not None and ts < cutoff:
                continue

        if "[FAIL]" in line or "Traceback (most recent call last):" in line:
            failures += 1
        if "[SKIP]" in line:
            skips += 1
        m = summary_re.search(line)
        if not m:
            continue
        users = int(m.group(1))
        notified = int(m.group(2))
        auto_requested = int(m.group(3))
        dry_run = m.group(4).lower() == "true"

        runs += 1
        max_users = max(max_users, users)
        notified_total += notified
        auto_requested_total += auto_requested
        if dry_run:
            dry_run_count += 1
        if notified == 0 and auto_requested == 0:
            zero_activity += 1

print(json.dumps(
    {
        "runs": runs,
        "max_users": max_users,
        "notified_total": notified_total,
        "auto_requested_total": auto_requested_total,
        "dry_run_count": dry_run_count,
        "failures": failures,
        "skips": skips,
        "zero_activity_runs": zero_activity,
        "window_hours": window_hours,
    },
    ensure_ascii=False,
))
PY
)"

RUNS="$(SUMMARY="$SUMMARY" python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("SUMMARY", "{}"))
print(int(obj.get("runs", 0) or 0))
PY
)"

if [[ "$RUNS" -lt 1 ]]; then
  {
    echo "[$(date -Is)] Personalized digest skipped: no summary lines in window"
    echo "window_hours=$WINDOW_HOURS source_log=$SOURCE_LOG"
  } >>"$DIGEST_LOG"
  exit 0
fi

MESSAGE="$(SUMMARY="$SUMMARY" SOURCE_LOG="$SOURCE_LOG" HOSTNAME_VALUE="$HOSTNAME_VALUE" python3 - <<'PY'
import json
import os

obj = json.loads(os.environ.get("SUMMARY", "{}"))
host = os.environ.get("HOSTNAME_VALUE", "unknown")
source_log = os.environ.get("SOURCE_LOG", "")

lines = [
    f"Personalized Plex daily digest ({obj.get('window_hours', 24)}h)",
    f"host={host}",
    f"runs={obj.get('runs', 0)}",
    f"users_max={obj.get('max_users', 0)}",
    f"notified_total={obj.get('notified_total', 0)}",
    f"auto_requested_total={obj.get('auto_requested_total', 0)}",
    f"dry_run_runs={obj.get('dry_run_count', 0)}",
    f"zero_activity_runs={obj.get('zero_activity_runs', 0)}",
    f"skips={obj.get('skips', 0)}",
    f"failure_signals={obj.get('failures', 0)}",
    f"log={source_log}",
]
print("\n".join(lines))
PY
)"

TITLE="Personalized Plex Digest"
PRIORITY="default"
FAILURES="$(SUMMARY="$SUMMARY" python3 - <<'PY'
import json, os
obj = json.loads(os.environ.get("SUMMARY", "{}"))
print(int(obj.get("failures", 0) or 0))
PY
)"
if [[ "$FAILURES" -gt 0 ]]; then
  PRIORITY="high"
fi

curl -fsS -X POST "$NTFY_URL" \
  -H "Title: $TITLE" \
  -H "Priority: $PRIORITY" \
  -H "Tags: bar_chart,movie_camera" \
  -d "$MESSAGE" >/dev/null

{
  echo "[$(date -Is)] Personalized digest sent"
  echo "$MESSAGE"
} >>"$DIGEST_LOG"
