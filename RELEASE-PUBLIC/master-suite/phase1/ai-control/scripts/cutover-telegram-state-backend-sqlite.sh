#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${CUTOVER_ENV_FILE:-.env}"
DB_PATH_DEFAULT="${TELEGRAM_STATE_SQLITE_PATH:-/state/telegram_state.db}"
DB_PATH="${CUTOVER_SQLITE_PATH:-$DB_PATH_DEFAULT}"
SKIP_MIGRATION="${CUTOVER_SKIP_MIGRATION:-false}"
BACKUP_FILE="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FAIL] Missing $ENV_FILE"
  exit 1
fi

cp "$ENV_FILE" "$BACKUP_FILE"
echo "[INFO] Backup created: $BACKUP_FILE"

python3 - <<'PY' "$ENV_FILE" "$DB_PATH"
from pathlib import Path
import sys

path = Path(sys.argv[1])
sqlite_path = sys.argv[2]
lines = path.read_text(encoding='utf-8').splitlines()

backend_key = 'TELEGRAM_STATE_BACKEND='
sqlite_key = 'TELEGRAM_STATE_SQLITE_PATH='
backend_set = False
sqlite_set = False
out = []

for raw in lines:
    line = raw
    if line.startswith(backend_key):
        out.append('TELEGRAM_STATE_BACKEND=sqlite')
        backend_set = True
    elif line.startswith(sqlite_key):
        out.append(f'TELEGRAM_STATE_SQLITE_PATH={sqlite_path}')
        sqlite_set = True
    else:
        out.append(line)

if not backend_set:
    out.append('TELEGRAM_STATE_BACKEND=sqlite')
if not sqlite_set:
    out.append(f'TELEGRAM_STATE_SQLITE_PATH={sqlite_path}')

path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('UPDATED_ENV=1')
PY

if [[ "$SKIP_MIGRATION" != "true" ]]; then
  echo "[INFO] Migrating JSON runtime state to SQLite: $DB_PATH"
  docker compose exec -T ntfy-n8n-bridge python - <<'PY' "$DB_PATH"
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

sqlite_path = sys.argv[1]
sources = {
    'delivery': ('/state/telegram_delivery_state.json', {'users': {}, 'updated_at': now()}),
    'dedupe': ('/state/telegram_dedupe_state.json', {'items': {}}),
    'notify_stats': ('/state/telegram_notify_stats.json', {'events': [], 'updated_at': now()}),
    'digest_queue': ('/state/telegram_digest_queue.json', {'users': {}, 'updated_at': now()}),
    'incidents': ('/state/telegram_incidents.json', {'incidents': {}, 'updated_at': now()}),
}

path = Path(sqlite_path)
if path.parent:
    path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(path))
try:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS state_kv (
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    for key, (src, default) in sources.items():
        payload = default
        p = Path(src)
        if p.exists():
            try:
                candidate = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(candidate, dict):
                    payload = candidate
            except Exception:
                pass

        conn.execute(
            '''INSERT INTO state_kv(key,payload,updated_at)
               VALUES(?,?,?)
               ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at''',
            (key, json.dumps(payload, ensure_ascii=False), now()),
        )
        print(f'migrated {key} from {src}')

    conn.commit()
finally:
    conn.close()

print(f'done db={sqlite_path}')
PY
else
  echo "[WARN] Skipping migration because CUTOVER_SKIP_MIGRATION=true"
fi

echo "[INFO] Restarting ntfy-n8n-bridge with SQLite backend"
docker compose up -d ntfy-n8n-bridge >/dev/null
sleep 3

echo "[INFO] Bridge status:"
docker compose ps ntfy-n8n-bridge

echo "[OK] Cutover complete."
echo "[NEXT] Optional verification:"
echo "  set -a && source .env && set +a && ./scripts/run-media-synthetic-check-and-alert.sh"
