#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
OUT_LOG="$LOG_DIR/ux-metrics-weekly-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_ALERT_TOPIC="${NTFY_ALERT_TOPIC:-ops-alerts}"
NTFY_CHAT_TOPIC="${NTFY_CHAT_TOPIC:-ai-chat}"
ALERT_URL="${NTFY_BASE%/}/${NTFY_ALERT_TOPIC}"
RAG_WEBHOOK_STATUS=0
NEG_RATE_WARN_THRESHOLD="${UX_NEG_RATE_WARN_THRESHOLD:-0.35}"
ROLLUP_DAYS="${UX_WEEKLY_ROLLUP_DAYS:-7}"
CHAT_FETCH_TIMEOUT_SECONDS="${UX_WEEKLY_CHAT_FETCH_TIMEOUT_SECONDS:-30}"
FETCH_TIMEOUT_WARN_ON_PARTIAL="${UX_METRICS_TIMEOUT_WARN_ON_PARTIAL:-false}"
CUE_WARN_THRESHOLD_CORRECTION="${UX_WEEKLY_CUE_WARN_CORRECTION:-0.25}"
CUE_WARN_THRESHOLD_ADDITIONAL_INFO="${UX_WEEKLY_CUE_WARN_ADDITIONAL_INFO:-0.25}"
CUE_WARN_THRESHOLD_RETRY="${UX_WEEKLY_CUE_WARN_RETRY:-0.20}"
CUE_WARN_THRESHOLD_FRUSTRATION="${UX_WEEKLY_CUE_WARN_FRUSTRATION:-0.10}"
UNCERTAINTY_COMPLIANCE_MIN="${UX_UNCERTAINTY_COMPLIANCE_MIN:-0.95}"
REPEAT_MISTAKE_WARN_THRESHOLD="${UX_WEEKLY_REPEAT_MISTAKE_WARN_THRESHOLD:-${UX_REPEAT_MISTAKE_WARN_THRESHOLD:-0.08}}"
ROLLUP_HOURS="$((ROLLUP_DAYS * 24))"
CHAT_URL="${NTFY_BASE%/}/${NTFY_CHAT_TOPIC}/json?since=${ROLLUP_HOURS}h"
CHAT_FETCH_MODE="ok"

TMP_SUMMARY="$(mktemp)"
TMP_CHAT_RAW="$(mktemp)"
trap 'rm -f "$TMP_SUMMARY" "$TMP_CHAT_RAW"' EXIT

echo "[$(date -Is)] Ensuring rag-query webhook is healthy (auto-heal enabled)" | tee -a "$OUT_LOG"
set +e
./scripts/ensure-rag-webhook-ready.sh >>"$OUT_LOG" 2>&1
RAG_WEBHOOK_STATUS=$?
set -e

if [[ $RAG_WEBHOOK_STATUS -ne 0 ]]; then
    echo "[FAIL] rag-query webhook preflight failed" | tee -a "$OUT_LOG"
    TITLE="AI UX Weekly Rollup Preflight Failed"
    TITLE_ENCODED="$(python3 - <<'PY' "$TITLE"
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1]))
PY
)"
    MESSAGE="UX weekly rollup preflight failed on $(hostname) at $(date -Is). rag_webhook=${RAG_WEBHOOK_STATUS} log=${OUT_LOG}"
    curl -fsS -X POST "${ALERT_URL}?title=${TITLE_ENCODED}" \
        -H "Content-Type: text/plain" \
        -d "$MESSAGE" >/dev/null 2>&1 || true
    exit 1
fi
echo "[$(date -Is)] rag-query webhook preflight passed" | tee -a "$OUT_LOG"

set +e
curl -fsS --max-time "$CHAT_FETCH_TIMEOUT_SECONDS" "$CHAT_URL" >"$TMP_CHAT_RAW"
CHAT_CURL_STATUS=$?
set -e

