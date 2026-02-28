#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

if [[ -f .env.secrets ]]; then
  set -a
  source .env.secrets
  set +a
fi

DRILL_STATE="${REQTRACK_DRILL_STATE_FILE:-/tmp/reqtrack-drill-state.json}"
BASE_ARGS=(--dry-drill --dry-drill-stateful --emit-ntfy --state-file "$DRILL_STATE" --json)

if ! command -v jq >/dev/null 2>&1; then
  echo "[FAIL] jq is required for this drill helper"
  exit 1
fi

rm -f "$DRILL_STATE"

echo "--- RUN1 (initial alert expected) ---"
./scripts/reqtrack "${BASE_ARGS[@]}" | jq '{dry_drill_stateful,stale_count,notify_candidate_count,ntfy,items:[.items[]|{id:.request_id,age:.age_minutes,level:.incident.current_level,notified:.incident.should_notify}]}'

echo "--- RUN2 (dedupe expected, no new notify) ---"
./scripts/reqtrack "${BASE_ARGS[@]}" | jq '{dry_drill_stateful,stale_count,notify_candidate_count,ntfy,items:[.items[]|{id:.request_id,age:.age_minutes,level:.incident.current_level,notified:.incident.should_notify}]}'

echo "--- RUN3 (level-up re-alert expected via age bump) ---"
./scripts/reqtrack "${BASE_ARGS[@]}" --dry-drill-admin-age-minutes 130 --dry-drill-user-age-minutes 140 | jq '{dry_drill_stateful,stale_count,notify_candidate_count,ntfy,items:[.items[]|{id:.request_id,age:.age_minutes,level:.incident.current_level,notified:.incident.should_notify}]}'

echo "--- DRILL STATE FILE ---"
cat "$DRILL_STATE"

echo "[OK] Stateful reqtrack drill complete"
