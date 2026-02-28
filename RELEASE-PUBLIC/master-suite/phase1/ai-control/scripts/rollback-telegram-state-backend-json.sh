#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ROLLBACK_ENV_FILE:-.env}"
BACKUP_FILE="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FAIL] Missing $ENV_FILE"
  exit 1
fi

cp "$ENV_FILE" "$BACKUP_FILE"
echo "[INFO] Backup created: $BACKUP_FILE"

python3 - <<'PY' "$ENV_FILE"
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding='utf-8').splitlines()

backend_key = 'TELEGRAM_STATE_BACKEND='
sqlite_key = 'TELEGRAM_STATE_SQLITE_PATH='
backend_set = False
sqlite_set = False
out = []

for raw in lines:
    line = raw
    if line.startswith(backend_key):
        out.append('TELEGRAM_STATE_BACKEND=json')
        backend_set = True
    elif line.startswith(sqlite_key):
        out.append(line)
        sqlite_set = True
    else:
        out.append(line)

if not backend_set:
    out.append('TELEGRAM_STATE_BACKEND=json')
if not sqlite_set:
    out.append('TELEGRAM_STATE_SQLITE_PATH=/state/telegram_state.db')

path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('UPDATED_ENV=1')
PY

echo "[INFO] Restarting ntfy-n8n-bridge with JSON backend"
docker compose up -d ntfy-n8n-bridge >/dev/null
sleep 3

echo "[INFO] Bridge status:"
docker compose ps ntfy-n8n-bridge

echo "[OK] Rollback complete."
echo "[NEXT] Optional verification:"
echo "  set -a && source .env && set +a && ./scripts/run-media-synthetic-check-and-alert.sh"
