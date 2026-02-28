#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  echo "Usage: $0 [BOT_TOKEN]"
  echo ""
  echo "Reads token from first arg or TELEGRAM_BOT_TOKEN env var (.env is auto-loaded)."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

TOKEN="${1:-${TELEGRAM_BOT_TOKEN:-}}"
if [[ -z "$TOKEN" ]]; then
  echo "[FAIL] Missing bot token. Pass as arg or set TELEGRAM_BOT_TOKEN in .env"
  echo "Example: $0 123456789:ABCDEF..."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[FAIL] curl is required"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[FAIL] python3 is required"
  exit 1
fi

RAW="$(curl -fsS "https://api.telegram.org/bot${TOKEN}/getUpdates")"

python3 - <<'PY' "$RAW"
import json
import sys

raw = sys.argv[1]
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print('[FAIL] Telegram API returned non-JSON response')
    raise SystemExit(1)

if not payload.get('ok'):
    print('[FAIL] Telegram API returned ok=false')
    print(payload)
    raise SystemExit(1)

updates = payload.get('result', [])
if not updates:
    print('[WARN] No updates found yet.')
    print('Send any message to your bot in Telegram, then rerun this script.')
    raise SystemExit(0)

rows = []
for update in updates:
    message = update.get('message') or update.get('edited_message') or {}
    if not message:
        continue
    chat = message.get('chat') or {}
    sender = message.get('from') or {}
    rows.append({
        'update_id': update.get('update_id'),
        'user_id': sender.get('id'),
        'username': sender.get('username') or '',
        'chat_id': chat.get('id'),
        'chat_type': chat.get('type') or '',
        'text': (message.get('text') or message.get('caption') or '')[:80],
    })

if not rows:
    print('[WARN] Updates exist but no message objects found.')
    raise SystemExit(0)

print('Candidate IDs from recent updates:')
print('update_id\tuser_id\tchat_id\tchat_type\tusername\ttext')
for r in rows:
    print(f"{r['update_id']}\t{r['user_id']}\t{r['chat_id']}\t{r['chat_type']}\t{r['username']}\t{r['text']}")

user_ids = sorted({str(r['user_id']) for r in rows if r.get('user_id') is not None})
if user_ids:
    print('\nUse this in .env:')
    print('TELEGRAM_ALLOWED_USER_IDS=' + ','.join(user_ids))
PY
