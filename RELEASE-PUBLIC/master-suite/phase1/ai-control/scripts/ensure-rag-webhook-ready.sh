#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

N8N_BASE="${N8N_BASE:-http://127.0.0.1:5678}"
RAG_WEBHOOK_PATH="${N8N_RAG_WEBHOOK_PATH:-/webhook/rag-query}"
VERIFY_TIMEOUT_SECONDS="${N8N_RAG_VERIFY_TIMEOUT_SECONDS:-25}"
AUTO_HEAL_ENABLED="${N8N_RAG_AUTO_HEAL_ENABLED:-true}"
MAX_HEAL_ATTEMPTS="${N8N_RAG_AUTO_HEAL_MAX_ATTEMPTS:-2}"
HEAL_SLEEP_SECONDS="${N8N_RAG_AUTO_HEAL_SLEEP_SECONDS:-3}"
NTFY_BASE="${NTFY_BASE:-http://localhost:8091}"
NTFY_TOPIC="${N8N_RAG_HEAL_ALERT_TOPIC:-ops-alerts}"
NTFY_URL="${NTFY_BASE%/}/${NTFY_TOPIC}"

verify_rag_webhook() {
  local body http_code
  body="$(mktemp)"

  http_code="$(curl -sS --max-time "$VERIFY_TIMEOUT_SECONDS" -o "$body" -w "%{http_code}" \
    -H 'Content-Type: application/json' \
    -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"user","tenant_id":"u_9001","full_name":"Smoke User","telegram_username":"smokeuser","message":"healthcheck ping"}' \
    "${N8N_BASE%/}${RAG_WEBHOOK_PATH}" || true)"

  if [[ "$http_code" != "200" ]]; then
    rm -f "$body"
    return 1
  fi

  if ! grep -q '"reply"' "$body"; then
    rm -f "$body"
    return 1
  fi

  if grep -qiE 'not registered|active version not found|error in workflow' "$body"; then
    rm -f "$body"
    return 1
  fi

  rm -f "$body"
  return 0
}

alert_failure() {
  local message="$1"
  curl -fsS -X POST "$NTFY_URL" \
    -H "Title: RAG Webhook Auto-Heal Failed" \
    -H "Priority: high" \
    -H "Tags: rotating_light,warning" \
    -d "$message" >/dev/null 2>&1 || true
}

if verify_rag_webhook; then
  echo "[OK] rag-query webhook is healthy"
  exit 0
fi

echo "[WARN] rag-query webhook check failed"

if [[ "$AUTO_HEAL_ENABLED" != "true" ]]; then
  echo "[FAIL] auto-heal disabled and webhook is unhealthy"
  exit 1
fi

attempt=1
while [[ "$attempt" -le "$MAX_HEAL_ATTEMPTS" ]]; do
  echo "[INFO] Auto-heal attempt ${attempt}/${MAX_HEAL_ATTEMPTS}: publish + restart + verify"
  if ./scripts/publish-rag-query-workflow.sh --verify >/tmp/rag_webhook_autofix.log 2>&1; then
    if verify_rag_webhook; then
      echo "[OK] rag-query webhook recovered"
      exit 0
    fi
  fi

  if [[ "$attempt" -lt "$MAX_HEAL_ATTEMPTS" ]]; then
    sleep "$HEAL_SLEEP_SECONDS"
  fi
  attempt=$((attempt + 1))
done

TAIL_LOG="$(tail -n 80 /tmp/rag_webhook_autofix.log 2>/dev/null || true)"
MESSAGE="rag-query webhook auto-heal failed on $(hostname) at $(date -Is).\n\nTail log:\n${TAIL_LOG}"
alert_failure "$MESSAGE"

echo "[FAIL] rag-query webhook auto-heal failed"
exit 1
