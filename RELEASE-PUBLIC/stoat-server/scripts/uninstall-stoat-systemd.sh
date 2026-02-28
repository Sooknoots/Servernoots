#!/usr/bin/env bash
set -euo pipefail

UNIT_NAME="stoat-server.service"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found; this script requires systemd." >&2
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root or with sudo." >&2
  echo "Example: sudo $0" >&2
  exit 1
fi

if systemctl list-unit-files | grep -q "^${UNIT_NAME}"; then
  systemctl disable --now "$UNIT_NAME" || true
fi

if [[ -f "$UNIT_PATH" ]]; then
  rm -f "$UNIT_PATH"
fi

systemctl daemon-reload
systemctl reset-failed

if command -v docker >/dev/null 2>&1 && [[ -f "$ROOT_DIR/docker-compose.yml" ]]; then
  (
    cd "$ROOT_DIR"
    docker compose down || true
  )
fi

echo "Stoat service uninstalled and container stack cleaned up."