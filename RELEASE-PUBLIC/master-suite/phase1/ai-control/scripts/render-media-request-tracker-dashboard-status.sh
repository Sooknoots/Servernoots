#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

if [[ -f .env.secrets ]]; then
  set -a
  source .env.secrets
  set +a
fi

OUT_FILE="${REQTRACK_DASHBOARD_STATUS_FILE:-logs/media-request-tracker-dashboard-status.json}"
STALE_MINUTES="${REQTRACK_STALE_MINUTES:-60}"
TAKE="${REQTRACK_TAKE:-120}"
KPI_WINDOW_HOURS="${REQTRACK_KPI_WINDOW_HOURS:-24}"

mkdir -p "$(dirname "$OUT_FILE")"

TMP_LIVE="$(mktemp)"
TMP_KPI="$(mktemp)"
cleanup() {
  rm -f "$TMP_LIVE" "$TMP_KPI"
}
trap cleanup EXIT

live_ok=false
kpi_ok=false

if ./scripts/reqtrack --json --stale-minutes "$STALE_MINUTES" --take "$TAKE" >"$TMP_LIVE" 2>/dev/null; then
  live_ok=true
else
  printf '{"error":"live_probe_failed"}' >"$TMP_LIVE"
fi

if ./scripts/reqtrack --json --kpi-report --kpi-window-hours "$KPI_WINDOW_HOURS" >"$TMP_KPI" 2>/dev/null; then
  kpi_ok=true
else
  printf '{"error":"kpi_probe_failed"}' >"$TMP_KPI"
fi

python3 - "$TMP_LIVE" "$TMP_KPI" "$OUT_FILE" "$live_ok" "$kpi_ok" <<'PY'
import json
import sys
from datetime import datetime, timezone

live_path, kpi_path, out_path, live_ok_raw, kpi_ok_raw = sys.argv[1:]
live_ok = str(live_ok_raw).lower() == "true"
kpi_ok = str(kpi_ok_raw).lower() == "true"

def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}

live = load_json(live_path)
kpi_root = load_json(kpi_path)
kpi = kpi_root.get("kpi") if isinstance(kpi_root.get("kpi"), dict) else {}
totals = kpi.get("totals") if isinstance(kpi.get("totals"), dict) else {}
window = kpi.get("window") if isinstance(kpi.get("window"), dict) else {}

status = "ok"
if not live_ok and not kpi_ok:
    status = "error"
elif not live_ok or not kpi_ok:
    status = "warn"
elif int(live.get("stale_count") or 0) > 0:
    status = "warn"

summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "sources": {
        "live_probe_ok": live_ok,
        "kpi_probe_ok": kpi_ok,
        "state_file": str(live.get("state_file") or kpi_root.get("state_file") or ""),
    },
    "live": {
        "stale_count": int(live.get("stale_count") or 0),
        "notify_candidate_count": int(live.get("notify_candidate_count") or 0),
        "admin_escalations": int(live.get("admin_escalations") or 0),
        "user_prompts": int(live.get("user_prompts") or 0),
        "fix_attempted": int(((live.get("fix_summary") or {}).get("attempted") or 0)),
        "fix_applied": int(((live.get("fix_summary") or {}).get("applied") or 0)),
    },
    "kpi": {
        "window_hours": int(kpi.get("window_hours") or kpi_root.get("kpi_window_hours") or 24),
        "active": int(totals.get("active") or 0),
        "resolved": int(totals.get("resolved") or 0),
        "opened_window": int(window.get("opened") or 0),
        "resolved_window": int(window.get("resolved") or 0),
        "notified_window": int(window.get("notified") or 0),
    },
}

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2)
    handle.write("\n")

print(json.dumps({"status": status, "out_file": out_path}, ensure_ascii=False))
PY
