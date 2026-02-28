#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="checkpoints/memory-release-gate"
mkdir -p "$OUT_DIR"

LOG_FILE="$OUT_DIR/memory-release-gate-${STAMP_UTC}.log"
REPLAY_FILE="$OUT_DIR/memory-replay-${STAMP_UTC}.json"
SMOKE_FILE="$OUT_DIR/memory-smoke-${STAMP_UTC}.log"
SMOKE_LIVE_FILE="$OUT_DIR/memory-smoke-live-${STAMP_UTC}.log"
SMOKE_LIVE_STATUS_FILE="$OUT_DIR/memory-smoke-live-status-${STAMP_UTC}.json"
SUMMARY_FILE="$OUT_DIR/memory-release-gate-summary-${STAMP_UTC}.json"
MAX_ATTEMPTS="${MEMORY_RELEASE_GATE_MAX_ATTEMPTS:-2}"
RETRY_BACKOFF_SECONDS="${MEMORY_RELEASE_GATE_RETRY_BACKOFF_SECONDS:-15}"

ATTEMPT=1
ATTEMPTS_USED=0
FIRST_GATE_RC=0
GATE_RC=1

while (( ATTEMPT <= MAX_ATTEMPTS )); do
    ATTEMPTS_USED="$ATTEMPT"
    if (( ATTEMPT == 1 )); then
        {
            echo "[checkpoint] attempt=${ATTEMPT}/${MAX_ATTEMPTS}"
            set +e
            ./scripts/run-memory-release-gate.sh
            GATE_RC=$?
            set -e
            echo "[checkpoint] attempt=${ATTEMPT} rc=${GATE_RC}"
        } >"$LOG_FILE" 2>&1
        FIRST_GATE_RC="$GATE_RC"
    else
        {
            echo
            echo "[checkpoint] retry attempt=${ATTEMPT}/${MAX_ATTEMPTS} backoff=${RETRY_BACKOFF_SECONDS}s"
            set +e
            ./scripts/run-memory-release-gate.sh
            GATE_RC=$?
            set -e
            echo "[checkpoint] attempt=${ATTEMPT} rc=${GATE_RC}"
        } >>"$LOG_FILE" 2>&1
    fi

    if (( GATE_RC == 0 )); then
        break
    fi

    if (( ATTEMPT < MAX_ATTEMPTS )); then
        sleep "$RETRY_BACKOFF_SECONDS"
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

if [[ -f /tmp/memory-replay.json ]]; then
  cp /tmp/memory-replay.json "$REPLAY_FILE"
fi

if [[ -f /tmp/memory-smoke.log ]]; then
  cp /tmp/memory-smoke.log "$SMOKE_FILE"
fi

if [[ -f /tmp/memory-smoke-live.log ]]; then
    cp /tmp/memory-smoke-live.log "$SMOKE_LIVE_FILE"
fi

if [[ -f /tmp/memory-smoke-live-status.json ]]; then
    cp /tmp/memory-smoke-live-status.json "$SMOKE_LIVE_STATUS_FILE"
fi

python3 - <<PY
import json
from pathlib import Path

summary_path = Path(${SUMMARY_FILE@Q})
log_path = Path(${LOG_FILE@Q})
replay_path = Path(${REPLAY_FILE@Q})
smoke_path = Path(${SMOKE_FILE@Q})
smoke_live_path = Path(${SMOKE_LIVE_FILE@Q})
smoke_live_status_path = Path(${SMOKE_LIVE_STATUS_FILE@Q})

gate_rc = int(${GATE_RC})
first_gate_rc = int(${FIRST_GATE_RC})
attempts_used = int(${ATTEMPTS_USED})
max_attempts = int(${MAX_ATTEMPTS})
retry_backoff_seconds = int(${RETRY_BACKOFF_SECONDS})
metrics = {}
live_smoke_signal = None

if replay_path.exists():
    try:
        payload = json.loads(replay_path.read_text(encoding="utf-8"))
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        for key in (
            "memory_scope_accuracy",
            "conflict_false_positive_rate",
            "memory_write_gate_accuracy",
            "memory_context_latency_ms_p95",
            "total_cases",
        ):
            metrics[key] = summary.get(key)
    except Exception as exc:
        metrics["parse_error"] = str(exc)

if smoke_live_status_path.exists():
    try:
        live_smoke_signal = json.loads(smoke_live_status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        live_smoke_signal = {"enabled": False, "parse_error": str(exc)}

out = {
    "timestamp_utc": "${STAMP_UTC}",
    "overall_passed": gate_rc == 0,
    "gate_rc": gate_rc,
    "first_gate_rc": first_gate_rc,
    "attempts_used": attempts_used,
    "max_attempts": max_attempts,
    "retry_backoff_seconds": retry_backoff_seconds,
    "artifacts": {
        "gate_log": str(log_path),
        "replay_json": str(replay_path) if replay_path.exists() else "",
        "smoke_log": str(smoke_path) if smoke_path.exists() else "",
        "smoke_live_log": str(smoke_live_path) if smoke_live_path.exists() else "",
        "smoke_live_status": str(smoke_live_status_path) if smoke_live_status_path.exists() else "",
    },
    "metrics": metrics,
    "live_smoke_signal": live_smoke_signal,
}

summary_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"MEMORY_RELEASE_GATE_CHECKPOINT={'PASS' if gate_rc == 0 else 'FAIL'}")
print(f"SUMMARY_FILE={summary_path}")
print(f"GATE_LOG={log_path}")
PY

LATEST_LINK="$OUT_DIR/latest-memory-release-gate-summary.json"
cp "$SUMMARY_FILE" "$LATEST_LINK"

exit "$GATE_RC"
