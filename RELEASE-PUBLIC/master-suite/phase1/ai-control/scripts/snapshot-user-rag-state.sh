#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_ROOT="${BASE_DIR}/snapshots/user-rag"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_ROOT}/${STAMP}"
QDRANT_BASE="${QDRANT_BASE:-http://127.0.0.1:6333}"
BRIDGE_CONTAINER="${BRIDGE_CONTAINER:-telegram-n8n-bridge}"

mkdir -p "${OUT_DIR}"

echo "[snapshot] output: ${OUT_DIR}"

if docker ps --format '{{.Names}}' | grep -qx "${BRIDGE_CONTAINER}"; then
  echo "[snapshot] exporting telegram user registry"
  docker exec "${BRIDGE_CONTAINER}" /bin/sh -lc "cat /state/telegram_users.json" > "${OUT_DIR}/telegram_users.json"
else
  echo "[snapshot] WARNING: ${BRIDGE_CONTAINER} not running, skipping telegram_users.json"
fi

echo "[snapshot] listing qdrant collections"
collections_json="$(curl -fsS "${QDRANT_BASE}/collections")"
echo "${collections_json}" > "${OUT_DIR}/collections.json"

mapfile -t collections < <(
  echo "${collections_json}" | jq -r '.result.collections[]?.name' | grep -E '^day4_rag_(u_[0-9]+|shared_public)$' || true
)

if [[ ${#collections[@]} -eq 0 ]]; then
  echo "[snapshot] no tenant/shared collections found"
else
  for collection in "${collections[@]}"; do
    echo "[snapshot] creating snapshot for ${collection}"
    curl -fsS -X POST "${QDRANT_BASE}/collections/${collection}/snapshots" >/dev/null

    snap_list="$(curl -fsS "${QDRANT_BASE}/collections/${collection}/snapshots")"
    snap_name="$(echo "${snap_list}" | jq -r '.result[]?.name' | tail -n 1)"

    if [[ -z "${snap_name}" || "${snap_name}" == "null" ]]; then
      echo "[snapshot] WARNING: no snapshot name returned for ${collection}"
      continue
    fi

    echo "${snap_list}" > "${OUT_DIR}/${collection}.snapshots.json"
    curl -fsS "${QDRANT_BASE}/collections/${collection}/snapshots/${snap_name}" -o "${OUT_DIR}/${collection}.${snap_name}"

    info="$(curl -fsS "${QDRANT_BASE}/collections/${collection}")"
    echo "${info}" > "${OUT_DIR}/${collection}.info.json"
  done
fi

{
  echo "timestamp=${STAMP}"
  echo "qdrant_base=${QDRANT_BASE}"
  echo "bridge_container=${BRIDGE_CONTAINER}"
  echo "collections_count=${#collections[@]}"
  printf 'collections=%s\n' "${collections[*]:-none}"
} > "${OUT_DIR}/manifest.txt"

echo "[snapshot] complete"
echo "[snapshot] manifest: ${OUT_DIR}/manifest.txt"
