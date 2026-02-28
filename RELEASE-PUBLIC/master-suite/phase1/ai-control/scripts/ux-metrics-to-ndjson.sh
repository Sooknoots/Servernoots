#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/cli_error_style.sh"

print_usage() {
  cat >&2 <<EOF
Usage: $0 [--kind daily|weekly|both|auto] [--require-kind] [--latest] <log-file> [<log-file> ...]
Example (all blocks): $0 logs/ux-metrics-$(date +%F).log logs/ux-metrics-weekly-$(date +%F).log
Example (latest only): $0 --latest logs/ux-metrics-$(date +%F).log logs/ux-metrics-weekly-$(date +%F).log
Example (weekly only): $0 --kind weekly --latest logs/ux-metrics-$(date +%F).log logs/ux-metrics-weekly-$(date +%F).log
Example (no filtering alias): $0 --kind both --latest logs/ux-metrics-$(date +%F).log logs/ux-metrics-weekly-$(date +%F).log
$(cli_exit_codes_text)
EOF
}

MODE="all"
KIND=""
REQUIRE_KIND="0"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      print_usage
      exit 0
      ;;
    --latest)
      MODE="latest"
      shift
      ;;
    --require-kind)
      REQUIRE_KIND="1"
      shift
      ;;
    --kind)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --kind (expected: daily, weekly, both, or auto)" >&2
        exit "$CLI_EXIT_USAGE"
      fi
      case "$2" in
        daily|weekly|both|auto) KIND="$2" ;;
        *)
          echo "Invalid --kind value: $2 (expected: daily, weekly, both, or auto)" >&2
            exit "$CLI_EXIT_USAGE"
          ;;
      esac
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      if [[ "$1" == -* ]]; then
        echo "Unknown option: $1" >&2
        print_usage
        exit "$CLI_EXIT_USAGE"
      fi
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  print_usage
  exit "$CLI_EXIT_USAGE"
fi

for log_file in "$@"; do
  if [[ "$log_file" = /* ]]; then
    target="$log_file"
  else
    target="$ROOT_DIR/$log_file"
  fi

  if [[ "$MODE" == "latest" ]]; then
    if [[ -n "$KIND" ]]; then
      args=("$target" --kind "$KIND" --latest-ndjson)
      if [[ "$REQUIRE_KIND" == "1" ]]; then
        args+=(--require-kind)
      fi
      row="$(python3 "$ROOT_DIR/scripts/parse-ux-metrics-log.py" "${args[@]}")"
      if [[ -n "$row" && "$row" != "{}" ]]; then
        echo "$row"
      fi
    else
      row="$(python3 "$ROOT_DIR/scripts/parse-ux-metrics-log.py" "$target" --latest-ndjson)"
      if [[ -n "$row" && "$row" != "{}" ]]; then
        echo "$row"
      fi
    fi
  else
    if [[ -n "$KIND" ]]; then
      args=("$target" --kind "$KIND" --all --ndjson)
      if [[ "$REQUIRE_KIND" == "1" ]]; then
        args+=(--require-kind)
      fi
      python3 "$ROOT_DIR/scripts/parse-ux-metrics-log.py" "${args[@]}"
    else
      python3 "$ROOT_DIR/scripts/parse-ux-metrics-log.py" "$target" --all --ndjson
    fi
  fi
done
