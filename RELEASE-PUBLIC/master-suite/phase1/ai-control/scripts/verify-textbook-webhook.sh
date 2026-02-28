#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WEBHOOK_URL="${TEXTBOOK_WEBHOOK_URL:-http://127.0.0.1:5678/webhook/textbook-fulfillment}"
TIMEOUT_SECONDS="${TEXTBOOK_WEBHOOK_VERIFY_TIMEOUT_SECONDS:-20}"

PAYLOAD='{"textbook_request":"healthcheck textbook details","delivery_email":"student@example.edu","lawful_sources_only":true,"user_id":"1"}'
if [[ "${1:-}" == "--payload" && -n "${2:-}" ]]; then
  PAYLOAD="$2"
fi

echo "[INFO] Verifying textbook webhook: $WEBHOOK_URL"
RESP="$(curl -sS --max-time "$TIMEOUT_SECONDS" -H 'Content-Type: application/json' -d "$PAYLOAD" "$WEBHOOK_URL" || true)"

if [[ -z "$RESP" ]]; then
  echo "[FAIL] Empty response from webhook"
  exit 1
fi

if echo "$RESP" | grep -q 'requested webhook "POST textbook-fulfillment" is not registered'; then
  echo "[FAIL] Webhook is not registered"
  echo "$RESP"
  exit 1
fi

if echo "$RESP" | grep -q 'Textbook fulfillment queued for'; then
  echo "[OK] Webhook reachable and workflow active"
  exit 0
fi

if echo "$RESP" | grep -q 'Please provide textbook details first and re-confirm'; then
  echo "[OK] Webhook reachable and workflow active (validation path)"
  exit 0
fi

if echo "$RESP" | grep -q 'Please set a valid delivery email and confirm again'; then
  echo "[OK] Webhook reachable and workflow active (email validation path)"
  exit 0
fi

echo "[WARN] Webhook responded with unexpected message"
echo "$RESP"
exit 0