if [[ $CHAT_CURL_STATUS -ne 0 ]]; then
    if [[ -s "$TMP_CHAT_RAW" ]]; then
        CHAT_FETCH_MODE="partial_error_${CHAT_CURL_STATUS}"
        if [[ "$CHAT_CURL_STATUS" -eq 28 ]]; then
            CHAT_FETCH_MODE="partial_timeout"
            CHAT_BYTES="$(wc -c <"$TMP_CHAT_RAW" | tr -d ' ')"
            if [[ "$FETCH_TIMEOUT_WARN_ON_PARTIAL" == "true" ]]; then
                echo "[WARN] chat fetch timed out (status=28); using partial payload bytes=${CHAT_BYTES} from ${CHAT_URL}" | tee -a "$OUT_LOG"
            else
                echo "[INFO] chat fetch timed out (status=28); using partial payload bytes=${CHAT_BYTES} from ${CHAT_URL}" | tee -a "$OUT_LOG"
            fi
        else
            echo "[WARN] chat fetch exited status=$CHAT_CURL_STATUS; using partial payload from ${CHAT_URL}" | tee -a "$OUT_LOG"
        fi
    else
        CHAT_FETCH_MODE="empty_error_${CHAT_CURL_STATUS}"
        echo "[WARN] could not fetch chat stream from ${CHAT_URL}; cue rollup will use no-data fallback" | tee -a "$OUT_LOG"
    fi
fi

python3 - <<'PY' "$LOG_DIR" "$ROLLUP_DAYS" "$NEG_RATE_WARN_THRESHOLD" "$TMP_SUMMARY" "$TMP_CHAT_RAW" "$CUE_WARN_THRESHOLD_CORRECTION" "$CUE_WARN_THRESHOLD_ADDITIONAL_INFO" "$CUE_WARN_THRESHOLD_RETRY" "$CUE_WARN_THRESHOLD_FRUSTRATION" "$UNCERTAINTY_COMPLIANCE_MIN" "$REPEAT_MISTAKE_WARN_THRESHOLD"
import datetime as dt
import json
import re
import sys
from pathlib import Path

log_dir = Path(sys.argv[1])
rollup_days = max(1, int(sys.argv[2]))
neg_warn_threshold = float(sys.argv[3])
out_path = Path(sys.argv[4])
chat_raw_path = Path(sys.argv[5])
cue_warn_thresholds = {
    "correction": float(sys.argv[6]),
    "additional_info": float(sys.argv[7]),
    "retry": float(sys.argv[8]),
    "frustration": float(sys.argv[9]),
}
uncertainty_compliance_min = float(sys.argv[10])
repeat_mistake_warn_threshold = float(sys.argv[11])

block_header = re.compile(r"^UX metrics summary on .* at (?P<ts>.+)$")
block_samples = re.compile(
    r"^ux_samples=(?P<samples>\d+) positive=(?P<positive>\d+) neutral=(?P<neutral>\d+) negative=(?P<negative>\d+)$"
)
block_scores = re.compile(r"^negative_rate=(?P<neg>[0-9.]+)% avg_ux_score=(?P<avg>-?[0-9.]+)$")
block_cues = re.compile(
    r"^negative_cues correction=(?P<correction>\d+) additional_info=(?P<additional_info>\d+) retry=(?P<retry>\d+) frustration=(?P<frustration>\d+) cue_samples=(?P<cue_samples>\d+)$"
)
block_kpi = re.compile(
    r"^uncertainty_compliance=(?P<uncertainty>[0-9.]+)%\s+low_conf_samples=(?P<low_conf>\d+)\s+compliant=(?P<compliant>\d+)\s+repeat_mistake_rate=(?P<repeat_rate>[0-9.]+)%\s+repeat_mistake_count=(?P<repeat_count>\d+)\s+repeat_mistake_samples=(?P<repeat_samples>\d+)$"
)

