#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/smtp-provider-switch.sh --provider <name> [options]

Providers:
  mailpit | gmail | sendgrid | brevo | mailgun | postmark | ses | custom

Options:
  --provider <name>
  --from <email>
  --user <value>
  --password <value>
  --host <smtp_host>
  --port <smtp_port>
  --ssl <true|false>
  --starttls <true|false>
  --env-file <path>
  --no-restart
  --help

Notes:
  - For Gmail, use an App Password (not your account password).
  - For SendGrid, set user to 'apikey' and password to your API key.
  - For SES, override --host to your region endpoint when needed.
EOF
}

PROVIDER=""
SMTP_FROM="${SMTP_FROM:-}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-}"
SMTP_SSL="${SMTP_SSL:-}"
SMTP_STARTTLS="${SMTP_STARTTLS:-}"
ENV_FILE="$ROOT_DIR/.env"
RESTART_BRIDGE="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      PROVIDER="${2:-}"
      shift 2
      ;;
    --from)
      SMTP_FROM="${2:-}"
      shift 2
      ;;
    --user)
      SMTP_USER="${2:-}"
      shift 2
      ;;
    --password)
      SMTP_PASSWORD="${2:-}"
      shift 2
      ;;
    --host)
      SMTP_HOST="${2:-}"
      shift 2
      ;;
    --port)
      SMTP_PORT="${2:-}"
      shift 2
      ;;
    --ssl)
      SMTP_SSL="${2:-}"
      shift 2
      ;;
    --starttls)
      SMTP_STARTTLS="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --no-restart)
      RESTART_BRIDGE="false"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROVIDER" ]]; then
  echo "--provider is required" >&2
  usage
  exit 1
fi

PROVIDER="$(echo "$PROVIDER" | tr '[:upper:]' '[:lower:]')"

case "$PROVIDER" in
  mailpit)
    SMTP_HOST="mailpit"
    SMTP_PORT="1025"
    SMTP_SSL="false"
    SMTP_STARTTLS="false"
    SMTP_USER=""
    SMTP_PASSWORD=""
    SMTP_FROM="${SMTP_FROM:-no-reply@servernoots.local}"
    ;;
  gmail)
    SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_SSL="${SMTP_SSL:-false}"
    SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
    ;;
  sendgrid)
    SMTP_HOST="${SMTP_HOST:-smtp.sendgrid.net}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_SSL="${SMTP_SSL:-false}"
    SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
    SMTP_USER="${SMTP_USER:-apikey}"
    ;;
  brevo)
    SMTP_HOST="${SMTP_HOST:-smtp-relay.brevo.com}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_SSL="${SMTP_SSL:-false}"
    SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
    ;;
  mailgun)
    SMTP_HOST="${SMTP_HOST:-smtp.mailgun.org}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_SSL="${SMTP_SSL:-false}"
    SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
    ;;
  postmark)
    SMTP_HOST="${SMTP_HOST:-smtp.postmarkapp.com}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_SSL="${SMTP_SSL:-false}"
    SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
    ;;
  ses)
    SMTP_HOST="${SMTP_HOST:-email-smtp.us-east-1.amazonaws.com}"
    SMTP_PORT="${SMTP_PORT:-587}"
    SMTP_SSL="${SMTP_SSL:-false}"
    SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
    ;;
  custom)
    ;;
  *)
    echo "Unsupported provider: $PROVIDER" >&2
    usage
    exit 1
    ;;
esac

if [[ -z "$SMTP_HOST" || -z "$SMTP_PORT" || -z "$SMTP_FROM" ]]; then
  echo "Missing required SMTP fields. Need host, port, and from." >&2
  exit 1
fi

if [[ "$PROVIDER" != "mailpit" && -z "$SMTP_PASSWORD" ]]; then
  echo "SMTP password/API key is required for provider '$PROVIDER'. Pass --password or set SMTP_PASSWORD." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d%H%M%S)"

python3 - <<'PY' "$ENV_FILE" "$SMTP_HOST" "$SMTP_PORT" "$SMTP_USER" "$SMTP_PASSWORD" "$SMTP_FROM" "$SMTP_SSL" "$SMTP_STARTTLS"
import pathlib
import sys

env_path = pathlib.Path(sys.argv[1])
updates = {
    "TEXTBOOK_SMTP_HOST": sys.argv[2],
    "TEXTBOOK_SMTP_PORT": sys.argv[3],
    "TEXTBOOK_SMTP_USER": sys.argv[4],
    "TEXTBOOK_SMTP_PASSWORD": sys.argv[5],
    "TEXTBOOK_SMTP_FROM": sys.argv[6],
    "TEXTBOOK_SMTP_USE_SSL": sys.argv[7],
    "TEXTBOOK_SMTP_USE_STARTTLS": sys.argv[8],
}

lines = env_path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key, _ = line.split("=", 1)
    key = key.strip()
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

echo "Configured provider: $PROVIDER"
echo "TEXTBOOK_SMTP_HOST=$SMTP_HOST"
echo "TEXTBOOK_SMTP_PORT=$SMTP_PORT"
echo "TEXTBOOK_SMTP_FROM=$SMTP_FROM"
echo "TEXTBOOK_SMTP_USE_SSL=$SMTP_SSL"
echo "TEXTBOOK_SMTP_USE_STARTTLS=$SMTP_STARTTLS"

if [[ "$RESTART_BRIDGE" == "true" ]]; then
  docker compose up -d --force-recreate telegram-n8n-bridge >/dev/null
  echo "telegram-n8n-bridge recreated with new SMTP settings"
fi

echo "Next: run /textbook resend in Telegram, then ./scripts/smtpcheck"
