#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_SERVICE="$ROOT_DIR/systemd/stoat-server.service"
DST_SERVICE="/etc/systemd/system/stoat-server.service"

if [[ ! -f "$SRC_SERVICE" ]]; then
  echo "Service file not found: $SRC_SERVICE" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found; this script requires systemd." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found; install Docker first." >&2
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root or with sudo." >&2
  echo "Example: sudo $0" >&2
  exit 1
fi

cp "$SRC_SERVICE" "$DST_SERVICE"
systemctl daemon-reload
systemctl enable --now stoat-server.service

echo "Stoat service installed and started."
systemctl --no-pager --full status stoat-server.service | sed -n '1,20p'