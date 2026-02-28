#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SCOPE_MIN="${MEMORY_SCOPE_MIN:-0.95}"
CONFLICT_FP_MAX="${MEMORY_CONFLICT_FP_MAX:-0.05}"
WRITE_GATE_MIN="${MEMORY_WRITE_GATE_MIN:-0.98}"
LATENCY_P95_MAX="${MEMORY_LATENCY_P95_MAX:-250}"
HARD_SMOKE_MODE="${MEMORY_RELEASE_GATE_HARD_SMOKE_MODE:-local}"
LIVE_SIGNAL_ENABLED="${MEMORY_RELEASE_GATE_LIVE_SIGNAL_ENABLED:-1}"

LIVE_SMOKE_LOG="/tmp/memory-smoke-live.log"
LIVE_SMOKE_STATUS_JSON="/tmp/memory-smoke-live-status.json"

rm -f "$LIVE_SMOKE_LOG" "$LIVE_SMOKE_STATUS_JSON"

echo "[gate] hard smoke --mode ${HARD_SMOKE_MODE}"
./scripts/eval-telegram-chat-smoke.py --mode "$HARD_SMOKE_MODE" >/tmp/memory-smoke.log

LIVE_SIGNAL_RC=0
LIVE_SIGNAL_MODE="disabled"
if [[ "$LIVE_SIGNAL_ENABLED" == "1" ]]; then
    LIVE_SIGNAL_MODE="live"
    echo "[gate] live smoke signal --mode live (non-blocking)"
    set +e
    ./scripts/eval-telegram-chat-smoke.py --mode live >"$LIVE_SMOKE_LOG" 2>&1
    LIVE_SIGNAL_RC=$?
    set -e
fi

echo "[gate] replay --json"
python3 ./scripts/eval-memory-replay.py --json >/tmp/memory-replay.json

echo "[gate] threshold checks"
MEMORY_SCOPE_MIN="$SCOPE_MIN" \
MEMORY_CONFLICT_FP_MAX="$CONFLICT_FP_MAX" \
MEMORY_WRITE_GATE_MIN="$WRITE_GATE_MIN" \
MEMORY_LATENCY_P95_MAX="$LATENCY_P95_MAX" \
LIVE_SIGNAL_MODE="$LIVE_SIGNAL_MODE" \
LIVE_SIGNAL_RC="$LIVE_SIGNAL_RC" \
python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

path = "/tmp/memory-replay.json"
payload = json.load(open(path, encoding="utf-8"))
summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

live_signal_mode = os.environ.get("LIVE_SIGNAL_MODE", "disabled")
live_signal_rc = int(os.environ.get("LIVE_SIGNAL_RC", "0"))
live_smoke_status_path = Path("/tmp/memory-smoke-live-status.json")

live_smoke_status = {
    "enabled": live_signal_mode == "live",
    "mode": live_signal_mode,
    "rc": live_signal_rc,
    "passed": live_signal_rc == 0,
    "note": (
        "non_blocking_signal"
        if live_signal_mode == "live"
        else "live_signal_disabled"
    ),
}
live_smoke_status_path.write_text(
    json.dumps(live_smoke_status, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)


def parse_metric(name: str, default: float) -> float:
    raw = summary.get(name)
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)

scope = parse_metric("memory_scope_accuracy", 0.0)
conflict_fp = parse_metric("conflict_false_positive_rate", 1.0)
write_acc = parse_metric("memory_write_gate_accuracy", 0.0)
latency_p95 = parse_metric("memory_context_latency_ms_p95", 10**9)

scope_min = float(os.environ.get("MEMORY_SCOPE_MIN", "0.95"))
conflict_max = float(os.environ.get("MEMORY_CONFLICT_FP_MAX", "0.05"))
write_min = float(os.environ.get("MEMORY_WRITE_GATE_MIN", "0.98"))
latency_max = float(os.environ.get("MEMORY_LATENCY_P95_MAX", "250"))

failures = []
if scope < scope_min:
    failures.append(f"scope {scope:.4f} < {scope_min:.4f}")
if conflict_fp > conflict_max:
    failures.append(f"conflict_fp {conflict_fp:.4f} > {conflict_max:.4f}")
if write_acc < write_min:
    failures.append(f"write_gate_acc {write_acc:.4f} < {write_min:.4f}")
if latency_p95 > latency_max:
    failures.append(f"latency_p95 {latency_p95:.2f} > {latency_max:.2f}")

if failures:
    print("MEMORY_RELEASE_GATE=FAIL")
    for item in failures:
        print(f"- {item}")
    if live_signal_mode == "live":
        print(f"- live_smoke_signal_rc={live_signal_rc} (non-blocking)")
    sys.exit(1)

print("MEMORY_RELEASE_GATE=PASS")
print(
    f"scope={scope:.4f} conflict_fp={conflict_fp:.4f} "
    f"write_gate_acc={write_acc:.4f} latency_p95={latency_p95:.2f}"
)
if live_signal_mode == "live":
    print(f"live_smoke_signal_rc={live_signal_rc} (non-blocking)")
PY