cue_patterns = {
    "correction": re.compile(r"\b(actually|not quite|that's wrong|that is wrong|incorrect|you missed|you forgot|i meant|to clarify|correction|not what i asked|wrong answer|that's not right)\b", re.IGNORECASE),
    "additional_info": re.compile(r"\b(additional info|more context|for context|here is context|use this|new detail|also note|another detail|clarification:|update:)\b", re.IGNORECASE),
    "retry": re.compile(r"\b(again|repeat|still wrong|you didn't|you did not|try again|one more time)\b", re.IGNORECASE),
    "frustration": re.compile(r"\b(wtf|broken|not working|this sucks|annoying|frustrating|ugh)\b", re.IGNORECASE),
}
repeat_mistake_pattern = re.compile(
    r"\b(still wrong|you didn't|you did not|not what i asked|again|try again|one more time|repeat)\b",
    re.IGNORECASE,
)


def parse_day_file(path: Path):
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    blocks = []
    idx = 0
    while idx < len(lines):
        m = block_header.match(lines[idx].strip())
        if not m:
            idx += 1
            continue
        block = {"ts": m.group("ts")}
        for j in range(idx + 1, min(idx + 8, len(lines))):
            line = lines[j].strip()
            sm = block_samples.match(line)
            if sm:
                block.update({
                    "ux_samples": int(sm.group("samples")),
                    "positive": int(sm.group("positive")),
                    "neutral": int(sm.group("neutral")),
                    "negative": int(sm.group("negative")),
                })
            sc = block_scores.match(line)
            if sc:
                block.update({
                    "negative_rate_pct": float(sc.group("neg")),
                    "avg_ux_score": float(sc.group("avg")),
                })
            cm = block_cues.match(line)
            if cm:
                block.update({
                    "cue_correction": int(cm.group("correction")),
                    "cue_additional_info": int(cm.group("additional_info")),
                    "cue_retry": int(cm.group("retry")),
                    "cue_frustration": int(cm.group("frustration")),
                    "cue_samples": int(cm.group("cue_samples")),
                })
            km = block_kpi.match(line)
            if km:
                block.update({
                    "uncertainty_compliance_pct": float(km.group("uncertainty")),
                    "low_confidence_samples": int(km.group("low_conf")),
                    "uncertainty_compliant_samples": int(km.group("compliant")),
                    "repeat_mistake_rate_pct": float(km.group("repeat_rate")),
                    "repeat_mistake_count": int(km.group("repeat_count")),
                    "repeat_mistake_samples": int(km.group("repeat_samples")),
                })
        if "ux_samples" in block and "avg_ux_score" in block:
            blocks.append(block)
        idx += 1
    return blocks[-1] if blocks else None


def parse_cues(path: Path):
    counts = {k: 0 for k in cue_patterns}
    samples = 0
    repeat_mistake_count = 0
    if not path.exists() or path.stat().st_size == 0:
        return counts, samples, repeat_mistake_count

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue

        message = str(obj.get("message", "")).strip()
        if not message:
            continue

        samples += 1
        if repeat_mistake_pattern.search(message):
            repeat_mistake_count += 1
        for name, pattern in cue_patterns.items():
            if pattern.search(message):
                counts[name] += 1

    return counts, samples, repeat_mistake_count


today = dt.date.today()
rows = []
for back in range(rollup_days - 1, -1, -1):
    day = today - dt.timedelta(days=back)
    file_path = log_dir / f"ux-metrics-{day.isoformat()}.log"
    parsed = parse_day_file(file_path)
    rows.append({"date": day.isoformat(), "file": str(file_path), "data": parsed})

valid = [r for r in rows if r["data"] and r["data"].get("ux_samples", 0) > 0]
cue_rows = [r["data"] for r in rows if r.get("data") and r["data"].get("cue_samples", 0) > 0]
if cue_rows:
    cue_counts = {
        "correction": sum(int(r.get("cue_correction", 0)) for r in cue_rows),
        "additional_info": sum(int(r.get("cue_additional_info", 0)) for r in cue_rows),
        "retry": sum(int(r.get("cue_retry", 0)) for r in cue_rows),
        "frustration": sum(int(r.get("cue_frustration", 0)) for r in cue_rows),
    }
    cue_samples = sum(int(r.get("cue_samples", 0)) for r in cue_rows)
    repeat_mistake_count = sum(int(r.get("repeat_mistake_count", 0)) for r in cue_rows)
    repeat_mistake_samples = sum(int(r.get("repeat_mistake_samples", r.get("cue_samples", 0))) for r in cue_rows)
