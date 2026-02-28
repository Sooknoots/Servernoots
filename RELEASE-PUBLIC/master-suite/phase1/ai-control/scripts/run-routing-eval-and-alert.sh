#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/routing-eval-$(date +%F).log"

NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${NTFY_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"
RAG_WEBHOOK_STATUS=0

DRY_FAIL_MODE=""
if [[ "${1:-}" == "--dry-fail" ]]; then
  DRY_FAIL_MODE="${2:-}"
  if [[ -z "$DRY_FAIL_MODE" ]]; then
    echo "Usage: $0 [--dry-fail contains|route|contract|http|error]"
    exit 2
  fi
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $0 [--dry-fail contains|route|contract|http|error]"
  exit 0
fi

if [[ -n "$DRY_FAIL_MODE" ]]; then
  case "$DRY_FAIL_MODE" in
    contains)
      cat >"$LOG_FILE" <<'EOF'
Running synthetic dry-fail routing check
[FAIL] dry_fail_contains: route=default-web-first expected=default-web-first contains=['synthetic-token'] reason=contains
Result: 1 failing case(s)
EOF
      ;;
    route)
      cat >"$LOG_FILE" <<'EOF'
Running synthetic dry-fail routing check
[FAIL] dry_fail_route: route=smalltalk:status expected=default-web-first reason=route
Result: 1 failing case(s)
EOF
      ;;
    contract)
      cat >"$LOG_FILE" <<'EOF'
Running synthetic dry-fail routing check
[FAIL] dry_fail_contract: route=default-web-first expected=default-web-first contract={pc:<missing>, tone_target:<missing>, brevity:<missing>, safety:<missing>} reason=contract
Result: 1 failing case(s)
EOF
      ;;
    http)
      cat >"$LOG_FILE" <<'EOF'
Running synthetic dry-fail routing check
[FAIL] dry_fail_http: HTTP 503 reason=http
Result: 1 failing case(s)
EOF
      ;;
    error)
      cat >"$LOG_FILE" <<'EOF'
Running synthetic dry-fail routing check
[FAIL] dry_fail_error: simulated exception reason=error
Result: 1 failing case(s)
EOF
      ;;
    *)
      echo "Invalid --dry-fail mode: $DRY_FAIL_MODE"
      echo "Usage: $0 [--dry-fail contains|route|contract|http|error]"
      exit 2
      ;;
  esac
  STATUS=1
else
  set +e
  {
    echo "[$(date -Is)] Ensuring rag-query webhook is healthy (auto-heal enabled)"
    ./scripts/ensure-rag-webhook-ready.sh
    RAG_WEBHOOK_STATUS=$?
  } >>"$LOG_FILE" 2>&1
  set -e

  if [[ $RAG_WEBHOOK_STATUS -ne 0 ]]; then
    STATUS=1
  else
  set +e
  echo "[$(date -Is)] Running routing eval" >>"$LOG_FILE"
  ./scripts/eval-routing.py --require-contract >>"$LOG_FILE" 2>&1
  STATUS=$?
  set -e
  fi
fi

if [[ $STATUS -eq 0 ]]; then
  echo "[OK] Routing eval passed ($(date -Is))" >>"$LOG_FILE"
  exit 0
fi

HOSTNAME_VALUE="$(hostname)"
TITLE="AI Routing Eval Failed"
FAIL_LINES="$(grep '^\[FAIL\]' "$LOG_FILE" || true)"

ROUTE_FAIL_COUNT=0
CONTAINS_FAIL_COUNT=0
CONTRACT_FAIL_COUNT=0
HTTP_FAIL_COUNT=0
ERROR_FAIL_COUNT=0

if [[ -n "$FAIL_LINES" ]]; then
  ROUTE_FAIL_COUNT="$(grep -c 'reason=.*route' <<<"$FAIL_LINES" || true)"
  CONTAINS_FAIL_COUNT="$(grep -c 'reason=.*contains' <<<"$FAIL_LINES" || true)"
  CONTRACT_FAIL_COUNT="$(grep -c 'reason=.*contract' <<<"$FAIL_LINES" || true)"
  HTTP_FAIL_COUNT="$(grep -c 'reason=http' <<<"$FAIL_LINES" || true)"
  ERROR_FAIL_COUNT="$(grep -c 'reason=error' <<<"$FAIL_LINES" || true)"
fi

FAIL_PREVIEW="$(printf '%s\n' "$FAIL_LINES" | head -n 6)"

MESSAGE=$(cat <<EOF
Routing eval failed on ${HOSTNAME_VALUE} at $(date -Is).
Summary: route_mismatch=${ROUTE_FAIL_COUNT}, content_missing=${CONTAINS_FAIL_COUNT}, contract_missing_or_invalid=${CONTRACT_FAIL_COUNT}, http=${HTTP_FAIL_COUNT}, other=${ERROR_FAIL_COUNT}
rag_webhook=${RAG_WEBHOOK_STATUS}
Log: ${LOG_FILE}

Failed cases:
${FAIL_PREVIEW}
EOF
)

curl -fsS -X POST "${NTFY_URL}?title=$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote('AI Routing Eval Failed'))
PY
)" \
  -H "Content-Type: text/plain" \
  -d "$MESSAGE" >/dev/null 2>&1 || true

exit $STATUS
