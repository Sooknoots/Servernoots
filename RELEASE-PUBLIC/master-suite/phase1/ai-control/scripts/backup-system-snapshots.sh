#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd -- "${BASE_DIR}/../../.." && pwd)"

SOURCE_SNAPSHOTS="${SOURCE_SNAPSHOTS:-${BASE_DIR}/snapshots}"
SOURCE_CHECKPOINTS="${SOURCE_CHECKPOINTS:-${WORKSPACE_ROOT}/checkpoints}"
DEST_ROOT="${DEST_ROOT:-/media/sook/Seagate Expansion Drive/SERVERNOOTS BACKUPS}"

if ! command -v rsync >/dev/null 2>&1; then
  echo "[FAIL] rsync is required but not installed"
  exit 1
fi

if [[ ! -d "${SOURCE_SNAPSHOTS}" ]]; then
  echo "[FAIL] Missing source snapshots directory: ${SOURCE_SNAPSHOTS}"
  exit 1
fi

if [[ ! -d "${SOURCE_CHECKPOINTS}" ]]; then
  echo "[FAIL] Missing source checkpoints directory: ${SOURCE_CHECKPOINTS}"
  exit 1
fi

if [[ ! -d "${DEST_ROOT}" ]]; then
  echo "[FAIL] Missing destination root: ${DEST_ROOT}"
  exit 1
fi

if [[ ! -w "${DEST_ROOT}" ]]; then
  echo "[FAIL] Destination root is not writable: ${DEST_ROOT}"
  exit 1
fi

STAMP="$(date +%F_%H%M%S)"
DEST_DIR="${DEST_ROOT%/}/system-snapshots/${STAMP}"

echo "[backup] source snapshots: ${SOURCE_SNAPSHOTS}"
echo "[backup] source checkpoints: ${SOURCE_CHECKPOINTS}"
echo "[backup] destination: ${DEST_DIR}"

mkdir -p "${DEST_DIR}/ai-control-snapshots" "${DEST_DIR}/checkpoints"

rsync -a "${SOURCE_SNAPSHOTS}/" "${DEST_DIR}/ai-control-snapshots/"
rsync -a "${SOURCE_CHECKPOINTS}/" "${DEST_DIR}/checkpoints/"

src_snapshot_count="$(find "${SOURCE_SNAPSHOTS}" -type f 2>/dev/null | wc -l | tr -d ' ')"
dst_snapshot_count="$(find "${DEST_DIR}/ai-control-snapshots" -type f 2>/dev/null | wc -l | tr -d ' ')"
src_checkpoint_count="$(find "${SOURCE_CHECKPOINTS}" -type f 2>/dev/null | wc -l | tr -d ' ')"
dst_checkpoint_count="$(find "${DEST_DIR}/checkpoints" -type f 2>/dev/null | wc -l | tr -d ' ')"

if [[ "${src_snapshot_count}" != "${dst_snapshot_count}" ]]; then
  echo "[FAIL] Snapshot count mismatch: src=${src_snapshot_count} dst=${dst_snapshot_count}"
  exit 1
fi

if [[ "${src_checkpoint_count}" != "${dst_checkpoint_count}" ]]; then
  echo "[FAIL] Checkpoint count mismatch: src=${src_checkpoint_count} dst=${dst_checkpoint_count}"
  exit 1
fi

{
  echo "timestamp=${STAMP}"
  echo "source_snapshots=${SOURCE_SNAPSHOTS}"
  echo "source_checkpoints=${SOURCE_CHECKPOINTS}"
  echo "snapshot_files=${dst_snapshot_count}"
  echo "checkpoint_files=${dst_checkpoint_count}"
} > "${DEST_DIR}/backup-manifest.txt"

echo "${DEST_DIR}" > "${DEST_ROOT%/}/system-snapshots/latest-path.txt"

echo "[OK] Backup complete"
echo "[OK] Snapshot files: ${dst_snapshot_count}"
echo "[OK] Checkpoint files: ${dst_checkpoint_count}"
echo "[OK] Manifest: ${DEST_DIR}/backup-manifest.txt"
echo "[OK] Latest path marker: ${DEST_ROOT%/}/system-snapshots/latest-path.txt"