else:
    cue_counts, cue_samples, repeat_mistake_count = parse_cues(chat_raw_path)
    repeat_mistake_samples = cue_samples

kpi_rows = [r["data"] for r in rows if r.get("data")]
low_confidence_samples = sum(int(r.get("low_confidence_samples", 0)) for r in kpi_rows)
uncertainty_compliant_samples = sum(int(r.get("uncertainty_compliant_samples", 0)) for r in kpi_rows)
uncertainty_compliance_rate = (
    (uncertainty_compliant_samples / low_confidence_samples)
    if low_confidence_samples > 0
    else 1.0
)
repeat_mistake_rate = (repeat_mistake_count / repeat_mistake_samples) if repeat_mistake_samples > 0 else 0.0

top_negative_cues = sorted(cue_counts.items(), key=lambda kv: (-kv[1], kv[0]))
top_negative_cues = [item for item in top_negative_cues if item[1] > 0][:3]
cue_rates = {
    name: (count / cue_samples if cue_samples > 0 else 0.0)
    for name, count in cue_counts.items()
}

if not valid:
    out = {
        "status": "no-data",
        "days_considered": rollup_days,
        "days_with_data": 0,
        "total_samples": 0,
        "total_positive": 0,
        "total_neutral": 0,
        "total_negative": 0,
        "aggregate_negative_rate": 0.0,
        "weighted_avg_ux_score": 0.0,
        "delta_avg_vs_prev_day": 0.0,
        "delta_neg_rate_vs_prev_day": 0.0,
        "warn_reasons": [],
        "cue_rates": cue_rates,
        "cue_warn_thresholds": cue_warn_thresholds,
        "cue_counts": cue_counts,
        "cue_samples": cue_samples,
        "low_confidence_samples": low_confidence_samples,
        "uncertainty_compliant_samples": uncertainty_compliant_samples,
        "uncertainty_compliance_rate": uncertainty_compliance_rate,
        "repeat_mistake_count": repeat_mistake_count,
        "repeat_mistake_samples": repeat_mistake_samples,
        "repeat_mistake_rate": repeat_mistake_rate,
        "top_negative_cues": top_negative_cues,
        "rows": rows,
    }
