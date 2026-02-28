#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ROTATION_ENV_FILE:-.env}"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/secret-rotation-drill-$(date +%F).log"
STAMP="$(date +%Y%m%d%H%M%S)"
BACKUP_FILE="${ENV_FILE}.bak.${STAMP}"

MODE="rehearsal"
if [[ "${1:-}" == "--apply" ]]; then
  MODE="apply"
fi

log() {
  echo "[$(date -Is)] $*" | tee -a "$LOG_FILE"
}

fail() {
  log "[FAIL] $*"
  exit 1
}

if [[ ! -f "$ENV_FILE" ]]; then
  fail "Missing $ENV_FILE"
fi

cp "$ENV_FILE" "$BACKUP_FILE"
log "Created backup: $BACKUP_FILE"

update_env_value() {
  local key="$1"
  local value="$2"
  python3 - <<'PY' "$ENV_FILE" "$key" "$value"
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
prefix = f"{key}="
lines = path.read_text(encoding="utf-8").splitlines()
out = []
found = False
for line in lines:
    if line.startswith(prefix):
        out.append(f"{key}={value}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"updated {key}")
PY
}

if [[ "$MODE" == "apply" ]]; then
  NEW_TELEGRAM_BOT_TOKEN="${NEW_TELEGRAM_BOT_TOKEN:-}"
  NEW_OVERSEERR_API_KEY="${NEW_OVERSEERR_API_KEY:-}"

  if [[ -z "$NEW_TELEGRAM_BOT_TOKEN" || -z "$NEW_OVERSEERR_API_KEY" ]]; then
    fail "--apply requires NEW_TELEGRAM_BOT_TOKEN and NEW_OVERSEERR_API_KEY environment variables"
  fi

  log "Applying rotated secrets into $ENV_FILE"
  update_env_value "TELEGRAM_BOT_TOKEN" "$NEW_TELEGRAM_BOT_TOKEN" >/dev/null
  update_env_value "OVERSEERR_API_KEY" "$NEW_OVERSEERR_API_KEY" >/dev/null
else
  log "Rehearsal mode: no secret values changed"
fi

log "Restarting bridge services"
docker compose up -d --force-recreate telegram-n8n-bridge ntfy-n8n-bridge >/dev/null
sleep 3

log "Running telegram healthcheck"
./scripts/telegram-healthcheck.sh | tee -a "$LOG_FILE"

log "Running media synthetic check with .env loaded"
set -a
source "$ENV_FILE"
set +a
./scripts/run-media-synthetic-check-and-alert.sh | tee -a "$LOG_FILE"

ROLLBACK_CMD="cp '$BACKUP_FILE' '$ENV_FILE' && docker compose up -d telegram-n8n-bridge ntfy-n8n-bridge"
log "Rollback command: $ROLLBACK_CMD"

if [[ "$MODE" == "apply" ]]; then
  log "Rotation drill (apply mode) completed successfully"
else
  log "Rotation drill rehearsal completed successfully"
fi

exit 0
