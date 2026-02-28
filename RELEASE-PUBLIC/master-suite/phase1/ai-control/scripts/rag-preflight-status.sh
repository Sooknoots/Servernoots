#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="${1:-$(date +%F)}"

runners=(
  "run-telegram-chat-smoke-and-alert.sh"
  "run-textbook-synthetic-check-and-alert.sh"
  "run-media-synthetic-check-and-alert.sh"
  "run-routing-eval-and-alert.sh"
  "run-ux-metrics-and-alert.sh"
  "run-ux-metrics-weekly-rollup-and-alert.sh"
)

log_for_runner() {
  case "$1" in
    run-telegram-chat-smoke-and-alert.sh) echo "logs/telegram-chat-smoke-${STAMP}.log" ;;
    run-textbook-synthetic-check-and-alert.sh) echo "logs/textbook-synthetic-check-${STAMP}.log" ;;
    run-media-synthetic-check-and-alert.sh) echo "logs/media-synthetic-check-${STAMP}.log" ;;
    run-routing-eval-and-alert.sh) echo "logs/routing-eval-${STAMP}.log" ;;
    run-ux-metrics-and-alert.sh) echo "logs/ux-metrics-${STAMP}.log" ;;
    run-ux-metrics-weekly-rollup-and-alert.sh) echo "logs/ux-metrics-weekly-${STAMP}.log" ;;
    *) echo "" ;;
  esac
}

success_pattern_for_runner() {
  case "$1" in
    run-telegram-chat-smoke-and-alert.sh) echo "\\[OK\\] Telegram/chat smoke checks passed" ;;
    run-textbook-synthetic-check-and-alert.sh) echo "\\[OK\\] Textbook synthetic checks passed" ;;
    run-media-synthetic-check-and-alert.sh) echo "media fanout check passed" ;;
    run-routing-eval-and-alert.sh) echo "\\[OK\\] Routing eval passed" ;;
    run-ux-metrics-and-alert.sh) echo "window=.* status=(ok|warn|no-data)" ;;
    run-ux-metrics-weekly-rollup-and-alert.sh) echo "status=(ok|warn|no-data) window_days=" ;;
    *) echo "" ;;
  esac
}

last_line_num() {
  local pattern="$1"
  local file="$2"
  local line
  line="$(grep -nE "$pattern" "$file" 2>/dev/null | tail -n 1 | cut -d: -f1 || true)"
  if [[ -z "$line" ]]; then
    echo 0
  else
    echo "$line"
  fi
}

verify_rag_webhook_live() {
  local url="${N8N_BASE:-http://127.0.0.1:5678}"
  local path="${N8N_RAG_WEBHOOK_PATH:-/webhook/rag-query}"
  local body http_code
  body="$(mktemp)"

  http_code="$(curl -sS --max-time 15 -o "$body" -w "%{http_code}" \
    -H 'Content-Type: application/json' \
    -d '{"source":"telegram","chat_id":700,"user_id":9001,"role":"user","tenant_id":"u_9001","full_name":"Smoke User","telegram_username":"smokeuser","message":"healthcheck ping"}' \
    "${url%/}${path}" || true)"

  if [[ "$http_code" != "200" ]]; then
    rm -f "$body"
    echo "unhealthy(http_${http_code})"
    return
  fi

  if ! grep -q '"reply"' "$body"; then
    rm -f "$body"
    echo "unhealthy(missing_reply)"
    return
  fi

  if grep -qiE 'not registered|active version not found|error in workflow' "$body"; then
    rm -f "$body"
    echo "unhealthy(workflow_signal)"
    return
  fi

  rm -f "$body"
  echo "healthy"
}

coverage_ok=0

echo "RAG preflight status (${STAMP})"
echo "----------------------------------------"
printf "%-42s %-10s %-8s %-10s %s\n" "runner" "coverage" "log" "result" "note"

for runner in "${runners[@]}"; do
  runner_path="scripts/${runner}"
  coverage="missing"
  log_state="missing"
  result="unknown"
  note="-"

  if [[ -f "$runner_path" ]] && grep -q "ensure-rag-webhook-ready.sh" "$runner_path"; then
    coverage="ok"
    coverage_ok=$((coverage_ok + 1))
  fi

  log_file="$(log_for_runner "$runner")"
  if [[ -n "$log_file" && -f "$log_file" ]]; then
    log_state="present"
    success_pat="$(success_pattern_for_runner "$runner")"
    success_line="$(last_line_num "$success_pat" "$log_file")"
    fail_line="$(last_line_num '\\[FAIL\\]|Result: [1-9][0-9]* failing check\\(s\\)|Result: [1-9][0-9]* failing case\\(s\\)|failed on ' "$log_file")"

    if [[ "$success_line" -gt 0 && "$success_line" -ge "$fail_line" ]]; then
      result="pass"
      note="line=${success_line}"
    elif [[ "$fail_line" -gt 0 ]]; then
      result="fail"
      note="line=${fail_line}"
    else
      result="unknown"
      note="no_match"
    fi
  fi

  printf "%-42s %-10s %-8s %-10s %s\n" "$runner" "$coverage" "$log_state" "$result" "$note"
done

if [[ "$coverage_ok" -eq "${#runners[@]}" ]]; then
  echo "preflight_coverage=ok (${coverage_ok}/${#runners[@]})"
else
  echo "preflight_coverage=fail (${coverage_ok}/${#runners[@]})"
fi

live_status="$(verify_rag_webhook_live)"
echo "rag_query_live=${live_status}"