else:
    total_samples = sum(r["data"]["ux_samples"] for r in valid)
    total_positive = sum(r["data"]["positive"] for r in valid)
    total_neutral = sum(r["data"]["neutral"] for r in valid)
    total_negative = sum(r["data"]["negative"] for r in valid)

    weighted_avg = sum(r["data"]["avg_ux_score"] * r["data"]["ux_samples"] for r in valid) / max(1, total_samples)
    agg_neg_rate = total_negative / max(1, total_samples)

    latest = valid[-1]["data"]
    prev = valid[-2]["data"] if len(valid) > 1 else None
    delta_avg = 0.0
    delta_neg_rate = 0.0
    if prev:
        delta_avg = latest["avg_ux_score"] - prev["avg_ux_score"]
        delta_neg_rate = (latest["negative_rate_pct"] / 100.0) - (prev["negative_rate_pct"] / 100.0)

    warn_reasons = []
    if agg_neg_rate >= neg_warn_threshold:
        warn_reasons.append(f"negative_rate>={neg_warn_threshold:.2f}")
    for cue_name, threshold in cue_warn_thresholds.items():
        if cue_samples > 0 and cue_rates.get(cue_name, 0.0) >= threshold:
            warn_reasons.append(f"{cue_name}_rate>={threshold:.2f}")
    if low_confidence_samples > 0 and uncertainty_compliance_rate < uncertainty_compliance_min:
        warn_reasons.append(f"uncertainty_compliance<{uncertainty_compliance_min:.2f}")
    if repeat_mistake_samples > 0 and repeat_mistake_rate >= repeat_mistake_warn_threshold:
        warn_reasons.append(f"repeat_mistake_rate>={repeat_mistake_warn_threshold:.2f}")
    if delta_neg_rate >= 0.10:
        warn_reasons.append("delta_neg_rate>=0.10")
    if delta_avg <= -0.25:
        warn_reasons.append("delta_avg<=-0.25")

    warn = bool(warn_reasons)

    out = {
        "status": "warn" if warn else "ok",
        "days_considered": rollup_days,
        "days_with_data": len(valid),
        "total_samples": total_samples,
        "total_positive": total_positive,
        "total_neutral": total_neutral,
        "total_negative": total_negative,
        "aggregate_negative_rate": agg_neg_rate,
        "weighted_avg_ux_score": weighted_avg,
        "delta_avg_vs_prev_day": delta_avg,
        "delta_neg_rate_vs_prev_day": delta_neg_rate,
        "warn_reasons": warn_reasons,
        "cue_rates": cue_rates,
        "cue_warn_thresholds": cue_warn_thresholds,
        "cue_counts": cue_counts,
        "cue_samples": cue_samples,
        "low_confidence_samples": low_confidence_samples,
        "uncertainty_compliant_samples": uncertainty_compliant_samples,
        "uncertainty_compliance_rate": uncertainty_compliance_rate,
        "repeat_mistake_count": repeat_mistake_count,
        "repeat_mistake_samples": repeat_mistake_samples,
        "repeat_mistake_rate": repeat_mistake_rate,
        "top_negative_cues": top_negative_cues,
        "rows": rows,
    }

out_path.write_text(json.dumps(out), encoding="utf-8")
PY

STATUS="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['status'])
PY
)"
DAYS_WITH_DATA="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['days_with_data'])
PY
)"
TOTAL_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['total_samples'])
PY
)"
POSITIVE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['total_positive'])
PY
)"
NEUTRAL="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['total_neutral'])
PY
)"
NEGATIVE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['total_negative'])
PY
)"
AGG_NEG_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['aggregate_negative_rate']
print(f"{v:.2%}")
PY
)"
WEIGHTED_AVG="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['weighted_avg_ux_score']
print(f"{v:.2f}")
PY
)"
DELTA_AVG="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['delta_avg_vs_prev_day']
print(f"{v:+.2f}")
PY
)"
DELTA_NEG_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['delta_neg_rate_vs_prev_day']
print(f"{v:+.2%}")
PY
)"
TOP_NEGATIVE_CUES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
data=json.loads(open(sys.argv[1], encoding='utf-8').read())
rows=data.get('top_negative_cues') or []
if not rows:
    print('none')
else:
    print(', '.join(f"{name}:{count}" for name,count in rows))
PY
)"
CHAT_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read()).get('cue_samples', 0))
PY
)"
LOW_CONFIDENCE_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read()).get('low_confidence_samples', 0))
PY
)"
UNCERTAINTY_COMPLIANT_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read()).get('uncertainty_compliant_samples', 0))
PY
)"
UNCERTAINTY_COMPLIANCE_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read()).get('uncertainty_compliance_rate', 0.0)
print(f"{v:.2%}")
PY
)"
REPEAT_MISTAKE_COUNT="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read()).get('repeat_mistake_count', 0))
PY
)"
REPEAT_MISTAKE_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read()).get('repeat_mistake_samples', 0))
PY
)"
REPEAT_MISTAKE_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read()).get('repeat_mistake_rate', 0.0)
print(f"{v:.2%}")
PY
)"
WEEKLY_CUE_RATES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
data=json.loads(open(sys.argv[1], encoding='utf-8').read())
samples=max(0, int(data.get('cue_samples', 0)))
counts=data.get('cue_counts', {}) or {}
fields=[
    ('correction', int(counts.get('correction', 0))),
    ('additional_info', int(counts.get('additional_info', 0))),
    ('retry', int(counts.get('retry', 0))),
    ('frustration', int(counts.get('frustration', 0))),
]
if samples <= 0:
    print('correction=0.00% additional_info=0.00% retry=0.00% frustration=0.00%')
