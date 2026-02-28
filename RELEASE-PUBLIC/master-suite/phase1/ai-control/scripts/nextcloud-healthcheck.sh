#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ok() { echo "[OK] $*"; }
fail() { echo "[FAIL] $*"; exit 1; }

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is not installed or not in PATH"
fi

if ! docker compose ps --status running nextcloud | grep -q nextcloud; then
  fail "nextcloud is not running. Start with: docker compose up -d nextcloud-db nextcloud"
fi
ok "nextcloud container is running"

HOST_PORT="${NEXTCLOUD_HOST_PORT:-8085}"
CODE=""
for _ in $(seq 1 30); do
  CODE="$(curl -sS --max-time 8 -o /tmp/nextcloud-health.html -w "%{http_code}" "http://127.0.0.1:${HOST_PORT}" || true)"
  if [[ "$CODE" == "200" || "$CODE" == "302" ]]; then
    break
  fi
  sleep 2
done

if [[ "$CODE" != "200" && "$CODE" != "302" ]]; then
  fail "nextcloud HTTP check returned $CODE"
fi
ok "nextcloud HTTP endpoint reachable on 127.0.0.1:${HOST_PORT}"

echo
echo "Nextcloud healthcheck passed."
