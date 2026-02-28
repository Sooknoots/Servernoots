#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ux-metrics-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_REPLIES_TOPIC="${NTFY_REPLIES_TOPIC:-ai-replies}"
NTFY_CHAT_TOPIC="${NTFY_CHAT_TOPIC:-ai-chat}"
NTFY_ALERT_TOPIC="${NTFY_ALERT_TOPIC:-ops-alerts}"
SINCE_WINDOW="${UX_METRICS_SINCE:-24h}"
NEG_RATE_WARN_THRESHOLD="${UX_NEG_RATE_WARN_THRESHOLD:-0.35}"
FETCH_TIMEOUT_SECONDS="${UX_METRICS_FETCH_TIMEOUT_SECONDS:-30}"
FETCH_TIMEOUT_WARN_ON_PARTIAL="${UX_METRICS_TIMEOUT_WARN_ON_PARTIAL:-false}"
CUE_WARN_THRESHOLD_CORRECTION="${UX_DAILY_CUE_WARN_CORRECTION:-0.25}"
CUE_WARN_THRESHOLD_ADDITIONAL_INFO="${UX_DAILY_CUE_WARN_ADDITIONAL_INFO:-0.25}"
CUE_WARN_THRESHOLD_RETRY="${UX_DAILY_CUE_WARN_RETRY:-0.20}"
CUE_WARN_THRESHOLD_FRUSTRATION="${UX_DAILY_CUE_WARN_FRUSTRATION:-0.10}"
UNCERTAINTY_COMPLIANCE_MIN="${UX_UNCERTAINTY_COMPLIANCE_MIN:-0.95}"
REPEAT_MISTAKE_WARN_THRESHOLD="${UX_REPEAT_MISTAKE_WARN_THRESHOLD:-0.08}"
REPLIES_URL="${NTFY_BASE%/}/${NTFY_REPLIES_TOPIC}/json?since=${SINCE_WINDOW}"
CHAT_URL="${NTFY_BASE%/}/${NTFY_CHAT_TOPIC}/json?since=${SINCE_WINDOW}"
ALERT_URL="${NTFY_BASE%/}/${NTFY_ALERT_TOPIC}"
RAG_WEBHOOK_STATUS=0
REPLIES_FETCH_MODE="ok"
CHAT_FETCH_MODE="ok"

TMP_RAW="$(mktemp)"
TMP_CHAT_RAW="$(mktemp)"
TMP_SUMMARY="$(mktemp)"
trap 'rm -f "$TMP_RAW" "$TMP_CHAT_RAW" "$TMP_SUMMARY"' EXIT

echo "[$(date -Is)] Ensuring rag-query webhook is healthy (auto-heal enabled)" | tee -a "$LOG_FILE"
set +e
./scripts/ensure-rag-webhook-ready.sh >>"$LOG_FILE" 2>&1
RAG_WEBHOOK_STATUS=$?
set -e

if [[ $RAG_WEBHOOK_STATUS -ne 0 ]]; then
  echo "[FAIL] rag-query webhook preflight failed" | tee -a "$LOG_FILE"
  TITLE="AI UX Metrics Preflight Failed"
  TITLE_ENCODED="$(python3 - <<'PY' "$TITLE"
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1]))
PY
)"
  MESSAGE="UX metrics preflight failed on $(hostname) at $(date -Is). rag_webhook=${RAG_WEBHOOK_STATUS} log=${LOG_FILE}"
  curl -fsS -X POST "${ALERT_URL}?title=${TITLE_ENCODED}" \
    -H "Content-Type: text/plain" \
    -d "$MESSAGE" >/dev/null 2>&1 || true
  exit 1
fi
echo "[$(date -Is)] rag-query webhook preflight passed" | tee -a "$LOG_FILE"

set +e
curl -fsS --max-time "$FETCH_TIMEOUT_SECONDS" "$REPLIES_URL" >"$TMP_RAW"
CURL_STATUS=$?
set -e

