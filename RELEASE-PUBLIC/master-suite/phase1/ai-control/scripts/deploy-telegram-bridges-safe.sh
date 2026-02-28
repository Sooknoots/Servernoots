#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/telegram-bridges-safe-deploy-$(date +%F).log"

INCLUDE_LIVE="${TELEGRAM_RELEASE_GATE_INCLUDE_LIVE:-false}"
FORCE_RECREATE="${TELEGRAM_DEPLOY_FORCE_RECREATE:-false}"

{
  echo "[$(date -Is)] Starting Telegram bridge safe deploy"
  echo "[$(date -Is)] Running release gate (include_live=${INCLUDE_LIVE})"

  TELEGRAM_RELEASE_GATE_INCLUDE_LIVE="$INCLUDE_LIVE" ./scripts/run-telegram-release-gate.sh

  if [[ "$FORCE_RECREATE" == "true" ]]; then
    echo "[$(date -Is)] Deploying with force-recreate"
    docker compose up -d --force-recreate ntfy-n8n-bridge telegram-n8n-bridge
  else
    echo "[$(date -Is)] Deploying without force-recreate"
    docker compose up -d ntfy-n8n-bridge telegram-n8n-bridge
  fi

  echo "[$(date -Is)] Service status"
  docker compose ps ntfy-n8n-bridge telegram-n8n-bridge

  echo "[$(date -Is)] Telegram bridge recent logs"
  docker logs --since 20s telegram-n8n-bridge 2>&1 | tail -n 40 || true

  echo "[$(date -Is)] ntfy bridge recent logs"
  docker logs --since 20s ntfy-n8n-bridge 2>&1 | tail -n 40 || true

  echo "[$(date -Is)] Telegram bridge safe deploy passed"
} | tee "$LOG_FILE"
