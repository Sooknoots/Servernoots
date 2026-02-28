#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
STAMP_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/memory-release-gate-signal-alert-${STAMP_UTC}.log"
LATEST_LOG="$LOG_DIR/memory-release-gate-signal-alert-latest.log"

THRESHOLD="${MEMORY_RELEASE_GATE_SIGNAL_ALERT_THRESHOLD:-2}"
STATE_FILE="${MEMORY_RELEASE_GATE_SIGNAL_ALERT_STATE_FILE:-$ROOT_DIR/checkpoints/memory-release-gate/live-signal-alert-state.json}"
SUMMARY_FILE="${MEMORY_RELEASE_GATE_SIGNAL_SUMMARY_FILE:-$ROOT_DIR/checkpoints/memory-release-gate/latest-memory-release-gate-summary.json}"

NTFY_BASE="${MEMORY_RELEASE_GATE_SIGNAL_NOTIFY_BASE:-http://127.0.0.1:8091}"
NTFY_TOPIC="${MEMORY_RELEASE_GATE_SIGNAL_NOTIFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"

{
  echo "[$(date -Is)] memory-release-gate-signal-alert start threshold=${THRESHOLD}"

    THRESHOLD="$THRESHOLD" \
    STATE_FILE="$STATE_FILE" \
    SUMMARY_FILE="$SUMMARY_FILE" \
    NTFY_URL="$NTFY_URL" \
    python3 - <<'PY'
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

threshold = int(os.environ.get("THRESHOLD", "2"))
state_path = Path(os.environ["STATE_FILE"])
summary_path = Path(os.environ["SUMMARY_FILE"])
ntfy_url = os.environ["NTFY_URL"]

state_path.parent.mkdir(parents=True, exist_ok=True)

previous = {}
if state_path.exists():
    try:
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        previous = {}

prev_consecutive = int(previous.get("consecutive_failures") or 0)

enabled = False
passed = True
mode = "unknown"
rc = 0
note = "no_summary"
summary_timestamp = None

if summary_path.exists():
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        mode = "parse_error"
        passed = False
        note = f"summary_parse_error:{exc}"
    else:
        summary_timestamp = payload.get("timestamp_utc")
        signal = payload.get("live_smoke_signal") or {}
        enabled = bool(signal.get("enabled"))
        passed = bool(signal.get("passed"))
        mode = str(signal.get("mode") or "unknown")
        rc = int(signal.get("rc") or 0)
        note = str(signal.get("note") or "")

if enabled and not passed:
    consecutive = prev_consecutive + 1
else:
    consecutive = 0

should_alert = enabled and (not passed) and consecutive >= threshold and prev_consecutive < threshold

now_iso = datetime.now(timezone.utc).isoformat()
state_out = {
    "updated_at": now_iso,
    "threshold": threshold,
    "summary_path": str(summary_path),
    "summary_timestamp": summary_timestamp,
    "enabled": enabled,
    "passed": passed,
    "mode": mode,
    "rc": rc,
    "note": note,
    "consecutive_failures": consecutive,
    "should_alert": should_alert,
}

if should_alert:
    title = urllib.parse.quote("Memory Live Signal Degraded")
    host = os.uname().nodename
    message = (
        f"Debounced memory live-signal alert on {host} at {now_iso}.\n"
        f"Consecutive failures: {consecutive} (threshold={threshold}).\n"
        f"mode={mode} rc={rc} note={note}\n"
        f"summary={summary_path}"
    )
    req = urllib.request.Request(
        url=f"{ntfy_url}?title={title}",
        data=message.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        state_out["alert_sent"] = True
        state_out["alert_sent_at"] = now_iso
    except Exception as exc:
        state_out["alert_sent"] = False
        state_out["alert_error"] = str(exc)
else:
    state_out["alert_sent"] = False

state_path.write_text(json.dumps(state_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

status = "PASS"
if enabled and not passed:
    status = "FAIL"
elif not enabled:
    status = "DISABLED"

print(f"MEMORY_RELEASE_GATE_SIGNAL_STATUS={status}")
print(f"MEMORY_RELEASE_GATE_SIGNAL_MODE={mode}")
print(f"MEMORY_RELEASE_GATE_SIGNAL_RC={rc}")
print(f"MEMORY_RELEASE_GATE_SIGNAL_NOTE={note}")
print(f"MEMORY_RELEASE_GATE_SIGNAL_CONSECUTIVE={consecutive}")
print(f"MEMORY_RELEASE_GATE_SIGNAL_THRESHOLD={threshold}")
print(f"MEMORY_RELEASE_GATE_SIGNAL_ALERT_SENT={'true' if state_out.get('alert_sent') else 'false'}")
print(f"STATE_FILE={state_path}")
PY

  echo "[$(date -Is)] memory-release-gate-signal-alert done"
} >>"$LOG_FILE" 2>&1

cp "$LOG_FILE" "$LATEST_LOG"
tail -n 40 "$LOG_FILE"
