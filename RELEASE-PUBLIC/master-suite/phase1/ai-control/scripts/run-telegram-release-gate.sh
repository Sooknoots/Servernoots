#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/telegram-release-gate-$(date +%F).log"

INCLUDE_LIVE="${TELEGRAM_RELEASE_GATE_INCLUDE_LIVE:-false}"

CHECKS=(
  textbook_pick_alias_local
  textbook_untrusted_source_local
  textbook_delivery_ack_retry_local
  notify_health_local
  notify_delivery_retry_local
  notify_quarantine_media_bypass_once_local
  notify_quarantine_media_bypass_status_local
  memory_regression_local
  memory_tier_decay_order_local
  memory_intent_scope_local
)

{
  echo "[$(date -Is)] Telegram release gate started"
  echo "[$(date -Is)] Compiling Python modules"
  /usr/bin/python3 -m py_compile \
    ./bridge/telegram_to_n8n.py \
    ./bridge/ntfy_to_n8n.py \
    ./scripts/eval-telegram-chat-smoke.py

  ARGS=(--mode local)
  for check in "${CHECKS[@]}"; do
    ARGS+=(--check "$check")
  done

  echo "[$(date -Is)] Running local smoke checks (${#CHECKS[@]} checks)"
  /usr/bin/python3 ./scripts/eval-telegram-chat-smoke.py "${ARGS[@]}"

  if [[ "$INCLUDE_LIVE" == "true" ]]; then
    echo "[$(date -Is)] Running live textbook fulfillment contract check"
    /usr/bin/python3 ./scripts/eval-telegram-chat-smoke.py --mode live --check textbook_fulfillment_contract
  else
    echo "[$(date -Is)] Live checks skipped (set TELEGRAM_RELEASE_GATE_INCLUDE_LIVE=true to include)"
  fi

  echo "[$(date -Is)] Telegram release gate passed"
} | tee "$LOG_FILE"