if [[ $CURL_STATUS -ne 0 ]]; then
  if [[ -s "$TMP_RAW" ]]; then
    REPLIES_FETCH_MODE="partial_error_${CURL_STATUS}"
    if [[ "$CURL_STATUS" -eq 28 ]]; then
      REPLIES_FETCH_MODE="partial_timeout"
      REPLIES_BYTES="$(wc -c <"$TMP_RAW" | tr -d ' ')"
      if [[ "$FETCH_TIMEOUT_WARN_ON_PARTIAL" == "true" ]]; then
        echo "[WARN] replies fetch timed out (status=28); using partial payload bytes=${REPLIES_BYTES} from ${REPLIES_URL}" | tee -a "$LOG_FILE"
      else
        echo "[INFO] replies fetch timed out (status=28); using partial payload bytes=${REPLIES_BYTES} from ${REPLIES_URL}" | tee -a "$LOG_FILE"
      fi
    else
      echo "[WARN] fetch exited status=$CURL_STATUS; using partial payload from ${REPLIES_URL}" | tee -a "$LOG_FILE"
    fi
  else
    echo "[FAIL] could not fetch replies stream from ${REPLIES_URL}" | tee -a "$LOG_FILE"
    exit 1
  fi
fi

set +e
curl -fsS --max-time "$FETCH_TIMEOUT_SECONDS" "$CHAT_URL" >"$TMP_CHAT_RAW"
CHAT_CURL_STATUS=$?
set -e

if [[ $CHAT_CURL_STATUS -ne 0 ]]; then
  if [[ -s "$TMP_CHAT_RAW" ]]; then
    CHAT_FETCH_MODE="partial_error_${CHAT_CURL_STATUS}"
    if [[ "$CHAT_CURL_STATUS" -eq 28 ]]; then
      CHAT_FETCH_MODE="partial_timeout"
      CHAT_BYTES="$(wc -c <"$TMP_CHAT_RAW" | tr -d ' ')"
      if [[ "$FETCH_TIMEOUT_WARN_ON_PARTIAL" == "true" ]]; then
        echo "[WARN] chat fetch timed out (status=28); using partial payload bytes=${CHAT_BYTES} from ${CHAT_URL}" | tee -a "$LOG_FILE"
      else
        echo "[INFO] chat fetch timed out (status=28); using partial payload bytes=${CHAT_BYTES} from ${CHAT_URL}" | tee -a "$LOG_FILE"
      fi
    else
      echo "[WARN] chat fetch exited status=$CHAT_CURL_STATUS; using partial payload from ${CHAT_URL}" | tee -a "$LOG_FILE"
    fi
  else
    CHAT_FETCH_MODE="empty_error_${CHAT_CURL_STATUS}"
    echo "[WARN] could not fetch chat stream from ${CHAT_URL}; cue metrics default to zero" | tee -a "$LOG_FILE"
  fi
fi

python3 - <<'PY' "$TMP_RAW" "$TMP_CHAT_RAW" "$TMP_SUMMARY" "$NEG_RATE_WARN_THRESHOLD" "$CUE_WARN_THRESHOLD_CORRECTION" "$CUE_WARN_THRESHOLD_ADDITIONAL_INFO" "$CUE_WARN_THRESHOLD_RETRY" "$CUE_WARN_THRESHOLD_FRUSTRATION" "$UNCERTAINTY_COMPLIANCE_MIN" "$REPEAT_MISTAKE_WARN_THRESHOLD"
import json
import re
import sys
from pathlib import Path

raw_path = Path(sys.argv[1])
chat_raw_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])
neg_threshold = float(sys.argv[4])
cue_warn_thresholds = {
  "correction": float(sys.argv[5]),
  "additional_info": float(sys.argv[6]),
  "retry": float(sys.argv[7]),
  "frustration": float(sys.argv[8]),
}
uncertainty_compliance_min = float(sys.argv[9])
repeat_mistake_warn_threshold = float(sys.argv[10])

label_counts = {"positive": 0, "neutral": 0, "negative": 0}
score_values = []
lines_seen = 0
ux_seen = 0