else:
    print(' '.join(f"{name}={(count/samples)*100:.2f}%" for name, count in fields))
PY
)"
WARN_REASONS="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
rows=json.loads(open(sys.argv[1], encoding='utf-8').read()).get('warn_reasons') or []
print('none' if not rows else ','.join(rows))
PY
)"
WARN_CODES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
rows=json.loads(open(sys.argv[1], encoding='utf-8').read()).get('warn_reasons') or []
codes=[]
for reason in rows:
    if reason.startswith('negative_rate>='):
        codes.append('NEG_RATE')
    elif reason.startswith('correction_rate>='):
        codes.append('CUE_CORRECTION')
    elif reason.startswith('additional_info_rate>='):
        codes.append('CUE_ADDITIONAL_INFO')
    elif reason.startswith('retry_rate>='):
        codes.append('CUE_RETRY')
    elif reason.startswith('frustration_rate>='):
        codes.append('CUE_FRUSTRATION')
    elif reason.startswith('delta_neg_rate>='):
        codes.append('DELTA_NEG_RATE')
    elif reason.startswith('delta_avg<='):
        codes.append('DELTA_AVG')
    elif reason.startswith('uncertainty_compliance<'):
        codes.append('UNCERTAINTY_COMPLIANCE')
    elif reason.startswith('repeat_mistake_rate>='):
        codes.append('REPEAT_MISTAKE')
print('none' if not codes else ','.join(codes))
PY
)"

HOSTNAME_VALUE="$(hostname)"
TITLE_PREFIX="AI UX Weekly Rollup"
if [[ "$STATUS" == "warn" ]]; then
  TITLE="${TITLE_PREFIX} Warning"
elif [[ "$STATUS" == "no-data" ]]; then
  TITLE="${TITLE_PREFIX} No Data"
else
  TITLE="${TITLE_PREFIX} OK"
fi

TITLE_ENCODED="$(python3 - <<'PY' "$TITLE"
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1]))
PY
)"

MESSAGE=$(cat <<EOF
Weekly UX rollup on ${HOSTNAME_VALUE} at $(date -Is)
status=${STATUS} window_days=${ROLLUP_DAYS} days_with_data=${DAYS_WITH_DATA}
rag_webhook=${RAG_WEBHOOK_STATUS}
fetch_mode_chat=${CHAT_FETCH_MODE} fetch_timeout_s=${CHAT_FETCH_TIMEOUT_SECONDS}
samples=${TOTAL_SAMPLES} positive=${POSITIVE} neutral=${NEUTRAL} negative=${NEGATIVE}
aggregate_negative_rate=${AGG_NEG_RATE} weighted_avg_ux_score=${WEIGHTED_AVG}
delta_avg_vs_prev_day=${DELTA_AVG} delta_neg_rate_vs_prev_day=${DELTA_NEG_RATE}
top_negative_cues=${TOP_NEGATIVE_CUES} cue_samples=${CHAT_SAMPLES}
weekly_negative_cue_rates ${WEEKLY_CUE_RATES}
uncertainty_compliance=${UNCERTAINTY_COMPLIANCE_RATE} low_conf_samples=${LOW_CONFIDENCE_SAMPLES} compliant=${UNCERTAINTY_COMPLIANT_SAMPLES} repeat_mistake_rate=${REPEAT_MISTAKE_RATE} repeat_mistake_count=${REPEAT_MISTAKE_COUNT} repeat_mistake_samples=${REPEAT_MISTAKE_SAMPLES}
warn_reasons=${WARN_REASONS}
warn_codes=${WARN_CODES}
log=${OUT_LOG}
EOF
)

echo "$MESSAGE" | tee -a "$OUT_LOG"

curl -fsS -X POST "${ALERT_URL}?title=${TITLE_ENCODED}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit 0
