#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
OUT_LOG="$LOG_DIR/telegram-safe-deploy-weekly-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${NTFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"
ROLLUP_DAYS="${TELEGRAM_SAFE_DEPLOY_WEEKLY_DAYS:-7}"

TMP_SUMMARY="$(mktemp)"
trap 'rm -f "$TMP_SUMMARY"' EXIT

python3 - <<'PY' "$LOG_DIR" "$ROLLUP_DAYS" "$TMP_SUMMARY"
import datetime as dt
import json
import pathlib
import re
import sys

log_dir = pathlib.Path(sys.argv[1])
days = max(1, int(sys.argv[2]))
out_path = pathlib.Path(sys.argv[3])

today = dt.date.today()
rows = []
started_re = re.compile(r"Telegram scheduled safe run started \(mode=(?P<mode>[^)]+)\)")
finished_re = re.compile(r"Telegram scheduled safe run finished \(status=(?P<status>\d+)\)")

for back in range(days - 1, -1, -1):
    d = today - dt.timedelta(days=back)
    path = log_dir / f"telegram-safe-deploy-{d.isoformat()}.log"
    entry = {
        "date": d.isoformat(),
        "exists": path.exists(),
        "path": str(path),
        "mode": "unknown",
        "status": "missing",
    }
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        mode = "unknown"
        status = "unknown"
        for line in lines:
            m = started_re.search(line)
            if m:
                mode = m.group("mode").strip()
            f = finished_re.search(line)
            if f:
                status = "pass" if f.group("status") == "0" else "fail"
        entry["mode"] = mode
        entry["status"] = status
    rows.append(entry)

existing = [r for r in rows if r["exists"]]
passes = sum(1 for r in existing if r["status"] == "pass")
fails = sum(1 for r in existing if r["status"] == "fail")
missing = sum(1 for r in rows if not r["exists"])

mode_counts = {}
for r in existing:
    mode_counts[r["mode"]] = mode_counts.get(r["mode"], 0) + 1

overall = "ok"
reasons = []
if fails > 0:
    overall = "warn"
    reasons.append("failed_runs")
if missing > 0:
    overall = "warn"
    reasons.append("missing_logs")
if not existing:
    overall = "warn"
    reasons.append("no_runs")

summary = {
    "window_days": days,
    "days_with_logs": len(existing),
    "passes": passes,
    "fails": fails,
    "missing_logs": missing,
    "mode_counts": mode_counts,
    "overall": overall,
    "reasons": reasons,
    "rows": rows,
}
out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
PY

SUMMARY_JSON="$(cat "$TMP_SUMMARY")"
STATUS="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
obj=json.loads(open(sys.argv[1],encoding='utf-8').read())
print(obj.get('overall','warn'))
PY
)"

TITLE="Telegram Safe Deploy Weekly Rollup"
if [[ "$STATUS" != "ok" ]]; then
  TITLE="Telegram Safe Deploy Weekly Rollup WARN"
fi

MESSAGE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
obj=json.loads(open(sys.argv[1],encoding='utf-8').read())
rows=obj.get('rows',[])
recent='\n'.join([f"- {r['date']}: status={r['status']} mode={r['mode']}" for r in rows[-7:]])
print(
  f"window_days={obj.get('window_days')}\n"
  f"days_with_logs={obj.get('days_with_logs')}\n"
  f"passes={obj.get('passes')} fails={obj.get('fails')} missing_logs={obj.get('missing_logs')}\n"
  f"mode_counts={obj.get('mode_counts')}\n"
  f"overall={obj.get('overall')} reasons={obj.get('reasons')}\n\n"
  f"Recent days:\n{recent}"
)
PY
)"

{
  echo "[$(date -Is)] Telegram safe deploy weekly rollup"
  echo "$SUMMARY_JSON"
} >>"$OUT_LOG"

TITLE_ENC="$(python3 - <<'PY' "$TITLE"
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1]))
PY
)"

curl -fsS -X POST "${NTFY_URL}?title=${TITLE_ENC}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

echo "[OK] Weekly rollup sent. Log: $OUT_LOG"