pattern = re.compile(r"ux:(positive|neutral|negative)\s+ux_score:([\-0-9.]+)", re.IGNORECASE)
low_confidence_pattern = re.compile(r"\bconf:low\b", re.IGNORECASE)
uncertainty_markers = (
    "based on available context",
    "may be missing details",
    "not enough information",
    "insufficient information",
    "i don't have enough information",
    "i do not have enough information",
    "strong rag matches were not found",
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

low_confidence_samples = 0
uncertainty_compliant_samples = 0

for raw_line in raw_path.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = raw_line.strip()
    if not line:
        continue
    lines_seen += 1
    try:
        obj = json.loads(line)
    except Exception:
        continue
    msg = str(obj.get("message", ""))

    lowered_msg = msg.lower()
    if low_confidence_pattern.search(msg):
      low_confidence_samples += 1
      if any(marker in lowered_msg for marker in uncertainty_markers):
        uncertainty_compliant_samples += 1

    m = pattern.search(msg)
    if not m:
        continue

    label = m.group(1).lower()
    score = float(m.group(2))
    ux_seen += 1
    label_counts[label] = label_counts.get(label, 0) + 1
    score_values.append(score)

cue_counts = {k: 0 for k in cue_patterns}
cue_samples = 0
repeat_mistake_count = 0
if chat_raw_path.exists() and chat_raw_path.stat().st_size > 0:
    for raw_line in chat_raw_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = str(obj.get("message", "")).strip()
        if not msg:
            continue
        cue_samples += 1
        if repeat_mistake_pattern.search(msg):
          repeat_mistake_count += 1
        for name, pat in cue_patterns.items():
            if pat.search(msg):
                cue_counts[name] += 1

cue_rates = {
    "correction": (cue_counts["correction"] / cue_samples) if cue_samples > 0 else 0.0,
    "additional_info": (cue_counts["additional_info"] / cue_samples) if cue_samples > 0 else 0.0,
    "retry": (cue_counts["retry"] / cue_samples) if cue_samples > 0 else 0.0,
    "frustration": (cue_counts["frustration"] / cue_samples) if cue_samples > 0 else 0.0,
}

uncertainty_compliance_rate = (
  (uncertainty_compliant_samples / low_confidence_samples)
  if low_confidence_samples > 0
  else 1.0
)
repeat_mistake_rate = (repeat_mistake_count / cue_samples) if cue_samples > 0 else 0.0

warn_reasons = []

if ux_seen == 0:
    out = {
        "status": "no-data",
        "lines_seen": lines_seen,
        "ux_seen": ux_seen,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "negative_rate": 0.0,
        "avg_score": 0.0,
        "cue_samples": cue_samples,
        "cue_correction": cue_counts["correction"],
        "cue_additional_info": cue_counts["additional_info"],
        "cue_retry": cue_counts["retry"],
        "cue_frustration": cue_counts["frustration"],
        "low_confidence_samples": low_confidence_samples,
        "uncertainty_compliant_samples": uncertainty_compliant_samples,
        "uncertainty_compliance_rate": uncertainty_compliance_rate,
        "repeat_mistake_count": repeat_mistake_count,
        "repeat_mistake_samples": cue_samples,
        "repeat_mistake_rate": repeat_mistake_rate,
        "warn_reasons": warn_reasons,
    }
else:
    avg = sum(score_values) / len(score_values)
    neg_rate = label_counts["negative"] / ux_seen
    if neg_rate >= neg_threshold:
        warn_reasons.append(f"negative_rate>={neg_threshold:.2f}")
    for cue_name, threshold in cue_warn_thresholds.items():
        if cue_samples > 0 and cue_rates.get(cue_name, 0.0) >= threshold:
            warn_reasons.append(f"{cue_name}_rate>={threshold:.2f}")
    if low_confidence_samples > 0 and uncertainty_compliance_rate < uncertainty_compliance_min:
      warn_reasons.append(f"uncertainty_compliance<{uncertainty_compliance_min:.2f}")
    if cue_samples > 0 and repeat_mistake_rate >= repeat_mistake_warn_threshold:
      warn_reasons.append(f"repeat_mistake_rate>={repeat_mistake_warn_threshold:.2f}")
    status = "warn" if warn_reasons else "ok"
    out = {
        "status": status,
        "lines_seen": lines_seen,
        "ux_seen": ux_seen,
        "positive": label_counts["positive"],
        "neutral": label_counts["neutral"],
        "negative": label_counts["negative"],
        "negative_rate": neg_rate,
        "avg_score": avg,
        "cue_samples": cue_samples,
        "cue_correction": cue_counts["correction"],
        "cue_additional_info": cue_counts["additional_info"],
        "cue_retry": cue_counts["retry"],
        "cue_frustration": cue_counts["frustration"],
        "low_confidence_samples": low_confidence_samples,
        "uncertainty_compliant_samples": uncertainty_compliant_samples,
        "uncertainty_compliance_rate": uncertainty_compliance_rate,
        "repeat_mistake_count": repeat_mistake_count,
        "repeat_mistake_samples": cue_samples,
        "repeat_mistake_rate": repeat_mistake_rate,
        "warn_reasons": warn_reasons,
    }

out_path.write_text(json.dumps(out), encoding="utf-8")
PY

STATUS="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['status'])
PY
)"
UX_SEEN="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['ux_seen'])
PY
)"
POSITIVE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['positive'])
PY
)"
NEUTRAL="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['neutral'])
PY
)"
NEGATIVE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['negative'])
PY
)"
NEG_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['negative_rate']
print(f"{v:.2%}")
PY
)"
AVG_SCORE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['avg_score']
print(f"{v:.2f}")
PY
)"
CUE_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['cue_samples'])
PY
)"
CUE_CORRECTION="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['cue_correction'])
PY
)"
CUE_ADDITIONAL_INFO="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['cue_additional_info'])
PY
)"
CUE_RETRY="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['cue_retry'])
PY
)"
CUE_FRUSTRATION="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['cue_frustration'])
PY
)"
LOW_CONFIDENCE_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['low_confidence_samples'])
PY
)"
UNCERTAINTY_COMPLIANT_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['uncertainty_compliant_samples'])
PY
)"
UNCERTAINTY_COMPLIANCE_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['uncertainty_compliance_rate']
print(f"{v:.2%}")
PY
)"
REPEAT_MISTAKE_COUNT="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['repeat_mistake_count'])
PY
)"
REPEAT_MISTAKE_SAMPLES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
print(json.loads(open(sys.argv[1], encoding='utf-8').read())['repeat_mistake_samples'])
PY
)"
REPEAT_MISTAKE_RATE="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
v=json.loads(open(sys.argv[1], encoding='utf-8').read())['repeat_mistake_rate']
print(f"{v:.2%}")
PY
)"
TOP_NEGATIVE_CUES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
data=json.loads(open(sys.argv[1], encoding='utf-8').read())
items=[
  ("correction", int(data.get("cue_correction", 0))),
  ("additional_info", int(data.get("cue_additional_info", 0))),
  ("retry", int(data.get("cue_retry", 0))),
  ("frustration", int(data.get("cue_frustration", 0))),
]
rows=[(k,v) for (k,v) in sorted(items, key=lambda kv: (-kv[1], kv[0])) if v > 0][:3]
print('none' if not rows else ', '.join(f"{k}:{v}" for (k,v) in rows))
PY
)"
CUE_RATES="$(python3 - <<'PY' "$TMP_SUMMARY"
import json,sys
data=json.loads(open(sys.argv[1], encoding='utf-8').read())
samples=max(0, int(data.get('cue_samples', 0)))
fields=[
  ('correction', int(data.get('cue_correction', 0))),
  ('additional_info', int(data.get('cue_additional_info', 0))),
  ('retry', int(data.get('cue_retry', 0))),
  ('frustration', int(data.get('cue_frustration', 0))),
]
if samples <= 0:
  print('correction=0.00% additional_info=0.00% retry=0.00% frustration=0.00%')
