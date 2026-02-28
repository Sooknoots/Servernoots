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

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/media-request-tracker-$(date +%F).log"

REQTRACK_STALE_MINUTES="${REQTRACK_STALE_MINUTES:-60}"
REQTRACK_TAKE="${REQTRACK_TAKE:-120}"
REQTRACK_TIMEOUT="${REQTRACK_TIMEOUT:-20}"
REQTRACK_ATTEMPT_FIXES="${REQTRACK_ATTEMPT_FIXES:-false}"
REQTRACK_AUTO_APPROVE_PENDING="${REQTRACK_AUTO_APPROVE_PENDING:-false}"
REQTRACK_FIX_ACTIONS="${REQTRACK_FIX_ACTIONS:-approve_pending}"
REQTRACK_FIX_RETRY_ENABLED="${REQTRACK_FIX_RETRY_ENABLED:-false}"
REQTRACK_MAX_FIXES_PER_RUN="${REQTRACK_MAX_FIXES_PER_RUN:-3}"
REQTRACK_FIX_MIN_AGE_MINUTES="${REQTRACK_FIX_MIN_AGE_MINUTES:-120}"
REQTRACK_FIX_RETRY_MIN_SINCE_UPDATE_MINUTES="${REQTRACK_FIX_RETRY_MIN_SINCE_UPDATE_MINUTES:-180}"
REQTRACK_FIX_REQUIRE_ADMIN_TARGET="${REQTRACK_FIX_REQUIRE_ADMIN_TARGET:-true}"
REQTRACK_FIX_DRY_RUN="${REQTRACK_FIX_DRY_RUN:-false}"
REQTRACK_FIX_APPROVAL_MODE="${REQTRACK_FIX_APPROVAL_MODE:-direct}"
REQTRACK_FIX_APPROVAL_TOKEN="${REQTRACK_FIX_APPROVAL_TOKEN:-}"
REQTRACK_FIX_PROPOSAL_TTL_MINUTES="${REQTRACK_FIX_PROPOSAL_TTL_MINUTES:-60}"
REQTRACK_FIX_PROPOSAL_FILE="${REQTRACK_FIX_PROPOSAL_FILE:-logs/media-request-tracker-fix-proposals.json}"
REQTRACK_FIX_AUDIT_ENABLED="${REQTRACK_FIX_AUDIT_ENABLED:-true}"
REQTRACK_FIX_AUDIT_FILE="${REQTRACK_FIX_AUDIT_FILE:-logs/media-request-tracker-fix-audit.ndjson}"
REQTRACK_FIX_ACTOR="${REQTRACK_FIX_ACTOR:-reqtrack}"
REQTRACK_SUPPRESS_BY_REQUESTER_MINUTES="${REQTRACK_SUPPRESS_BY_REQUESTER_MINUTES:-0}"
REQTRACK_SUPPRESS_BY_TITLE_MINUTES="${REQTRACK_SUPPRESS_BY_TITLE_MINUTES:-0}"

ARGS=(
  --stale-minutes "$REQTRACK_STALE_MINUTES"
  --take "$REQTRACK_TAKE"
  --timeout "$REQTRACK_TIMEOUT"
  --suppress-by-requester-minutes "$REQTRACK_SUPPRESS_BY_REQUESTER_MINUTES"
  --suppress-by-title-minutes "$REQTRACK_SUPPRESS_BY_TITLE_MINUTES"
  --emit-ntfy
)

if [[ "$REQTRACK_ATTEMPT_FIXES" == "true" ]]; then
  ARGS+=(
    --attempt-fixes
    --fix-actions "$REQTRACK_FIX_ACTIONS"
    --fix-retry-min-since-update-minutes "$REQTRACK_FIX_RETRY_MIN_SINCE_UPDATE_MINUTES"
    --max-fixes-per-run "$REQTRACK_MAX_FIXES_PER_RUN"
    --fix-min-age-minutes "$REQTRACK_FIX_MIN_AGE_MINUTES"
    --fix-approval-mode "$REQTRACK_FIX_APPROVAL_MODE"
    --fix-proposal-ttl-minutes "$REQTRACK_FIX_PROPOSAL_TTL_MINUTES"
    --fix-proposal-file "$REQTRACK_FIX_PROPOSAL_FILE"
    --fix-audit-file "$REQTRACK_FIX_AUDIT_FILE"
    --fix-actor "$REQTRACK_FIX_ACTOR"
  )

  if [[ -n "$REQTRACK_FIX_APPROVAL_TOKEN" ]]; then
    ARGS+=(--fix-approval-token "$REQTRACK_FIX_APPROVAL_TOKEN")
  fi

  if [[ "$REQTRACK_FIX_AUDIT_ENABLED" == "true" ]]; then
    ARGS+=(--fix-audit-enabled)
  else
    ARGS+=(--no-fix-audit-enabled)
  fi

  if [[ "$REQTRACK_FIX_RETRY_ENABLED" == "true" ]]; then
    ARGS+=(--fix-retry-enabled)
  else
    ARGS+=(--no-fix-retry-enabled)
  fi

  if [[ "$REQTRACK_FIX_REQUIRE_ADMIN_TARGET" == "true" ]]; then
    ARGS+=(--fix-require-admin-target)
  else
    ARGS+=(--no-fix-require-admin-target)
  fi

  if [[ "$REQTRACK_FIX_DRY_RUN" == "true" ]]; then
    ARGS+=(--fix-dry-run)
  else
    ARGS+=(--no-fix-dry-run)
  fi
fi

if [[ "$REQTRACK_AUTO_APPROVE_PENDING" == "true" ]]; then
  ARGS+=(--auto-approve-pending)
fi

{
  echo "[$(date -Is)] Starting stale media request tracker"
  ./scripts/reqtrack "${ARGS[@]}"
  echo "[$(date -Is)] Tracker run complete"
} >>"$LOG_FILE" 2>&1
