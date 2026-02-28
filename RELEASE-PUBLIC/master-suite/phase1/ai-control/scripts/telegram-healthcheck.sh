#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ok() { echo "[OK] $*"; }
warn() { echo "[WARN] $*"; }
fail() { echo "[FAIL] $*"; exit 1; }

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is not installed or not in PATH"
fi

if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose is not available"
fi

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  fail "TELEGRAM_BOT_TOKEN is missing. Set it in ai-control/.env"
fi
ok "TELEGRAM_BOT_TOKEN is set"

if [[ -z "${TELEGRAM_ALLOWED_USER_IDS:-}" ]]; then
  warn "TELEGRAM_ALLOWED_USER_IDS is empty (bridge will be open to any Telegram user who can message the bot)"
else
  ok "TELEGRAM_ALLOWED_USER_IDS is set"
fi

if ! docker compose ps --status running telegram-n8n-bridge | grep -q telegram-n8n-bridge; then
  fail "telegram-n8n-bridge is not running. Start with: docker compose up -d telegram-n8n-bridge"
fi
ok "telegram-n8n-bridge is running"

if ! docker compose ps --status running n8n | grep -q n8n; then
  fail "n8n is not running"
fi
ok "n8n is running"

HTTP_CODE="$(curl -s -o /tmp/telegram-webhook-health.json -w "%{http_code}" \
  -X POST "http://127.0.0.1:5678/webhook/rag-query" \
  -H "Content-Type: application/json" \
  -d '{"source":"telegram","chat_id":999999,"user_id":999999,"message":"healthcheck ping"}')"

if [[ "$HTTP_CODE" != "200" ]]; then
  fail "rag-query webhook returned HTTP $HTTP_CODE"
fi
ok "rag-query webhook returned HTTP 200"

if grep -q '"reply"' /tmp/telegram-webhook-health.json; then
  ok "Webhook returned direct JSON reply for Telegram source"
else
  warn "Webhook response does not include reply field; check workflow last node/branching"
  echo "Response body:"
  cat /tmp/telegram-webhook-health.json
  exit 1
fi

echo
echo "Telegram bridge healthcheck passed."