else:
  print(' '.join(f"{name}={(count/samples)*100:.2f}%" for name,count in fields))
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
TITLE_PREFIX="AI UX Metrics"
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
UX metrics summary on ${HOSTNAME_VALUE} at $(date -Is)
window=${SINCE_WINDOW} status=${STATUS}
rag_webhook=${RAG_WEBHOOK_STATUS}
fetch_mode_replies=${REPLIES_FETCH_MODE} fetch_mode_chat=${CHAT_FETCH_MODE} fetch_timeout_s=${FETCH_TIMEOUT_SECONDS}
ux_samples=${UX_SEEN} positive=${POSITIVE} neutral=${NEUTRAL} negative=${NEGATIVE}
negative_rate=${NEG_RATE} avg_ux_score=${AVG_SCORE}
negative_cues correction=${CUE_CORRECTION} additional_info=${CUE_ADDITIONAL_INFO} retry=${CUE_RETRY} frustration=${CUE_FRUSTRATION} cue_samples=${CUE_SAMPLES}
negative_cue_rates ${CUE_RATES}
uncertainty_compliance=${UNCERTAINTY_COMPLIANCE_RATE} low_conf_samples=${LOW_CONFIDENCE_SAMPLES} compliant=${UNCERTAINTY_COMPLIANT_SAMPLES} repeat_mistake_rate=${REPEAT_MISTAKE_RATE} repeat_mistake_count=${REPEAT_MISTAKE_COUNT} repeat_mistake_samples=${REPEAT_MISTAKE_SAMPLES}
top_negative_cues=${TOP_NEGATIVE_CUES}
warn_reasons=${WARN_REASONS}
warn_codes=${WARN_CODES}
log=${LOG_FILE}
EOF
)

echo "$MESSAGE" | tee -a "$LOG_FILE"

curl -fsS -X POST "${ALERT_URL}?title=${TITLE_ENCODED}" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit 0
