#!/usr/bin/env python3
import json
import io
import hashlib
import mimetypes
import os
import pathlib
import re
import sqlite3
import smtplib
import threading
import sys
import time
import zipfile
from email.message import EmailMessage
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

try:
    from policy_loader import load_policy_telegram_settings
except ModuleNotFoundError:
    bridge_dir = pathlib.Path(__file__).resolve().parent
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    from policy_loader import load_policy_telegram_settings


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def parse_int(value: str, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def parse_float(value: str, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


TOKEN = env("TELEGRAM_BOT_TOKEN")
ALLOWED_IDS_RAW = env("TELEGRAM_ALLOWED_USER_IDS")
POLL_TIMEOUT = parse_int(env("TELEGRAM_POLL_TIMEOUT", "50"), 50)
N8N_BASE = env("N8N_BASE", "http://n8n:5678")
RAG_WEBHOOK = env("N8N_RAG_WEBHOOK", "/webhook/rag-query")
RAG_INGEST_WEBHOOK = env("N8N_RAG_INGEST_WEBHOOK", "/webhook/rag-ingest")
OPS_WEBHOOK = env("N8N_OPS_WEBHOOK", "/webhook/ops-commands-ingest")
TEXTBOOK_WEBHOOK = env("N8N_TEXTBOOK_WEBHOOK", "/webhook/textbook-fulfillment")
RESEARCH_WEBHOOK = env("N8N_RESEARCH_WEBHOOK", "/webhook/deep-research")
N8N_WEBHOOK_RETRY_ATTEMPTS = parse_int(env("N8N_WEBHOOK_RETRY_ATTEMPTS", "4"), 4)
N8N_WEBHOOK_RETRY_DELAY_SECONDS = max(0.2, float(env("N8N_WEBHOOK_RETRY_DELAY_SECONDS", "1.0") or "1.0"))
TEXTBOOK_SMTP_HOST = env("TEXTBOOK_SMTP_HOST", "")
TEXTBOOK_SMTP_PORT = parse_int(env("TEXTBOOK_SMTP_PORT", "587"), 587)
TEXTBOOK_SMTP_USER = env("TEXTBOOK_SMTP_USER", "")
TEXTBOOK_SMTP_PASSWORD = env("TEXTBOOK_SMTP_PASSWORD", "")
TEXTBOOK_SMTP_FROM = env("TEXTBOOK_SMTP_FROM", "")
TEXTBOOK_SMTP_USE_SSL = env("TEXTBOOK_SMTP_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
TEXTBOOK_SMTP_USE_STARTTLS = env("TEXTBOOK_SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes", "on"}
TEXTBOOK_ENFORCE_FILE_DOMAIN_ALLOWLIST = env("TEXTBOOK_ENFORCE_FILE_DOMAIN_ALLOWLIST", "true").lower() in {"1", "true", "yes", "on"}
TEXTBOOK_ALLOWED_FILE_DOMAINS_RAW = env(
    "TEXTBOOK_ALLOWED_FILE_DOMAINS",
    "example.edu,books.google.com,openlibrary.org,archive.org,gutenberg.org,www.gutenberg.org,*.edu,*.gov",
)
TEXTBOOK_SEARCH_PROVIDERS_RAW = env(
    "TEXTBOOK_SEARCH_PROVIDERS",
    "googlebooks,openlibrary,internetarchive,gutendex",
)
TEXTBOOK_DOWNLOAD_LINK_ENABLED = env("TEXTBOOK_DOWNLOAD_LINK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
TEXTBOOK_DOWNLOAD_PUBLIC_BASE_URL = env("TEXTBOOK_DOWNLOAD_PUBLIC_BASE_URL", "").rstrip("/")
TEXTBOOK_DOWNLOAD_BIND_HOST = env("TEXTBOOK_DOWNLOAD_BIND_HOST", "0.0.0.0")
TEXTBOOK_DOWNLOAD_PORT = parse_int(env("TEXTBOOK_DOWNLOAD_PORT", "8113"), 8113)
TEXTBOOK_DOWNLOAD_TTL_SECONDS = parse_int(env("TEXTBOOK_DOWNLOAD_TTL_SECONDS", "86400"), 86400)
TEXTBOOK_DOWNLOAD_MAX_BYTES = parse_int(env("TEXTBOOK_DOWNLOAD_MAX_BYTES", "52428800"), 52428800)
TEXTBOOK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS = parse_int(env("TEXTBOOK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS", "300"), 300)
TEXTBOOK_DOWNLOAD_STATE_PATH = pathlib.Path(env("TELEGRAM_TEXTBOOK_DOWNLOAD_STATE", "/state/telegram_textbook_downloads.json"))
TEXTBOOK_DOWNLOAD_FILES_DIR = pathlib.Path(env("TELEGRAM_TEXTBOOK_DOWNLOAD_DIR", "/state/textbook-downloads"))
WORKSPACE_STATE_PATH = pathlib.Path(env("TELEGRAM_WORKSPACE_STATE", "/state/telegram_workspace_state.json"))
WORKSPACE_TTL_SECONDS = parse_int(env("TELEGRAM_WORKSPACE_TTL_SECONDS", "86400"), 86400)
WORKSPACE_CLEANUP_INTERVAL_SECONDS = parse_int(env("TELEGRAM_WORKSPACE_CLEANUP_INTERVAL_SECONDS", "300"), 300)
WORKSPACE_MAX_DOCS = parse_int(env("TELEGRAM_WORKSPACE_MAX_DOCS", "8"), 8)
OVERSEERR_URL = env("OVERSEERR_URL", "http://host.docker.internal:5055").rstrip("/")
OVERSEERR_API_KEY = env("OVERSEERR_API_KEY")
MEDIA_SELECTION_PATH = pathlib.Path(env("TELEGRAM_MEDIA_SELECTION_STATE", "/state/telegram_media_selection.json"))
MEDIA_SELECTION_TTL_SECONDS = parse_int(env("TELEGRAM_MEDIA_SELECTION_TTL_SECONDS", "600"), 600)
TEXTBOOK_STATE_PATH = pathlib.Path(env("TELEGRAM_TEXTBOOK_STATE", "/state/telegram_textbook_requests.json"))
TEXTBOOK_REQUEST_TTL_SECONDS = parse_int(env("TELEGRAM_TEXTBOOK_REQUEST_TTL_SECONDS", "1800"), 1800)
TEXTBOOK_COVER_PREVIEW_ENABLED = env("TELEGRAM_TEXTBOOK_COVER_PREVIEW_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
RESEARCH_STATE_PATH = pathlib.Path(env("TELEGRAM_RESEARCH_STATE", "/state/telegram_research_jobs.json"))
RESEARCH_MAX_QUERY_CHARS = parse_int(env("TELEGRAM_RESEARCH_MAX_QUERY_CHARS", "2000"), 2000)
RESEARCH_DEFAULT_LINK_TTL_SECONDS = parse_int(env("TELEGRAM_RESEARCH_LINK_TTL_SECONDS", "86400"), 86400)
RESEARCH_NEXTCLOUD_BASE_URL = env("RESEARCH_NEXTCLOUD_BASE_URL", "http://nextcloud")
RESEARCH_NEXTCLOUD_USER = env("RESEARCH_NEXTCLOUD_USER", "")
RESEARCH_NEXTCLOUD_PASSWORD = env("RESEARCH_NEXTCLOUD_PASSWORD", "")
RESEARCH_NEXTCLOUD_FOLDER = env("RESEARCH_NEXTCLOUD_FOLDER", "research-reports")
DEFAULT_MODE = env("TELEGRAM_DEFAULT_MODE", "rag").lower()
STATE_PATH = pathlib.Path(env("TELEGRAM_BRIDGE_STATE", "/state/telegram_bridge_state.json"))
APPROVALS_PATH = pathlib.Path(env("TELEGRAM_APPROVALS_STATE", "/state/telegram_approvals.json"))
CODING_ACCESS_AUDIT_PATH = pathlib.Path(env("TELEGRAM_CODING_ACCESS_AUDIT", "/state/telegram_coding_access_audit.jsonl"))
APPROVAL_TTL_SECONDS = parse_int(env("TELEGRAM_APPROVAL_TTL_SECONDS", "300"), 300)
APPROVAL_MAX_PENDING_PER_USER = parse_int(env("TELEGRAM_APPROVAL_MAX_PENDING_PER_USER", "3"), 3)
RATE_LIMIT_PATH = pathlib.Path(env("TELEGRAM_RATE_LIMIT_STATE", "/state/telegram_rate_limit.json"))
RATE_LIMIT_WINDOW_SECONDS = parse_int(env("TELEGRAM_RATE_LIMIT_WINDOW_SECONDS", "30"), 30)
RATE_LIMIT_MAX_REQUESTS = parse_int(env("TELEGRAM_RATE_LIMIT_MAX_REQUESTS", "6"), 6)
RATE_LIMIT_NOTICE_DEBOUNCE_ENABLED = env("TELEGRAM_RATE_LIMIT_NOTICE_DEBOUNCE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
ADMIN_COMMAND_COOLDOWN_SECONDS = parse_int(env("TELEGRAM_ADMIN_COMMAND_COOLDOWN_SECONDS", "15"), 15)
ADMIN_COMMAND_COOLDOWN_COMMANDS_RAW = env(
    "TELEGRAM_ADMIN_COMMAND_COOLDOWN_COMMANDS",
    "/status,/health,/ratelimit,/notify stats,/digest stats",
)
ADMIN_COMMAND_COOLDOWN_PATH = pathlib.Path(
    env("TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE", "/state/telegram_admin_command_cooldowns.json")
)
SHORT_INPUT_MIN_CHARS = parse_int(env("TELEGRAM_SHORT_INPUT_MIN_CHARS", "3"), 3)
LOW_SIGNAL_FILTER_ENABLED = env("TELEGRAM_LOW_SIGNAL_FILTER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
LOW_SIGNAL_TOKEN_MAX_CHARS = parse_int(env("TELEGRAM_LOW_SIGNAL_TOKEN_MAX_CHARS", "2"), 2)
REPLY_MAX_CHARS = parse_int(env("TELEGRAM_REPLY_MAX_CHARS", "1800"), 1800)
TELEGRAM_MESSAGE_REVIEW_ENABLED = env("TELEGRAM_MESSAGE_REVIEW_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
TELEGRAM_MESSAGE_REVIEW_MAX_CHARS = parse_int(env("TELEGRAM_MESSAGE_REVIEW_MAX_CHARS", str(REPLY_MAX_CHARS)), REPLY_MAX_CHARS)
REPLY_SHOW_SOURCES = env("TELEGRAM_REPLY_SHOW_SOURCES", "false").lower() in {"1", "true", "yes", "on"}
MEMORY_PATH = pathlib.Path(env("TELEGRAM_MEMORY_STATE", "/state/telegram_memory.json"))
MEMORY_MAX_CHARS = parse_int(env("TELEGRAM_MEMORY_MAX_CHARS", "1200"), 1200)
MEMORY_MAX_ITEMS = parse_int(env("TELEGRAM_MEMORY_MAX_ITEMS", "20"), 20)
MEMORY_TTL_DAYS = parse_int(env("TELEGRAM_MEMORY_TTL_DAYS", "30"), 30)
MEMORY_ENABLED_BY_DEFAULT = env("TELEGRAM_MEMORY_ENABLED_BY_DEFAULT", "false").lower() == "true"
MEMORY_MIN_CONFIDENCE = min(1.0, max(0.0, parse_float(env("TELEGRAM_MEMORY_MIN_CONFIDENCE", "0.0"), 0.0)))
MEMORY_RECENCY_HALF_LIFE_DAYS = max(0.25, parse_float(env("TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS", "7.0"), 7.0))
MEMORY_RECENCY_HALF_LIFE_DAYS_PROFILE = max(
    0.25,
    parse_float(env("TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS_PROFILE", str(MEMORY_RECENCY_HALF_LIFE_DAYS)), MEMORY_RECENCY_HALF_LIFE_DAYS),
)
MEMORY_RECENCY_HALF_LIFE_DAYS_PREFERENCE = max(
    0.25,
    parse_float(env("TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS_PREFERENCE", str(MEMORY_RECENCY_HALF_LIFE_DAYS)), MEMORY_RECENCY_HALF_LIFE_DAYS),
)
MEMORY_RECENCY_HALF_LIFE_DAYS_SESSION = max(
    0.25,
    parse_float(env("TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS_SESSION", "2.0"), 2.0),
)
MEMORY_SYNTHESIS_ENABLED = env("TELEGRAM_MEMORY_SYNTHESIS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
MEMORY_SYNTHESIS_MAX_ITEMS = parse_int(env("TELEGRAM_MEMORY_SYNTHESIS_MAX_ITEMS", "8"), 8)
MEMORY_CONFLICT_REQUIRE_CONFIRMATION = env("TELEGRAM_MEMORY_CONFLICT_REQUIRE_CONFIRMATION", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_CONFLICT_PROMPT_ENABLED = env("TELEGRAM_MEMORY_CONFLICT_PROMPT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_CONFLICT_REMINDER_ENABLED = env("TELEGRAM_MEMORY_CONFLICT_REMINDER_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_CONFLICT_REMINDER_SECONDS = max(300, parse_int(env("TELEGRAM_MEMORY_CONFLICT_REMINDER_SECONDS", "21600"), 21600))
MEMORY_INTENT_SCOPE_ENABLED = env("TELEGRAM_MEMORY_INTENT_SCOPE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_CANARY_ENABLED = env("TELEGRAM_MEMORY_CANARY_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_CANARY_PERCENT_RAW = env("TELEGRAM_MEMORY_CANARY_PERCENT", "100")
MEMORY_CANARY_SALT = env("TELEGRAM_MEMORY_CANARY_SALT", "memory-v2")
MEMORY_CANARY_INCLUDE_USER_IDS_RAW = env("TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS", "")
MEMORY_CANARY_EXCLUDE_USER_IDS_RAW = env("TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS", "")
MEMORY_TELEMETRY_ENABLED = env("TELEGRAM_MEMORY_TELEMETRY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_TELEMETRY_PATH = pathlib.Path(env("TELEGRAM_MEMORY_TELEMETRY_PATH", "/state/telegram_memory_telemetry.jsonl"))
MEMORY_WRITE_MIN_CONFIDENCE = min(1.0, max(0.0, parse_float(env("TELEGRAM_MEMORY_WRITE_MIN_CONFIDENCE", "0.7"), 0.7)))
MEMORY_WRITE_REQUIRE_EXPLICIT_FOR_USER_NOTES = env("TELEGRAM_MEMORY_WRITE_REQUIRE_EXPLICIT_FOR_USER_NOTES", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_FEEDBACK_RANKING_ENABLED = env("TELEGRAM_MEMORY_FEEDBACK_RANKING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MEMORY_TIER_ORDER: dict[str, int] = {
    "profile": 0,
    "preference": 1,
    "session": 2,
}
MEMORY_SOURCE_TRUST: dict[str, float] = {
    "textbook_email_preference": 0.95,
    "telegram_user_note": 0.9,
    "user_note": 0.85,
    "textbook_request": 0.8,
    "textbook_ingest": 0.75,
    "legacy_note": 0.7,
}
MEMORY_WRITE_TRUSTED_SOURCES: set[str] = {
    "textbook_email_preference",
    "textbook_request",
    "textbook_ingest",
}
USER_REGISTRY_PATH = pathlib.Path(env("TELEGRAM_USER_REGISTRY", "/state/telegram_users.json"))
BOOTSTRAP_ADMINS_RAW = env("TELEGRAM_BOOTSTRAP_ADMINS")
QUARANTINE_CLEAR_ALL_ADMINS_RAW = env("TELEGRAM_NOTIFY_QUARANTINE_CLEAR_ALL_ADMINS", BOOTSTRAP_ADMINS_RAW)
DEFAULT_ADMIN_NOTIFY_TOPICS_RAW = env("TELEGRAM_DEFAULT_ADMIN_NOTIFY_TOPICS", "critical,ops,audit")
EMERGENCY_ADMIN_USERNAMES_RAW = env("TELEGRAM_EMERGENCY_ADMIN_USERNAMES", "<your_admin_username>")
NOTIFY_POLICY_ENABLED = env("TELEGRAM_NOTIFICATIONS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
NOTIFY_POLICY_CRITICAL_ONLY = env("TELEGRAM_NOTIFY_CRITICAL_ONLY", "true").lower() in {"1", "true", "yes", "on"}
NOTIFY_POLICY_MIN_PRIORITY = parse_int(env("TELEGRAM_NOTIFY_MIN_PRIORITY", "5"), 5)
NOTIFY_POLICY_MAX_MESSAGE_CHARS = parse_int(env("TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS", "280"), 280)
NOTIFY_POLICY_DROP_PATTERNS_RAW = env("TELEGRAM_NOTIFY_DROP_PATTERNS", "smoke test,direct fanout,log check")
NOTIFY_POLICY_DEDUPE_WINDOW_SECONDS = parse_int(env("TELEGRAM_DEDUPE_WINDOW_SECONDS", "120"), 120)
NOTIFY_POLICY_DEDUPE_BY_TOPIC_RAW = env("TELEGRAM_DEDUPE_WINDOW_SECONDS_BY_TOPIC", "ops-alerts=180,ops-audit=45,media-alerts=90")
POLICY_FILE = env("POLICY_FILE", "/app/policy/policy.v1.yaml")
NOTIFY_STATS_PATH = pathlib.Path(env("TELEGRAM_NOTIFY_STATS_STATE", "/ntfy-state/telegram_notify_stats.json"))
NOTIFY_STATS_SQLITE_PATH = pathlib.Path(
    env("TELEGRAM_NOTIFY_STATS_SQLITE_PATH", str(NOTIFY_STATS_PATH.with_name("telegram_state.db")))
)
NTFY_PUBLISH_BASE = env("NTFY_PUBLISH_BASE", "http://ntfy").rstrip("/")
NOTIFY_VALIDATE_TOPIC = env("TELEGRAM_NOTIFY_VALIDATE_TOPIC", "ops-validate")
NOTIFY_VALIDATE_TIMEOUT_SECONDS = parse_int(env("TELEGRAM_NOTIFY_VALIDATE_TIMEOUT_SECONDS", "20"), 20)
NOTIFY_VALIDATE_POLL_SECONDS = max(0.2, float(env("TELEGRAM_NOTIFY_VALIDATE_POLL_SECONDS", "1.0") or "1.0"))
NOTIFY_VALIDATE_PUBLISH_FALLBACKS_RAW = env(
    "TELEGRAM_NOTIFY_VALIDATE_PUBLISH_FALLBACKS",
    "http://ntfy:80,http://127.0.0.1:8091",
)
DIGEST_QUEUE_PATH = pathlib.Path(env("TELEGRAM_DIGEST_QUEUE_STATE", "/ntfy-state/telegram_digest_queue.json"))
INCIDENT_STATE_PATH = pathlib.Path(env("TELEGRAM_INCIDENT_STATE", "/ntfy-state/telegram_incidents.json"))
REQTRACK_STATE_PATH = pathlib.Path(env("TELEGRAM_REQTRACK_STATE", "/ntfy-state/media-request-tracker-state.json"))
DELIVERY_STATE_PATH = pathlib.Path(env("TELEGRAM_DELIVERY_STATE", "/ntfy-state/telegram_delivery_state.json"))
DELIVERY_SQLITE_PATH = pathlib.Path(
    env("TELEGRAM_DELIVERY_SQLITE_PATH", str(NOTIFY_STATS_SQLITE_PATH))
)
MEDIA_QUARANTINE_BYPASS_TTL_SECONDS = parse_int(env("TELEGRAM_MEDIA_QUARANTINE_BYPASS_TTL_SECONDS", "1800"), 1800)
MEDIA_FIRST_SEEN_STATE_PATH = pathlib.Path(
    env("TELEGRAM_MEDIA_FIRST_SEEN_STATE", "/ntfy-state/telegram_media_first_seen.json")
)
MEDIA_FIRST_SEEN_SQLITE_PATH = pathlib.Path(
    env("TELEGRAM_MEDIA_FIRST_SEEN_SQLITE_PATH", str(NOTIFY_STATS_SQLITE_PATH))
)
INCIDENT_ACK_TTL_SECONDS = parse_int(env("TELEGRAM_INCIDENT_ACK_TTL_SECONDS", "21600"), 21600)
INCIDENT_LIST_LIMIT = parse_int(env("TELEGRAM_INCIDENT_LIST_LIMIT", "8"), 8)
REQTRACK_INCIDENT_LIST_LIMIT = parse_int(env("TELEGRAM_REQTRACK_INCIDENT_LIST_LIMIT", "8"), 8)
REQTRACK_DEFAULT_SNOOZE_MINUTES = parse_int(env("TELEGRAM_REQTRACK_SNOOZE_MINUTES", "120"), 120)
REQTRACK_DEFAULT_KPI_WINDOW_HOURS = parse_int(env("TELEGRAM_REQTRACK_KPI_WINDOW_HOURS", "24"), 24)
REQTRACK_WEEKLY_KPI_WINDOW_HOURS = parse_int(env("TELEGRAM_REQTRACK_KPI_WEEKLY_WINDOW_HOURS", "168"), 168)
REQTRACK_JSON_CHUNK_MAX_CHARS = max(
    300,
    min(
        max(300, TELEGRAM_MESSAGE_REVIEW_MAX_CHARS - 32),
        parse_int(env("TELEGRAM_REQTRACK_JSON_CHUNK_MAX_CHARS", str(max(300, TELEGRAM_MESSAGE_REVIEW_MAX_CHARS - 120))), max(300, TELEGRAM_MESSAGE_REVIEW_MAX_CHARS - 120)),
    ),
)
PROFILE_SEED_PATH = pathlib.Path(env("TELEGRAM_PROFILE_SEED_PATH", "/work/discord-seed/discord_user_profiles.json"))
PROFILE_MAX_CHARS = parse_int(env("TELEGRAM_PROFILE_MAX_CHARS", "2200"), 2200)
PROFILE_PREVIEW_CHARS = parse_int(env("TELEGRAM_PROFILE_PREVIEW_CHARS", "220"), 220)
PROFILE_MATCH_HIGH_CONFIDENCE_MIN_SCORE = parse_int(env("TELEGRAM_PROFILE_MATCH_HIGH_CONFIDENCE_MIN_SCORE", "95"), 95)
PROFILE_MATCH_HIGH_CONFIDENCE_MIN_GAP = parse_int(env("TELEGRAM_PROFILE_MATCH_HIGH_CONFIDENCE_MIN_GAP", "15"), 15)
CHILD_GUARDRAILS_ENABLED = env("TELEGRAM_CHILD_GUARDRAILS_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
CHILD_ACCOUNT_ADULT_MIN_AGE = max(13, parse_int(env("TELEGRAM_CHILD_ACCOUNT_ADULT_MIN_AGE", "18"), 18))
CHILD_MEDIA_ALLOWED_RATINGS_RAW = env(
    "TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS",
    "G,PG,TV-Y,TV-Y7,TV-G,TV-PG",
)
CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13_RAW = env("TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13", "")
CHILD_MEDIA_ALLOWED_RATINGS_13_15_RAW = env("TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_13_15", "")
CHILD_MEDIA_ALLOWED_RATINGS_16_17_RAW = env("TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_16_17", "")
CHILD_MEDIA_DENY_UNKNOWN_RATINGS = env("TELEGRAM_CHILD_MEDIA_DENY_UNKNOWN_RATINGS", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CHILD_MEDIA_BLOCK_IF_ADULT_FLAG = env("TELEGRAM_CHILD_MEDIA_BLOCK_IF_ADULT_FLAG", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CHILD_MEDIA_BLOCKED_GENRE_IDS_RAW = env("TELEGRAM_CHILD_MEDIA_BLOCKED_GENRE_IDS", "27")
CHILD_MEDIA_BLOCKED_KEYWORDS_RAW = env(
    "TELEGRAM_CHILD_MEDIA_BLOCKED_KEYWORDS",
    "nudity,sexual content,explicit sex,rape,gore,graphic violence,torture,profanity,blasphemy,drug use,substance abuse,self-harm,suicide,disturbing scenes",
)
NOTIFY_POLICY_LOADED_AT = datetime.now(timezone.utc).isoformat()


if not TOKEN:
    print("[telegram-bridge] TELEGRAM_BOT_TOKEN is required", flush=True)
    sys.exit(1)

BOT_API_BASE = f"https://api.telegram.org/bot{TOKEN}"
BOT_FILE_BASE = f"https://api.telegram.org/file/bot{TOKEN}"


def parse_allowed_ids(raw: str) -> set[int]:
    if not raw:
        return set()
    values = [item.strip() for item in raw.split(",") if item.strip()]
    ids = set()
    for value in values:
        try:
            ids.add(int(value))
        except ValueError:
            print(f"[telegram-bridge] ignoring invalid user id '{value}'", flush=True)
    return ids


ALLOWED_IDS = parse_allowed_ids(ALLOWED_IDS_RAW)
BOOTSTRAP_ADMINS = parse_allowed_ids(BOOTSTRAP_ADMINS_RAW)
QUARANTINE_CLEAR_ALL_ADMINS = parse_allowed_ids(QUARANTINE_CLEAR_ALL_ADMINS_RAW)
MEMORY_CANARY_INCLUDE_USER_IDS = parse_allowed_ids(MEMORY_CANARY_INCLUDE_USER_IDS_RAW)
MEMORY_CANARY_EXCLUDE_USER_IDS = parse_allowed_ids(MEMORY_CANARY_EXCLUDE_USER_IDS_RAW)
MEMORY_CANARY_PERCENT = max(0, min(100, parse_int(MEMORY_CANARY_PERCENT_RAW, 100)))

NOTIFICATION_TOPIC_LABELS: dict[str, str] = {
    "critical": "Critical incidents",
    "ops": "Operations alerts",
    "audit": "Audit/security alerts",
    "ai": "AI/system updates",
    "media": "Media request and readiness alerts",
    "maintenance": "Maintenance notices",
}
NOTIFY_TEST_CATEGORY_ICON: dict[str, str] = {
    "critical": "🚨",
    "ops": "ℹ️",
    "audit": "ℹ️",
    "ai": "ℹ️",
    "maintenance": "ℹ️",
}


def parse_csv_strings(raw: str) -> list[str]:
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for item in str(raw or "").split(","):
        token = item.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError:
            continue
    return values


def parse_command_keys(raw: str) -> set[str]:
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def normalize_slash_command_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if not token.startswith("/"):
        token = f"/{token}"
    if "@" in token:
        token = token.split("@", 1)[0]
    return token


def parse_topic_window_overrides(raw: str) -> dict[str, int]:
    overrides: dict[str, int] = {}
    for part in (raw or "").split(","):
        item = part.strip()
        if not item or "=" not in item:
            continue
        topic, value = item.split("=", 1)
        topic = topic.strip()
        value = value.strip()
        if not topic or not value:
            continue
        try:
            seconds = int(value)
        except ValueError:
            continue
        if seconds > 0:
            overrides[topic] = seconds
    return overrides


def load_notify_stats_state() -> dict[str, Any]:
    def _empty_state() -> dict[str, Any]:
        return {"events": [], "updated_at": ""}

    def _from_json_file() -> dict[str, Any]:
        if not NOTIFY_STATS_PATH.exists():
            return _empty_state()
        try:
            data = json.loads(NOTIFY_STATS_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return _empty_state()
            events = data.get("events")
            if not isinstance(events, list):
                data["events"] = []
            return data
        except Exception:
            return _empty_state()

    def _from_sqlite_file() -> dict[str, Any]:
        if not NOTIFY_STATS_SQLITE_PATH.exists():
            return _empty_state()
        conn = None
        try:
            conn = sqlite3.connect(str(NOTIFY_STATS_SQLITE_PATH))
            row = conn.execute("SELECT payload FROM state_kv WHERE key = ?", ("notify_stats",)).fetchone()
            if not row:
                return _empty_state()
            payload = json.loads(str(row[0]))
            if not isinstance(payload, dict):
                return _empty_state()
            events = payload.get("events")
            if not isinstance(events, list):
                payload["events"] = []
            return payload
        except Exception:
            return _empty_state()
        finally:
            if conn is not None:
                conn.close()

    def _max_event_ts(state_obj: dict[str, Any]) -> int:
        raw = state_obj.get("events") if isinstance(state_obj, dict) else []
        events = raw if isinstance(raw, list) else []
        latest = 0
        for event in events:
            if not isinstance(event, dict):
                continue
            try:
                ts = int(event.get("ts", 0) or 0)
            except (TypeError, ValueError):
                continue
            if ts > latest:
                latest = ts
        return latest

    json_state = _from_json_file()
    sqlite_state = _from_sqlite_file()
    if _max_event_ts(sqlite_state) > _max_event_ts(json_state):
        return sqlite_state
    return json_state


def load_digest_queue_state() -> dict[str, Any]:
    if not DIGEST_QUEUE_PATH.exists():
        return {"users": {}, "updated_at": ""}
    try:
        data = json.loads(DIGEST_QUEUE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"users": {}, "updated_at": ""}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data
    except Exception:
        return {"users": {}, "updated_at": ""}


def load_delivery_state() -> dict[str, Any]:
    def _empty_state() -> dict[str, Any]:
        return {"users": {}, "updated_at": ""}

    def _from_json_file() -> dict[str, Any]:
        if not DELIVERY_STATE_PATH.exists():
            return _empty_state()
        try:
            data = json.loads(DELIVERY_STATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return _empty_state()
            users = data.get("users")
            if not isinstance(users, dict):
                data["users"] = {}
            return data
        except Exception:
            return _empty_state()

    def _from_sqlite_file() -> dict[str, Any]:
        if not DELIVERY_SQLITE_PATH.exists():
            return _empty_state()
        conn = None
        try:
            conn = sqlite3.connect(str(DELIVERY_SQLITE_PATH))
            row = conn.execute("SELECT payload FROM state_kv WHERE key = ?", ("delivery",)).fetchone()
            if not row:
                return _empty_state()
            payload = json.loads(str(row[0]))
            if not isinstance(payload, dict):
                return _empty_state()
            users = payload.get("users")
            if not isinstance(users, dict):
                payload["users"] = {}
            return payload
        except Exception:
            return _empty_state()
        finally:
            if conn is not None:
                conn.close()

    def _score(state_obj: dict[str, Any]) -> int:
        score = 0
        users_raw = state_obj.get("users") if isinstance(state_obj, dict) else {}
        users = users_raw if isinstance(users_raw, dict) else {}
        for item in users.values():
            if not isinstance(item, dict):
                continue
            for key in ("notify_delivery_last_failed_at", "notify_delivery_last_sent_at", "notify_quarantine_until"):
                try:
                    score = max(score, int(item.get(key, 0) or 0))
                except (TypeError, ValueError):
                    continue
        marker = state_obj.get("media_quarantine_bypass_once") if isinstance(state_obj, dict) else None
        if isinstance(marker, dict):
            for key in ("armed_at", "consumed_at", "expires_at"):
                try:
                    score = max(score, int(marker.get(key, 0) or 0))
                except (TypeError, ValueError):
                    continue
        return score

    json_state = _from_json_file()
    sqlite_state = _from_sqlite_file()
    if _score(sqlite_state) >= _score(json_state):
        return sqlite_state
    return json_state


def load_media_first_seen_state() -> dict[str, Any]:
    def _empty_state() -> dict[str, Any]:
        return {"items": {}, "updated_at": ""}

    def _from_json_file() -> dict[str, Any]:
        if not MEDIA_FIRST_SEEN_STATE_PATH.exists():
            return _empty_state()
        try:
            data = json.loads(MEDIA_FIRST_SEEN_STATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return _empty_state()
            items = data.get("items")
            if not isinstance(items, dict):
                data["items"] = {}
            return data
        except Exception:
            return _empty_state()

    def _from_sqlite_file() -> dict[str, Any]:
        if not MEDIA_FIRST_SEEN_SQLITE_PATH.exists():
            return _empty_state()
        conn = None
        try:
            conn = sqlite3.connect(str(MEDIA_FIRST_SEEN_SQLITE_PATH))
            row = conn.execute("SELECT payload FROM state_kv WHERE key = ?", ("media_first_seen",)).fetchone()
            if not row:
                return _empty_state()
            payload = json.loads(str(row[0]))
            if not isinstance(payload, dict):
                return _empty_state()
            items = payload.get("items")
            if not isinstance(items, dict):
                payload["items"] = {}
            return payload
        except Exception:
            return _empty_state()
        finally:
            if conn is not None:
                conn.close()

    def _max_seen_ts(state_obj: dict[str, Any]) -> int:
        raw = state_obj.get("items") if isinstance(state_obj, dict) else {}
        items = raw if isinstance(raw, dict) else {}
        latest = 0
        for value in items.values():
            if not isinstance(value, dict):
                continue
            try:
                first_seen = int(value.get("first_seen", 0) or 0)
                last_seen = int(value.get("last_seen", first_seen) or first_seen)
            except (TypeError, ValueError):
                continue
            candidate = max(first_seen, last_seen)
            if candidate > latest:
                latest = candidate
        return latest

    json_state = _from_json_file()
    sqlite_state = _from_sqlite_file()
    if _max_seen_ts(sqlite_state) > _max_seen_ts(json_state):
        return sqlite_state
    return json_state


def save_media_first_seen_state(state: dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        state = {"items": {}, "updated_at": utc_now()}
    if "updated_at" not in state:
        state["updated_at"] = utc_now()

    try:
        if MEDIA_FIRST_SEEN_SQLITE_PATH.exists():
            conn = sqlite3.connect(str(MEDIA_FIRST_SEEN_SQLITE_PATH))
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_kv (
                        key TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO state_kv(key, payload, updated_at)
                    VALUES(?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                    """,
                    ("media_first_seen", json.dumps(state, ensure_ascii=False), utc_now()),
                )
                conn.commit()
                return True
            finally:
                conn.close()
    except Exception as exc:
        print(f"[telegram-bridge] failed to save media-first-seen sqlite state: {exc}", flush=True)

    try:
        MEDIA_FIRST_SEEN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEDIA_FIRST_SEEN_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to save media-first-seen json state: {exc}", flush=True)
        return False


def normalize_media_first_seen_lookup_text(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value)


def media_first_seen_title_key_part(key: str) -> str:
    parts = str(key or "").split("|")
    if len(parts) >= 3:
        return str(parts[2]).strip().lower()
    return ""


def clear_media_first_seen_entries(clear_all: bool, title_query: str) -> tuple[int, int]:
    state = load_media_first_seen_state()
    items_raw = state.get("items") if isinstance(state, dict) else {}
    items = items_raw if isinstance(items_raw, dict) else {}
    total = len(items)
    if total <= 0:
        return 0, 0

    target_norm = normalize_media_first_seen_lookup_text(title_query)
    updated: dict[str, Any] = {}
    removed = 0
    for key, value in items.items():
        if not isinstance(key, str):
            continue
        should_remove = False
        if clear_all:
            should_remove = True
        else:
            key_title = media_first_seen_title_key_part(key)
            if key_title and target_norm and (target_norm in key_title or key_title in target_norm):
                should_remove = True
        if should_remove:
            removed += 1
            continue
        updated[key] = value

    if removed <= 0:
        return 0, total

    state["items"] = updated
    state["updated_at"] = utc_now()
    save_media_first_seen_state(state)
    return removed, total


def save_delivery_state(state: dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        state = {"users": {}, "updated_at": utc_now()}
    if "updated_at" not in state:
        state["updated_at"] = utc_now()

    try:
        if DELIVERY_SQLITE_PATH.exists():
            conn = sqlite3.connect(str(DELIVERY_SQLITE_PATH))
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_kv (
                        key TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO state_kv(key, payload, updated_at)
                    VALUES(?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                    """,
                    ("delivery", json.dumps(state, ensure_ascii=False), utc_now()),
                )
                conn.commit()
                return True
            finally:
                conn.close()
    except Exception as exc:
        print(f"[telegram-bridge] failed to save delivery sqlite state: {exc}", flush=True)

    try:
        DELIVERY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DELIVERY_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to save delivery state: {exc}", flush=True)
        return False


def save_digest_queue_state(state: dict[str, Any]) -> bool:
    try:
        DIGEST_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DIGEST_QUEUE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to save digest queue state: {exc}", flush=True)
        return False


def digest_queue_counts(state: dict[str, Any]) -> tuple[int, int]:
    users_raw = state.get("users") if isinstance(state, dict) else {}
    users = users_raw if isinstance(users_raw, dict) else {}
    queued_users = 0
    queued_items = 0
    for entry in users.values():
        if not isinstance(entry, dict):
            continue
        items = entry.get("items")
        if not isinstance(items, list) or not items:
            continue
        queued_users += 1
        queued_items += len(items)
    return queued_users, queued_items


def format_digest_flush_message(items: list[dict[str, Any]]) -> str:
    lines = [
        f"🕘 Deferred alert digest ({len(items)} item{'s' if len(items) != 1 else ''})",
        "Queued during quiet hours:",
    ]
    preview_limit = 12
    for item in items[:preview_limit]:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "unknown")).strip() or "unknown"
        title = " ".join(str(item.get("title", "")).split())
        message = " ".join(str(item.get("message", "")).split())
        summary = title or message or "(no summary)"
        if title and message and not message.lower().startswith(title.lower()):
            summary = f"{title}: {message}"
        if len(summary) > 120:
            summary = summary[:119].rstrip() + "…"
        lines.append(f"- [{topic}] {summary}")
    if len(items) > preview_limit:
        lines.append(f"- …and {len(items) - preview_limit} more")
    return "\n".join(lines)


def flush_deferred_digests_now() -> dict[str, int]:
    state = load_digest_queue_state()
    users_raw = state.get("users") if isinstance(state, dict) else {}
    users = users_raw if isinstance(users_raw, dict) else {}

    attempted = 0
    sent = 0
    failed = 0

    for user_id_raw, entry in list(users.items()):
        if not isinstance(entry, dict):
            continue
        items = entry.get("items")
        if not isinstance(items, list) or not items:
            continue

        attempted += 1
        try:
            target_chat_id = int(user_id_raw)
        except (TypeError, ValueError):
            failed += 1
            continue

        ok = send_message(target_chat_id, format_digest_flush_message(items))
        if ok:
            sent += 1
            users.pop(str(user_id_raw), None)
        else:
            failed += 1

    state["users"] = users
    state["updated_at"] = utc_now()
    state["last_flush"] = {
        "at": utc_now(),
        "attempted": attempted,
        "sent": sent,
        "failed": failed,
    }
    save_digest_queue_state(state)

    _, remaining_items = digest_queue_counts(state)
    return {
        "attempted": attempted,
        "sent": sent,
        "failed": failed,
        "remaining": remaining_items,
    }


def digest_stats_snapshot() -> dict[str, Any]:
    state = load_digest_queue_state()
    queued_users, queued_items = digest_queue_counts(state)
    last_flush_raw = state.get("last_flush") if isinstance(state, dict) else {}
    last_flush = last_flush_raw if isinstance(last_flush_raw, dict) else {}
    return {
        "queued_users": int(queued_users),
        "queued_items": int(queued_items),
        "updated_at": str(state.get("updated_at", "") or ""),
        "last_flush_at": str(last_flush.get("at", "") or ""),
        "last_flush_attempted": int(last_flush.get("attempted", 0) or 0),
        "last_flush_sent": int(last_flush.get("sent", 0) or 0),
        "last_flush_failed": int(last_flush.get("failed", 0) or 0),
    }


def build_digest_stats_report() -> str:
    snapshot = digest_stats_snapshot()
    return "\n".join(
        [
            "Digest queue stats:",
            f"- queued_users: {snapshot['queued_users']}",
            f"- queued_items: {snapshot['queued_items']}",
            f"- state_updated_at: {snapshot['updated_at'] or '(unknown)'} (age={_format_age(snapshot['updated_at'])})",
            f"- last_flush_at: {snapshot['last_flush_at'] or '(never)'} (age={_format_age(snapshot['last_flush_at'])})",
            f"- last_flush_attempted: {snapshot['last_flush_attempted']}",
            f"- last_flush_sent: {snapshot['last_flush_sent']}",
            f"- last_flush_failed: {snapshot['last_flush_failed']}",
        ]
    )


def build_notify_stats_report() -> str:
    data = load_notify_stats_state()
    events_raw = data.get("events", [])
    if not isinstance(events_raw, list):
        events_raw = []
    now = int(time.time())
    threshold = now - 86400

    events: list[dict[str, Any]] = []
    for event in events_raw:
        if not isinstance(event, dict):
            continue
        try:
            ts = int(event.get("ts", 0))
        except (TypeError, ValueError):
            continue
        if ts >= threshold:
            events.append(event)

    sent = 0
    partial = 0
    skipped = 0
    failed = 0
    rate_limited = 0
    deferred = 0
    by_reason: dict[str, int] = {}
    by_topic: dict[str, int] = {}

    for event in events:
        result = str(event.get("result", "")).strip().lower()
        topic = str(event.get("topic", "unknown"))
        reason = str(event.get("reason", "")).strip().lower() or "(none)"
        by_topic[topic] = by_topic.get(topic, 0) + 1
        if result == "sent":
            sent += 1
        elif result == "sent_partial":
            partial += 1
            by_reason[reason] = by_reason.get(reason, 0) + 1
        elif result == "rate_limited":
            rate_limited += 1
            by_reason["rate_limited"] = by_reason.get("rate_limited", 0) + 1
        elif result == "deferred":
            deferred += 1
            by_reason["quiet_hours"] = by_reason.get("quiet_hours", 0) + 1
        elif result == "failed":
            failed += 1
            by_reason[reason] = by_reason.get(reason, 0) + 1
        else:
            skipped += 1
            by_reason[reason] = by_reason.get(reason, 0) + 1

    updated_at = str(data.get("updated_at", "")).strip() or "(unknown)"
    lines = [
        "Notification stats (last 24h):",
        f"- sent: {sent}",
        f"- sent_partial: {partial}",
        f"- skipped: {skipped}",
        f"- failed: {failed}",
        f"- rate_limited: {rate_limited}",
        f"- deferred: {deferred}",
        f"- updated_at: {updated_at}",
    ]

    if by_reason:
        lines.append("- top skip/fail reasons:")
        for reason, count in sorted(by_reason.items(), key=lambda item: (-item[1], item[0]))[:6]:
            lines.append(f"  - {reason}: {count}")

    if by_topic:
        lines.append("- activity by topic:")
        for topic, count in sorted(by_topic.items(), key=lambda item: (-item[1], item[0]))[:8]:
            lines.append(f"  - {topic}: {count}")

    if not events:
        lines.append("- no events in the last 24h")

    return "\n".join(lines)


def is_retryable_delivery_reason(reason: str) -> bool:
    normalized = normalize_text(reason)
    if not normalized or normalized in {"(none)", "none"}:
        return True
    if normalized.startswith("telegram_http_400"):
        return False
    if "chat not found" in normalized or "forbidden" in normalized or "bot was blocked" in normalized:
        return False
    return True


def build_notify_health_report() -> str:
    data = load_notify_stats_state()
    events_raw = data.get("events", [])
    if not isinstance(events_raw, list):
        events_raw = []
    now_ts = int(time.time())
    threshold = now_ts - 86400

    events: list[dict[str, Any]] = []
    for event in events_raw:
        if not isinstance(event, dict):
            continue
        try:
            ts = int(event.get("ts", 0) or 0)
        except (TypeError, ValueError):
            ts = 0
        if ts >= threshold:
            events.append(event)

    total = len(events)
    sent = 0
    sent_partial = 0
    failed = 0
    deferred = 0
    skipped = 0
    recipients_delivered = 0
    topic_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    latest_event_ts = 0

    for event in events:
        result = normalize_text(event.get("result", ""))
        topic = str(event.get("topic", "unknown")).strip() or "unknown"
        reason = normalize_text(event.get("reason", "")) or "(none)"
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        try:
            recipients_delivered += int(event.get("recipients", 0) or 0)
        except (TypeError, ValueError):
            pass
        try:
            latest_event_ts = max(latest_event_ts, int(event.get("ts", 0) or 0))
        except (TypeError, ValueError):
            pass

        if result == "sent":
            sent += 1
        elif result == "sent_partial":
            sent_partial += 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        elif result == "failed":
            failed += 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        elif result in {"deferred", "rate_limited"}:
            deferred += 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        else:
            skipped += 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    delivery_state = load_delivery_state()
    users_raw = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
    users = users_raw if isinstance(users_raw, dict) else {}
    active_quarantine = 0
    delivery_inbox = 0
    permanent_failures = 0
    transient_failures = 0

    for item in users.values():
        if not isinstance(item, dict):
            continue
        try:
            until_ts = int(item.get("notify_quarantine_until", 0) or 0)
        except (TypeError, ValueError):
            until_ts = 0
        if until_ts > now_ts:
            active_quarantine += 1

        reason = str(item.get("notify_delivery_last_reason", "")).strip()
        streak = int(item.get("notify_delivery_fail_streak", 0) or 0)
        try:
            failed_at = int(item.get("notify_delivery_last_failed_at", 0) or 0)
        except (TypeError, ValueError):
            failed_at = 0
        if reason or streak > 0 or failed_at > 0:
            delivery_inbox += 1
            if is_retryable_delivery_reason(reason):
                transient_failures += 1
            else:
                permanent_failures += 1

    marker_raw = delivery_state.get("media_quarantine_bypass_once") if isinstance(delivery_state, dict) else None
    marker = marker_raw if isinstance(marker_raw, dict) else {}
    bypass_enabled = bool(marker.get("enabled", False))
    try:
        bypass_expires_at = int(marker.get("expires_at", 0) or 0)
    except (TypeError, ValueError):
        bypass_expires_at = 0
    bypass_remaining = max(0, bypass_expires_at - now_ts) if bypass_expires_at > 0 else 0

    lines = [
        "Notification health (last 24h):",
        f"- total_events: {total}",
        f"- sent: {sent}",
        f"- sent_partial: {sent_partial}",
        f"- failed: {failed}",
        f"- deferred_or_rate_limited: {deferred}",
        f"- skipped: {skipped}",
        f"- recipient_deliveries: {recipients_delivered}",
        f"- latest_event_age: {format_age_from_unix_ts(latest_event_ts, now_ts=now_ts) if latest_event_ts > 0 else 'none'}",
        f"- delivery_inbox_entries: {delivery_inbox} (transient={transient_failures}, permanent={permanent_failures})",
        f"- quarantined_active: {active_quarantine}",
        f"- media_bypass_once_enabled: {'yes' if bypass_enabled else 'no'}",
        f"- media_bypass_once_expires_in: {bypass_remaining}s",
    ]

    if topic_counts:
        lines.append("- top_topics:")
        for topic, count in sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))[:6]:
            lines.append(f"  - {topic}: {count}")

    if reason_counts:
        lines.append("- top_non_sent_reasons:")
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:6]:
            lines.append(f"  - {reason}: {count}")

    return "\n".join(lines)


def build_media_first_seen_report(limit: int = 10) -> str:
    state = load_media_first_seen_state()
    items_raw = state.get("items") if isinstance(state, dict) else {}
    items = items_raw if isinstance(items_raw, dict) else {}
    now_ts = int(time.time())
    rows: list[tuple[int, int, int, str]] = []
    for key, value in items.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        try:
            first_seen = int(value.get("first_seen", 0) or 0)
            last_seen = int(value.get("last_seen", first_seen) or first_seen)
            event_count = int(value.get("event_count", 1) or 1)
        except (TypeError, ValueError):
            continue
        rows.append((last_seen, first_seen, max(1, event_count), key))

    if not rows:
        return "Media first-seen cache: no tracked Plex availability titles yet."

    rows.sort(key=lambda row: row[0], reverse=True)
    cap = max(1, min(50, int(limit)))
    lines = [
        "Media first-seen cache:",
        f"- entries: {len(rows)}",
        f"- state_updated_at: {str(state.get('updated_at', '') or '(unknown)')}",
    ]
    for last_seen, first_seen, event_count, key in rows[:cap]:
        lines.append(
            f"- key={key} seen={event_count} first_age={format_age_from_unix_ts(first_seen, now_ts=now_ts)} last_age={format_age_from_unix_ts(last_seen, now_ts=now_ts)}"
        )
    if len(rows) > cap:
        lines.append(f"- ...and {len(rows) - cap} more")
    return "\n".join(lines)


def normalize_publish_base(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if not value.startswith("http://") and not value.startswith("https://"):
        value = f"http://{value}"
    return value.rstrip("/")


def parse_publish_base_candidates() -> list[str]:
    ordered: list[str] = []

    primary = normalize_publish_base(NTFY_PUBLISH_BASE)
    if primary:
        ordered.append(primary)

    for item in str(NOTIFY_VALIDATE_PUBLISH_FALLBACKS_RAW or "").split(","):
        candidate = normalize_publish_base(item)
        if candidate:
            ordered.append(candidate)

    deduped: list[str] = []
    for value in ordered:
        if value not in deduped:
            deduped.append(value)
    return deduped


def publish_notify_validate_probe(probe_id: str, requested_by: int) -> tuple[bool, str]:
    topic = str(NOTIFY_VALIDATE_TOPIC or "ops-alerts").strip() or "ops-alerts"
    encoded_topic = urllib.parse.quote(topic, safe="")
    body = (
        f"notify_validate_probe_id={probe_id}\n"
        f"source=telegram_notify_validate\n"
        f"requested_by={requested_by}\n"
    ).encode("utf-8")
    errors: list[str] = []

    for base in parse_publish_base_candidates():
        publish_url = f"{base}/{encoded_topic}"
        request = urllib.request.Request(
            url=publish_url,
            data=body,
            headers={
                "Title": f"Telegram notify validate {probe_id}",
                "Priority": "5",
                "Tags": "white_check_mark,mag",
                "Content-Type": "text/plain; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                pass
            return True, f"published:{base}"
        except urllib.error.HTTPError as exc:
            errors.append(f"{base}:http_{exc.code}")
        except Exception as exc:
            errors.append(f"{base}:{exc}")

    details = "; ".join(errors[:4]) if errors else "no_publish_candidates"
    if len(details) > 300:
        details = details[:299].rstrip() + "…"
    return False, f"publish_error:{details}"


def find_notify_probe_event(probe_id: str, min_ts: int) -> dict[str, Any] | None:
    state = load_notify_stats_state()
    events_raw = state.get("events", []) if isinstance(state, dict) else []
    events = events_raw if isinstance(events_raw, list) else []
    topic = str(NOTIFY_VALIDATE_TOPIC or "ops-alerts").strip() or "ops-alerts"

    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        try:
            ts = int(event.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < max(0, int(min_ts)):
            continue
        if str(event.get("topic", "")).strip() != topic:
            continue
        if str(event.get("probe_id", "")).strip() != probe_id:
            continue
        return event
    return None


def wait_for_notify_validate_event(probe_id: str, min_ts: int) -> dict[str, Any] | None:
    timeout_seconds = max(2, int(NOTIFY_VALIDATE_TIMEOUT_SECONDS))
    poll_seconds = max(0.2, float(NOTIFY_VALIDATE_POLL_SECONDS))
    deadline = time.time() + timeout_seconds
    while time.time() <= deadline:
        event = find_notify_probe_event(probe_id=probe_id, min_ts=min_ts)
        if event is not None:
            return event
        time.sleep(poll_seconds)
    return None


def run_notify_validate_probe(request_user_id: int) -> dict[str, Any]:
    started_at = time.time()
    started_ts = int(started_at)
    probe_id = f"nv-{started_ts}-{int(request_user_id)}"
    topic = str(NOTIFY_VALIDATE_TOPIC or "ops-alerts").strip() or "ops-alerts"

    published, publish_detail = publish_notify_validate_probe(probe_id=probe_id, requested_by=request_user_id)
    if not published:
        return {
            "ok": False,
            "stage": "publish",
            "probe_id": probe_id,
            "topic": topic,
            "detail": publish_detail,
            "latency_seconds": round(max(0.0, time.time() - started_at), 1),
        }

    event = wait_for_notify_validate_event(probe_id=probe_id, min_ts=started_ts)
    if event is None:
        return {
            "ok": False,
            "stage": "wait",
            "probe_id": probe_id,
            "topic": topic,
            "detail": "timeout_waiting_for_fanout_event",
            "latency_seconds": round(max(0.0, time.time() - started_at), 1),
        }

    result = str(event.get("result", "")).strip().lower()
    reason = str(event.get("reason", "")).strip() or "(none)"
    try:
        recipients = int(event.get("recipients", 0) or 0)
    except (TypeError, ValueError):
        recipients = 0
    passed = result in {"sent", "sent_partial", "deferred"}
    return {
        "ok": bool(passed),
        "stage": "fanout",
        "probe_id": probe_id,
        "topic": topic,
        "detail": result or "unknown_result",
        "reason": reason,
        "recipients": int(recipients),
        "latency_seconds": round(max(0.0, time.time() - started_at), 1),
    }


def format_notify_validate_report(summary: dict[str, Any]) -> str:
    ok = bool(summary.get("ok", False))
    status = "PASS ✅" if ok else "FAIL ❌"
    lines = [
        f"Notify validate: {status}",
        f"- stage: {summary.get('stage', '(unknown)')}",
        f"- topic: {summary.get('topic', '(unknown)')}",
        f"- probe_id: {summary.get('probe_id', '(unknown)')}",
        f"- detail: {summary.get('detail', '(unknown)')}",
        f"- reason: {summary.get('reason', '(none)')}",
        f"- recipients: {int(summary.get('recipients', 0) or 0)}",
        f"- latency_seconds: {summary.get('latency_seconds', 'n/a')}",
    ]
    if not ok:
        lines.append("- tip: check /notify delivery list, /notify quarantine list, and /notify stats")
    return "\n".join(lines)


def _parse_utc_timestamp(raw: str) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _format_age(raw_timestamp: str) -> str:
    parsed = _parse_utc_timestamp(raw_timestamp)
    if not parsed:
        return "unknown"
    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_seconds = max(0, int((now - parsed).total_seconds()))
    if age_seconds < 60:
        return f"{age_seconds}s"
    if age_seconds < 3600:
        return f"{age_seconds // 60}m"
    return f"{age_seconds // 3600}h"


def build_status_snapshot() -> dict[str, Any]:
    users = USER_REGISTRY.get("users") if isinstance(USER_REGISTRY, dict) else {}
    if not isinstance(users, dict):
        users = {}
    active_users = sum(1 for rec in users.values() if isinstance(rec, dict) and str(rec.get("status", "active")) == "active")
    admin_users = sum(
        1
        for rec in users.values()
        if isinstance(rec, dict)
        and str(rec.get("status", "active")) == "active"
        and str(rec.get("role", "user")) == "admin"
    )

    notify_stats = load_notify_stats_state()
    notify_updated_at = str(notify_stats.get("updated_at", "") or "")
    incident_state = load_incident_state()
    incident_updated_at = str(incident_state.get("updated_at", "") or "")
    digest_state = load_digest_queue_state()
    digest_updated_at = str(digest_state.get("updated_at", "") or "")
    digest_users, digest_items = digest_queue_counts(digest_state)

    notify_events = notify_stats.get("events", [])
    if not isinstance(notify_events, list):
        notify_events = []
    last_24h_threshold = int(time.time()) - 86400

    outcome_counts = {
        "sent": 0,
        "sent_partial": 0,
        "failed": 0,
        "rate_limited": 0,
        "deferred": 0,
        "skipped": 0,
    }
    for event in notify_events:
        if not isinstance(event, dict):
            continue
        try:
            ts = int(event.get("ts", 0))
        except (TypeError, ValueError):
            continue
        if ts < last_24h_threshold:
            continue
        result = str(event.get("result", "")).strip().lower()
        if result in outcome_counts:
            outcome_counts[result] += 1
        else:
            outcome_counts["skipped"] += 1

    memory_users = MEMORY_STATE.get("users") if isinstance(MEMORY_STATE, dict) else {}
    if not isinstance(memory_users, dict):
        memory_users = {}
    memory_conflicts_total = 0
    memory_conflicts_stale = 0
    memory_conflicts_oldest_age_seconds = 0
    for entry in memory_users.values():
        if not isinstance(entry, dict):
            continue
        conflict_summary = summarize_user_memory_conflicts(entry)
        memory_conflicts_total += int(conflict_summary.get("total", 0) or 0)
        memory_conflicts_stale += int(conflict_summary.get("stale", 0) or 0)
        memory_conflicts_oldest_age_seconds = max(
            memory_conflicts_oldest_age_seconds,
            int(conflict_summary.get("oldest_age_seconds", 0) or 0),
        )

    return {
        "notifications_policy_enabled": bool(NOTIFY_POLICY_ENABLED),
        "notify_critical_only": bool(NOTIFY_POLICY_CRITICAL_ONLY),
        "notify_min_priority": int(NOTIFY_POLICY_MIN_PRIORITY),
        "users_active": int(active_users),
        "admins_active": int(admin_users),
        "notify_stats_updated_at": notify_updated_at,
        "notify_stats_age": _format_age(notify_updated_at),
        "incident_state_updated_at": incident_updated_at,
        "incident_state_age": _format_age(incident_updated_at),
        "digest_queue_users": int(digest_users),
        "digest_queue_items": int(digest_items),
        "digest_state_updated_at": digest_updated_at,
        "digest_state_age": _format_age(digest_updated_at),
        "delivery_outcomes_24h": outcome_counts,
        "memory_conflicts_total": int(memory_conflicts_total),
        "memory_conflicts_stale": int(memory_conflicts_stale),
        "memory_conflicts_oldest_age_seconds": int(memory_conflicts_oldest_age_seconds),
        "memory_canary_enabled": bool(MEMORY_CANARY_ENABLED),
        "memory_canary_percent": int(MEMORY_CANARY_PERCENT),
        "memory_canary_include_users": int(len(MEMORY_CANARY_INCLUDE_USER_IDS)),
        "memory_canary_exclude_users": int(len(MEMORY_CANARY_EXCLUDE_USER_IDS)),
    }


def build_status_report() -> str:
    snapshot = build_status_snapshot()
    outcomes = snapshot.get("delivery_outcomes_24h") if isinstance(snapshot, dict) else {}
    if not isinstance(outcomes, dict):
        outcomes = {}

    lines = [
        "Bridge status:",
        f"- notifications_policy: {'on' if snapshot.get('notifications_policy_enabled') else 'off'}",
        f"- notify_critical_only: {'on' if snapshot.get('notify_critical_only') else 'off'}",
        f"- notify_min_priority: {snapshot.get('notify_min_priority', NOTIFY_POLICY_MIN_PRIORITY)}",
        f"- users_active: {snapshot.get('users_active', 0)}",
        f"- admins_active: {snapshot.get('admins_active', 0)}",
        f"- notify_stats_updated: {snapshot.get('notify_stats_updated_at') or '(unknown)'} (age={snapshot.get('notify_stats_age', 'unknown')})",
        f"- incident_state_updated: {snapshot.get('incident_state_updated_at') or '(unknown)'} (age={snapshot.get('incident_state_age', 'unknown')})",
        f"- digest_queue: users={int(snapshot.get('digest_queue_users', 0))}, items={int(snapshot.get('digest_queue_items', 0))}",
        f"- digest_state_updated: {snapshot.get('digest_state_updated_at') or '(unknown)'} (age={snapshot.get('digest_state_age', 'unknown')})",
        f"- memory_conflicts_total: {int(snapshot.get('memory_conflicts_total', 0))}",
        f"- memory_conflicts_stale: {int(snapshot.get('memory_conflicts_stale', 0))}",
        f"- memory_conflicts_oldest_age_s: {int(snapshot.get('memory_conflicts_oldest_age_seconds', 0))}",
        f"- memory_canary: {'on' if snapshot.get('memory_canary_enabled') else 'off'} ({int(snapshot.get('memory_canary_percent', 100))}% cohort)",
        f"- memory_canary_overrides: include={int(snapshot.get('memory_canary_include_users', 0))}, exclude={int(snapshot.get('memory_canary_exclude_users', 0))}",
        "- delivery_outcomes_24h:",
        f"  - sent: {int(outcomes.get('sent', 0))}",
        f"  - sent_partial: {int(outcomes.get('sent_partial', 0))}",
        f"  - failed: {int(outcomes.get('failed', 0))}",
        f"  - rate_limited: {int(outcomes.get('rate_limited', 0))}",
        f"  - deferred: {int(outcomes.get('deferred', 0))}",
        f"  - skipped: {int(outcomes.get('skipped', 0))}",
    ]
    return "\n".join(lines)


def build_status_json_report() -> str:
    return json.dumps(build_status_snapshot(), ensure_ascii=False, sort_keys=True)


def probe_n8n_reachability() -> dict[str, Any]:
    base = str(N8N_BASE or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "detail": "n8n_base_missing"}

    candidates = [
        f"{base}/healthz",
        f"{base}/healthz/readiness",
        f"{base}/",
    ]
    checked: list[str] = []
    for url in candidates:
        try:
            with urllib.request.urlopen(url, timeout=8) as response:
                code = int(getattr(response, "status", 200) or 200)
            return {"ok": code < 500, "detail": f"http_{code}", "url": url}
        except urllib.error.HTTPError as exc:
            checked.append(f"{url}:http_{exc.code}")
        except Exception as exc:
            checked.append(f"{url}:{exc}")

    detail = "; ".join(checked[:3]) if checked else "unreachable"
    if len(detail) > 220:
        detail = detail[:219].rstrip() + "…"
    return {"ok": False, "detail": detail}


def latest_notify_fanout_snapshot(now_ts: int | None = None) -> dict[str, Any] | None:
    state = load_notify_stats_state()
    events_raw = state.get("events", []) if isinstance(state, dict) else []
    events = events_raw if isinstance(events_raw, list) else []
    now = int(now_ts or time.time())

    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        result = normalize_text(event.get("result", ""))
        if result not in {"sent", "sent_partial", "deferred"}:
            continue
        try:
            ts = int(event.get("ts", 0) or 0)
        except (TypeError, ValueError):
            ts = 0
        try:
            recipients = int(event.get("recipients", 0) or 0)
        except (TypeError, ValueError):
            recipients = 0
        topic = str(event.get("topic", "unknown") or "unknown")
        return {
            "ts": ts,
            "age": format_age_from_unix_ts(ts, now_ts=now) if ts > 0 else "unknown",
            "topic": topic,
            "result": result,
            "recipients": recipients,
            "probe_id": str(event.get("probe_id", "") or ""),
        }
    return None


def build_health_snapshot(request_user_id: int, include_validate_probe: bool = True) -> dict[str, Any]:
    snapshot = build_status_snapshot()
    n8n = probe_n8n_reachability()
    now_ts = int(time.time())
    fanout = latest_notify_fanout_snapshot(now_ts=now_ts)
    validate = run_notify_validate_probe(request_user_id=request_user_id) if include_validate_probe else {}
    return {
        "checked_at": utc_now(),
        "bridge": snapshot,
        "n8n": n8n,
        "notify_validate": validate,
        "last_fanout": fanout,
    }


def build_health_report(request_user_id: int, include_validate_probe: bool = True) -> str:
    health = build_health_snapshot(request_user_id=request_user_id, include_validate_probe=include_validate_probe)
    bridge_raw = health.get("bridge")
    bridge: dict[str, Any] = bridge_raw if isinstance(bridge_raw, dict) else {}
    n8n_raw = health.get("n8n")
    n8n: dict[str, Any] = n8n_raw if isinstance(n8n_raw, dict) else {}
    validate_raw = health.get("notify_validate")
    validate: dict[str, Any] = validate_raw if isinstance(validate_raw, dict) else {}
    fanout_raw = health.get("last_fanout")
    fanout: dict[str, Any] = fanout_raw if isinstance(fanout_raw, dict) else {}

    validate_ok = bool(validate.get("ok", False)) if include_validate_probe else True
    n8n_ok = bool(n8n.get("ok", False))
    overall_ok = bool(n8n_ok and validate_ok)
    status_label = "PASS ✅" if overall_ok else "DEGRADED ⚠️"

    lines = [
        f"System health: {status_label}",
        f"- checked_at: {health.get('checked_at', '(unknown)')}",
        f"- bridge_users_active: {int(bridge.get('users_active', 0) or 0)}",
        f"- bridge_admins_active: {int(bridge.get('admins_active', 0) or 0)}",
        f"- notify_stats_age: {bridge.get('notify_stats_age', 'unknown')}",
        f"- incident_state_age: {bridge.get('incident_state_age', 'unknown')}",
        f"- n8n_reachable: {'yes' if n8n_ok else 'no'} ({n8n.get('detail', '(unknown)')})",
    ]

    if include_validate_probe:
        lines.extend(
            [
                f"- notify_validate: {'PASS' if validate_ok else 'FAIL'}",
                f"  - stage: {validate.get('stage', '(unknown)')}",
                f"  - detail: {validate.get('detail', '(unknown)')}",
                f"  - recipients: {int(validate.get('recipients', 0) or 0)}",
                f"  - latency_seconds: {validate.get('latency_seconds', 'n/a')}",
            ]
        )
    else:
        lines.append("- notify_validate: skipped")

    if fanout:
        lines.extend(
            [
                f"- last_fanout_age: {fanout.get('age', 'unknown')}",
                f"- last_fanout_topic: {fanout.get('topic', 'unknown')}",
                f"- last_fanout_result: {fanout.get('result', 'unknown')} recipients={int(fanout.get('recipients', 0) or 0)}",
            ]
        )
    else:
        lines.append("- last_fanout: none")

    if not overall_ok:
        lines.append("- tip: run /status, /notify health, and /notify delivery list for deeper diagnostics")

    return "\n".join(lines)


def build_health_json_report(request_user_id: int, include_validate_probe: bool = True) -> str:
    return json.dumps(
        build_health_snapshot(request_user_id=request_user_id, include_validate_probe=include_validate_probe),
        ensure_ascii=False,
        sort_keys=True,
    )


def load_incident_state() -> dict[str, Any]:
    if not INCIDENT_STATE_PATH.exists():
        return {"incidents": {}, "updated_at": ""}
    try:
        data = json.loads(INCIDENT_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"incidents": {}, "updated_at": ""}
        incidents = data.get("incidents")
        if not isinstance(incidents, dict):
            data["incidents"] = {}
        return data
    except Exception:
        return {"incidents": {}, "updated_at": ""}


def save_incident_state(state: dict[str, Any]) -> bool:
    try:
        INCIDENT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        INCIDENT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to save incident state: {exc}", flush=True)
        return False


def load_reqtrack_state() -> dict[str, Any]:
    if not REQTRACK_STATE_PATH.exists():
        return {"version": 1, "updated_at": int(time.time()), "incidents": {}}
    try:
        data = json.loads(REQTRACK_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "updated_at": int(time.time()), "incidents": {}}
        incidents = data.get("incidents")
        if not isinstance(incidents, dict):
            incidents = {}
        return {
            "version": 1,
            "updated_at": int(data.get("updated_at") or int(time.time())),
            "incidents": incidents,
        }
    except Exception:
        return {"version": 1, "updated_at": int(time.time()), "incidents": {}}


def save_reqtrack_state(state: dict[str, Any]) -> bool:
    try:
        REQTRACK_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = int(time.time())
        REQTRACK_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to save reqtrack state: {exc}", flush=True)
        return False


def list_reqtrack_incidents(state: dict[str, Any], status_filter: str) -> list[dict[str, Any]]:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    rows: list[dict[str, Any]] = []
    for key, value in incidents.items():
        record = value if isinstance(value, dict) else {}
        status = str(record.get("status") or "")
        if status_filter == "active" and status != "active":
            continue
        if status_filter == "resolved" and status != "resolved":
            continue
        rows.append(
            {
                "key": str(key),
                "status": status,
                "title": str(record.get("title") or ""),
                "request_id": str(record.get("request_id") or ""),
                "type": str(record.get("type") or ""),
                "last_seen_ts": int(record.get("last_seen_ts") or 0),
                "last_notified_level": int(record.get("last_notified_level") or 0),
                "acked": bool(record.get("acked")),
                "snoozed_until": int(record.get("snoozed_until") or 0),
            }
        )
    rows.sort(key=lambda row: int(row.get("last_seen_ts") or 0), reverse=True)
    return rows


def apply_reqtrack_incident_action(
    state: dict[str, Any],
    action: str,
    incident_key: str,
    actor: str,
    note: str,
    snooze_minutes: int,
) -> tuple[bool, str, dict[str, Any]]:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    record_raw = incidents.get(incident_key)
    if not isinstance(record_raw, dict):
        return False, f"incident_not_found:{incident_key}", {}

    now_ts = int(time.time())
    record = dict(record_raw)

    if action == "ack":
        record["acked"] = True
        record["acked_ts"] = now_ts
        record["acked_by"] = actor
        record["ack_note"] = note
    elif action == "snooze":
        record["snoozed_until"] = now_ts + (max(1, snooze_minutes) * 60)
        record["snoozed_by"] = actor
        record["snooze_note"] = note
    elif action == "unsnooze":
        record["snoozed_until"] = 0
        record["snoozed_by"] = actor
        record["snooze_note"] = note
    elif action == "close":
        record["status"] = "resolved"
        record["resolved_ts"] = now_ts
        record["closed_manually"] = True
        record["closed_by"] = actor
        record["close_note"] = note
    else:
        return False, f"unsupported_action:{action}", {}

    incidents[incident_key] = record
    state["incidents"] = incidents
    return (
        True,
        "ok",
        {
            "key": incident_key,
            "status": str(record.get("status") or ""),
            "acked": bool(record.get("acked")),
            "snoozed_until": int(record.get("snoozed_until") or 0),
            "resolved_ts": int(record.get("resolved_ts") or 0),
        },
    )


def build_reqtrack_kpi_digest(state: dict[str, Any], now_ts: int, window_hours: int) -> dict[str, Any]:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    window_seconds = max(1, window_hours) * 3600
    window_start = now_ts - window_seconds

    active_count = 0
    resolved_count = 0
    acked_active_count = 0
    snoozed_active_count = 0

    opened_in_window = 0
    resolved_in_window = 0
    notified_in_window = 0
    realerted_in_window = 0
    manual_closes_in_window = 0
    acked_in_window = 0
    reopened_in_window = 0
    level2plus_notified_in_window = 0

    first_seen_active_values: list[int] = []
    mtta_seconds_values: list[int] = []
    active_age_buckets = {
        "lt_1h": 0,
        "h1_4": 0,
        "h4_24": 0,
        "gte_24h": 0,
    }
    long_running_active_24h = 0
    top_realerted_candidates: list[dict[str, Any]] = []

    for value in incidents.values():
        record = value if isinstance(value, dict) else {}
        status = str(record.get("status") or "")
        first_seen_ts = int(record.get("first_seen_ts") or 0)
        resolved_ts = int(record.get("resolved_ts") or 0)
        acked_ts = int(record.get("acked_ts") or 0)
        reopened_ts = int(record.get("reopened_ts") or 0)
        snoozed_until = int(record.get("snoozed_until") or 0)
        notify_count = int(record.get("notify_count") or 0)
        last_notified_ts = int(record.get("last_notified_ts") or 0)
        last_notified_level = int(record.get("last_notified_level") or 0)

        if status == "active":
            active_count += 1
            if first_seen_ts > 0:
                active_age_seconds = max(0, now_ts - first_seen_ts)
                first_seen_active_values.append(active_age_seconds)
                active_age_minutes = int(active_age_seconds / 60)
                if active_age_minutes < 60:
                    active_age_buckets["lt_1h"] += 1
                elif active_age_minutes < 240:
                    active_age_buckets["h1_4"] += 1
                elif active_age_minutes < 1440:
                    active_age_buckets["h4_24"] += 1
                else:
                    active_age_buckets["gte_24h"] += 1
                    long_running_active_24h += 1
            if bool(record.get("acked")):
                acked_active_count += 1
            if snoozed_until > now_ts:
                snoozed_active_count += 1
        elif status == "resolved":
            resolved_count += 1

        if first_seen_ts >= window_start:
            opened_in_window += 1
        if resolved_ts >= window_start:
            resolved_in_window += 1
        if bool(record.get("closed_manually")) and resolved_ts >= window_start:
            manual_closes_in_window += 1
        if acked_ts >= window_start:
            acked_in_window += 1
        if reopened_ts >= window_start:
            reopened_in_window += 1

        if last_notified_ts >= window_start:
            notified_in_window += 1
            if notify_count > 1:
                realerted_in_window += 1
            if last_notified_level >= 2:
                level2plus_notified_in_window += 1

        if notify_count > 1:
            top_realerted_candidates.append(
                {
                    "key": str(record.get("key") or ""),
                    "title": str(record.get("title") or ""),
                    "request_id": str(record.get("request_id") or ""),
                    "status": status,
                    "notify_count": notify_count,
                    "last_notified_level": last_notified_level,
                    "last_notified_ts": last_notified_ts,
                }
            )

        if acked_ts > 0 and first_seen_ts > 0 and acked_ts >= first_seen_ts and acked_ts >= window_start:
            mtta_seconds_values.append(acked_ts - first_seen_ts)

    avg_active_age_minutes = (
        int(sum(first_seen_active_values) / len(first_seen_active_values) / 60)
        if first_seen_active_values
        else 0
    )
    mtta_minutes = (
        int(sum(mtta_seconds_values) / len(mtta_seconds_values) / 60)
        if mtta_seconds_values
        else 0
    )

    top_realerted = sorted(
        top_realerted_candidates,
        key=lambda row: (
            int(row.get("notify_count") or 0),
            int(row.get("last_notified_ts") or 0),
        ),
        reverse=True,
    )[:5]

    return {
        "generated_ts": now_ts,
        "window_hours": max(1, window_hours),
        "window_start_ts": window_start,
        "state_updated_at": int(state.get("updated_at") or 0),
        "totals": {
            "incidents_total": len(incidents),
            "active": active_count,
            "resolved": resolved_count,
            "acked_active": acked_active_count,
            "snoozed_active": snoozed_active_count,
        },
        "window": {
            "opened": opened_in_window,
            "resolved": resolved_in_window,
            "notified": notified_in_window,
            "realerted": realerted_in_window,
            "acked": acked_in_window,
            "reopened": reopened_in_window,
            "level2plus_notified": level2plus_notified_in_window,
            "manual_closes": manual_closes_in_window,
            "mtta_minutes": mtta_minutes,
        },
        "health": {
            "active_avg_age_minutes": avg_active_age_minutes,
            "active_age_buckets": active_age_buckets,
            "long_running_active_24h": long_running_active_24h,
        },
        "quality": {
            "top_realerted": top_realerted,
        },
    }


def render_reqtrack_kpi_digest_text(kpi: dict[str, Any], state_path: pathlib.Path) -> str:
    totals_raw = kpi.get("totals")
    totals: dict[str, Any] = totals_raw if isinstance(totals_raw, dict) else {}
    window_raw = kpi.get("window")
    window: dict[str, Any] = window_raw if isinstance(window_raw, dict) else {}
    health_raw = kpi.get("health")
    health: dict[str, Any] = health_raw if isinstance(health_raw, dict) else {}
    quality_raw = kpi.get("quality")
    quality: dict[str, Any] = quality_raw if isinstance(quality_raw, dict) else {}
    buckets_raw = health.get("active_age_buckets")
    buckets: dict[str, Any] = buckets_raw if isinstance(buckets_raw, dict) else {}
    top_realerted_raw = quality.get("top_realerted")
    top_realerted: list[dict[str, Any]] = top_realerted_raw if isinstance(top_realerted_raw, list) else []

    lines = [
        "Reqtrack KPI digest:",
        f"- state_file: {state_path}",
        f"- window_hours: {kpi.get('window_hours', 24)}",
        f"- incidents_total: {int(totals.get('incidents_total', 0))}",
        f"- active: {int(totals.get('active', 0))}",
        f"- resolved: {int(totals.get('resolved', 0))}",
        f"- acked_active: {int(totals.get('acked_active', 0))}",
        f"- snoozed_active: {int(totals.get('snoozed_active', 0))}",
        f"- opened_window: {int(window.get('opened', 0))}",
        f"- resolved_window: {int(window.get('resolved', 0))}",
        f"- notified_window: {int(window.get('notified', 0))}",
        f"- realerted_window: {int(window.get('realerted', 0))}",
        f"- acked_window: {int(window.get('acked', 0))}",
        f"- reopened_window: {int(window.get('reopened', 0))}",
        f"- level2plus_notified_window: {int(window.get('level2plus_notified', 0))}",
        f"- manual_closes_window: {int(window.get('manual_closes', 0))}",
        f"- mtta_minutes: {int(window.get('mtta_minutes', 0))}",
        f"- active_avg_age_minutes: {int(health.get('active_avg_age_minutes', 0))}",
        f"- active_age_buckets: lt_1h={int(buckets.get('lt_1h', 0))} h1_4={int(buckets.get('h1_4', 0))} h4_24={int(buckets.get('h4_24', 0))} gte_24h={int(buckets.get('gte_24h', 0))}",
        f"- long_running_active_24h: {int(health.get('long_running_active_24h', 0))}",
    ]

    if top_realerted:
        lines.append("- top_realerted:")
        for item in top_realerted[:3]:
            lines.append(
                "  * "
                + f"{str(item.get('key') or item.get('request_id') or 'request:?')} "
                + f"notify_count={int(item.get('notify_count') or 0)} "
                + f"level={int(item.get('last_notified_level') or 0)} "
                + f"status={str(item.get('status') or '')} "
                + f"title={str(item.get('title') or '')}"
            )

    return "\n".join(lines)


def normalize_incident_id(raw: str) -> str:
    value = "".join(ch for ch in (raw or "").strip().upper() if ch.isalnum() or ch == "-")
    return value


def incident_status(record: dict[str, Any], now_ts: int) -> str:
    try:
        snoozed_until = int(record.get("snoozed_until", 0) or 0)
    except (TypeError, ValueError):
        snoozed_until = 0
    if snoozed_until > now_ts:
        return "snoozed"

    try:
        acked_at = int(record.get("acked_at", 0) or 0)
    except (TypeError, ValueError):
        acked_at = 0
    if acked_at > 0 and now_ts - acked_at <= max(60, INCIDENT_ACK_TTL_SECONDS):
        return "acknowledged"

    return "active"


def incident_brief(record: dict[str, Any], max_chars: int = 90) -> str:
    title = " ".join(str(record.get("title", "")).split())
    message = " ".join(str(record.get("message", "")).split())
    base = title or message or "(no summary)"
    if title and message and not message.lower().startswith(title.lower()):
        base = f"{title}: {message}"
    if len(base) <= max_chars:
        return base
    return base[: max(1, max_chars - 1)].rstrip() + "…"


POLICY_TELEGRAM_SETTINGS = load_policy_telegram_settings(POLICY_FILE)
policy_topic_labels = {
    key: value
    for key, value in POLICY_TELEGRAM_SETTINGS.get("topic_labels", {}).items()
    if isinstance(key, str) and isinstance(value, str)
}
if policy_topic_labels:
    NOTIFICATION_TOPIC_LABELS = {
        key: value
        for key, value in policy_topic_labels.items()
        if key
    }
policy_admin_topics = {
    topic
    for topic in POLICY_TELEGRAM_SETTINGS.get("default_admin_notify_topics", [])
    if topic in NOTIFICATION_TOPIC_LABELS
}
DEFAULT_ADMIN_NOTIFY_TOPICS = {
    topic for topic in parse_csv_strings(DEFAULT_ADMIN_NOTIFY_TOPICS_RAW) if topic in NOTIFICATION_TOPIC_LABELS
}
if policy_admin_topics:
    DEFAULT_ADMIN_NOTIFY_TOPICS = policy_admin_topics
EMERGENCY_ADMIN_USERNAMES = set(parse_csv_strings(EMERGENCY_ADMIN_USERNAMES_RAW))
NOTIFY_POLICY_DROP_PATTERNS = parse_csv_strings(NOTIFY_POLICY_DROP_PATTERNS_RAW)
NOTIFY_POLICY_DEDUPE_BY_TOPIC = parse_topic_window_overrides(NOTIFY_POLICY_DEDUPE_BY_TOPIC_RAW)
policy_dedupe_default = POLICY_TELEGRAM_SETTINGS.get("dedupe_default_window_seconds")
if isinstance(policy_dedupe_default, int) and policy_dedupe_default > 0:
    NOTIFY_POLICY_DEDUPE_WINDOW_SECONDS = policy_dedupe_default
policy_dedupe_by_topic = POLICY_TELEGRAM_SETTINGS.get("dedupe_by_topic", {})
if isinstance(policy_dedupe_by_topic, dict) and policy_dedupe_by_topic:
    NOTIFY_POLICY_DEDUPE_BY_TOPIC = {
        topic: int(seconds)
        for topic, seconds in policy_dedupe_by_topic.items()
        if isinstance(topic, str) and isinstance(seconds, int) and seconds > 0
    }
policy_approval_ttl = POLICY_TELEGRAM_SETTINGS.get("approval_default_ttl_seconds")
if isinstance(policy_approval_ttl, int) and policy_approval_ttl > 0:
    APPROVAL_TTL_SECONDS = policy_approval_ttl
policy_approval_max_pending = POLICY_TELEGRAM_SETTINGS.get("approval_max_pending_per_user")
if isinstance(policy_approval_max_pending, int) and policy_approval_max_pending > 0:
    APPROVAL_MAX_PENDING_PER_USER = policy_approval_max_pending
policy_rate_limit_rpm = POLICY_TELEGRAM_SETTINGS.get("rate_limit_requests_per_minute")
policy_rate_limit_burst = POLICY_TELEGRAM_SETTINGS.get("rate_limit_burst")
if isinstance(policy_rate_limit_rpm, int) and policy_rate_limit_rpm > 0:
    burst = policy_rate_limit_burst if isinstance(policy_rate_limit_burst, int) and policy_rate_limit_burst >= 0 else 0
    RATE_LIMIT_WINDOW_SECONDS = 60
    RATE_LIMIT_MAX_REQUESTS = max(1, policy_rate_limit_rpm + burst)
policy_memory_enabled_by_default = POLICY_TELEGRAM_SETTINGS.get("memory_enabled_by_default")
if isinstance(policy_memory_enabled_by_default, bool):
    MEMORY_ENABLED_BY_DEFAULT = policy_memory_enabled_by_default
policy_memory_min_confidence = POLICY_TELEGRAM_SETTINGS.get("memory_min_speaker_confidence")
if isinstance(policy_memory_min_confidence, (float, int)):
    MEMORY_MIN_CONFIDENCE = min(1.0, max(0.0, float(policy_memory_min_confidence)))
policy_child_guardrails_enabled = POLICY_TELEGRAM_SETTINGS.get("child_guardrails_enabled")
if isinstance(policy_child_guardrails_enabled, bool):
    CHILD_GUARDRAILS_ENABLED = policy_child_guardrails_enabled
policy_child_adult_min_age = POLICY_TELEGRAM_SETTINGS.get("child_account_adult_min_age")
if isinstance(policy_child_adult_min_age, int) and policy_child_adult_min_age >= 13:
    CHILD_ACCOUNT_ADULT_MIN_AGE = policy_child_adult_min_age
policy_child_media_allowed_ratings = POLICY_TELEGRAM_SETTINGS.get("child_media_allowed_ratings")
if isinstance(policy_child_media_allowed_ratings, list) and policy_child_media_allowed_ratings:
    CHILD_MEDIA_ALLOWED_RATINGS_RAW = ",".join(str(item or "") for item in policy_child_media_allowed_ratings)
policy_child_media_allowed_ratings_under_13 = POLICY_TELEGRAM_SETTINGS.get("child_media_allowed_ratings_under_13")
if isinstance(policy_child_media_allowed_ratings_under_13, list) and policy_child_media_allowed_ratings_under_13:
    CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13_RAW = ",".join(str(item or "") for item in policy_child_media_allowed_ratings_under_13)
policy_child_media_allowed_ratings_13_15 = POLICY_TELEGRAM_SETTINGS.get("child_media_allowed_ratings_13_15")
if isinstance(policy_child_media_allowed_ratings_13_15, list) and policy_child_media_allowed_ratings_13_15:
    CHILD_MEDIA_ALLOWED_RATINGS_13_15_RAW = ",".join(str(item or "") for item in policy_child_media_allowed_ratings_13_15)
policy_child_media_allowed_ratings_16_17 = POLICY_TELEGRAM_SETTINGS.get("child_media_allowed_ratings_16_17")
if isinstance(policy_child_media_allowed_ratings_16_17, list) and policy_child_media_allowed_ratings_16_17:
    CHILD_MEDIA_ALLOWED_RATINGS_16_17_RAW = ",".join(str(item or "") for item in policy_child_media_allowed_ratings_16_17)
policy_child_media_deny_unknown = POLICY_TELEGRAM_SETTINGS.get("child_media_deny_unknown_ratings")
if isinstance(policy_child_media_deny_unknown, bool):
    CHILD_MEDIA_DENY_UNKNOWN_RATINGS = policy_child_media_deny_unknown
policy_child_media_block_if_adult_flag = POLICY_TELEGRAM_SETTINGS.get("child_media_block_if_adult_flag")
if isinstance(policy_child_media_block_if_adult_flag, bool):
    CHILD_MEDIA_BLOCK_IF_ADULT_FLAG = policy_child_media_block_if_adult_flag
policy_child_media_blocked_genre_ids = POLICY_TELEGRAM_SETTINGS.get("child_media_blocked_genre_ids")
if isinstance(policy_child_media_blocked_genre_ids, list) and policy_child_media_blocked_genre_ids:
    CHILD_MEDIA_BLOCKED_GENRE_IDS_RAW = ",".join(str(item or "") for item in policy_child_media_blocked_genre_ids)
policy_child_media_blocked_keywords = POLICY_TELEGRAM_SETTINGS.get("child_media_blocked_keywords")
if isinstance(policy_child_media_blocked_keywords, list) and policy_child_media_blocked_keywords:
    CHILD_MEDIA_BLOCKED_KEYWORDS_RAW = ",".join(str(item or "") for item in policy_child_media_blocked_keywords)
POLICY_MEMORY_VOICE_OPT_IN_REQUIRED = bool(POLICY_TELEGRAM_SETTINGS.get("memory_voice_opt_in_required", True))
POLICY_MEMORY_LOW_CONFIDENCE_WRITE_POLICY = str(
    POLICY_TELEGRAM_SETTINGS.get("memory_low_confidence_write_policy") or "deny"
).strip().lower() or "deny"
policy_retention_raw_audio = POLICY_TELEGRAM_SETTINGS.get("retention_raw_audio_persist")
POLICY_RETENTION_RAW_AUDIO_PERSIST = bool(policy_retention_raw_audio) if isinstance(policy_retention_raw_audio, bool) else False
POLICY_MEMORY_WRITE_MODE = "summary_only"
TEXTBOOK_ALLOWED_FILE_DOMAINS = parse_csv_strings(TEXTBOOK_ALLOWED_FILE_DOMAINS_RAW)
TEXTBOOK_SEARCH_PROVIDERS = {
    item
    for item in parse_csv_strings(TEXTBOOK_SEARCH_PROVIDERS_RAW)
    if item in {"googlebooks", "openlibrary", "internetarchive", "gutendex"}
}
if not TEXTBOOK_SEARCH_PROVIDERS:
    TEXTBOOK_SEARCH_PROVIDERS = {"googlebooks", "openlibrary"}


def normalize_content_rating(value: str) -> str:
    rating = re.sub(r"\s+", "", str(value or "").strip().upper())
    rating = rating.replace("_", "-")
    return rating


CHILD_MEDIA_ALLOWED_RATINGS = {
    normalize_content_rating(item)
    for item in parse_csv_strings(CHILD_MEDIA_ALLOWED_RATINGS_RAW)
    if normalize_content_rating(item)
}
CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13 = {
    normalize_content_rating(item)
    for item in parse_csv_strings(CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13_RAW)
    if normalize_content_rating(item)
}
CHILD_MEDIA_ALLOWED_RATINGS_13_15 = {
    normalize_content_rating(item)
    for item in parse_csv_strings(CHILD_MEDIA_ALLOWED_RATINGS_13_15_RAW)
    if normalize_content_rating(item)
}
CHILD_MEDIA_ALLOWED_RATINGS_16_17 = {
    normalize_content_rating(item)
    for item in parse_csv_strings(CHILD_MEDIA_ALLOWED_RATINGS_16_17_RAW)
    if normalize_content_rating(item)
}
if not CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13:
    CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13 = set(CHILD_MEDIA_ALLOWED_RATINGS)
if not CHILD_MEDIA_ALLOWED_RATINGS_13_15:
    CHILD_MEDIA_ALLOWED_RATINGS_13_15 = set(CHILD_MEDIA_ALLOWED_RATINGS)
if not CHILD_MEDIA_ALLOWED_RATINGS_16_17:
    CHILD_MEDIA_ALLOWED_RATINGS_16_17 = set(CHILD_MEDIA_ALLOWED_RATINGS)
CHILD_MEDIA_BLOCKED_GENRE_IDS = {value for value in parse_csv_ints(CHILD_MEDIA_BLOCKED_GENRE_IDS_RAW) if value > 0}
CHILD_MEDIA_BLOCKED_KEYWORDS = {item for item in parse_csv_strings(CHILD_MEDIA_BLOCKED_KEYWORDS_RAW) if item}


def normalize_account_class(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"adult", "child"}:
        return normalized
    return "adult"


def parse_account_age(value: Any) -> int | None:
    try:
        age = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if age < 1 or age > 120:
        return None
    return age


def classify_account_by_age(age: int | None) -> str:
    if isinstance(age, int) and age >= CHILD_ACCOUNT_ADULT_MIN_AGE:
        return "adult"
    if isinstance(age, int):
        return "child"
    return "adult"


def get_record_account_age(record: dict[str, Any] | None) -> int | None:
    if not isinstance(record, dict):
        return None
    return parse_account_age(record.get("age"))


def get_record_account_class(record: dict[str, Any] | None) -> str:
    if not isinstance(record, dict):
        return "adult"
    parsed_age = get_record_account_age(record)
    if isinstance(parsed_age, int):
        return classify_account_by_age(parsed_age)
    value = normalize_account_class(str(record.get("account_class", "")))
    if value in {"adult", "child"} and str(record.get("account_class", "")).strip():
        return value
    return "adult"


def is_child_guardrails_account(record: dict[str, Any] | None) -> bool:
    if not CHILD_GUARDRAILS_ENABLED:
        return False
    return get_record_account_class(record) == "child"


UTILITY_COMMAND_TOKENS = {
    "/start",
    "/whoami",
    "/status",
    "/health",
    "/digest",
    "/selftest",
    "/ratelimit",
    "/pending",
    "/approve",
    "/deny",
    "/user",
    "/notify",
    "/ack",
    "/snooze",
    "/unsnooze",
    "/incident",
    "/reqtrack",
    "/profile",
    "/feedback",
    "/discord",
    "/memory",
    "/tone",
    "/textbook",
    "/workspace",
    "/coding",
    "/research",
}
ALLOWED_SLASH_COMMAND_TOKENS = set(UTILITY_COMMAND_TOKENS) | {"/rag", "/ops", "/media", "/request", "/book"}
DEFAULT_USER_ROLE_COMMAND_ALLOWLIST = {
    "/start",
    "/whoami",
    "/selftest",
    "/notify",
    "/memory",
    "/profile",
    "/feedback",
    "/discord",
    "/textbook",
    "/workspace",
    "/coding",
    "/rag",
    "/research",
    "/media",
    "/request",
    "/book",
}
ROLE_COMMAND_ALLOWLIST: dict[str, set[str]] = {
    "user": set(DEFAULT_USER_ROLE_COMMAND_ALLOWLIST),
    "admin": set(ALLOWED_SLASH_COMMAND_TOKENS),
}
policy_role_allowlist = POLICY_TELEGRAM_SETTINGS.get("role_command_allowlist", {})
if isinstance(policy_role_allowlist, dict):
    for role_key_raw, command_values in policy_role_allowlist.items():
        role_key = str(role_key_raw or "").strip().lower()
        if role_key not in {"user", "admin"}:
            continue
        if not isinstance(command_values, list):
            continue
        parsed_allowlist: set[str] = set()
        for command_value in command_values:
            token = normalize_slash_command_token(command_value)
            if token and token in ALLOWED_SLASH_COMMAND_TOKENS:
                parsed_allowlist.add(token)
        if parsed_allowlist:
            ROLE_COMMAND_ALLOWLIST[role_key] = parsed_allowlist


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def is_low_signal_text(text: str) -> bool:
    if not LOW_SIGNAL_FILTER_ENABLED:
        return False
    normalized = " ".join(str(text or "").strip().split())
    if not normalized or normalized.startswith("/"):
        return False
    if " " in normalized:
        return False
    if len(normalized) > max(1, LOW_SIGNAL_TOKEN_MAX_CHARS):
        return False
    return bool(re.fullmatch(r"[a-zA-Z]+", normalized))


def command_token(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    first = raw.split()[0].lower()
    if first.startswith("/") and "@" in first:
        return first.split("@", 1)[0]
    return first


def is_role_command_allowed(role: str, token: str) -> bool:
    role_key = normalize_text(role) or "user"
    allowed_tokens = ROLE_COMMAND_ALLOWLIST.get(role_key)
    if not isinstance(allowed_tokens, set) or not allowed_tokens:
        return True
    return token in allowed_tokens


def role_command_denied_message(token: str) -> str:
    if token == "/ops":
        return "⛔ /ops is admin-only."
    if token == "/notify":
        return "⛔ This command is not allowed for your role. (Tip: use /notify me for your personal delivery status.)"
    return "⛔ This command is not allowed for your role."


def normalize_notify_topics(raw_topics: Any) -> set[str]:
    if not isinstance(raw_topics, list):
        return set()
    return {
        normalize_text(topic)
        for topic in raw_topics
        if normalize_text(topic) in NOTIFICATION_TOPIC_LABELS or normalize_text(topic) == "all"
    }


def ensure_notification_settings(record: dict[str, Any]) -> bool:
    changed = False
    role = str(record.get("role", "user"))
    selected_topics = normalize_notify_topics(record.get("notify_topics"))

    if not selected_topics:
        if role == "admin":
            selected_topics = set(DEFAULT_ADMIN_NOTIFY_TOPICS or {"critical", "ops"})
        else:
            selected_topics = {"media"}
        changed = True

    if role != "admin":
        if record.get("emergency_contact"):
            record["emergency_contact"] = False
            changed = True
    else:
        is_emergency_default = normalize_text(record.get("telegram_username", "")) in EMERGENCY_ADMIN_USERNAMES
        existing = bool(record.get("emergency_contact", False))
        if "emergency_contact" not in record:
            record["emergency_contact"] = is_emergency_default or existing
            changed = True

    normalized_list = sorted(selected_topics)
    if record.get("notify_topics") != normalized_list:
        record["notify_topics"] = normalized_list
        changed = True

    return changed


def expected_admin_profile() -> dict[str, str]:
    return {
        "first_name": "james",
        "last_name": "hunsaker",
        "username": "<your_admin_username>",
    }


def load_user_registry() -> dict[str, Any]:
    if not USER_REGISTRY_PATH.exists():
        return {"users": {}}
    try:
        data = json.loads(USER_REGISTRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"users": {}}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data
    except Exception:
        return {"users": {}}


def save_user_registry(registry: dict[str, Any]) -> None:
    USER_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    USER_REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def get_user_record(registry: dict[str, Any], user_id: int) -> dict[str, Any] | None:
    users = registry.get("users") or {}
    record = users.get(str(user_id))
    return record if isinstance(record, dict) else None


def set_user_record(registry: dict[str, Any], user_id: int, role: str, status: str = "active") -> None:
    users = registry.setdefault("users", {})
    existing = users.get(str(user_id), {})
    base = existing if isinstance(existing, dict) else {}
    users[str(user_id)] = {
        **base,
        "role": role,
        "status": status,
        "updated_at": utc_now(),
        "created_at": base.get("created_at", utc_now()),
    }


def bootstrap_registry(registry: dict[str, Any]) -> dict[str, Any]:
    changed = False
    for user_id in ALLOWED_IDS:
        if not get_user_record(registry, user_id):
            role = "admin" if user_id in BOOTSTRAP_ADMINS else "user"
            set_user_record(registry, user_id, role)
            changed = True
    for user_id in BOOTSTRAP_ADMINS:
        record = get_user_record(registry, user_id)
        if not record:
            set_user_record(registry, user_id, "admin")
            changed = True
        elif record.get("role") != "admin":
            set_user_record(registry, user_id, "admin", status=str(record.get("status", "active")))
            changed = True
    users = registry.get("users") or {}
    for rec in users.values():
        if isinstance(rec, dict) and ensure_notification_settings(rec):
            rec["updated_at"] = utc_now()
            changed = True
    if changed:
        save_user_registry(registry)
    return registry


USER_REGISTRY = bootstrap_registry(load_user_registry())


def load_approvals() -> dict[str, Any]:
    if not APPROVALS_PATH.exists():
        return {"next_id": 1, "pending": {}}
    try:
        data = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"next_id": 1, "pending": {}}
        pending = data.get("pending")
        if not isinstance(pending, dict):
            data["pending"] = {}
        if not isinstance(data.get("next_id"), int):
            data["next_id"] = 1
        return data
    except Exception:
        return {"next_id": 1, "pending": {}}


def save_approvals(state: dict[str, Any]) -> None:
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


APPROVALS_STATE = load_approvals()


def load_media_selection_state() -> dict[str, Any]:
    if not MEDIA_SELECTION_PATH.exists():
        return {"pending": {}}
    try:
        data = json.loads(MEDIA_SELECTION_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"pending": {}}
        pending = data.get("pending")
        if not isinstance(pending, dict):
            data["pending"] = {}
        return data
    except Exception:
        return {"pending": {}}


def save_media_selection_state(state: dict[str, Any]) -> None:
    MEDIA_SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEDIA_SELECTION_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


MEDIA_SELECTION_STATE = load_media_selection_state()


def load_textbook_state() -> dict[str, Any]:
    if not TEXTBOOK_STATE_PATH.exists():
        return {"pending": {}, "pending_ingest": {}, "last_fulfillment": {}}
    try:
        data = json.loads(TEXTBOOK_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"pending": {}, "pending_ingest": {}, "last_fulfillment": {}}
        pending = data.get("pending")
        if not isinstance(pending, dict):
            data["pending"] = {}
        pending_ingest = data.get("pending_ingest")
        if not isinstance(pending_ingest, dict):
            data["pending_ingest"] = {}
        last_fulfillment = data.get("last_fulfillment")
        if not isinstance(last_fulfillment, dict):
            data["last_fulfillment"] = {}
        return data
    except Exception:
        return {"pending": {}, "pending_ingest": {}, "last_fulfillment": {}}


def save_textbook_state(state: dict[str, Any]) -> None:
    TEXTBOOK_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEXTBOOK_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


TEXTBOOK_STATE = load_textbook_state()
TEXTBOOK_DOWNLOAD_STATE_LOCK = threading.Lock()
TEXTBOOK_DOWNLOAD_SERVER_STARTED = False
TEXTBOOK_DOWNLOAD_LAST_CLEANUP_TS = 0


def load_textbook_download_state() -> dict[str, Any]:
    if not TEXTBOOK_DOWNLOAD_STATE_PATH.exists():
        return {"entries": {}}
    try:
        data = json.loads(TEXTBOOK_DOWNLOAD_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"entries": {}}
        entries = data.get("entries")
        if not isinstance(entries, dict):
            data["entries"] = {}
        return data
    except Exception:
        return {"entries": {}}


def save_textbook_download_state(state: dict[str, Any]) -> None:
    TEXTBOOK_DOWNLOAD_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEXTBOOK_DOWNLOAD_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


TEXTBOOK_DOWNLOAD_STATE = load_textbook_download_state()


def textbook_download_base_url() -> str:
    if TEXTBOOK_DOWNLOAD_PUBLIC_BASE_URL:
        return TEXTBOOK_DOWNLOAD_PUBLIC_BASE_URL
    return f"http://127.0.0.1:{TEXTBOOK_DOWNLOAD_PORT}"


def _guess_textbook_extension(content_type: str, source_url: str) -> str:
    ctype = str(content_type or "").split(";", 1)[0].strip().lower()
    if ctype:
        ext = mimetypes.guess_extension(ctype)
        if ext:
            return ext
    parsed = urllib.parse.urlparse(str(source_url or ""))
    suffix = pathlib.Path(parsed.path).suffix.strip().lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        return suffix
    return ".bin"


def _safe_textbook_filename(title: str, source_url: str, content_type: str) -> str:
    base = str(title or "").strip() or pathlib.Path(urllib.parse.urlparse(str(source_url or "")).path).name
    if not base:
        base = "textbook-download"
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-._") or "textbook-download"
    ext = pathlib.Path(base).suffix.strip().lower()
    guessed_ext = _guess_textbook_extension(content_type=content_type, source_url=source_url)
    if not ext:
        base = f"{base}{guessed_ext}"
    return base[:140]


def cleanup_expired_textbook_downloads(now_ts: int | None = None) -> tuple[int, int]:
    ts_now = int(now_ts or time.time())
    removed_entries = 0
    removed_files = 0
    with TEXTBOOK_DOWNLOAD_STATE_LOCK:
        entries = TEXTBOOK_DOWNLOAD_STATE.setdefault("entries", {})
        if not isinstance(entries, dict):
            entries = {}
            TEXTBOOK_DOWNLOAD_STATE["entries"] = entries

        for token, entry in list(entries.items()):
            if not isinstance(entry, dict):
                entries.pop(token, None)
                removed_entries += 1
                continue
            try:
                expires_at = int(entry.get("expires_at", 0) or 0)
            except (TypeError, ValueError):
                expires_at = 0
            file_path = pathlib.Path(str(entry.get("file_path", "")).strip())
            expired = expires_at > 0 and ts_now > expires_at
            missing = not file_path.exists()
            if not expired and not missing:
                continue
            if file_path.exists():
                try:
                    file_path.unlink()
                    removed_files += 1
                except Exception:
                    pass
            entries.pop(token, None)
            removed_entries += 1

        save_textbook_download_state(TEXTBOOK_DOWNLOAD_STATE)
    return removed_entries, removed_files


def build_textbook_download_link(
    user_id: int,
    fulfillment_id: str,
    source_url: str,
    file_mime: str,
    selected_candidate: dict[str, Any],
) -> tuple[str, int, str]:
    if not TEXTBOOK_DOWNLOAD_LINK_ENABLED:
        return "", 0, "download_link_disabled"

    source = str(source_url or "").strip()
    if not source:
        return "", 0, "missing_source_url"

    if not source.startswith(("http://", "https://")):
        return "", 0, "invalid_source_scheme"

    allowed_source, allowed_reason = is_textbook_file_url_allowed(source)
    if not allowed_source:
        return "", 0, f"untrusted_source:{allowed_reason}"

    max_bytes = max(1_000_000, int(TEXTBOOK_DOWNLOAD_MAX_BYTES))
    request = urllib.request.Request(
        url=source,
        headers={"User-Agent": "servernoots-telegram-bridge/1.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                return "", 0, "file_too_large"
            response_content_type = str(response.headers.get("Content-Type") or "").strip()
    except urllib.error.HTTPError as exc:
        return "", 0, f"source_fetch_http_{exc.code}"
    except Exception as exc:
        return "", 0, f"source_fetch_error:{exc}"

    content_type = str(response_content_type or file_mime or "application/octet-stream").strip()
    ttl_seconds = max(300, int(TEXTBOOK_DOWNLOAD_TTL_SECONDS))
    now_ts = int(time.time())
    expires_at = now_ts + ttl_seconds
    source_hash = hashlib.sha256(source.encode("utf-8", errors="ignore")).hexdigest()[:16]
    token_seed = f"{fulfillment_id}|{user_id}|{source_hash}|{now_ts}|{len(raw)}"
    token = hashlib.sha256(token_seed.encode("utf-8", errors="ignore")).hexdigest()[:40]

    title = ""
    if isinstance(selected_candidate, dict):
        title = str(selected_candidate.get("title", "")).strip()
    file_name = _safe_textbook_filename(title=title, source_url=source, content_type=content_type)

    TEXTBOOK_DOWNLOAD_FILES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = (TEXTBOOK_DOWNLOAD_FILES_DIR / token).resolve()
    file_path.write_bytes(raw)

    entry = {
        "token": token,
        "user_id": int(user_id),
        "fulfillment_id": str(fulfillment_id or "").strip(),
        "source_url": source,
        "content_type": content_type,
        "file_name": file_name,
        "file_path": str(file_path),
        "size_bytes": len(raw),
        "created_at": now_ts,
        "expires_at": expires_at,
    }

    with TEXTBOOK_DOWNLOAD_STATE_LOCK:
        entries = TEXTBOOK_DOWNLOAD_STATE.setdefault("entries", {})
        if not isinstance(entries, dict):
            entries = {}
            TEXTBOOK_DOWNLOAD_STATE["entries"] = entries
        entries[token] = entry
        save_textbook_download_state(TEXTBOOK_DOWNLOAD_STATE)

    base = textbook_download_base_url().rstrip("/")
    link = f"{base}/textbook-download/{token}"
    return link, expires_at, "ok"


def get_textbook_download_entry(token: str) -> dict[str, Any] | None:
    candidate = str(token or "").strip()
    if not re.fullmatch(r"[a-f0-9]{32,64}", candidate):
        return None

    with TEXTBOOK_DOWNLOAD_STATE_LOCK:
        entries = TEXTBOOK_DOWNLOAD_STATE.get("entries")
        if not isinstance(entries, dict):
            return None
        entry = entries.get(candidate)
        if not isinstance(entry, dict):
            return None
        try:
            expires_at = int(entry.get("expires_at", 0) or 0)
        except (TypeError, ValueError):
            expires_at = 0
        if expires_at <= 0 or int(time.time()) > expires_at:
            file_path = pathlib.Path(str(entry.get("file_path", "")).strip())
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass
            entries.pop(candidate, None)
            save_textbook_download_state(TEXTBOOK_DOWNLOAD_STATE)
            return None
        return dict(entry)


class TextbookDownloadHandler(BaseHTTPRequestHandler):
    server_version = "TelegramTextbookDownload/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = str(parsed.path or "").strip()
        prefix = "/textbook-download/"
        if not route.startswith(prefix):
            self.send_error(404, "not_found")
            return

        token = route[len(prefix) :].strip().split("/")[0]
        entry = get_textbook_download_entry(token)
        if not entry:
            self.send_error(410, "expired_or_missing")
            return

        file_path = pathlib.Path(str(entry.get("file_path", "")).strip())
        if not file_path.exists():
            self.send_error(410, "expired_or_missing")
            return

        try:
            content = file_path.read_bytes()
        except Exception:
            self.send_error(500, "file_read_failed")
            return

        content_type = str(entry.get("content_type") or "application/octet-stream").strip() or "application/octet-stream"
        file_name = str(entry.get("file_name") or "textbook-download.bin").strip() or "textbook-download.bin"
        quoted = urllib.parse.quote(file_name)

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f"attachment; filename=\"{file_name}\"; filename*=UTF-8''{quoted}")
        self.send_header("Cache-Control", "private, no-store, max-age=0")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def start_textbook_download_server() -> None:
    global TEXTBOOK_DOWNLOAD_SERVER_STARTED
    if TEXTBOOK_DOWNLOAD_SERVER_STARTED:
        return
    if not TEXTBOOK_DOWNLOAD_LINK_ENABLED:
        print("[telegram-bridge] textbook download links disabled", flush=True)
        return

    def _serve() -> None:
        try:
            with ThreadingHTTPServer((TEXTBOOK_DOWNLOAD_BIND_HOST, TEXTBOOK_DOWNLOAD_PORT), TextbookDownloadHandler) as server:
                print(
                    f"[telegram-bridge] textbook download server listening on {TEXTBOOK_DOWNLOAD_BIND_HOST}:{TEXTBOOK_DOWNLOAD_PORT}",
                    flush=True,
                )
                server.serve_forever()
        except Exception as exc:
            print(f"[telegram-bridge] textbook download server failed: {exc}", flush=True)

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    TEXTBOOK_DOWNLOAD_SERVER_STARTED = True


def load_workspace_state() -> dict[str, Any]:
    if not WORKSPACE_STATE_PATH.exists():
        return {"active": {}}
    try:
        data = json.loads(WORKSPACE_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"active": {}}
        active = data.get("active")
        if not isinstance(active, dict):
            data["active"] = {}
        return data
    except Exception:
        return {"active": {}}


def save_workspace_state(state: dict[str, Any]) -> None:
    WORKSPACE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


WORKSPACE_STATE = load_workspace_state()
WORKSPACE_LAST_CLEANUP_TS = 0


def load_research_state() -> dict[str, Any]:
    if not RESEARCH_STATE_PATH.exists():
        return {"jobs": {}}
    try:
        data = json.loads(RESEARCH_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"jobs": {}}
        jobs = data.get("jobs")
        if not isinstance(jobs, dict):
            data["jobs"] = {}
        return data
    except Exception:
        return {"jobs": {}}


def save_research_state(state: dict[str, Any]) -> None:
    RESEARCH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


RESEARCH_STATE = load_research_state()
RESEARCH_STATE_LOCK = threading.Lock()


def generate_research_run_id(user_id: int, query: str) -> str:
    now_ts = int(time.time())
    entropy = f"{user_id}:{now_ts}:{query[:120]}"
    suffix = hashlib.sha256(entropy.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"rr-{now_ts}-{suffix}"


def get_research_job(run_id: str) -> dict[str, Any] | None:
    jobs = RESEARCH_STATE.get("jobs") if isinstance(RESEARCH_STATE, dict) else {}
    if not isinstance(jobs, dict):
        return None
    item = jobs.get(run_id)
    return item if isinstance(item, dict) else None


def set_research_job(run_id: str, payload: dict[str, Any]) -> None:
    jobs = RESEARCH_STATE.get("jobs") if isinstance(RESEARCH_STATE, dict) else {}
    if not isinstance(jobs, dict):
        jobs = {}
    jobs[run_id] = payload
    RESEARCH_STATE["jobs"] = jobs
    save_research_state(RESEARCH_STATE)


def apply_research_webhook_result(run_id: str, result: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    job = get_research_job(run_id)
    if not isinstance(job, dict):
        return None

    status = normalize_text(result.get("status"))
    if status in {"queued", "running", "ready", "failed"}:
        job["status"] = status

    report_url = str(
        result.get("report_url")
        or result.get("download_url")
        or result.get("nextcloud_url")
        or ""
    ).strip()
    if report_url:
        job["report_url"] = report_url

    error_text = str(result.get("error") or result.get("detail") or "").strip()
    if error_text:
        job["error"] = error_text[:400]

    report_title = str(result.get("report_title") or result.get("title") or "").strip()
    if report_title:
        job["report_title"] = report_title[:180]

    expires_at_raw = result.get("link_expires_at")
    try:
        expires_at = int(expires_at_raw or 0)
    except (TypeError, ValueError):
        expires_at = 0
    if expires_at > 0:
        job["link_expires_at"] = expires_at

    job["updated_at"] = int(time.time())
    set_research_job(run_id, job)
    return job


def is_valid_email(value: str) -> bool:
    email = str(value or "").strip()
    if not email or len(email) > 254:
        return False
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.fullmatch(pattern, email))


def parse_textbook_fields(raw: str) -> dict[str, str]:
    text = " ".join(str(raw or "").replace("\n", " ").split())
    fields: dict[str, str] = {}
    if not text:
        return fields

    isbn_match = re.search(r"\b(?:isbn(?:-1[03])?[:\s]*)?((?:97[89][\s-]?)?[0-9][0-9\s-]{8,}[0-9Xx])\b", text)
    if isbn_match:
        isbn = re.sub(r"[^0-9Xx]", "", isbn_match.group(1)).upper()
        if isbn:
            fields["isbn"] = isbn

    edition_match = re.search(r"\b(\d{1,2}(?:st|nd|rd|th)\s+ed(?:ition)?)\b", text, flags=re.IGNORECASE)
    if edition_match:
        fields["edition"] = edition_match.group(1)

    author_match = re.search(r"\bauthor[:\s]+([^,;|]+)", text, flags=re.IGNORECASE)
    if author_match:
        fields["author"] = author_match.group(1).strip()

    title_match = re.search(r"\btitle[:\s]+([^,;|]+)", text, flags=re.IGNORECASE)
    if title_match:
        fields["title"] = title_match.group(1).strip()

    course_match = re.search(r"\bcourse[:\s]+([^,;|]+)", text, flags=re.IGNORECASE)
    if course_match:
        fields["course"] = course_match.group(1).strip()

    return fields


def textbook_help_text() -> str:
    return (
        "📚 Textbook commands\n"
        "1) /textbook request <details>\n"
        "2) /textbook email <you@example.com>\n"
        "3) /textbook <n> (alias for /textbook pick <n>)\n"
        "4) /textbook confirm\n"
        "5) /textbook ingest <yes|no> (optional)\n"
        "\n"
        "Status + follow-up:\n"
        "• /textbook status\n"
        "• /textbook resend\n"
        "• /textbook delivered\n"
        "• /textbook failed <reason>\n"
        "• /textbook cancel\n"
        "\n"
        "Email tools:\n"
        "• /textbook email show\n"
        "• /textbook email clear\n"
        "\n"
        "Suggested request format:\n"
        "title: Calculus: Early Transcendentals, author: Stewart, edition: 8th, isbn: 9781285741550, course: MATH-2413"
    )


def workspace_help_text() -> str:
    return (
        "Workspace commands (temporary 24h knowledge):\n"
        "/workspace create <name>\n"
        "/workspace add <url-or-text>\n"
        "/workspace mode <auto|workspace|memory|status>\n"
        "/workspace status\n"
        "/workspace close\n"
        "\n"
        "Examples:\n"
        "/workspace create bmw-x5-manual\n"
        "/workspace add https://example.com/manuals/bmw-x5-2022.pdf\n"
        "/workspace add torque specs for rear axle are ..."
    )


def workspace_ttl_seconds() -> int:
    return max(3600, WORKSPACE_TTL_SECONDS)


def get_workspace(user_id: int) -> dict[str, Any] | None:
    active = WORKSPACE_STATE.get("active") or {}
    entry = active.get(str(user_id))
    return entry if isinstance(entry, dict) else None


def workspace_query_mode(entry: dict[str, Any] | None) -> str:
    if not isinstance(entry, dict):
        return "auto"
    mode = str(entry.get("query_mode", "auto")).strip().lower()
    if mode not in {"auto", "workspace", "memory"}:
        return "auto"
    return mode


def set_workspace(user_id: int, entry: dict[str, Any]) -> None:
    active = WORKSPACE_STATE.setdefault("active", {})
    active[str(user_id)] = entry
    WORKSPACE_STATE["active"] = active
    save_workspace_state(WORKSPACE_STATE)


def delete_workspace_doc_from_qdrant(tenant_id: str, doc_id: str) -> tuple[bool, str]:
    collection = f"day4_rag_{tenant_id}"
    url = f"http://qdrant:6333/collections/{collection}/points/delete?wait=true"
    payload = {
        "filter": {
            "must": [
                {"key": "doc_id", "match": {"value": doc_id}},
                {"key": "source_type", "match": {"value": "workspace_temp"}},
            ]
        }
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            if not raw:
                return True, "ok"
            parsed = json.loads(raw)
            status = str(((parsed.get("result") or {}).get("status") or "ok")).strip().lower()
            return (status in {"acknowledged", "completed", "ok"}, status or "ok")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return True, "collection_missing"
        return False, f"http_{exc.code}"
    except Exception as exc:
        return False, str(exc)


def clear_workspace(user_id: int, reason: str) -> tuple[int, int]:
    active = WORKSPACE_STATE.setdefault("active", {})
    entry = active.get(str(user_id))
    if not isinstance(entry, dict):
        return 0, 0

    tenant_id = f"u_{user_id}"
    docs_raw = entry.get("docs")
    docs = docs_raw if isinstance(docs_raw, list) else []
    removed = 0
    failed = 0
    for item in docs:
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("doc_id", "")).strip()
        if not doc_id:
            continue
        ok, _ = delete_workspace_doc_from_qdrant(tenant_id, doc_id)
        if ok:
            removed += 1
        else:
            failed += 1

    active.pop(str(user_id), None)
    WORKSPACE_STATE["active"] = active
    save_workspace_state(WORKSPACE_STATE)
    print(
        f"[telegram-bridge] workspace cleared user_id={user_id} reason={reason} removed={removed} failed={failed}",
        flush=True,
    )
    return removed, failed


def cleanup_expired_workspace_for_user(user_id: int, now_ts: int | None = None) -> tuple[bool, int, int]:
    now_value = int(now_ts if now_ts is not None else time.time())
    entry = get_workspace(user_id)
    if not entry:
        return False, 0, 0
    expires_at = parse_int(str(entry.get("expires_at", "0")), 0)
    if expires_at <= 0 or now_value < expires_at:
        return False, 0, 0
    removed, failed = clear_workspace(user_id, reason="expired")
    return True, removed, failed


def cleanup_expired_workspaces(now_ts: int | None = None) -> tuple[int, int, int]:
    now_value = int(now_ts if now_ts is not None else time.time())
    active = WORKSPACE_STATE.get("active") or {}
    if not isinstance(active, dict) or not active:
        return 0, 0, 0

    expired_users: list[int] = []
    for user_id_raw, entry in active.items():
        if not isinstance(entry, dict):
            continue
        expires_at = parse_int(str(entry.get("expires_at", "0")), 0)
        if expires_at > 0 and now_value >= expires_at:
            try:
                expired_users.append(int(user_id_raw))
            except ValueError:
                continue

    workspaces_cleared = 0
    docs_removed = 0
    docs_failed = 0
    for user_id in expired_users:
        removed, failed = clear_workspace(user_id, reason="expired")
        workspaces_cleared += 1
        docs_removed += removed
        docs_failed += failed
    return workspaces_cleared, docs_removed, docs_failed


def resolve_workspace_query_context(
    user_id: int,
    memory_enabled: bool,
    memory_summary: str,
) -> dict[str, Any]:
    expired_now, _, _ = cleanup_expired_workspace_for_user(user_id)
    entry = get_workspace(user_id)
    mode = workspace_query_mode(entry)
    workspace_active = isinstance(entry, dict)

    workspace_id = ""
    workspace_expires_at = 0
    workspace_doc_ids: list[str] = []
    if workspace_active and isinstance(entry, dict):
        workspace_id = str(entry.get("workspace_id", "")).strip()
        workspace_expires_at = parse_int(str(entry.get("expires_at", "0")), 0)
        docs_raw = entry.get("docs")
        docs = docs_raw if isinstance(docs_raw, list) else []
        workspace_doc_ids = [
            str(item.get("doc_id", "")).strip()
            for item in docs
            if isinstance(item, dict) and str(item.get("doc_id", "")).strip()
        ]

    if mode == "workspace":
        memory_enabled_effective = False
        memory_summary_effective = ""
    elif mode == "memory":
        memory_enabled_effective = bool(memory_enabled)
        memory_summary_effective = memory_summary
    else:
        memory_enabled_effective = bool(memory_enabled)
        memory_summary_effective = memory_summary

    return {
        "workspace_mode": mode,
        "workspace_active": workspace_active,
        "workspace_id": workspace_id,
        "workspace_expires_at": workspace_expires_at,
        "workspace_doc_ids": workspace_doc_ids,
        "workspace_expired_now": bool(expired_now),
        "memory_enabled_effective": memory_enabled_effective,
        "memory_summary_effective": memory_summary_effective,
        "workspace_context_only": mode == "workspace",
        "memory_context_only": mode == "memory",
    }


def clear_textbook_request(user_id: int) -> None:
    pending = TEXTBOOK_STATE.setdefault("pending", {})
    pending.pop(str(user_id), None)
    TEXTBOOK_STATE["pending"] = pending
    save_textbook_state(TEXTBOOK_STATE)


def get_textbook_request(user_id: int) -> dict[str, Any] | None:
    pending = TEXTBOOK_STATE.get("pending") or {}
    entry = pending.get(str(user_id))
    if not isinstance(entry, dict):
        return None
    created_at = parse_int(str(entry.get("created_at", "0")), 0)
    ttl = max(300, TEXTBOOK_REQUEST_TTL_SECONDS)
    if created_at <= 0 or int(time.time()) > created_at + ttl:
        clear_textbook_request(user_id)
        return None
    return entry


def clear_textbook_ingest_offer(user_id: int) -> None:
    pending = TEXTBOOK_STATE.setdefault("pending_ingest", {})
    pending.pop(str(user_id), None)
    TEXTBOOK_STATE["pending_ingest"] = pending
    save_textbook_state(TEXTBOOK_STATE)


def set_textbook_ingest_offer(user_id: int, offer: dict[str, Any]) -> None:
    pending = TEXTBOOK_STATE.setdefault("pending_ingest", {})
    pending[str(user_id)] = offer
    TEXTBOOK_STATE["pending_ingest"] = pending
    save_textbook_state(TEXTBOOK_STATE)


def get_textbook_ingest_offer(user_id: int) -> dict[str, Any] | None:
    pending = TEXTBOOK_STATE.get("pending_ingest") or {}
    offer = pending.get(str(user_id))
    if not isinstance(offer, dict):
        return None
    created_at = parse_int(str(offer.get("created_at", "0")), 0)
    ttl = max(300, TEXTBOOK_REQUEST_TTL_SECONDS)
    if created_at <= 0 or int(time.time()) > created_at + ttl:
        clear_textbook_ingest_offer(user_id)
        return None
    return offer


def set_textbook_last_fulfillment(user_id: int, payload: dict[str, Any]) -> None:
    history = TEXTBOOK_STATE.setdefault("last_fulfillment", {})
    history[str(user_id)] = payload
    TEXTBOOK_STATE["last_fulfillment"] = history
    save_textbook_state(TEXTBOOK_STATE)


def get_textbook_last_fulfillment(user_id: int) -> dict[str, Any] | None:
    history = TEXTBOOK_STATE.get("last_fulfillment") or {}
    entry = history.get(str(user_id))
    if not isinstance(entry, dict):
        return None
    created_at = parse_int(str(entry.get("created_at", "0")), 0)
    ttl = max(1800, TEXTBOOK_REQUEST_TTL_SECONDS * 4)
    if created_at <= 0 or int(time.time()) > created_at + ttl:
        history.pop(str(user_id), None)
        TEXTBOOK_STATE["last_fulfillment"] = history
        save_textbook_state(TEXTBOOK_STATE)
        return None
    return entry


def append_status_timeline(status_timeline: list[str], status_value: str) -> list[str]:
    timeline = [str(item).strip() for item in status_timeline if str(item).strip()]
    timeline.append(f"{utc_now()}:{status_value}")
    return timeline[-12:]


def is_textbook_file_url_allowed(file_url: str) -> tuple[bool, str]:
    candidate = str(file_url or "").strip()
    if not candidate:
        return False, "missing_file_url"

    parsed = urllib.parse.urlparse(candidate)
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return False, "missing_host"

    if not TEXTBOOK_ENFORCE_FILE_DOMAIN_ALLOWLIST:
        return True, "allowlist_disabled"

    if not TEXTBOOK_ALLOWED_FILE_DOMAINS:
        return False, "allowlist_empty"

    for pattern_raw in TEXTBOOK_ALLOWED_FILE_DOMAINS:
        pattern = str(pattern_raw or "").strip().lower()
        if not pattern:
            continue
        if pattern == "*":
            return True, "matched:*"
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if host.endswith(suffix):
                return True, f"matched:{pattern}"
            continue
        if pattern.startswith("."):
            if host.endswith(pattern):
                return True, f"matched:{pattern}"
            continue
        if host == pattern or host.endswith(f".{pattern}"):
            return True, f"matched:{pattern}"

    return False, f"untrusted_host:{host}"


def send_textbook_delivery_email(
    delivery_email: str,
    details: str,
    file_url: str,
    fulfillment_id: str,
    selected_candidate: dict[str, Any],
) -> tuple[bool, str]:
    if not TEXTBOOK_SMTP_HOST or not TEXTBOOK_SMTP_FROM:
        return False, "smtp_not_configured"
    if not is_valid_email(delivery_email):
        return False, "invalid_delivery_email"
    if not str(file_url or "").strip():
        return False, "missing_file_url"

    title = str(selected_candidate.get("title", "")).strip() if isinstance(selected_candidate, dict) else ""
    author = str(selected_candidate.get("authors") or selected_candidate.get("author") or "").strip() if isinstance(selected_candidate, dict) else ""
    subject = f"Textbook delivery: {title or 'requested material'}"

    body_lines = [
        "Your textbook request has a deliverable file candidate.",
        "",
        f"Fulfillment ID: {fulfillment_id or '(unknown)'}",
        f"Request details: {details}",
        f"Title: {title or '(unknown)'}",
        f"Author(s): {author or '(unknown)'}",
        "",
        f"Download link: {file_url}",
        "",
        "This delivery includes lawful-source material only.",
    ]

    msg = EmailMessage()
    msg["From"] = TEXTBOOK_SMTP_FROM
    msg["To"] = delivery_email
    msg["Subject"] = subject
    msg.set_content("\n".join(body_lines))

    timeout = 20
    try:
        if TEXTBOOK_SMTP_USE_SSL:
            with smtplib.SMTP_SSL(TEXTBOOK_SMTP_HOST, TEXTBOOK_SMTP_PORT, timeout=timeout) as smtp:
                if TEXTBOOK_SMTP_USER:
                    smtp.login(TEXTBOOK_SMTP_USER, TEXTBOOK_SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(TEXTBOOK_SMTP_HOST, TEXTBOOK_SMTP_PORT, timeout=timeout) as smtp:
                if TEXTBOOK_SMTP_USE_STARTTLS:
                    smtp.starttls()
                if TEXTBOOK_SMTP_USER:
                    smtp.login(TEXTBOOK_SMTP_USER, TEXTBOOK_SMTP_PASSWORD)
                smtp.send_message(msg)
        return True, "email_dispatched"
    except Exception as exc:
        return False, f"smtp_error:{exc}"


def strip_html_tags(value: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_from_epub_bytes(file_bytes: bytes, max_chars: int = 12000) -> str:
    if not file_bytes:
        return ""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            page_names = [
                name
                for name in archive.namelist()
                if name.lower().endswith((".xhtml", ".html", ".htm", ".xml"))
            ]
            page_names.sort()
            chunks: list[str] = []
            total = 0
            for name in page_names:
                try:
                    data = archive.read(name)
                except Exception:
                    continue
                text = strip_html_tags(data.decode("utf-8", errors="ignore"))
                if not text:
                    continue
                remaining = max(0, max_chars - total)
                if remaining <= 0:
                    break
                if len(text) > remaining:
                    text = text[:remaining]
                chunks.append(text)
                total += len(text)
                if total >= max_chars:
                    break
            return "\n\n".join(chunks).strip()
    except Exception:
        return ""


def extract_text_from_pdf_bytes(file_bytes: bytes, max_chars: int = 12000) -> str:
    if not file_bytes:
        return ""

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(file_bytes))
        chunks: list[str] = []
        total = 0
        for page in reader.pages:
            page_text = str(page.extract_text() or "").strip()
            if not page_text:
                continue
            remaining = max(0, max_chars - total)
            if remaining <= 0:
                break
            if len(page_text) > remaining:
                page_text = page_text[:remaining]
            chunks.append(page_text)
            total += len(page_text)
            if total >= max_chars:
                break
        return "\n\n".join(chunks).strip()
    except Exception:
        pass

    # Safe fallback when dedicated PDF parser is unavailable.
    try:
        decoded = file_bytes.decode("latin-1", errors="ignore")
    except Exception:
        return ""

    candidates = re.findall(r"\(([^\)]{4,})\)", decoded)
    cleaned = []
    for item in candidates:
        value = re.sub(r"\\[nrt]", " ", item)
        value = re.sub(r"\\\d{1,3}", "", value)
        value = re.sub(r"\s+", " ", value).strip()
        if len(value) >= 4:
            cleaned.append(value)
    text = " ".join(cleaned)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def extract_text_from_file_payload(file_bytes: bytes, content_type: str, file_url: str, max_chars: int = 12000) -> str:
    if not file_bytes:
        return ""

    ctype = str(content_type or "").lower()
    lower_url = str(file_url or "").lower()

    is_pdf = "application/pdf" in ctype or lower_url.endswith(".pdf")
    is_epub = "application/epub+zip" in ctype or lower_url.endswith(".epub")
    if is_pdf:
        return extract_text_from_pdf_bytes(file_bytes=file_bytes, max_chars=max_chars)
    if is_epub:
        return extract_text_from_epub_bytes(file_bytes=file_bytes, max_chars=max_chars)

    text_like = any(token in ctype for token in {"text/", "json", "xml", "yaml", "markdown", "html"})
    looks_text_ext = any(lower_url.endswith(ext) for ext in {".txt", ".md", ".markdown", ".json", ".html", ".htm", ".csv"})

    if not text_like and not looks_text_ext:
        return ""

    decoded = file_bytes.decode("utf-8", errors="ignore")
    if "html" in ctype or lower_url.endswith((".html", ".htm")):
        decoded = strip_html_tags(decoded)
    else:
        decoded = re.sub(r"\s+", " ", decoded).strip()

    if len(decoded) > max(1000, max_chars):
        return decoded[:max_chars].rstrip() + "…"
    return decoded


def fetch_ingest_text_from_file_url(file_url: str, file_mime: str, max_bytes: int = 2_500_000, max_chars: int = 12000) -> str:
    url = str(file_url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return ""

    request = urllib.request.Request(
        url=url,
        headers={"User-Agent": "servernoots-telegram-bridge/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
        content_type = str(response.headers.get("Content-Type") or file_mime or "").strip()
    return extract_text_from_file_payload(raw, content_type=content_type, file_url=url, max_chars=max_chars)


def load_rate_limit_state() -> dict[str, Any]:
    if not RATE_LIMIT_PATH.exists():
        return {"users": {}, "notified_users": {}}
    try:
        data = json.loads(RATE_LIMIT_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"users": {}, "notified_users": {}}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        notified_users = data.get("notified_users")
        if not isinstance(notified_users, dict):
            data["notified_users"] = {}
        return data
    except Exception:
        return {"users": {}, "notified_users": {}}


def save_rate_limit_state(state: dict[str, Any]) -> None:
    RATE_LIMIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


RATE_LIMIT_STATE = load_rate_limit_state()


def load_admin_command_cooldown_state() -> dict[str, Any]:
    if not ADMIN_COMMAND_COOLDOWN_PATH.exists():
        return {"entries": {}}
    try:
        data = json.loads(ADMIN_COMMAND_COOLDOWN_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"entries": {}}
        entries = data.get("entries")
        if not isinstance(entries, dict):
            data["entries"] = {}
        return data
    except Exception:
        return {"entries": {}}


def save_admin_command_cooldown_state(state: dict[str, Any]) -> None:
    ADMIN_COMMAND_COOLDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_COMMAND_COOLDOWN_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


ADMIN_COMMAND_COOLDOWN_COMMANDS = parse_command_keys(ADMIN_COMMAND_COOLDOWN_COMMANDS_RAW)
ADMIN_COMMAND_COOLDOWN_STATE = load_admin_command_cooldown_state()


def check_and_record_admin_command_cooldown(user_id: int, command_key: str) -> tuple[bool, int, bool]:
    cooldown_seconds = max(0, ADMIN_COMMAND_COOLDOWN_SECONDS)
    normalized_command = str(command_key or "").strip().lower()
    if cooldown_seconds <= 0 or not normalized_command or normalized_command not in ADMIN_COMMAND_COOLDOWN_COMMANDS:
        return False, 0, False

    now = int(time.time())
    keep_after = now - max(3600, cooldown_seconds * 4)

    entries_raw = ADMIN_COMMAND_COOLDOWN_STATE.get("entries") if isinstance(ADMIN_COMMAND_COOLDOWN_STATE, dict) else {}
    entries = entries_raw if isinstance(entries_raw, dict) else {}
    cleaned: dict[str, dict[str, int]] = {}
    for key, payload in entries.items():
        if not isinstance(payload, dict):
            continue
        try:
            last_executed = int(payload.get("last_executed", 0) or 0)
            last_notified = int(payload.get("last_notified", 0) or 0)
        except (TypeError, ValueError):
            continue
        if max(last_executed, last_notified) < keep_after:
            continue
        cleaned[str(key)] = {
            "last_executed": last_executed,
            "last_notified": last_notified,
        }

    key = f"{int(user_id)}:{normalized_command}"
    entry = cleaned.get(key, {"last_executed": 0, "last_notified": 0})
    try:
        last_executed = int(entry.get("last_executed", 0) or 0)
    except (TypeError, ValueError):
        last_executed = 0

    if last_executed > 0 and now - last_executed < cooldown_seconds:
        retry_after = max(1, cooldown_seconds - (now - last_executed))
        try:
            last_notified = int(entry.get("last_notified", 0) or 0)
        except (TypeError, ValueError):
            last_notified = 0
        should_notify = (now - last_notified) >= cooldown_seconds
        if should_notify:
            entry["last_notified"] = now
        cleaned[key] = {
            "last_executed": last_executed,
            "last_notified": int(entry.get("last_notified", 0) or 0),
        }
        ADMIN_COMMAND_COOLDOWN_STATE["entries"] = cleaned
        save_admin_command_cooldown_state(ADMIN_COMMAND_COOLDOWN_STATE)
        return True, retry_after, should_notify

    cleaned[key] = {
        "last_executed": now,
        "last_notified": 0,
    }
    ADMIN_COMMAND_COOLDOWN_STATE["entries"] = cleaned
    save_admin_command_cooldown_state(ADMIN_COMMAND_COOLDOWN_STATE)
    return False, 0, False


def enforce_admin_command_cooldown(chat_id: int, user_id: int, command_key: str) -> bool:
    blocked, retry_after, should_notify = check_and_record_admin_command_cooldown(user_id=user_id, command_key=command_key)
    if not blocked:
        return False
    if should_notify:
        send_message(chat_id, f"⏳ Command cooldown active. Try again in about {retry_after}s.")
    return True


def load_memory_state() -> dict[str, Any]:
    if not MEMORY_PATH.exists():
        return {"users": {}}
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"users": {}}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data
    except Exception:
        return {"users": {}}


def save_memory_state(state: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def append_memory_telemetry(
    event: str,
    *,
    user_id: int | None = None,
    fields: dict[str, Any] | None = None,
) -> None:
    if not MEMORY_TELEMETRY_ENABLED:
        return

    payload = fields if isinstance(fields, dict) else {}
    normalized_fields: dict[str, Any] = {}
    for raw_key, raw_value in payload.items():
        key = normalize_memory_source(str(raw_key), fallback="")
        if not key:
            continue
        if isinstance(raw_value, bool):
            normalized_fields[key] = raw_value
        elif isinstance(raw_value, int):
            normalized_fields[key] = raw_value
        elif isinstance(raw_value, float):
            normalized_fields[key] = round(raw_value, 3)
        elif isinstance(raw_value, str):
            normalized_fields[key] = " ".join(raw_value.split())[:160]
        elif raw_value is None:
            normalized_fields[key] = ""

    entry: dict[str, Any] = {
        "ts": utc_now(),
        "timestamp": int(time.time()),
        "event": normalize_memory_source(event, fallback="unknown"),
    }
    if isinstance(user_id, int) and user_id > 0:
        entry["user_id"] = int(user_id)
    if normalized_fields:
        entry["fields"] = normalized_fields

    try:
        MEMORY_TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MEMORY_TELEMETRY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[telegram-bridge] memory_telemetry_write_failed: {exc}", flush=True)


MEMORY_STATE = load_memory_state()


def sanitize_memory_text(text: str) -> str:
    value = " ".join(text.strip().split())
    value = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[redacted-token]", value)
    value = re.sub(r"\bsk-[A-Za-z0-9]{20,}\b", "[redacted-key]", value)
    return value[:240]


def normalize_memory_source(value: str, fallback: str = "unknown") -> str:
    source = re.sub(r"[^a-z0-9:_-]+", "_", str(value or "").strip().lower()).strip("_")
    return source or fallback


def clamp_memory_confidence(value: Any, fallback: float = 1.0) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = fallback
    confidence = min(1.0, max(0.0, confidence))
    return round(confidence, 3)


def sanitize_memory_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for raw_key, raw_val in value.items():
        key = normalize_memory_source(str(raw_key), fallback="")
        if not key:
            continue
        if isinstance(raw_val, (str, int, float, bool)):
            cleaned[key] = " ".join(str(raw_val).split())[:120] if isinstance(raw_val, str) else raw_val
    return cleaned


def normalize_memory_tier(value: Any, source: str = "") -> str:
    tier = str(value or "").strip().lower()
    if tier in MEMORY_TIER_ORDER:
        return tier
    source_norm = normalize_memory_source(source, fallback="")
    if source_norm in {"textbook_email_preference", "telegram_user_note", "user_note"}:
        return "preference"
    if source_norm in {"discord_profile", "profile_seed", "profile_fact"}:
        return "profile"
    return "session"


def memory_canary_bucket(user_id: int) -> int:
    if user_id <= 0:
        return 0
    digest = hashlib.sha256(f"{MEMORY_CANARY_SALT}:{user_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def is_memory_v2_canary_user(user_id: int) -> bool:
    if user_id in MEMORY_CANARY_EXCLUDE_USER_IDS:
        return False
    if user_id in MEMORY_CANARY_INCLUDE_USER_IDS:
        return True
    if not MEMORY_CANARY_ENABLED:
        return True
    if MEMORY_CANARY_PERCENT <= 0:
        return False
    if MEMORY_CANARY_PERCENT >= 100:
        return True
    return memory_canary_bucket(user_id) < MEMORY_CANARY_PERCENT


def detect_memory_conflict_candidate(
    existing_notes: list[dict[str, Any]],
    new_text: str,
    source: str,
    tier: str,
) -> dict[str, Any] | None:
    if tier not in {"profile", "preference"}:
        return None

    new_norm = re.sub(r"\s+", " ", new_text.strip().lower())
    if not new_norm:
        return None

    def extract_subject_value(raw_text: str) -> tuple[str, str]:
        text_value = re.sub(r"\s+", " ", str(raw_text or "").strip().lower())
        text_value = re.sub(r"^\s*(remember|note that|for future)\s+", "", text_value).strip()
        text_value = text_value.strip(".?! ")
        if not text_value:
            return "", ""

        my_match = re.match(r"^(?:my)\s+([a-z0-9 _-]{2,80}?)\s+(?:is|are|was|were)\s+(.+)$", text_value)
        if my_match:
            subject = re.sub(r"\s+", "_", my_match.group(1).strip())
            value = re.sub(r"\s+", " ", my_match.group(2).strip())
            return subject, value

        pref_match = re.match(r"^(?:i)\s+prefer\s+(.+)$", text_value)
        if pref_match:
            value = re.sub(r"\s+", " ", pref_match.group(1).strip())
            return "preference", value

        fav_match = re.match(r"^(?:my)\s+favorite\s+([a-z0-9 _-]{2,80}?)\s+(?:is|are)\s+(.+)$", text_value)
        if fav_match:
            subject = f"favorite_{re.sub(r'\\s+', '_', fav_match.group(1).strip())}"
            value = re.sub(r"\s+", " ", fav_match.group(2).strip())
            return subject, value

        return "", text_value

    new_subject, new_value = extract_subject_value(new_norm)

    lower_bound = max(0, len(existing_notes) - max(1, MEMORY_MAX_ITEMS))
    for index in range(len(existing_notes) - 1, lower_bound - 1, -1):
        item = existing_notes[index]
        if not isinstance(item, dict):
            continue
        item_tier = normalize_memory_tier(item.get("tier"), source=str(item.get("source", "")))
        item_source = normalize_memory_source(str(item.get("source", "")), fallback="unknown")
        if item_tier != tier or item_source != source:
            continue
        prior_text = re.sub(r"\s+", " ", str(item.get("text", "")).strip().lower())
        if not prior_text:
            continue

        prior_subject, prior_value = extract_subject_value(prior_text)
        if prior_text == new_norm:
            return None
        if prior_text in new_norm or new_norm in prior_text:
            return None

        if new_subject and prior_subject and new_subject != prior_subject:
            continue
        if new_subject and prior_subject and new_subject == prior_subject:
            if prior_value == new_value:
                return None
            return {
                "prior_index": index,
                "prior_ts": parse_int(str(item.get("ts", "0")), 0),
                "prior_source": item_source,
                "prior_tier": item_tier,
                "prior_preview": str(item.get("text", ""))[:120],
            }

        if new_subject or prior_subject:
            continue

        return {
            "prior_index": index,
            "prior_ts": parse_int(str(item.get("ts", "0")), 0),
            "prior_source": item_source,
            "prior_tier": item_tier,
            "prior_preview": str(item.get("text", ""))[:120],
        }
    return None


def memory_conflict_group_id(source: str, tier: str, prior_ts: int, new_ts: int) -> str:
    source_norm = normalize_memory_source(source, fallback="unknown")
    tier_norm = normalize_memory_tier(tier, source=source_norm)
    older_ts = min(prior_ts, new_ts)
    newer_ts = max(prior_ts, new_ts)
    return f"memory_conflict_{source_norm}_{tier_norm}_{older_ts}_{newer_ts}"


def clear_memory_conflict_fields(item: dict[str, Any]) -> None:
    item.pop("conflict_candidate", None)
    item.pop("conflict_hint", None)
    item.pop("conflict_group", None)
    item.pop("conflict_detected_ts", None)
    provenance = item.get("provenance")
    if isinstance(provenance, dict):
        provenance.pop("conflict_candidate", None)
        if not provenance:
            item.pop("provenance", None)


def get_memory_conflict_detected_ts(item: dict[str, Any]) -> int:
    detected_ts = parse_int(str(item.get("conflict_detected_ts", "0")), 0)
    if detected_ts > 0:
        return detected_ts
    item_ts = parse_int(str(item.get("ts", "0")), 0)
    hint = item.get("conflict_hint") if isinstance(item.get("conflict_hint"), dict) else {}
    prior_ts = parse_int(str(hint.get("prior_ts", "0")), 0)
    if item_ts > 0 and prior_ts > 0:
        return max(item_ts, prior_ts)
    return max(item_ts, prior_ts)


def summarize_user_memory_conflicts(entry: dict[str, Any], now_ts: int | None = None) -> dict[str, Any]:
    now_value = int(now_ts or time.time())
    notes_raw = entry.get("notes") if isinstance(entry, dict) else []
    notes = notes_raw if isinstance(notes_raw, list) else []
    total = 0
    stale = 0
    oldest_age_seconds = 0
    for item in notes:
        if not isinstance(item, dict):
            continue
        if not bool(item.get("conflict_candidate", False)):
            continue
        total += 1
        detected_ts = get_memory_conflict_detected_ts(item)
        if detected_ts <= 0:
            continue
        age_seconds = max(0, now_value - detected_ts)
        oldest_age_seconds = max(oldest_age_seconds, age_seconds)
        if MEMORY_CONFLICT_REMINDER_ENABLED and age_seconds >= MEMORY_CONFLICT_REMINDER_SECONDS:
            stale += 1
    return {
        "total": total,
        "stale": stale,
        "oldest_age_seconds": oldest_age_seconds,
    }


def infer_memory_intent_scope(message_text: str, mode: str = "", user_id: int | None = None) -> str | None:
    if not MEMORY_INTENT_SCOPE_ENABLED:
        return None
    if isinstance(user_id, int) and user_id > 0 and not is_memory_v2_canary_user(user_id):
        return None

    text = re.sub(r"\s+", " ", str(message_text or "").strip().lower())
    mode_norm = str(mode or "").strip().lower()
    if mode_norm == "ops":
        return "ops"
    if not text:
        return None

    style_patterns = [
        r"\bstyle\b",
        r"\btone\b",
        r"\bbrevity\b",
        r"\bconcise\b",
        r"\bverbose\b",
        r"\bformal\b",
        r"\bcasual\b",
    ]
    media_patterns = [
        r"\bplex\b",
        r"\boverseerr\b",
        r"\bradarr\b",
        r"\bsonarr\b",
        r"\bmovie\b",
        r"\bshow\b",
        r"\bepisode\b",
        r"\bmedia\b",
    ]
    identity_patterns = [
        r"\bwho am i\b",
        r"\bmy name\b",
        r"\blegal name\b",
        r"\bname do you have for me\b",
        r"\bname is stored\b",
        r"\bstored name\b",
        r"\bmemory profile\b",
        r"\bidentity check\b",
        r"\bcall me\b",
        r"\bpronoun\b",
        r"\babout me\b",
        r"\bprofile\b",
    ]
    ops_patterns = [
        r"\bops\b",
        r"\brestart\b",
        r"\bservice\b",
        r"\bincident\b",
        r"\bhealth\b",
        r"\bstatus\b",
        r"\bdeploy\b",
        r"\bworkflow\b",
        r"\balert\b",
    ]

    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in style_patterns):
        return "style"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in media_patterns):
        return "media"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in identity_patterns):
        return "identity"
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in ops_patterns):
        return "ops"
    return None


def memory_note_matches_intent_scope(item: dict[str, Any], scope: str) -> bool:
    scope_norm = str(scope or "").strip().lower()
    if not scope_norm:
        return True

    text = re.sub(r"\s+", " ", str(item.get("text", "")).strip().lower())
    source = normalize_memory_source(str(item.get("source", "unknown")), fallback="unknown")
    tier = normalize_memory_tier(item.get("tier"), source=source)
    provenance = sanitize_memory_provenance(item.get("provenance"))
    command = normalize_memory_source(str(provenance.get("command", "")), fallback="")

    if scope_norm == "identity":
        if tier == "profile":
            return True
        return any(token in text for token in ["my name", "call me", "pronoun", "identity", "about me"])

    if scope_norm == "style":
        if command in {"feedback", "profile_style_set", "profile_style_reset"}:
            return True
        return any(token in text for token in ["style", "tone", "brevity", "concise", "formal", "casual"])

    if scope_norm == "media":
        return any(token in text for token in ["plex", "movie", "show", "episode", "overseerr", "radarr", "sonarr", "media"])

    if scope_norm == "ops":
        if source in {"ops_command", "ops_audit", "ops_alert", "incident_note"}:
            return True
        return any(token in text for token in ["ops", "restart", "service", "health", "status", "incident", "alert", "workflow", "deploy"])

    return True


def memory_write_gate_decision(
    text: str,
    source: str,
    tier: str,
    confidence: float,
    provenance: dict[str, Any] | None,
) -> tuple[bool, str]:
    raw_text = str(text or "").strip()
    if not raw_text:
        return False, "empty"

    source_norm = normalize_memory_source(source, fallback="user_note")
    tier_norm = normalize_memory_tier(tier, source=source_norm)
    confidence_norm = clamp_memory_confidence(confidence, fallback=0.0)

    if confidence_norm < MEMORY_WRITE_MIN_CONFIDENCE and source_norm not in MEMORY_WRITE_TRUSTED_SOURCES:
        return False, "low_confidence"

    sensitive_patterns = [
        r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\b(?:password|passwd|api[_ -]?key|secret|token|private[_ -]?key|ssh-rsa|bearer)\b",
    ]
    if any(re.search(pattern, raw_text, flags=re.IGNORECASE) for pattern in sensitive_patterns):
        return False, "sensitive_data"

    if source_norm in MEMORY_WRITE_TRUSTED_SOURCES:
        return True, "trusted_source"

    provenance_dict = provenance if isinstance(provenance, dict) else {}
    command = normalize_memory_source(str(provenance_dict.get("command", "")), fallback="")
    explicit_markers = [
        r"\bremember\b",
        r"\bsave this\b",
        r"\bnote that\b",
        r"\bfor future\b",
        r"\bmy preference\b",
        r"\bi prefer\b",
        r"\bdefault for me\b",
    ]
    explicit_intent = command == "memory_add" or any(
        re.search(pattern, raw_text, flags=re.IGNORECASE) for pattern in explicit_markers
    )

    if MEMORY_WRITE_REQUIRE_EXPLICIT_FOR_USER_NOTES and tier_norm in {"profile", "preference"} and not explicit_intent:
        return False, "explicit_intent_required"

    return True, "pass"


def memory_note_rank_score(item: dict[str, Any], now_ts: int | None = None) -> float:
    now_value = int(now_ts or time.time())
    ts_value = parse_int(str(item.get("ts", "0")), 0)
    age_seconds = max(0, now_value - ts_value)

    source = normalize_memory_source(str(item.get("source", "legacy_note")), fallback="legacy_note")
    tier = normalize_memory_tier(item.get("tier"), source=source)
    half_life_days = {
        "profile": MEMORY_RECENCY_HALF_LIFE_DAYS_PROFILE,
        "preference": MEMORY_RECENCY_HALF_LIFE_DAYS_PREFERENCE,
        "session": MEMORY_RECENCY_HALF_LIFE_DAYS_SESSION,
    }.get(tier, MEMORY_RECENCY_HALF_LIFE_DAYS)
    half_life_seconds = max(1.0, half_life_days * 86400.0)
    recency_decay = 0.5 ** (age_seconds / half_life_seconds)

    source_trust = MEMORY_SOURCE_TRUST.get(source, 0.75)
    confidence = clamp_memory_confidence(item.get("confidence"), fallback=0.9)

    tier_boost = {
        "profile": 1.15,
        "preference": 1.05,
        "session": 1.0,
    }.get(tier, 1.0)

    score = confidence * recency_decay * source_trust * tier_boost
    return round(float(score), 6)


def get_memory_entry(user_id: int) -> dict[str, Any]:
    users = MEMORY_STATE.setdefault("users", {})
    key = str(user_id)
    entry = users.get(key)
    if not isinstance(entry, dict):
        entry = {
            "enabled": MEMORY_ENABLED_BY_DEFAULT,
            "notes": [],
            "updated_at": int(time.time()),
        }
        users[key] = entry
    if not isinstance(entry.get("notes"), list):
        entry["notes"] = []
    if "enabled" not in entry:
        entry["enabled"] = MEMORY_ENABLED_BY_DEFAULT
    return entry


def clamp_memory_feedback_weight(value: Any, fallback: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = fallback
    numeric = min(1.25, max(0.8, numeric))
    return round(numeric, 3)


def get_memory_feedback_model(entry: dict[str, Any]) -> dict[str, Any]:
    raw_model = entry.get("feedback_model") if isinstance(entry, dict) else {}
    model = raw_model if isinstance(raw_model, dict) else {}
    tier_weights_raw = model.get("tier_weights") if isinstance(model.get("tier_weights"), dict) else {}
    source_weights_raw = model.get("source_weights") if isinstance(model.get("source_weights"), dict) else {}
    tier_weights: dict[str, float] = {}
    source_weights: dict[str, float] = {}

    for tier in MEMORY_TIER_ORDER:
        tier_weights[tier] = clamp_memory_feedback_weight(tier_weights_raw.get(tier, 1.0), fallback=1.0)

    for source_key, source_value in source_weights_raw.items():
        key = normalize_memory_source(str(source_key), fallback="")
        if not key:
            continue
        source_weights[key] = clamp_memory_feedback_weight(source_value, fallback=1.0)

    return {
        "global_weight": clamp_memory_feedback_weight(model.get("global_weight", 1.0), fallback=1.0),
        "tier_weights": tier_weights,
        "source_weights": source_weights,
        "signal_counts": model.get("signal_counts") if isinstance(model.get("signal_counts"), dict) else {},
        "updated_at": str(model.get("updated_at", "") or ""),
        "last_signal": str(model.get("last_signal", "") or ""),
    }


def adjust_memory_feedback_weight(current: Any, delta: float) -> float:
    return clamp_memory_feedback_weight(clamp_memory_feedback_weight(current, fallback=1.0) + delta, fallback=1.0)


def record_memory_feedback_signal(
    user_id: int,
    signal: str,
    note_source: str = "",
    note_tier: str = "",
) -> None:
    if not MEMORY_FEEDBACK_RANKING_ENABLED:
        return

    entry = get_memory_entry(user_id)
    model = get_memory_feedback_model(entry)
    signal_norm = normalize_memory_source(signal, fallback="unknown")
    source_norm = normalize_memory_source(note_source, fallback="")
    tier_norm = normalize_memory_tier(note_tier, source=source_norm) if note_tier else ""

    tier_weights = model.get("tier_weights") if isinstance(model.get("tier_weights"), dict) else {}
    source_weights = model.get("source_weights") if isinstance(model.get("source_weights"), dict) else {}
    signal_counts = model.get("signal_counts") if isinstance(model.get("signal_counts"), dict) else {}
    signal_counts[signal_norm] = int(signal_counts.get(signal_norm, 0) or 0) + 1

    global_weight = clamp_memory_feedback_weight(model.get("global_weight", 1.0), fallback=1.0)

    if signal_norm == "conflict_keep":
        if source_norm:
            source_weights[source_norm] = adjust_memory_feedback_weight(source_weights.get(source_norm, 1.0), 0.06)
        if tier_norm:
            tier_weights[tier_norm] = adjust_memory_feedback_weight(tier_weights.get(tier_norm, 1.0), 0.04)
    elif signal_norm == "conflict_drop":
        if source_norm:
            source_weights[source_norm] = adjust_memory_feedback_weight(source_weights.get(source_norm, 1.0), -0.08)
        if tier_norm:
            tier_weights[tier_norm] = adjust_memory_feedback_weight(tier_weights.get(tier_norm, 1.0), -0.05)
    elif signal_norm == "feedback_too_vague":
        tier_weights["preference"] = adjust_memory_feedback_weight(tier_weights.get("preference", 1.0), 0.03)
        tier_weights["profile"] = adjust_memory_feedback_weight(tier_weights.get("profile", 1.0), 0.02)
    elif signal_norm == "feedback_too_short":
        tier_weights["session"] = adjust_memory_feedback_weight(tier_weights.get("session", 1.0), 0.02)
        tier_weights["preference"] = adjust_memory_feedback_weight(tier_weights.get("preference", 1.0), 0.01)
    elif signal_norm == "feedback_too_long":
        tier_weights["session"] = adjust_memory_feedback_weight(tier_weights.get("session", 1.0), -0.03)
    elif signal_norm == "feedback_good":
        global_weight = adjust_memory_feedback_weight(global_weight, 0.01)

    entry["feedback_model"] = {
        "global_weight": global_weight,
        "tier_weights": tier_weights,
        "source_weights": source_weights,
        "signal_counts": signal_counts,
        "updated_at": utc_now(),
        "last_signal": signal_norm,
    }
    entry["updated_at"] = int(time.time())
    save_memory_state(MEMORY_STATE)

    append_memory_telemetry(
        "feedback_signal",
        user_id=user_id,
        fields={
            "signal": signal_norm,
            "source": source_norm,
            "tier": tier_norm,
            "global_weight": global_weight,
        },
    )


def memory_feedback_rank_multiplier(entry: dict[str, Any], item: dict[str, Any]) -> float:
    if not MEMORY_FEEDBACK_RANKING_ENABLED:
        return 1.0

    model = get_memory_feedback_model(entry)
    global_weight = clamp_memory_feedback_weight(model.get("global_weight", 1.0), fallback=1.0)
    source = normalize_memory_source(str(item.get("source", "")), fallback="")
    tier = normalize_memory_tier(item.get("tier"), source=source)
    source_weights = model.get("source_weights") if isinstance(model.get("source_weights"), dict) else {}
    tier_weights = model.get("tier_weights") if isinstance(model.get("tier_weights"), dict) else {}
    source_weight = clamp_memory_feedback_weight(source_weights.get(source, 1.0), fallback=1.0)
    tier_weight = clamp_memory_feedback_weight(tier_weights.get(tier, 1.0), fallback=1.0)
    return round(global_weight * source_weight * tier_weight, 6)


def prune_memory_entry(entry: dict[str, Any], now_ts: int | None = None) -> bool:
    changed = False
    now_value = int(now_ts or time.time())
    ttl_seconds = max(1, MEMORY_TTL_DAYS) * 86400
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []
    kept: list[dict[str, Any]] = []
    for item in notes:
        if not isinstance(item, dict):
            changed = True
            continue
        try:
            ts = int(item.get("ts", 0))
        except (TypeError, ValueError):
            changed = True
            continue
        if ts + ttl_seconds < now_value:
            changed = True
            continue
        text = sanitize_memory_text(str(item.get("text", "")))
        if not text:
            changed = True
            continue
        source = normalize_memory_source(str(item.get("source", "legacy_note")), fallback="legacy_note")
        tier = normalize_memory_tier(item.get("tier"), source=source)
        confidence = clamp_memory_confidence(item.get("confidence"), fallback=0.9)
        provenance = sanitize_memory_provenance(item.get("provenance"))
        if str(item.get("tier", "")).strip().lower() != tier:
            changed = True
        kept_item: dict[str, Any] = {
            "text": text,
            "ts": ts,
            "captured_at": ts,
            "source": source,
            "tier": tier,
            "confidence": confidence,
        }
        if provenance:
            kept_item["provenance"] = provenance
        if bool(item.get("conflict_candidate", False)):
            kept_item["conflict_candidate"] = True
            conflict_hint = item.get("conflict_hint")
            if isinstance(conflict_hint, dict):
                kept_hint: dict[str, Any] = {}
                prior_index = parse_int(str(conflict_hint.get("prior_index", "-1")), -1)
                if prior_index >= 0:
                    kept_hint["prior_index"] = prior_index
                prior_ts = parse_int(str(conflict_hint.get("prior_ts", "0")), 0)
                if prior_ts > 0:
                    kept_hint["prior_ts"] = prior_ts
                prior_source = normalize_memory_source(str(conflict_hint.get("prior_source", "")), fallback="")
                if prior_source:
                    kept_hint["prior_source"] = prior_source
                prior_tier = normalize_memory_tier(conflict_hint.get("prior_tier"), source=prior_source)
                if prior_tier:
                    kept_hint["prior_tier"] = prior_tier
                prior_preview = sanitize_memory_text(str(conflict_hint.get("prior_preview", "")))
                if prior_preview:
                    kept_hint["prior_preview"] = prior_preview
                if kept_hint:
                    kept_item["conflict_hint"] = kept_hint
            conflict_group = normalize_memory_source(str(item.get("conflict_group", "")), fallback="")
            if conflict_group:
                kept_item["conflict_group"] = conflict_group
            conflict_detected_ts = get_memory_conflict_detected_ts(item)
            if conflict_detected_ts > 0:
                kept_item["conflict_detected_ts"] = conflict_detected_ts
        write_gate = normalize_memory_source(str(item.get("write_gate", "")), fallback="")
        if write_gate:
            kept_item["write_gate"] = write_gate
        kept.append(kept_item)
    if len(kept) > max(1, MEMORY_MAX_ITEMS):
        kept = kept[-max(1, MEMORY_MAX_ITEMS) :]
        changed = True
    entry["notes"] = kept
    return changed


def get_memory_context(user_id: int, intent_scope: str | None = None) -> tuple[bool, str, list[dict[str, Any]]]:
    started = time.perf_counter()
    canary_v2_enabled = is_memory_v2_canary_user(user_id)
    use_conflict_confirmation = MEMORY_CONFLICT_REQUIRE_CONFIRMATION and canary_v2_enabled
    use_intent_scope = MEMORY_INTENT_SCOPE_ENABLED and canary_v2_enabled
    entry = get_memory_entry(user_id)
    changed = prune_memory_entry(entry)
    notes = entry.get("notes") if isinstance(entry.get("notes"), list) else []
    enabled = bool(entry.get("enabled", False))
    scope_norm = str(intent_scope or "").strip().lower()
    summary = ""
    provenance: list[dict[str, Any]] = []
    filtered_notes = []
    conflict_count = 0
    conflict_withheld_count = 0
    low_confidence_dropped = 0
    scope_matched_count = 0
    scope_unmatched_count = 0
    synthesis_input_count = 0
    synthesis_output_count = 0
    ranked_before_scope_count = 0
    if enabled and notes:
        now_value = int(time.time())
        scored_notes: list[tuple[float, dict[str, Any]]] = []
        for item in notes:
            if not isinstance(item, dict):
                continue
            if bool(item.get("conflict_candidate", False)):
                conflict_count += 1
                if use_conflict_confirmation:
                    conflict_withheld_count += 1
                    continue
            if clamp_memory_confidence(item.get("confidence"), fallback=1.0) < MEMORY_MIN_CONFIDENCE:
                low_confidence_dropped += 1
                continue
            base_score = memory_note_rank_score(item, now_ts=now_value)
            feedback_multiplier = memory_feedback_rank_multiplier(entry, item)
            scored_notes.append((round(base_score * feedback_multiplier, 6), item))

        scored_notes.sort(
            key=lambda pair: (
                -pair[0],
                MEMORY_TIER_ORDER.get(
                    normalize_memory_tier(pair[1].get("tier"), source=str(pair[1].get("source", ""))),
                    99,
                ),
                -parse_int(str(pair[1].get("ts", "0")), 0),
            )
        )
        filtered_notes = [item for _, item in scored_notes]
        ranked_before_scope_count = len(filtered_notes)

        if scope_norm and use_intent_scope:
            scoped_scored_notes = [(score, item) for score, item in scored_notes if memory_note_matches_intent_scope(item, scope_norm)]
            scope_matched_count = len(scoped_scored_notes)
            scope_unmatched_count = max(0, len(scored_notes) - scope_matched_count)
            if scoped_scored_notes:
                scored_notes = scoped_scored_notes
                filtered_notes = [item for _, item in scored_notes]
            else:
                filtered_notes = []
                scored_notes = []

        if MEMORY_SYNTHESIS_ENABLED and filtered_notes:
            synthesis_input_count = len(filtered_notes)
            synthesized_scored_notes: list[tuple[float, dict[str, Any]]] = []
            seen_texts: set[str] = set()
            seen_keys: set[str] = set()

            def memory_synthesis_key(note_item: dict[str, Any]) -> str:
                text_value = re.sub(r"\s+", " ", str(note_item.get("text", "")).strip().lower())
                text_value = re.sub(r"^\s*(remember|note that|for future)\s+", "", text_value)
                if not text_value:
                    return ""

                tier_value = normalize_memory_tier(
                    note_item.get("tier"),
                    source=str(note_item.get("source", "")),
                )

                matcher = re.match(
                    r"^(?:my|i)\s+([a-z0-9 _-]{2,80}?)(?:\s+(?:is|are|was|were|like|likes|prefer|prefers|favorite|favourite|from)\b|$)",
                    text_value,
                )
                if matcher:
                    subject_key = re.sub(r"\s+", "_", matcher.group(1).strip())
                    return f"{tier_value}:{subject_key}"

                tokens = re.findall(r"[a-z0-9]+", text_value)
                if not tokens:
                    return ""
                take_count = 6 if tier_value in {"profile", "preference"} else 8
                return f"{tier_value}:{'_'.join(tokens[:take_count])}"

            synthesis_limit = min(max(1, MEMORY_SYNTHESIS_MAX_ITEMS), max(1, MEMORY_MAX_ITEMS))
            for score, item in scored_notes:
                if not isinstance(item, dict):
                    continue
                normalized_text = re.sub(r"\s+", " ", str(item.get("text", "")).strip().lower())
                if not normalized_text or normalized_text in seen_texts:
                    continue

                synthesis_key = memory_synthesis_key(item)
                if synthesis_key and synthesis_key in seen_keys:
                    continue

                seen_texts.add(normalized_text)
                if synthesis_key:
                    seen_keys.add(synthesis_key)
                synthesized_scored_notes.append((score, item))
                if len(synthesized_scored_notes) >= synthesis_limit:
                    break

            if synthesized_scored_notes:
                scored_notes = synthesized_scored_notes
                filtered_notes = [item for _, item in scored_notes]
            synthesis_output_count = len(filtered_notes)

        lines = [str(item.get("text", "")).strip() for item in filtered_notes if isinstance(item, dict)]
        lines = [line for line in lines if line]
        if conflict_count > 0 and MEMORY_CONFLICT_PROMPT_ENABLED and use_conflict_confirmation:
            lines.append(
                f"⚠️ {conflict_count} memory conflict candidate(s) need confirmation; ask user to run /memory conflicts and /memory resolve."
            )
        summary = "\n".join(f"- {line}" for line in lines[: max(1, MEMORY_MAX_ITEMS)])
        if len(summary) > max(100, MEMORY_MAX_CHARS):
            summary = summary[: MEMORY_MAX_CHARS].rsplit("\n", 1)[0].strip()

        for score, item in scored_notes[:8]:
            if not isinstance(item, dict):
                continue
            note_meta: dict[str, Any] = {
                "source": normalize_memory_source(str(item.get("source", "unknown"))),
                "tier": normalize_memory_tier(item.get("tier"), source=str(item.get("source", ""))),
                "confidence": clamp_memory_confidence(item.get("confidence"), fallback=1.0),
                "ts": parse_int(str(item.get("ts", "0")), 0),
                "conflict_candidate": bool(item.get("conflict_candidate", False)),
                "score": score,
                "feedback_multiplier": memory_feedback_rank_multiplier(entry, item),
            }
            note_provenance = sanitize_memory_provenance(item.get("provenance"))
            if note_provenance:
                note_meta["provenance"] = note_provenance
            provenance.append(note_meta)
    if changed:
        entry["updated_at"] = int(time.time())
        save_memory_state(MEMORY_STATE)

    latency_ms = max(0.0, (time.perf_counter() - started) * 1000.0)
    note_count = len(notes) if isinstance(notes, list) else 0
    append_memory_telemetry(
        "context",
        user_id=user_id,
        fields={
            "enabled": enabled,
            "intent_scope": scope_norm,
            "total_notes": note_count,
            "ranked_before_scope": ranked_before_scope_count,
            "returned_notes": len(filtered_notes),
            "conflict_candidates": conflict_count,
            "conflict_withheld": conflict_withheld_count,
            "low_confidence_dropped": low_confidence_dropped,
            "scope_matched": scope_matched_count,
            "scope_unmatched": scope_unmatched_count,
            "synthesis_input": synthesis_input_count,
            "synthesis_output": synthesis_output_count,
            "changed": changed,
            "memory_v2_canary": canary_v2_enabled,
            "use_conflict_confirmation": use_conflict_confirmation,
            "use_intent_scope": use_intent_scope,
            "latency_ms": latency_ms,
        },
    )
    return enabled, summary, provenance


def get_memory_summary(user_id: int, intent_scope: str | None = None) -> tuple[bool, str]:
    enabled, summary, _ = get_memory_context(user_id, intent_scope=intent_scope)
    return enabled, summary


def set_memory_enabled(user_id: int, enabled: bool) -> None:
    entry = get_memory_entry(user_id)
    entry["enabled"] = bool(enabled)
    entry["updated_at"] = int(time.time())
    save_memory_state(MEMORY_STATE)


def clear_memory(user_id: int) -> None:
    entry = get_memory_entry(user_id)
    entry["notes"] = []
    entry["updated_at"] = int(time.time())
    save_memory_state(MEMORY_STATE)


def add_memory_note(
    user_id: int,
    text: str,
    source: str = "user_note",
    confidence: float = 1.0,
    provenance: dict[str, Any] | None = None,
    tier: str = "session",
) -> tuple[bool, int, str]:
    entry = get_memory_entry(user_id)
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []
    allowed, gate_reason = memory_write_gate_decision(
        text=text,
        source=source,
        tier=tier,
        confidence=confidence,
        provenance=provenance,
    )
    normalized_source = normalize_memory_source(source, fallback="user_note")
    normalized_tier = normalize_memory_tier(tier, source=source)
    normalized_confidence = clamp_memory_confidence(confidence, fallback=1.0)
    append_memory_telemetry(
        "write_gate",
        user_id=user_id,
        fields={
            "allowed": allowed,
            "reason": gate_reason,
            "source": normalized_source,
            "tier": normalized_tier,
            "confidence": normalized_confidence,
        },
    )
    if not allowed:
        return False, len(notes), gate_reason

    clean = sanitize_memory_text(text)
    if not clean:
        return False, len(notes), "empty"
    ts = int(time.time())
    note: dict[str, Any] = {
        "text": clean,
        "ts": ts,
        "captured_at": ts,
        "source": normalized_source,
        "tier": normalized_tier,
        "confidence": normalized_confidence,
    }
    cleaned_provenance = sanitize_memory_provenance(provenance)
    conflict_hint = detect_memory_conflict_candidate(
        existing_notes=notes,
        new_text=clean,
        source=normalized_source,
        tier=normalized_tier,
    )
    if conflict_hint:
        prior_index = parse_int(str(conflict_hint.get("prior_index", "-1")), -1)
        prior_ts = parse_int(str(conflict_hint.get("prior_ts", "0")), 0)
        conflict_detected_ts = max(ts, prior_ts)
        group_id = memory_conflict_group_id(normalized_source, normalized_tier, prior_ts, ts)
        note["conflict_candidate"] = True
        note["conflict_group"] = group_id
        note["conflict_hint"] = conflict_hint
        note["conflict_detected_ts"] = conflict_detected_ts
        if "conflict_candidate" not in cleaned_provenance:
            cleaned_provenance["conflict_candidate"] = True
        if 0 <= prior_index < len(notes) and isinstance(notes[prior_index], dict):
            prior_item = notes[prior_index]
            prior_item["conflict_candidate"] = True
            prior_item["conflict_group"] = group_id
            prior_item["conflict_detected_ts"] = conflict_detected_ts
            prior_item["conflict_hint"] = {
                "prior_ts": ts,
                "prior_source": normalized_source,
                "prior_tier": normalized_tier,
                "prior_preview": clean[:120],
            }
            prior_provenance = sanitize_memory_provenance(prior_item.get("provenance"))
            prior_provenance["conflict_candidate"] = True
            prior_item["provenance"] = prior_provenance
            notes[prior_index] = prior_item
        append_memory_telemetry(
            "conflict_detected",
            user_id=user_id,
            fields={
                "source": normalized_source,
                "tier": normalized_tier,
                "prior_ts": prior_ts,
                "new_ts": ts,
            },
        )
    if cleaned_provenance:
        note["provenance"] = cleaned_provenance
    note["write_gate"] = gate_reason
    notes.append(note)
    entry["notes"] = notes
    prune_memory_entry(entry)
    entry["updated_at"] = int(time.time())
    save_memory_state(MEMORY_STATE)
    append_memory_telemetry(
        "write_commit",
        user_id=user_id,
        fields={
            "reason": gate_reason,
            "source": normalized_source,
            "tier": normalized_tier,
            "confidence": normalized_confidence,
            "conflict_candidate": bool(note.get("conflict_candidate", False)),
            "total_notes": len(entry.get("notes", [])),
        },
    )
    return True, len(entry.get("notes", [])), gate_reason


def list_memory_conflicts(user_id: int) -> list[dict[str, Any]]:
    entry = get_memory_entry(user_id)
    changed = prune_memory_entry(entry)
    now_value = int(time.time())
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []
    conflicts: list[dict[str, Any]] = []
    for index, item in enumerate(notes, start=1):
        if not isinstance(item, dict):
            continue
        if not bool(item.get("conflict_candidate", False)):
            continue
        detected_ts = get_memory_conflict_detected_ts(item)
        age_seconds = max(0, now_value - detected_ts) if detected_ts > 0 else 0
        needs_reminder = bool(
            MEMORY_CONFLICT_REMINDER_ENABLED
            and detected_ts > 0
            and age_seconds >= MEMORY_CONFLICT_REMINDER_SECONDS
        )
        conflicts.append(
            {
                "index": index,
                "text": str(item.get("text", "")).strip(),
                "source": normalize_memory_source(str(item.get("source", "unknown"))),
                "tier": normalize_memory_tier(item.get("tier"), source=str(item.get("source", ""))),
                "ts": parse_int(str(item.get("ts", "0")), 0),
                "conflict_detected_ts": detected_ts,
                "age_seconds": age_seconds,
                "age": format_age_from_unix_ts(detected_ts, now_ts=now_value) if detected_ts > 0 else "unknown",
                "needs_reminder": needs_reminder,
                "hint": item.get("conflict_hint") if isinstance(item.get("conflict_hint"), dict) else {},
            }
        )
    if changed:
        entry["updated_at"] = int(time.time())
        save_memory_state(MEMORY_STATE)
    return conflicts


def resolve_memory_conflict(user_id: int, index: int, action: str) -> tuple[bool, str]:
    entry = get_memory_entry(user_id)
    prune_memory_entry(entry)
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []
    notes_before = len(notes)
    if index < 1 or index > len(notes):
        append_memory_telemetry(
            "conflict_resolve",
            user_id=user_id,
            fields={"action": action, "success": False, "reason": "index_out_of_range", "notes_before": notes_before},
        )
        return False, "Conflict index out of range."

    item = notes[index - 1]
    if not isinstance(item, dict):
        append_memory_telemetry(
            "conflict_resolve",
            user_id=user_id,
            fields={"action": action, "success": False, "reason": "invalid_note", "notes_before": notes_before},
        )
        return False, "Selected note is invalid."
    if not bool(item.get("conflict_candidate", False)):
        append_memory_telemetry(
            "conflict_resolve",
            user_id=user_id,
            fields={"action": action, "success": False, "reason": "not_conflict_candidate", "notes_before": notes_before},
        )
        return False, "Selected note is not marked as a conflict candidate."

    conflict_group = normalize_memory_source(str(item.get("conflict_group", "")), fallback="")
    mode = str(action or "").strip().lower()
    if mode == "keep":
        kept_item = dict(item)
        clear_memory_conflict_fields(kept_item)
        if conflict_group:
            retained: list[dict[str, Any]] = []
            kept_position = -1
            for pos, note_item in enumerate(notes, start=1):
                if not isinstance(note_item, dict):
                    continue
                group_value = normalize_memory_source(str(note_item.get("conflict_group", "")), fallback="")
                if group_value == conflict_group and pos != index:
                    continue
                if pos == index:
                    kept_position = len(retained)
                retained.append(note_item)
            notes = retained
            target = kept_position if kept_position >= 0 else max(0, min(len(notes) - 1, index - 1))
            if notes:
                notes[target] = kept_item
            else:
                notes = [kept_item]
        else:
            notes[index - 1] = kept_item
        entry["notes"] = notes
        entry["updated_at"] = int(time.time())
        save_memory_state(MEMORY_STATE)
        record_memory_feedback_signal(
            user_id=user_id,
            signal="conflict_keep",
            note_source=str(kept_item.get("source", "")),
            note_tier=str(kept_item.get("tier", "")),
        )
        append_memory_telemetry(
            "conflict_resolve",
            user_id=user_id,
            fields={
                "action": "keep",
                "success": True,
                "has_group": bool(conflict_group),
                "notes_before": notes_before,
                "notes_after": len(notes),
            },
        )
        return True, "✅ Conflict resolved: kept new memory note."

    if mode == "drop":
        removed = notes.pop(index - 1)
        if conflict_group:
            for note_item in notes:
                if not isinstance(note_item, dict):
                    continue
                group_value = normalize_memory_source(str(note_item.get("conflict_group", "")), fallback="")
                if group_value == conflict_group:
                    clear_memory_conflict_fields(note_item)
        entry["notes"] = notes
        entry["updated_at"] = int(time.time())
        save_memory_state(MEMORY_STATE)
        if isinstance(removed, dict):
            record_memory_feedback_signal(
                user_id=user_id,
                signal="conflict_drop",
                note_source=str(removed.get("source", "")),
                note_tier=str(removed.get("tier", "")),
            )
        append_memory_telemetry(
            "conflict_resolve",
            user_id=user_id,
            fields={
                "action": "drop",
                "success": True,
                "has_group": bool(conflict_group),
                "notes_before": notes_before,
                "notes_after": len(notes),
            },
        )
        removed_preview = str(removed.get("text", "")).strip()[:80] if isinstance(removed, dict) else ""
        return True, f"✅ Conflict resolved: dropped note ({removed_preview})."

    append_memory_telemetry(
        "conflict_resolve",
        user_id=user_id,
        fields={"action": action, "success": False, "reason": "unknown_action", "notes_before": notes_before},
    )
    return False, "Unknown resolve action. Use 'keep' or 'drop'."


def build_memory_export_text(user_id: int, max_chars: int | None = None) -> str:
    entry = get_memory_entry(user_id)
    prune_memory_entry(entry)
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []

    notes_export: list[dict[str, Any]] = []
    for index, item in enumerate(notes, start=1):
        if not isinstance(item, dict):
            continue
        note_row: dict[str, Any] = {
            "index": index,
            "text": str(item.get("text", "")).strip(),
            "tier": normalize_memory_tier(item.get("tier"), source=str(item.get("source", ""))),
            "source": normalize_memory_source(str(item.get("source", "unknown"))),
            "confidence": clamp_memory_confidence(item.get("confidence"), fallback=1.0),
            "ts": parse_int(str(item.get("ts", "0")), 0),
            "conflict_candidate": bool(item.get("conflict_candidate", False)),
        }
        if bool(item.get("conflict_candidate", False)):
            conflict_detected_ts = get_memory_conflict_detected_ts(item)
            if conflict_detected_ts > 0:
                note_row["conflict_detected_ts"] = conflict_detected_ts
                note_row["conflict_age_seconds"] = max(0, int(time.time()) - conflict_detected_ts)
        provenance = sanitize_memory_provenance(item.get("provenance"))
        if provenance:
            note_row["provenance"] = provenance
        notes_export.append(note_row)

    export_payload = {
        "user_id": int(user_id),
        "enabled": bool(entry.get("enabled", False)),
        "updated_at": parse_int(str(entry.get("updated_at", "0")), 0),
        "total_notes": len(notes_export),
        "feedback_model": get_memory_feedback_model(entry),
        "notes": notes_export,
    }

    rendered = json.dumps(export_payload, ensure_ascii=False, indent=2)
    limit = max_chars or max(400, REPLY_MAX_CHARS)
    if len(rendered) <= limit:
        return f"Memory export:\n{rendered}"

    trimmed_payload = dict(export_payload)
    trimmed_payload["notes"] = notes_export[: max(1, min(8, len(notes_export)))]
    trimmed_payload["truncated"] = True
    trimmed_payload["truncated_reason"] = "message_limit"
    rendered_trimmed = json.dumps(trimmed_payload, ensure_ascii=False, indent=2)
    if len(rendered_trimmed) > limit:
        rendered_trimmed = rendered_trimmed[: max(100, limit - 120)] + "\n  \"truncated\": true\n}"
    return f"Memory export (truncated):\n{rendered_trimmed}"


def build_memory_why_text(user_id: int, limit: int = 5) -> str:
    entry = get_memory_entry(user_id)
    prune_memory_entry(entry)
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []
    enabled = bool(entry.get("enabled", False))
    if not enabled:
        return "Memory influence report:\n- memory is disabled for your account."

    now_value = int(time.time())
    feedback_model = get_memory_feedback_model(entry)
    global_weight = clamp_memory_feedback_weight(feedback_model.get("global_weight", 1.0), fallback=1.0)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for item in notes:
        if not isinstance(item, dict):
            continue
        if clamp_memory_confidence(item.get("confidence"), fallback=1.0) < MEMORY_MIN_CONFIDENCE:
            continue
        base_score = memory_note_rank_score(item, now_ts=now_value)
        feedback_multiplier = memory_feedback_rank_multiplier(entry, item)
        ranked.append((round(base_score * feedback_multiplier, 6), item))

    ranked.sort(
        key=lambda pair: (
            -pair[0],
            MEMORY_TIER_ORDER.get(
                normalize_memory_tier(pair[1].get("tier"), source=str(pair[1].get("source", ""))),
                99,
            ),
            -parse_int(str(pair[1].get("ts", "0")), 0),
        )
    )

    if not ranked:
        return "Memory influence report:\n- no active memory notes passed current confidence filters."

    lines = ["Memory influence report:"]
    lines.append(f"- feedback_ranking: {'on' if MEMORY_FEEDBACK_RANKING_ENABLED else 'off'} global_weight={global_weight:.3f}")
    for rank, (score, item) in enumerate(ranked[: max(1, limit)], start=1):
        tier = normalize_memory_tier(item.get("tier"), source=str(item.get("source", "")))
        source = normalize_memory_source(str(item.get("source", "unknown")))
        confidence = clamp_memory_confidence(item.get("confidence"), fallback=1.0)
        feedback_multiplier = memory_feedback_rank_multiplier(entry, item)
        preview = str(item.get("text", "")).strip()[:120]
        lines.append(
            f"- #{rank} score={score:.3f} tier={tier} source={source} conf={confidence:.2f} feedback={feedback_multiplier:.3f} text={preview}"
        )
    lines.append(
        "Ranking formula: confidence × recency_decay × source_trust × tier_boost"
    )
    return "\n".join(lines)


def forget_memory_notes(
    user_id: int,
    index: int | None = None,
    source: str | None = None,
) -> tuple[bool, int, int, str]:
    entry = get_memory_entry(user_id)
    prune_memory_entry(entry)
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, list) else []

    if index is not None:
        if index < 1 or index > len(notes):
            return False, 0, len(notes), "index_out_of_range"
        notes.pop(index - 1)
        entry["notes"] = notes
        entry["updated_at"] = int(time.time())
        save_memory_state(MEMORY_STATE)
        return True, 1, len(notes), "index"

    if source is not None:
        source_norm = normalize_memory_source(source, fallback="")
        if not source_norm:
            return False, 0, len(notes), "invalid_source"
        kept: list[dict[str, Any]] = []
        removed = 0
        for item in notes:
            if not isinstance(item, dict):
                continue
            item_source = normalize_memory_source(str(item.get("source", "")), fallback="")
            if item_source == source_norm:
                removed += 1
                continue
            kept.append(item)
        if removed <= 0:
            return False, 0, len(notes), "source_not_found"
        entry["notes"] = kept
        entry["updated_at"] = int(time.time())
        save_memory_state(MEMORY_STATE)
        return True, removed, len(kept), f"source:{source_norm}"

    return False, 0, len(notes), "missing_selector"


def check_and_record_rate_limit(user_id: int) -> tuple[bool, int, bool]:
    now = int(time.time())
    window_start = now - max(1, RATE_LIMIT_WINDOW_SECONDS)

    users = RATE_LIMIT_STATE.setdefault("users", {})
    notified_users = RATE_LIMIT_STATE.setdefault("notified_users", {})
    user_key = str(user_id)
    raw_timestamps = users.get(str(user_id), [])
    if not isinstance(raw_timestamps, list):
        raw_timestamps = []

    recent = []
    for ts in raw_timestamps:
        try:
            value = int(ts)
        except (TypeError, ValueError):
            continue
        if value >= window_start:
            recent.append(value)

    if len(recent) >= max(1, RATE_LIMIT_MAX_REQUESTS):
        oldest = min(recent)
        retry_after = max(1, RATE_LIMIT_WINDOW_SECONDS - (now - oldest))
        users[user_key] = recent
        RATE_LIMIT_STATE["users"] = users
        should_notify = True
        if RATE_LIMIT_NOTICE_DEBOUNCE_ENABLED:
            should_notify = not bool(notified_users.get(user_key, False))
            if should_notify:
                notified_users[user_key] = True
                RATE_LIMIT_STATE["notified_users"] = notified_users
        save_rate_limit_state(RATE_LIMIT_STATE)
        return False, retry_after, should_notify

    recent.append(now)
    users[user_key] = recent
    RATE_LIMIT_STATE["users"] = users
    if user_key in notified_users:
        notified_users.pop(user_key, None)
        RATE_LIMIT_STATE["notified_users"] = notified_users
    save_rate_limit_state(RATE_LIMIT_STATE)
    return True, 0, False


def build_rate_limit_report(now: int | None = None) -> str:
    ts_now = int(now or time.time())
    window = max(1, RATE_LIMIT_WINDOW_SECONDS)
    users = RATE_LIMIT_STATE.get("users") or {}
    active_counts: list[tuple[int, int]] = []

    for user_key, raw_timestamps in users.items():
        try:
            uid = int(user_key)
        except (TypeError, ValueError):
            continue
        if not isinstance(raw_timestamps, list):
            continue
        recent = []
        threshold = ts_now - window
        for ts in raw_timestamps:
            try:
                value = int(ts)
            except (TypeError, ValueError):
                continue
            if value >= threshold:
                recent.append(value)
        if recent:
            active_counts.append((uid, len(recent)))

    active_counts.sort(key=lambda item: item[1], reverse=True)
    lines = [
        "Rate limit settings:",
        f"- max_requests: {RATE_LIMIT_MAX_REQUESTS}",
        f"- window_seconds: {RATE_LIMIT_WINDOW_SECONDS}",
        f"- notice_debounce: {'on' if RATE_LIMIT_NOTICE_DEBOUNCE_ENABLED else 'off'}",
    ]

    if not active_counts:
        lines.append("No user activity in the current window.")
        return "\n".join(lines)

    lines.append("Top users this window:")
    for uid, count in active_counts[:10]:
        lines.append(f"- user={uid} requests={count}")
    return "\n".join(lines)


def load_offset() -> int:
    if not STATE_PATH.exists():
        return 0
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return int(data.get("last_update_id", 0))
    except Exception:
        return 0


def save_offset(update_id: int) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"last_update_id": update_id}), encoding="utf-8")


def telegram_request(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BOT_API_BASE}/{method}"
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=POLL_TIMEOUT + 10) as response:
        data = response.read().decode("utf-8")
        return json.loads(data)


def review_outbound_telegram_text(text: str, max_chars: int) -> str:
    candidate = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    out_lines: list[str] = []
    for raw_line in candidate.split("\n"):
        line = re.sub(r"[ \t]+$", "", raw_line)
        stripped = line.strip()
        if re.fullmatch(r"[━─]{3,}", stripped) or re.fullmatch(r"[-_=~]{5,}", stripped):
            continue

        lowered = stripped.lower()
        if lowered.startswith("next:"):
            suffix = stripped.split(":", 1)[1].strip()
            line = f"📌 Next step: {suffix}" if suffix else "📌 Next step"
        elif lowered.startswith("start with:"):
            suffix = stripped.split(":", 1)[1].strip()
            line = f"📌 Next step: {suffix}" if suffix else "📌 Next step"
        elif lowered == "use one next step:":
            line = "📌 Next step:"

        out_lines.append(line)

    reviewed = "\n".join(out_lines)
    reviewed = re.sub(r"\n{3,}", "\n\n", reviewed).strip()
    if not reviewed:
        reviewed = "(no message content)"

    hard_cap = max(120, int(max_chars or REPLY_MAX_CHARS))
    if len(reviewed) > hard_cap:
        reviewed = reviewed[: hard_cap - 1].rstrip() + "…"
    return reviewed


def send_message(chat_id: int, text: str) -> bool:
    try:
        message_text = str(text or "")
        if TELEGRAM_MESSAGE_REVIEW_ENABLED:
            message_text = review_outbound_telegram_text(message_text, max_chars=TELEGRAM_MESSAGE_REVIEW_MAX_CHARS)
        telegram_request(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": message_text,
                "disable_web_page_preview": True,
            },
        )
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to send message: {exc}", flush=True)
        return False


def split_text_for_telegram_chunks(text: str, max_chars: int) -> list[str]:
    payload = str(text or "")
    cap = max(120, int(max_chars or 120))
    if len(payload) <= cap:
        return [payload]

    chunks: list[str] = []
    cursor = 0
    total = len(payload)
    while cursor < total:
        end = min(total, cursor + cap)
        if end < total:
            newline_index = payload.rfind("\n", cursor, end)
            if newline_index > cursor + (cap // 2):
                end = newline_index + 1
        part = payload[cursor:end].strip("\n")
        if not part:
            part = payload[cursor : min(total, cursor + cap)]
            end = cursor + len(part)
        chunks.append(part)
        cursor = end
        while cursor < total and payload[cursor] == "\n":
            cursor += 1
    return chunks


def send_reqtrack_json_payload(chat_id: int, payload: dict[str, Any]) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    content_cap = max(180, int(REQTRACK_JSON_CHUNK_MAX_CHARS or 180))
    parts = split_text_for_telegram_chunks(rendered, max_chars=content_cap)
    if len(parts) == 1:
        return send_message(chat_id, parts[0])

    sent_all = True
    total = len(parts)
    for idx, part in enumerate(parts, start=1):
        text = f"[reqtrack-json {idx}/{total}]\n{part}"
        if not send_message(chat_id, text):
            sent_all = False
            break
    return sent_all


def send_photo(chat_id: int, photo_url: str, caption: str = "") -> bool:
    if not TEXTBOOK_COVER_PREVIEW_ENABLED:
        return False
    photo = str(photo_url or "").strip()
    if not photo:
        return False
    if not TOKEN or TOKEN.strip().lower() in {"dummy", "test", "placeholder"}:
        return False
    try:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo,
        }
        if caption:
            reviewed_caption = str(caption)
            if TELEGRAM_MESSAGE_REVIEW_ENABLED:
                reviewed_caption = review_outbound_telegram_text(reviewed_caption, max_chars=900)
            payload["caption"] = reviewed_caption[:900]
        telegram_request("sendPhoto", payload)
        return True
    except Exception as exc:
        print(f"[telegram-bridge] failed to send photo: {exc}", flush=True)
        return False


def send_textbook_cover_previews(chat_id: int, options: list[dict[str, Any]], limit: int = 3) -> int:
    sent = 0
    if not TEXTBOOK_COVER_PREVIEW_ENABLED:
        return sent
    if not isinstance(options, list) or not options:
        return sent
    for index, item in enumerate(options[: max(1, limit)], start=1):
        if not isinstance(item, dict):
            continue
        cover_url = str(item.get("cover_url", "")).strip()
        if not cover_url:
            continue
        title = str(item.get("title", "")).strip() or "Unknown title"
        authors = str(item.get("authors", "")).strip() or "Unknown author"
        year = str(item.get("year", "")).strip()
        year_suffix = f" ({year})" if year else ""
        caption = f"Option {index}: {title}{year_suffix}\n{authors}"
        if send_photo(chat_id, cover_url, caption=caption):
            sent += 1
    return sent


def call_n8n(path: str, payload: dict[str, Any]) -> dict[str, Any] | str | None:
    url = urllib.parse.urljoin(N8N_BASE, path)
    data = json.dumps(payload).encode("utf-8")
    attempts = max(1, N8N_WEBHOOK_RETRY_ATTEMPTS)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url=url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return None
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return body
        except urllib.error.HTTPError as exc:
            details = ""
            try:
                details = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                details = ""
            details_lower = details.lower()
            transient_webhook_state = exc.code in {404, 500, 502, 503, 504} and (
                "active version not found" in details_lower
                or "requested webhook" in details_lower
                or "not registered" in details_lower
            )
            transient_server = exc.code in {429, 500, 502, 503, 504}
            transient = transient_webhook_state or transient_server
            if transient and attempt < attempts:
                print(
                    f"[telegram-bridge] n8n transient webhook error (attempt {attempt}/{attempts}) path={path} code={exc.code}",
                    flush=True,
                )
                time.sleep(N8N_WEBHOOK_RETRY_DELAY_SECONDS)
                continue
            raise
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(N8N_WEBHOOK_RETRY_DELAY_SECONDS)
                continue
            raise
    if last_error:
        raise last_error
    return None


def profile_seed_value(seed_text: str, field_name: str) -> str:
    if not seed_text:
        return ""
    pattern = rf"-\s*{re.escape(field_name)}\s*:\s*(.+)"
    match = re.search(pattern, seed_text, re.IGNORECASE)
    if not match:
        return ""
    return str(match.group(1)).strip()


def build_local_quick_reply(cleaned_text: str, user_record: dict[str, Any], user_id: int | None = None) -> str | None:
    text = (cleaned_text or "").strip()
    lowered = text.lower()
    if not lowered:
        return None

    if re.fullmatch(r"(how are you|how are you\??|hows it going\??|how is it going\??)", lowered):
        return "Running smoothly and online. What should we tackle next?"

    profile_query = bool(
        re.search(
            r"(what do you know about me|who am i|my profile|profile name|where did i come from|where am i from|what is my name)",
            lowered,
        )
    )
    discord_profile_data_query = bool(
        re.search(
            r"(discord.*profile.*(rag|data|seed)|profile.*rag.*data|do you have .*profile.*rag data|sooknoots.*profile.*rag)",
            lowered,
        )
    )
    if not profile_query and not discord_profile_data_query:
        return None

    full_name = str(user_record.get("full_name", "")).strip() or "(not set)"
    tg_username = str(user_record.get("telegram_username", "")).strip() or "(not set)"
    linked_name = str(user_record.get("linked_discord_name", "")).strip()
    linked_id = str(user_record.get("linked_discord_user_id", "")).strip()
    linked_alias = str(user_record.get("linked_discord_match", "")).strip()
    profile_seed = sanitize_profile_seed(str(user_record.get("user_profile_seed", "")))
    seed_primary_username = profile_seed_value(profile_seed, "Primary username")
    seed_display_name = profile_seed_value(profile_seed, "Display/global name")
    seed_origin = "Discord seed profile" if profile_seed else "No linked Discord profile seed"

    profile_name = linked_name or seed_display_name or full_name
    origin_detail = seed_primary_username or linked_alias or "(unknown)"
    discord_line = (
        f"- discord: {linked_name} ({linked_id})"
        if linked_name and linked_id
        else "- discord: (not linked)"
    )

    lines = [
        "Profile snapshot:",
        f"- profile_name: {profile_name}",
        f"- source: {seed_origin}",
        f"- origin_hint: {origin_detail}",
        f"- telegram_name: {full_name}",
        f"- telegram_username: @{tg_username}" if tg_username != "(not set)" else "- telegram_username: (not set)",
        discord_line,
    ]

    if discord_profile_data_query:
        lines.append(f"- rag_profile_seed_loaded: {'yes' if profile_seed else 'no'}")
        if not profile_seed:
            candidates = suggest_profile_seed_candidates(record=user_record, user_id=int(user_id or 0), limit=3)
            if candidates:
                top_score = int(candidates[0][0] or 0)
                second_score = int(candidates[1][0] or 0) if len(candidates) > 1 else -1
                high_confidence = len(candidates) == 1 or (
                    top_score >= PROFILE_MATCH_HIGH_CONFIDENCE_MIN_SCORE
                    and (top_score - second_score) >= PROFILE_MATCH_HIGH_CONFIDENCE_MIN_GAP
                )
                top_label = str(candidates[0][2])
                top_seed_id = str(candidates[0][1])
                lines.append(f"- best_match: {top_label} (id={top_seed_id})")
                lines.append(f"- first_action: /profile apply {top_seed_id}")
                if not high_confidence:
                    lines.append("- profile_seed_candidates:")
                    for _score, seed_id, label in candidates:
                        lines.append(f"  - {label} (id={seed_id}) -> /profile apply {seed_id}")
            else:
                lines.append("- profile_seed_candidates: (none found)")
        lines.append("Tip: run /profile show to inspect active profile seed context.")

    return "\n".join(lines)


def call_overseerr(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not OVERSEERR_API_KEY:
        raise RuntimeError("OVERSEERR_API_KEY is not configured")

    final_path = path if path.startswith("/") else f"/{path}"
    url = f"{OVERSEERR_URL}{final_path}"
    if query:
        encoded = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        if encoded:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}{encoded}"

    headers = {
        "Accept": "application/json",
                "Priority": "3",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method.upper(),
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return parsed


def parse_media_request_query(text: str) -> tuple[str, str, int | None] | None:
    parts = (text or "").strip().split()
    if len(parts) < 3:
        return None

    media_type_raw = parts[1].lower()
    if media_type_raw in {"show", "series"}:
        media_type = "tv"
    elif media_type_raw in {"movie", "tv"}:
        media_type = media_type_raw
    else:
        return None

    title_tokens = parts[2:]
    requested_year: int | None = None
    if title_tokens:
        last = title_tokens[-1]
        year_match = re.fullmatch(r"\(?([12][0-9]{3})\)?", last)
        if year_match:
            year_candidate = int(year_match.group(1))
            if 1900 <= year_candidate <= 2100:
                requested_year = year_candidate
                title_tokens = title_tokens[:-1]

    title = " ".join(title_tokens).strip()
    if not title:
        return None
    return media_type, title, requested_year


def media_help_text() -> str:
    return (
        "🎬 MEDIA REQUEST (Guided)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Follow one step at a time:\n"
        "1) Search\n"
        "   • /media movie Dune 2021\n"
        "   • /media tv Severance\n"
        "2) Confirm one result\n"
        "   • /media pick <number>\n"
        "\n"
        "That’s it — after your pick, request is submitted to Overseerr."
    )


def extract_content_rating_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    for key in ["certification", "contentRating", "content_rating", "rated", "rating"]:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = normalize_content_rating(value)
            if normalized:
                return normalized

    release_dates = payload.get("releaseDates")
    if isinstance(release_dates, dict):
        results = release_dates.get("results")
        if isinstance(results, list):
            for region in results:
                if not isinstance(region, dict):
                    continue
                entries = region.get("release_dates")
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    certification = normalize_content_rating(str(entry.get("certification", "")))
                    if certification:
                        return certification

    content_ratings = payload.get("contentRatings")
    if isinstance(content_ratings, dict):
        results = content_ratings.get("results")
        if isinstance(results, list):
            for entry in results:
                if not isinstance(entry, dict):
                    continue
                rating = normalize_content_rating(str(entry.get("rating", "")))
                if rating:
                    return rating

    media_info = payload.get("mediaInfo")
    if isinstance(media_info, dict):
        for key in ["certification", "contentRating", "content_rating", "rated"]:
            value = media_info.get(key)
            if isinstance(value, str):
                normalized = normalize_content_rating(value)
                if normalized:
                    return normalized

    for value in payload.values():
        if isinstance(value, dict):
            nested = extract_content_rating_from_payload(value)
            if nested:
                return nested
        if isinstance(value, list):
            for item in value:
                nested = extract_content_rating_from_payload(item)
                if nested:
                    return nested

    return ""


def extract_media_adult_flag(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ["adult", "isAdult", "is_adult"]:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}:
            return True
    media_info = payload.get("mediaInfo")
    if isinstance(media_info, dict):
        nested = extract_media_adult_flag(media_info)
        if nested:
            return True
    return False


def extract_media_genre_ids(payload: Any) -> set[int]:
    genre_ids: set[int] = set()
    if not isinstance(payload, dict):
        return genre_ids
    direct = payload.get("genreIds")
    if isinstance(direct, list):
        for item in direct:
            try:
                genre_ids.add(int(item))
            except (TypeError, ValueError):
                continue
    snake_direct = payload.get("genre_ids")
    if isinstance(snake_direct, list):
        for item in snake_direct:
            try:
                genre_ids.add(int(item))
            except (TypeError, ValueError):
                continue
    genres = payload.get("genres")
    if isinstance(genres, list):
        for entry in genres:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            try:
                genre_ids.add(int(str(entry_id)))
            except (TypeError, ValueError):
                continue
    media_info = payload.get("mediaInfo")
    if isinstance(media_info, dict):
        genre_ids.update(extract_media_genre_ids(media_info))
    return genre_ids


def extract_media_overview(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ["overview", "description", "plot"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    media_info = payload.get("mediaInfo")
    if isinstance(media_info, dict):
        nested = extract_media_overview(media_info)
        if nested:
            return nested
    return ""


def fetch_overseerr_content_metadata(media_type: str, media_id: int, search_item: dict[str, Any] | None = None) -> dict[str, Any]:
    details_payload = search_item if isinstance(search_item, dict) else {}
    details: dict[str, Any] = {
        "content_rating": normalize_content_rating(extract_content_rating_from_payload(details_payload)),
        "adult_flag": bool(extract_media_adult_flag(details_payload)),
        "genre_ids": sorted(extract_media_genre_ids(details_payload)),
        "overview": extract_media_overview(details_payload),
    }
    needs_api = (
        media_id > 0
        and (
            not details["content_rating"]
            or not details["overview"]
            or not details["genre_ids"]
            or (CHILD_MEDIA_BLOCK_IF_ADULT_FLAG and not details["adult_flag"])
        )
    )
    if not needs_api:
        return details

    detail_path = f"/api/v1/movie/{media_id}" if media_type == "movie" else f"/api/v1/tv/{media_id}"
    response = call_overseerr(method="GET", path=detail_path)
    if not isinstance(response, dict):
        return details

    if not details["content_rating"]:
        details["content_rating"] = normalize_content_rating(extract_content_rating_from_payload(response))
    if CHILD_MEDIA_BLOCK_IF_ADULT_FLAG and not details["adult_flag"]:
        details["adult_flag"] = bool(extract_media_adult_flag(response))
    response_genres = extract_media_genre_ids(response)
    if response_genres:
        details["genre_ids"] = sorted(response_genres)
    if not details["overview"]:
        details["overview"] = extract_media_overview(response)
    return details


def child_media_allowed_ratings_for_record(record: dict[str, Any] | None) -> set[str]:
    age = get_record_account_age(record)
    if isinstance(age, int):
        if age < 13:
            return CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13
        if age <= 15:
            return CHILD_MEDIA_ALLOWED_RATINGS_13_15
        if age < CHILD_ACCOUNT_ADULT_MIN_AGE:
            return CHILD_MEDIA_ALLOWED_RATINGS_16_17
    return CHILD_MEDIA_ALLOWED_RATINGS


def is_child_media_rating_allowed(content_rating: str, record: dict[str, Any] | None = None) -> bool:
    normalized = normalize_content_rating(content_rating)
    if not normalized:
        return not CHILD_MEDIA_DENY_UNKNOWN_RATINGS
    allowed_ratings = child_media_allowed_ratings_for_record(record)
    if normalized in allowed_ratings:
        return True
    return False


def child_media_guardrail_violations(candidate: dict[str, Any], record: dict[str, Any] | None) -> list[str]:
    violations: list[str] = []
    content_rating = str(candidate.get("content_rating") or "")
    if not is_child_media_rating_allowed(content_rating, record):
        allowed = ", ".join(sorted(child_media_allowed_ratings_for_record(record))) or "(none configured)"
        violations.append(
            f"rating {normalize_content_rating(content_rating) or 'unknown'} is not allowed (allowed: {allowed})"
        )

    if CHILD_MEDIA_BLOCK_IF_ADULT_FLAG and bool(candidate.get("adult_flag")):
        violations.append("title is marked adult by provider metadata")

    raw_genres = candidate.get("genre_ids")
    genre_ids: set[int] = set()
    if isinstance(raw_genres, list):
        for item in raw_genres:
            try:
                genre_ids.add(int(item))
            except (TypeError, ValueError):
                continue
    blocked_genres = sorted(genre_ids & CHILD_MEDIA_BLOCKED_GENRE_IDS)
    if blocked_genres:
        violations.append(f"genre guardrail hit (blocked genre IDs: {', '.join(str(value) for value in blocked_genres)})")

    if CHILD_MEDIA_BLOCKED_KEYWORDS:
        searchable_parts = [
            str(candidate.get("title") or "").strip().lower(),
            str(candidate.get("overview") or "").strip().lower(),
        ]
        searchable_text = " ".join(part for part in searchable_parts if part)
        for keyword in sorted(CHILD_MEDIA_BLOCKED_KEYWORDS):
            if keyword and keyword in searchable_text:
                violations.append(f"content descriptor matched blocked keyword '{keyword}'")
                break

    return violations


def media_status_label(status: Any) -> str:
    mapping = {
        1: "unknown",
        2: "requested",
        3: "processing",
        4: "partially available",
        5: "available in Plex",
    }
    try:
        key = int(status)
    except (TypeError, ValueError):
        return "unknown"
    return mapping.get(key, "unknown")


def media_candidate_details(item: dict[str, Any], fallback_title: str) -> dict[str, Any] | None:
    media_id = item.get("id")
    if media_id is None:
        return None
    title = str(item.get("title") or item.get("name") or fallback_title).strip() or fallback_title
    release_date = str(item.get("releaseDate") or item.get("firstAirDate") or "")
    year = release_date[:4] if len(release_date) >= 4 else ""
    media_info_raw = item.get("mediaInfo")
    media_info = media_info_raw if isinstance(media_info_raw, dict) else {}
    current_status = media_status_label(media_info.get("status"))
    content_rating = extract_content_rating_from_payload(item)
    return {
        "media_id": int(media_id),
        "title": title,
        "year": year,
        "current_status": current_status,
        "content_rating": content_rating,
        "adult_flag": bool(extract_media_adult_flag(item)),
        "genre_ids": sorted(extract_media_genre_ids(item)),
        "overview": extract_media_overview(item),
    }


def submit_media_request(chat_id: int, media_type: str, candidate: dict[str, Any]) -> bool:
    request_payload: dict[str, Any] = {
        "mediaType": media_type,
        "mediaId": int(candidate["media_id"]),
    }
    request_response = call_overseerr(
        method="POST",
        path="/api/v1/request",
        payload=request_payload,
    )

    request_id = request_response.get("id")
    year = str(candidate.get("year", "")).strip()
    title = str(candidate.get("title", "")).strip() or "(unknown title)"
    display = f"{title} ({year})" if year else title
    send_message(
        chat_id,
        "✅ REQUEST SUBMITTED\n"
        "━━━━━━━━━━━━━━━━\n"
        f"• type: {media_type}\n"
        f"• title: {display}\n"
        f"• request_id: {request_id if request_id is not None else 'created'}\n"
        f"• current_status: {candidate.get('current_status', 'unknown')}\n"
        f"• content_rating: {str(candidate.get('content_rating', '') or 'unknown')}\n"
        "\n"
        "📌 Next step: wait for Telegram media-ready alerts.\n"
        "(You can run reqboard in terminal for queue visibility.)",
    )
    return True


def clear_media_selection(user_id: int) -> None:
    pending = MEDIA_SELECTION_STATE.setdefault("pending", {})
    pending.pop(str(user_id), None)
    MEDIA_SELECTION_STATE["pending"] = pending
    save_media_selection_state(MEDIA_SELECTION_STATE)


def handle_media_pick_command(chat_id: int, user_id: int, text: str) -> bool:
    parts = (text or "").strip().split()
    if len(parts) < 3:
        send_message(
            chat_id,
            "🎯 PICK STEP\n"
            "━━━━━━━━━━\n"
            "Use: /media pick <number>",
        )
        return True

    if parts[1].lower() != "pick":
        send_message(
            chat_id,
            "🎯 PICK STEP\n"
            "━━━━━━━━━━\n"
            "Use: /media pick <number>",
        )
        return True

    try:
        selected_index = int(parts[2])
    except ValueError:
        send_message(
            chat_id,
            "❌ Pick must be a number.\n"
            "Example: /media pick 2",
        )
        return True

    pending = MEDIA_SELECTION_STATE.get("pending") or {}
    entry = pending.get(str(user_id))
    if not isinstance(entry, dict):
        send_message(
            chat_id,
            "No pending selection found.\n"
            "📌 Next step: start with /media <movie|tv> <title> [year]",
        )
        return True

    created_at = parse_int(str(entry.get("created_at", "0")), 0)
    ttl = max(60, MEDIA_SELECTION_TTL_SECONDS)
    if created_at <= 0 or int(time.time()) > created_at + ttl:
        clear_media_selection(user_id)
        send_message(chat_id, "Selection expired.\n📌 Next step: run /media again.")
        return True

    entry_chat_id = parse_int(str(entry.get("chat_id", "0")), 0)
    if entry_chat_id and entry_chat_id != chat_id:
        send_message(chat_id, "That pending selection belongs to another chat. Start a new /media search here.")
        return True

    options_raw = entry.get("options")
    options = options_raw if isinstance(options_raw, list) else []
    if not options:
        clear_media_selection(user_id)
        send_message(chat_id, "Selection list is empty.\n📌 Next step: run /media again.")
        return True

    if selected_index < 1 or selected_index > len(options):
        send_message(
            chat_id,
            f"❌ Choose a number between 1 and {len(options)}.\n"
            "Example: /media pick 1",
        )
        return True

    option = options[selected_index - 1]
    if not isinstance(option, dict):
        clear_media_selection(user_id)
        send_message(chat_id, "Selected option is invalid.\n📌 Next step: run /media again.")
        return True

    media_type = str(option.get("media_type", "")).lower().strip()
    if media_type not in {"movie", "tv"}:
        clear_media_selection(user_id)
        send_message(chat_id, "Selected option has invalid media type.\n📌 Next step: run /media again.")
        return True

    candidate = {
        "media_id": parse_int(str(option.get("media_id", "0")), 0),
        "title": str(option.get("title") or "").strip(),
        "year": str(option.get("year") or "").strip(),
        "current_status": str(option.get("current_status") or "unknown").strip(),
        "content_rating": normalize_content_rating(str(option.get("content_rating") or "")),
        "adult_flag": bool(option.get("adult_flag")),
        "genre_ids": option.get("genre_ids") if isinstance(option.get("genre_ids"), list) else [],
        "overview": str(option.get("overview") or "").strip(),
    }
    if candidate["media_id"] <= 0:
        clear_media_selection(user_id)
        send_message(chat_id, "Selected option is missing a media ID.\n📌 Next step: run /media again.")
        return True

    display_title = str(candidate.get("title") or "(unknown title)").strip()
    display_year = str(candidate.get("year") or "").strip()
    display_suffix = f" ({display_year})" if display_year else ""
    user_record = get_user_record(USER_REGISTRY, user_id)
    if is_child_guardrails_account(user_record):
        violations = child_media_guardrail_violations(candidate, user_record)
        if violations:
            send_message(
                chat_id,
                (
                    "⛔ This title is blocked by Child account media guardrails.\n"
                    f"Reason: {violations[0]}"
                ),
            )
            clear_media_selection(user_id)
            return True

    send_message(
        chat_id,
        "✅ PICK CONFIRMED\n"
        "━━━━━━━━━━━━━━\n"
        f"• selection: {display_title}{display_suffix}\n"
        f"• content_rating: {str(candidate.get('content_rating', '') or 'unknown')}\n"
        "Submitting request now...",
    )

    submit_media_request(chat_id, media_type, candidate)
    clear_media_selection(user_id)
    return True


def handle_media_request_command(chat_id: int, user_id: int, text: str) -> bool:
    token = command_token(text)
    if token not in {"/media", "/request"}:
        return False

    raw_parts = (text or "").strip().split()
    if len(raw_parts) >= 2 and raw_parts[1].lower() == "pick":
        return handle_media_pick_command(chat_id=chat_id, user_id=user_id, text=text)

    parsed = parse_media_request_query(text)
    if parsed is None:
        send_message(chat_id, media_help_text())
        return True

    media_type, title_query, requested_year = parsed
    user_record = get_user_record(USER_REGISTRY, user_id)
    enforce_child_guardrails = is_child_guardrails_account(user_record)

    if not OVERSEERR_API_KEY:
        send_message(
            chat_id,
            "❌ Media requests are not configured yet.\nMissing OVERSEERR_API_KEY in ai-control/.env",
        )
        return True

    try:
        search = call_overseerr(
            method="GET",
            path="/api/v1/search",
            query={"query": title_query, "page": 1, "language": "en"},
        )
        results_raw = search.get("results")
        results = results_raw if isinstance(results_raw, list) else []

        filtered: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            if str(item.get("mediaType", "")).lower() != media_type:
                continue
            filtered.append(item)

        if requested_year is not None:
            year_filtered: list[dict[str, Any]] = []
            for item in filtered:
                raw_date = str(item.get("releaseDate") or item.get("firstAirDate") or "")
                item_year = parse_int(raw_date[:4], 0)
                if item_year == requested_year:
                    year_filtered.append(item)
            if year_filtered:
                filtered = year_filtered

        if not filtered:
            year_note = f" ({requested_year})" if requested_year else ""
            send_message(
                chat_id,
                f"No {media_type} results found for: {title_query}{year_note}\n"
                "📌 Next step: try a simpler title or remove the year.",
            )
            return True

        candidates: list[dict[str, Any]] = []
        details_scan = filtered[:12]
        for item in details_scan:
            if not isinstance(item, dict):
                continue
            details = media_candidate_details(item=item, fallback_title=title_query)
            if details is None:
                continue
            media_id = int(details.get("media_id", 0) or 0)
            try:
                metadata = fetch_overseerr_content_metadata(media_type=media_type, media_id=media_id, search_item=item)
                details["content_rating"] = normalize_content_rating(str(metadata.get("content_rating") or details.get("content_rating") or ""))
                details["adult_flag"] = bool(metadata.get("adult_flag"))
                details["genre_ids"] = metadata.get("genre_ids") if isinstance(metadata.get("genre_ids"), list) else []
                details["overview"] = str(metadata.get("overview") or details.get("overview") or "").strip()
            except Exception:
                details["content_rating"] = normalize_content_rating(str(details.get("content_rating") or ""))
                details["adult_flag"] = bool(details.get("adult_flag"))
                details["genre_ids"] = details.get("genre_ids") if isinstance(details.get("genre_ids"), list) else []
                details["overview"] = str(details.get("overview") or "").strip()

            if enforce_child_guardrails and child_media_guardrail_violations(details, user_record):
                continue
            candidates.append(details)

        if not candidates:
            if enforce_child_guardrails:
                send_message(
                    chat_id,
                    (
                        "No allowed results found for this Child account under current media guardrails.\n"
                        f"Allowed ratings: {', '.join(sorted(child_media_allowed_ratings_for_record(user_record))) or '(none configured)'}"
                    ),
                )
                return True
            send_message(chat_id, "❌ Could not resolve media ID from Overseerr search result.")
            return True

        if len(candidates) == 1:
            shortlist = candidates[:1]
            pending = MEDIA_SELECTION_STATE.setdefault("pending", {})
            pending[str(user_id)] = {
                "chat_id": chat_id,
                "created_at": int(time.time()),
                "query": title_query,
                "requested_year": requested_year,
                "options": [
                    {
                        "media_type": media_type,
                        "media_id": int(shortlist[0]["media_id"]),
                        "title": str(shortlist[0].get("title") or "").strip(),
                        "year": str(shortlist[0].get("year") or "").strip(),
                        "current_status": str(shortlist[0].get("current_status") or "unknown").strip(),
                        "content_rating": str(shortlist[0].get("content_rating") or "").strip(),
                        "adult_flag": bool(shortlist[0].get("adult_flag")),
                        "genre_ids": shortlist[0].get("genre_ids") if isinstance(shortlist[0].get("genre_ids"), list) else [],
                        "overview": str(shortlist[0].get("overview") or "").strip(),
                    }
                ],
            }
            MEDIA_SELECTION_STATE["pending"] = pending
            save_media_selection_state(MEDIA_SELECTION_STATE)

            item = shortlist[0]
            year = f" ({item['year']})" if item.get("year") else ""
            send_message(
                chat_id,
                "✅ MATCH FOUND\n"
                "━━━━━━━━━━━━\n"
                f"1) {item['title']}{year} — {item['current_status']} — rating={str(item.get('content_rating') or 'unknown')}\n"
                "\n"
                "📌 Next step: confirm this selection\n"
                "👉 /media pick 1",
            )
            return True

        shortlist = candidates[:3]
        pending = MEDIA_SELECTION_STATE.setdefault("pending", {})
        pending[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "query": title_query,
            "requested_year": requested_year,
            "options": [
                {
                    "media_type": media_type,
                    "media_id": int(item["media_id"]),
                    "title": str(item.get("title") or "").strip(),
                    "year": str(item.get("year") or "").strip(),
                    "current_status": str(item.get("current_status") or "unknown").strip(),
                    "content_rating": str(item.get("content_rating") or "").strip(),
                    "adult_flag": bool(item.get("adult_flag")),
                    "genre_ids": item.get("genre_ids") if isinstance(item.get("genre_ids"), list) else [],
                    "overview": str(item.get("overview") or "").strip(),
                }
                for item in shortlist
            ],
        }
        MEDIA_SELECTION_STATE["pending"] = pending
        save_media_selection_state(MEDIA_SELECTION_STATE)

        lines = [
            "🔎 MULTIPLE MATCHES FOUND",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"Query: {title_query}",
            "",
            "Pick ONE option now:",
        ]
        for index, item in enumerate(shortlist, start=1):
            year = f" ({item['year']})" if item.get("year") else ""
            lines.append(
                f"{index}) {item['title']}{year} — {item['current_status']} — rating={str(item.get('content_rating') or 'unknown')}"
            )
        lines.append("")
        lines.append("👉 Reply with: /media pick <number>")
        lines.append(f"⏱️ Expires in {max(60, MEDIA_SELECTION_TTL_SECONDS)}s")
        send_message(chat_id, "\n".join(lines))
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            send_message(chat_id, "ℹ️ That title has already been requested.")
            return True
        send_message(chat_id, f"❌ Overseerr API error: HTTP {exc.code}")
        return True
    except Exception as exc:
        send_message(chat_id, f"❌ Media request failed: {exc}")
        return True


def normalize_match_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def score_textbook_candidate(candidate: dict[str, str], requested_title: str, requested_author: str, requested_isbn: str) -> int:
    score = 0
    candidate_title = normalize_match_text(candidate.get("title", ""))
    candidate_authors = normalize_match_text(candidate.get("authors", ""))
    candidate_isbn = normalize_match_text(candidate.get("isbn", ""))
    wanted_title = normalize_match_text(requested_title)
    wanted_author = normalize_match_text(requested_author)
    wanted_isbn = normalize_match_text(requested_isbn)

    if wanted_isbn and candidate_isbn:
        if candidate_isbn == wanted_isbn:
            score += 140
        elif wanted_isbn in candidate_isbn or candidate_isbn in wanted_isbn:
            score += 80

    if wanted_title and candidate_title:
        if candidate_title == wanted_title:
            score += 80
        elif wanted_title in candidate_title:
            score += 55
        elif candidate_title in wanted_title:
            score += 35

    if wanted_author and candidate_authors:
        if wanted_author in candidate_authors:
            score += 45
        elif candidate_authors in wanted_author:
            score += 20

    provider = str(candidate.get("provider", "")).lower()
    if provider == "googlebooks":
        score += 5
    elif provider == "openlibrary":
        score += 3
    elif provider == "internetarchive":
        score += 2
    elif provider == "gutendex":
        score += 1

    return score


def search_textbook_candidates(details: str, parsed_fields: dict[str, str], limit: int = 3) -> list[dict[str, str]]:
    query_parts: list[str] = []
    isbn = str(parsed_fields.get("isbn", "")).strip()
    title = str(parsed_fields.get("title", "")).strip()
    author = str(parsed_fields.get("author", "")).strip()

    if isbn:
        query_parts.append(f"isbn:{isbn}")
    if title:
        query_parts.append(title)
    if author:
        query_parts.append(author)
    if not query_parts:
        query_parts.append(details)

    query = " ".join(query_parts).strip()
    if not query:
        return []

    all_candidates: list[dict[str, str]] = []

    if "googlebooks" in TEXTBOOK_SEARCH_PROVIDERS:
        try:
            gb_params = urllib.parse.urlencode({"q": query, "maxResults": max(6, limit * 4), "printType": "books"})
            gb_url = f"https://www.googleapis.com/books/v1/volumes?{gb_params}"
            gb_request = urllib.request.Request(
                url=gb_url,
                headers={"Accept": "application/json", "User-Agent": "servernoots-telegram-bridge/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(gb_request, timeout=20) as response:
                gb_raw = response.read().decode("utf-8", errors="ignore")
            gb_payload = json.loads(gb_raw)
            gb_items = gb_payload.get("items") if isinstance(gb_payload, dict) else []
            if isinstance(gb_items, list):
                for item in gb_items:
                    if not isinstance(item, dict):
                        continue
                    volume_raw = item.get("volumeInfo")
                    volume: dict[str, Any] = volume_raw if isinstance(volume_raw, dict) else {}
                    found_title = str(volume.get("title") or "").strip()
                    if not found_title:
                        continue
                    authors_raw_value = volume.get("authors")
                    authors_raw: list[Any] = authors_raw_value if isinstance(authors_raw_value, list) else []
                    authors = ", ".join(str(value).strip() for value in authors_raw[:3] if str(value).strip())
                    published = str(volume.get("publishedDate") or "").strip()
                    year = published[:4] if len(published) >= 4 else ""
                    ids_value = volume.get("industryIdentifiers")
                    ids: list[Any] = ids_value if isinstance(ids_value, list) else []
                    found_isbn = ""
                    for ident in ids:
                        if not isinstance(ident, dict):
                            continue
                        value = str(ident.get("identifier") or "").strip()
                        if value:
                            found_isbn = re.sub(r"[^0-9Xx]", "", value).upper()
                            if found_isbn:
                                break
                    source_url = str(volume.get("infoLink") or "").strip() or "https://books.google.com"
                    image_links_value = volume.get("imageLinks")
                    image_links: dict[str, Any] = image_links_value if isinstance(image_links_value, dict) else {}
                    cover_url = str(
                        image_links.get("thumbnail")
                        or image_links.get("smallThumbnail")
                        or ""
                    ).strip()
                    if cover_url.startswith("http://"):
                        cover_url = "https://" + cover_url[len("http://") :]
                    all_candidates.append(
                        {
                            "provider": "googlebooks",
                            "title": found_title,
                            "authors": authors,
                            "year": year,
                            "isbn": found_isbn,
                            "source_url": source_url,
                            "cover_url": cover_url,
                        }
                    )
        except Exception as exc:
            print(f"[telegram-bridge] google books query failed: {exc}", flush=True)

    if "openlibrary" in TEXTBOOK_SEARCH_PROVIDERS:
        try:
            ol_params = urllib.parse.urlencode({"q": query, "limit": max(6, limit * 4)})
            ol_url = f"https://openlibrary.org/search.json?{ol_params}"
            ol_request = urllib.request.Request(
                url=ol_url,
                headers={"Accept": "application/json", "User-Agent": "servernoots-telegram-bridge/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(ol_request, timeout=20) as response:
                ol_raw = response.read().decode("utf-8", errors="ignore")
            ol_payload = json.loads(ol_raw)
            docs = ol_payload.get("docs") if isinstance(ol_payload, dict) else []
            if isinstance(docs, list):
                for item in docs:
                    if not isinstance(item, dict):
                        continue
                    found_title = str(item.get("title") or "").strip()
                    if not found_title:
                        continue
                    authors_raw_value = item.get("author_name")
                    authors_raw: list[Any] = authors_raw_value if isinstance(authors_raw_value, list) else []
                    authors = ", ".join(str(value).strip() for value in authors_raw[:3] if str(value).strip())
                    year = str(item.get("first_publish_year") or "").strip()
                    isbn_values = item.get("isbn") if isinstance(item.get("isbn"), list) else []
                    found_isbn = re.sub(r"[^0-9Xx]", "", str(isbn_values[0])).upper() if isbn_values else ""
                    key = str(item.get("key") or "").strip()
                    source_url = f"https://openlibrary.org{key}" if key.startswith("/") else "https://openlibrary.org"
                    cover_id = parse_int(str(item.get("cover_i") or "0"), 0)
                    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id > 0 else ""
                    all_candidates.append(
                        {
                            "provider": "openlibrary",
                            "title": found_title,
                            "authors": authors,
                            "year": year,
                            "isbn": found_isbn,
                            "source_url": source_url,
                            "cover_url": cover_url,
                        }
                    )
        except Exception as exc:
            print(f"[telegram-bridge] openlibrary query failed: {exc}", flush=True)

    if "internetarchive" in TEXTBOOK_SEARCH_PROVIDERS:
        try:
            ia_query = " OR ".join(part for part in [f"isbn:{isbn}" if isbn else "", query] if part)
            ia_params = urllib.parse.urlencode(
                {
                    "q": ia_query,
                    "rows": max(6, limit * 4),
                    "page": 1,
                    "fl[]": ["identifier", "title", "creator", "date", "year", "isbn"],
                    "output": "json",
                },
                doseq=True,
            )
            ia_url = f"https://archive.org/advancedsearch.php?{ia_params}"
            ia_request = urllib.request.Request(
                url=ia_url,
                headers={"Accept": "application/json", "User-Agent": "servernoots-telegram-bridge/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(ia_request, timeout=20) as response:
                ia_raw = response.read().decode("utf-8", errors="ignore")
            ia_payload = json.loads(ia_raw)
            ia_docs = (((ia_payload.get("response") or {}) if isinstance(ia_payload, dict) else {}).get("docs") or [])
            if isinstance(ia_docs, list):
                for item in ia_docs:
                    if not isinstance(item, dict):
                        continue
                    found_title = str(item.get("title") or "").strip()
                    if not found_title:
                        continue
                    creator = item.get("creator")
                    if isinstance(creator, list):
                        authors = ", ".join(str(value).strip() for value in creator[:3] if str(value).strip())
                    else:
                        authors = str(creator or "").strip()
                    year_value = str(item.get("year") or "").strip()
                    if not year_value:
                        date_value = str(item.get("date") or "").strip()
                        year_value = date_value[:4] if len(date_value) >= 4 else ""
                    isbn_field = item.get("isbn")
                    if isinstance(isbn_field, list):
                        raw_isbn = str(isbn_field[0] or "").strip() if isbn_field else ""
                    else:
                        raw_isbn = str(isbn_field or "").strip()
                    found_isbn = re.sub(r"[^0-9Xx]", "", raw_isbn).upper()
                    identifier = str(item.get("identifier") or "").strip()
                    source_url = f"https://archive.org/details/{identifier}" if identifier else "https://archive.org"
                    all_candidates.append(
                        {
                            "provider": "internetarchive",
                            "title": found_title,
                            "authors": authors,
                            "year": year_value,
                            "isbn": found_isbn,
                            "source_url": source_url,
                            "cover_url": "",
                        }
                    )
        except Exception as exc:
            print(f"[telegram-bridge] internet archive query failed: {exc}", flush=True)

    if "gutendex" in TEXTBOOK_SEARCH_PROVIDERS:
        try:
            gx_params = urllib.parse.urlencode({"search": query})
            gx_url = f"https://gutendex.com/books?{gx_params}"
            gx_request = urllib.request.Request(
                url=gx_url,
                headers={"Accept": "application/json", "User-Agent": "servernoots-telegram-bridge/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(gx_request, timeout=20) as response:
                gx_raw = response.read().decode("utf-8", errors="ignore")
            gx_payload = json.loads(gx_raw)
            gx_items = gx_payload.get("results") if isinstance(gx_payload, dict) else []
            if isinstance(gx_items, list):
                for item in gx_items[: max(6, limit * 4)]:
                    if not isinstance(item, dict):
                        continue
                    found_title = str(item.get("title") or "").strip()
                    if not found_title:
                        continue
                    authors_raw_value = item.get("authors")
                    authors_raw: list[Any] = authors_raw_value if isinstance(authors_raw_value, list) else []
                    authors = ", ".join(
                        str((author.get("name") if isinstance(author, dict) else author) or "").strip()
                        for author in authors_raw[:3]
                        if str((author.get("name") if isinstance(author, dict) else author) or "").strip()
                    )
                    formats_value = item.get("formats")
                    formats: dict[str, Any] = formats_value if isinstance(formats_value, dict) else {}
                    source_url = str(
                        formats.get("text/html")
                        or formats.get("application/epub+zip")
                        or formats.get("application/octet-stream")
                        or formats.get("text/plain; charset=utf-8")
                        or ""
                    ).strip()
                    book_id = parse_int(str(item.get("id") or "0"), 0)
                    if not source_url and book_id > 0:
                        source_url = f"https://www.gutenberg.org/ebooks/{book_id}"
                    cover_url = str(formats.get("image/jpeg") or "").strip()
                    all_candidates.append(
                        {
                            "provider": "gutendex",
                            "title": found_title,
                            "authors": authors,
                            "year": "",
                            "isbn": "",
                            "source_url": source_url or "https://www.gutenberg.org",
                            "cover_url": cover_url,
                        }
                    )
        except Exception as exc:
            print(f"[telegram-bridge] gutendex query failed: {exc}", flush=True)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in all_candidates:
        dedupe_key = (
            f"{normalize_match_text(item.get('title', ''))}|"
            f"{normalize_match_text(item.get('authors', ''))}|"
            f"{normalize_match_text(item.get('isbn', ''))}"
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(item)

    ranked = sorted(
        deduped,
        key=lambda item: score_textbook_candidate(item, requested_title=title, requested_author=author, requested_isbn=isbn),
        reverse=True,
    )

    return ranked[: max(1, limit)]


def render_textbook_candidates(options: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for index, item in enumerate(options, start=1):
        title = str(item.get("title", "")).strip() or "(unknown title)"
        authors = str(item.get("authors", "")).strip() or "(unknown author)"
        year = str(item.get("year", "")).strip()
        isbn = str(item.get("isbn", "")).strip()
        provider = str(item.get("provider", "catalog")).strip()
        cover_url = str(item.get("cover_url", "")).strip()
        suffix = f" ({year})" if year else ""
        isbn_txt = f", isbn={isbn}" if isbn else ""
        lines.append(f"{index}) {title}{suffix} — {authors}{isbn_txt} [{provider}]")
        if cover_url:
            lines.append(f"   cover: {cover_url}")
    return "\n".join(lines)


def render_textbook_candidates_compact(options: list[dict[str, str]], limit: int = 3) -> str:
    lines: list[str] = []
    cap = max(1, min(10, int(limit)))
    for index, item in enumerate(options[:cap], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip() or "(unknown title)"
        year = str(item.get("year", "")).strip()
        suffix = f" ({year})" if year else ""
        authors = str(item.get("authors", "")).strip() or "(unknown author)"
        provider = str(item.get("provider", "catalog")).strip() or "catalog"
        authors = re.sub(r"\s+", " ", authors)
        if len(authors) > 80:
            authors = authors[:79].rstrip() + "…"
        lines.append(f"{index}) {title}{suffix} — {authors} [{provider}]")
    if len(options) > cap:
        lines.append(f"…and {len(options) - cap} more")
    return "\n".join(lines)


def handle_textbook_command(chat_id: int, user_id: int, text: str, user_record: dict[str, Any], role: str) -> bool:
    parsed = parse_textbook_command(text)
    if parsed is None:
        return False

    command, rest = parsed
    token = command_token(text)
    if token == "/book" and command == "help":
        send_message(chat_id, "Alias: /book = /textbook\n\n" + textbook_help_text())
        return True

    if command in {"help", "?"}:
        send_message(chat_id, textbook_help_text())
        return True

    if re.fullmatch(r"\d+", str(command or "")):
        rest = str(command).strip()
        command = "pick"

    if command == "email":
        email_action = (rest or "").strip()
        if not email_action:
            send_message(
                chat_id,
                "📩 EMAIL STEP\n"
                "━━━━━━━━━━\n"
                "Use one of:\n"
                "• /textbook email <address>\n"
                "• /textbook email show\n"
                "• /textbook email clear",
            )
            return True
        if email_action.lower() == "show":
            saved = str(user_record.get("preferred_delivery_email", "")).strip()
            send_message(
                chat_id,
                "📩 SAVED DELIVERY EMAIL\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"{saved or '(none set)'}",
            )
            return True
        if email_action.lower() == "clear":
            user_record.pop("preferred_delivery_email", None)
            user_record["updated_at"] = utc_now()
            USER_REGISTRY.setdefault("users", {})[str(user_id)] = user_record
            save_user_registry(USER_REGISTRY)
            send_message(
                chat_id,
                "✅ Delivery email cleared.\n"
                "📌 Next step: /textbook request <details>",
            )
            return True
        candidate_email = email_action.strip()
        if not is_valid_email(candidate_email):
            send_message(
                chat_id,
                "❌ Invalid email format.\n"
                "Example: /textbook email student@school.edu",
            )
            return True
        user_record["preferred_delivery_email"] = candidate_email
        user_record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = user_record
        save_user_registry(USER_REGISTRY)
        add_memory_note(
            user_id,
            f"Preferred textbook delivery email: {candidate_email}",
            source="textbook_email_preference",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "textbook_email"},
            tier="preference",
        )
        pending = get_textbook_request(user_id)
        if pending:
            options_raw = pending.get("options")
            options = options_raw if isinstance(options_raw, list) else []
            selected = pending.get("selected_candidate") if isinstance(pending.get("selected_candidate"), dict) else {}
            if options and not selected:
                send_message(
                    chat_id,
                    "✅ Email saved.\n"
                    f"📌 Next step: pick a candidate with /textbook pick 1-{len(options)}",
                )
            else:
                send_message(
                    chat_id,
                    "✅ Email saved.\n"
                    "📌 Next step: /textbook confirm",
                )
        else:
            send_message(
                chat_id,
                f"✅ Saved delivery email: {candidate_email}\n"
                "📌 Next step: /textbook request <details>",
            )
        return True

    if command == "resend":
        last_fulfillment = get_textbook_last_fulfillment(user_id)
        if not last_fulfillment:
            send_message(chat_id, "No previous fulfillment found to resend.")
            return True

        delivery_email = str(last_fulfillment.get("delivery_email", "")).strip()
        if not is_valid_email(delivery_email):
            send_message(chat_id, "Saved delivery email is missing/invalid. Set with /textbook email you@example.com")
            return True

        source_file_url = str(last_fulfillment.get("source_file_url", "")).strip() or str(last_fulfillment.get("file_url", "")).strip()
        if not source_file_url:
            send_message(chat_id, "No file URL is recorded for last fulfillment, so resend is unavailable.")
            return True

        fulfillment_id = str(last_fulfillment.get("fulfillment_id", "")).strip() or f"textbook-{user_id}-{int(time.time())}"
        details = str(last_fulfillment.get("request_details", "")).strip() or "Textbook resend request"
        selected_candidate_raw = last_fulfillment.get("selected_candidate")
        selected_candidate = selected_candidate_raw if isinstance(selected_candidate_raw, dict) else {}
        timeline_raw = last_fulfillment.get("status_timeline")
        status_timeline = timeline_raw if isinstance(timeline_raw, list) else []
        previous_attempt_count = parse_int(str(last_fulfillment.get("dispatch_attempt_count", "0")), 0)

        dispatch_attempt_count = max(0, previous_attempt_count) + 1
        dispatch_result = ""
        delivery_status = "dispatch_failed"
        last_error = ""
        last_dispatch_at = utc_now()
        hosted_download_url = ""
        hosted_download_expires_at = 0

        existing_hosted_url = str(last_fulfillment.get("hosted_download_url", "")).strip()
        existing_hosted_expires_at = parse_int(str(last_fulfillment.get("hosted_download_expires_at", "0")), 0)
        if existing_hosted_url and existing_hosted_expires_at > int(time.time()):
            hosted_download_url = existing_hosted_url
            hosted_download_expires_at = existing_hosted_expires_at
        else:
            hosted_download_url, hosted_download_expires_at, link_reason = build_textbook_download_link(
                user_id=user_id,
                fulfillment_id=fulfillment_id,
                source_url=source_file_url,
                file_mime=str(last_fulfillment.get("file_mime", "")).strip(),
                selected_candidate=selected_candidate,
            )
            if not hosted_download_url:
                if str(link_reason).startswith("untrusted_source:"):
                    dispatch_result = f"download_link_unavailable:{link_reason}"
                    delivery_status = "dispatch_failed_untrusted_source"
                    last_error = dispatch_result
                else:
                    hosted_download_url = source_file_url
                    hosted_download_expires_at = 0
                    dispatch_result = f"download_link_fallback_source_url:{link_reason}"

        if hosted_download_url:
            dispatch_ok, dispatch_result = send_textbook_delivery_email(
                delivery_email=delivery_email,
                details=details,
                file_url=hosted_download_url,
                fulfillment_id=fulfillment_id,
                selected_candidate=selected_candidate,
            )
            if dispatch_ok:
                delivery_status = "email_redispatched"
                last_error = ""
            elif dispatch_result == "smtp_not_configured":
                delivery_status = "dispatch_skipped_not_configured"
                last_error = ""
            else:
                delivery_status = "dispatch_failed"
                last_error = dispatch_result

        status_timeline = append_status_timeline(status_timeline, delivery_status)
        set_textbook_last_fulfillment(
            user_id,
            {
                "created_at": int(time.time()),
                "fulfillment_id": fulfillment_id,
                "delivery_email": delivery_email,
                "delivery_status": delivery_status,
                "delivery_mode": "smtp_bridge",
                "status_timeline": status_timeline,
                "dispatch_result": dispatch_result,
                "dispatch_attempt_count": dispatch_attempt_count,
                "last_dispatch_at": last_dispatch_at,
                "last_error": last_error,
                "file_url": source_file_url,
                "source_file_url": source_file_url,
                "hosted_download_url": hosted_download_url,
                "hosted_download_expires_at": hosted_download_expires_at,
                "request_details": details,
                "selected_candidate": selected_candidate,
            },
        )

        if delivery_status == "email_redispatched":
            send_message(chat_id, "✅ Textbook delivery email resent successfully.")
        elif delivery_status == "dispatch_skipped_not_configured":
            send_message(chat_id, "⚠️ Resend skipped: SMTP not configured (set TEXTBOOK_SMTP_* envs).")
        elif delivery_status == "dispatch_failed_untrusted_source":
            send_message(chat_id, f"❌ Resend blocked by source allowlist: {dispatch_result}")
        else:
            send_message(chat_id, f"❌ Resend failed: {dispatch_result}")
        return True

    if command == "delivered":
        last_fulfillment = get_textbook_last_fulfillment(user_id)
        if not last_fulfillment:
            send_message(chat_id, "No previous fulfillment found.")
            return True
        timeline_raw = last_fulfillment.get("status_timeline")
        status_timeline = timeline_raw if isinstance(timeline_raw, list) else []
        status_timeline = append_status_timeline(status_timeline, "delivery_confirmed_by_user")
        last_fulfillment["delivery_status"] = "delivery_confirmed_by_user"
        last_fulfillment["status_timeline"] = status_timeline
        last_fulfillment["updated_at"] = int(time.time())
        set_textbook_last_fulfillment(user_id, last_fulfillment)
        send_message(chat_id, "✅ Marked last textbook fulfillment as delivered.")
        return True

    if command == "failed":
        reason = " ".join((rest or "").split()).strip()
        if not reason:
            send_message(chat_id, "Usage: /textbook failed <reason>")
            return True
        last_fulfillment = get_textbook_last_fulfillment(user_id)
        if not last_fulfillment:
            send_message(chat_id, "No previous fulfillment found.")
            return True
        timeline_raw = last_fulfillment.get("status_timeline")
        status_timeline = timeline_raw if isinstance(timeline_raw, list) else []
        status_timeline = append_status_timeline(status_timeline, "delivery_reported_failed_by_user")
        last_fulfillment["delivery_status"] = "delivery_reported_failed_by_user"
        last_fulfillment["status_timeline"] = status_timeline
        last_fulfillment["last_error"] = f"user_reported:{reason[:240]}"
        last_fulfillment["updated_at"] = int(time.time())
        set_textbook_last_fulfillment(user_id, last_fulfillment)
        send_message(chat_id, "✅ Marked last textbook fulfillment as failed. You can run /textbook resend.")
        return True

    if command == "cancel":
        clear_textbook_request(user_id)
        send_message(chat_id, "✅ Textbook request canceled.")
        return True

    if command == "status":
        pending = get_textbook_request(user_id)
        ingest_offer = get_textbook_ingest_offer(user_id)
        last_fulfillment = get_textbook_last_fulfillment(user_id)
        if not pending:
            if ingest_offer:
                source_name = str(ingest_offer.get("source_name", "textbook")).strip() or "textbook"
                send_message(
                    chat_id,
                    "📌 Textbook status\n"
                    "No pending request.\n"
                    f"Ingest offer pending: {source_name}\n"
                    "📌 Next step: /textbook ingest yes OR /textbook ingest no",
                )
                return True
            if last_fulfillment:
                status_value = str(last_fulfillment.get("delivery_status", "unknown")).strip() or "unknown"
                fulfillment_id = str(last_fulfillment.get("fulfillment_id", "")).strip() or "(unknown)"
                delivery_email = str(last_fulfillment.get("delivery_email", "")).strip() or "(unknown)"
                last_error = str(last_fulfillment.get("last_error", "")).strip()
                next_step = "📌 Next step: /textbook request <details>"
                if status_value.startswith("dispatch_failed") or status_value.startswith("delivery_reported_failed"):
                    next_step = "📌 Next step: /textbook resend"
                elif status_value.startswith("email_dispatched") or status_value.startswith("email_redispatched"):
                    next_step = "📌 Next step: /textbook delivered OR /textbook failed <reason>"
                lines = [
                    "📌 Textbook status",
                    "No pending request.",
                    f"Last: {status_value}",
                    f"🆔 {fulfillment_id}",
                    f"📩 {delivery_email}",
                ]
                if last_error:
                    lines.append(f"⚠️ {last_error}")
                lines.append(next_step)
                send_message(chat_id, "\n".join(lines))
                return True
            send_message(
                chat_id,
                "📌 Textbook status\n"
                "No pending textbook request.\n"
                "📌 Next step: /textbook request <details>",
            )
            return True
        details = str(pending.get("details", "")).strip()
        summary = str(pending.get("candidate_summary", "")).strip()
        delivery_email = str(pending.get("delivery_email", "")).strip()
        selected = pending.get("selected_candidate") if isinstance(pending.get("selected_candidate"), dict) else None
        selected_title = str((selected or {}).get("title", "")).strip()
        compact_details = details[:120] + ("…" if len(details) > 120 else "")
        lines = [
            "📌 Textbook status",
            "Pending request.",
            f"📝 {compact_details or '(details missing)'}",
            f"📩 {delivery_email or '(email not set)'}",
            f"✅ {selected_title or '(no candidate selected)'}",
        ]
        options_raw = pending.get("options")
        options = options_raw if isinstance(options_raw, list) else []
        if options:
            lines.append(f"📚 candidates: {len(options)}")
            lines.append(render_textbook_candidates_compact(options, limit=2))
        elif summary:
            lines.append("📚 candidate summary available")
        if ingest_offer:
            lines.append("📎 ingest offer pending")
        if not delivery_email:
            lines.append("📌 Next step: /textbook email you@example.com")
        elif not selected_title:
            if options:
                lines.append(f"📌 Next step: /textbook <n> (1-{len(options)})")
            else:
                lines.append("📌 Next step: refine with /textbook request <details>")
        else:
            lines.append("📌 Next step: /textbook confirm")
        send_message(chat_id, "\n".join(lines))
        return True

    if command == "ingest":
        action = (rest or "").strip().lower()
        offer = get_textbook_ingest_offer(user_id)
        if action == "status":
            if not offer:
                send_message(chat_id, "No pending ingest offer. Complete /textbook confirm first.")
                return True
            source_name = str(offer.get("source_name", "textbook")).strip() or "textbook"
            send_message(
                chat_id,
                "🧠 INGEST STEP\n"
                "━━━━━━━━━━\n"
                f"Pending ingest offer: {source_name}\n"
                "Reply with ONE command:\n"
                "• /textbook ingest yes\n"
                "• /textbook ingest no",
            )
            return True

        if action not in {"yes", "no"}:
            send_message(chat_id, "Usage: /textbook ingest <yes|no|status>")
            return True

        if not offer:
            send_message(chat_id, "No pending ingest offer. Complete /textbook confirm first.")
            return True

        if action == "no":
            clear_textbook_ingest_offer(user_id)
            send_message(chat_id, "✅ Skipped textbook ingest.")
            return True

        file_url = str(offer.get("file_url", "")).strip()
        file_mime = str(offer.get("file_mime", "")).strip()
        extracted_file_text = ""
        if file_url:
            try:
                extracted_file_text = fetch_ingest_text_from_file_url(file_url=file_url, file_mime=file_mime)
            except Exception as exc:
                print(f"[telegram-bridge] textbook file extraction failed: {exc}", flush=True)

        ingest_text = extracted_file_text or str(offer.get("ingest_text", "")).strip()
        ingest_payload = {
            "source": "telegram",
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "tenant_id": f"u_{user_id}",
            "text": ingest_text,
            "source_name": str(offer.get("source_name", "textbook-material")).strip() or "textbook-material",
            "source_type": "textbook",
            "doc_id": str(offer.get("doc_id", "")).strip() or f"textbook-{user_id}-{int(time.time())}",
            "timestamp": int(time.time()),
        }

        if not str(ingest_payload.get("text", "")).strip():
            send_message(chat_id, "Ingest text payload is empty, so nothing was indexed.")
            clear_textbook_ingest_offer(user_id)
            return True

        try:
            _ = call_n8n(RAG_INGEST_WEBHOOK, ingest_payload)
            add_memory_note(
                user_id,
                f"Textbook material ingested: {ingest_payload['source_name']}",
                source="textbook_ingest",
                confidence=0.9,
                provenance={"channel": "telegram", "source_name": ingest_payload["source_name"]},
                tier="session",
            )
            origin_note = "(from file)" if extracted_file_text else "(from summary)"
            send_message(chat_id, f"✅ Textbook material queued for private RAG ingest {origin_note}.")
            clear_textbook_ingest_offer(user_id)
        except urllib.error.HTTPError as exc:
            send_message(chat_id, f"❌ RAG ingest webhook error: HTTP {exc.code}")
        except Exception as exc:
            send_message(chat_id, f"❌ RAG ingest failed: {exc}")
        return True

    if command == "pick":
        pending = get_textbook_request(user_id)
        if not pending:
            send_message(chat_id, "No pending textbook request. Start with /textbook request <details>")
            return True
        options_raw = pending.get("options")
        options = options_raw if isinstance(options_raw, list) else []
        if not options:
            send_message(chat_id, "No candidate list is available to pick from. Start a new /textbook request.")
            return True
        if not rest:
            send_message(chat_id, "Usage: /textbook pick <1-3>")
            return True
        try:
            selected_index = int(rest.strip())
        except ValueError:
            send_message(chat_id, "Pick index must be a number. Example: /textbook pick 2")
            return True
        if selected_index < 1 or selected_index > len(options):
            send_message(chat_id, f"Choose a value between 1 and {len(options)}. Example: /textbook pick 1")
            return True
        selected = options[selected_index - 1]
        if not isinstance(selected, dict):
            send_message(chat_id, "Selected option is invalid. Start a new /textbook request.")
            return True
        pending["selected_candidate"] = selected
        pending["selected_index"] = selected_index
        pending["updated_at"] = int(time.time())
        state_pending = TEXTBOOK_STATE.setdefault("pending", {})
        state_pending[str(user_id)] = pending
        TEXTBOOK_STATE["pending"] = state_pending
        save_textbook_state(TEXTBOOK_STATE)
        title = str(selected.get("title", "")).strip() or "(unknown title)"
        authors = str(selected.get("authors", "")).strip()
        edition = str(selected.get("edition", "")).strip()
        cover_url = str(selected.get("cover_url", "")).strip()
        lines = [
            "✅ Candidate selected",
            f"• title: {title}",
            f"• authors: {authors or '(unknown)'}",
        ]
        if edition:
            lines.append(f"• edition: {edition}")
        if cover_url:
            lines.append(f"• cover: {cover_url}")
        lines.append("📌 Next step: /textbook confirm")
        cover_sent = False
        if TEXTBOOK_COVER_PREVIEW_ENABLED and cover_url:
            cover_sent = send_photo(
                chat_id,
                cover_url,
                caption=f"Selected textbook cover preview\n{title}",
            )
        send_message(
            chat_id,
            "\n".join(lines),
        )
        return True

    if command == "request":
        details = " ".join((rest or "").split()).strip()
        if len(details) < 10:
            send_message(chat_id, "Please provide more textbook details. Example: /textbook request title: ..., author: ..., edition: ..., isbn: ...")
            return True

        lowered = details.lower()
        if any(phrase in lowered for phrase in {"pirate", "torrent", "crack", "free pdf", "libgen", "zlibrary", "z-lib"}):
            send_message(
                chat_id,
                "I can only help with legal textbook fulfillment (official publisher, campus library, OER, or user-authorized copy). Please resend with lawful sourcing intent.",
            )
            return True

        parsed_fields = parse_textbook_fields(details)
        requested_edition = str(parsed_fields.get("edition", "")).strip()
        has_isbn = bool(parsed_fields.get("isbn"))
        word_count = len(details.split())
        if not has_isbn and word_count < 4:
            send_message(chat_id, "Please include at least title+author or ISBN so I can validate the exact textbook.")
            return True

        delivery_email = str(user_record.get("preferred_delivery_email", "")).strip()
        if not is_valid_email(delivery_email):
            delivery_email = ""

        lookup_prompt = (
            "Find legal acquisition options for this college textbook request. "
            "Prioritize official publisher, campus bookstore/library, and open educational resources. "
            "Return concise validation fields (title, author, edition, ISBN if available), then legal source links only. "
            "Do not provide piracy or unauthorized download guidance.\n\n"
            f"Textbook request: {details}"
        )
        candidates: list[dict[str, str]] = []
        try:
            candidates = search_textbook_candidates(details=details, parsed_fields=parsed_fields, limit=3)
        except Exception as exc:
            print(f"[telegram-bridge] textbook search failed: {exc}", flush=True)

        candidate_summary = ""
        if candidates:
            candidate_summary = render_textbook_candidates(candidates)
        else:
            try:
                lookup_payload = {
                    "source": "telegram",
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "role": role,
                    "tenant_id": f"u_{user_id}",
                    "full_name": str(user_record.get("full_name", "")),
                    "telegram_username": str(user_record.get("telegram_username", "")),
                    "message": lookup_prompt,
                    "memory_enabled": False,
                    "memory_summary": "",
                    "timestamp": int(time.time()),
                }
                lookup_result = call_n8n(RAG_WEBHOOK, lookup_payload)
                candidate_summary = extract_reply_text(lookup_result)
            except Exception as exc:
                candidate_summary = (
                    "Could not run automated legal source lookup right now. "
                    f"Reason: {exc}"
                )

        pending = TEXTBOOK_STATE.setdefault("pending", {})
        pending[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "details": details,
            "parsed_fields": parsed_fields,
            "candidate_summary": candidate_summary,
            "delivery_email": delivery_email,
            "options": candidates,
            "selected_candidate": candidates[0] if len(candidates) == 1 else {},
            "selected_index": 1 if len(candidates) == 1 else 0,
        }
        TEXTBOOK_STATE["pending"] = pending
        save_textbook_state(TEXTBOOK_STATE)

        lines = [
            "📚 Textbook candidate review",
            f"• request: {details}",
            f"• delivery_email: {delivery_email or '(not set)'}",
            f"• options_found: {len(candidates)}",
            "• review options and choose one",
            "",
            render_textbook_candidates_compact(candidates, limit=3) if candidates else (candidate_summary[:700] + ("…" if len(candidate_summary) > 700 else "")),
            "",
            "Use ONE next step:",
        ]
        if not requested_edition:
            lines.append("💡 Tip: add edition to narrow results (example: edition: 8th).")
        if not delivery_email:
            lines.append("👉 /textbook email you@example.com")
        elif len(candidates) > 1:
            lines.append(f"👉 /textbook <n> (1-{len(candidates)})")
            lines.append("👉 /textbook pick <n>")
            lines.append("👉 or refine search: /textbook request title: ..., author: ..., edition: ..., isbn: ...")
        elif len(candidates) == 1:
            selected_cover = str((candidates[0] or {}).get("cover_url", "")).strip()
            if selected_cover:
                lines.append(f"🖼️ cover preview: {selected_cover}")
            lines.append("👉 /textbook confirm")
        else:
            lines.append("👉 /textbook request <more-specific details>")
        lines.append("(Cancel anytime: /textbook cancel)")
        send_message(chat_id, "\n".join(lines))
        if candidates and TEXTBOOK_COVER_PREVIEW_ENABLED:
            _ = send_textbook_cover_previews(chat_id=chat_id, options=candidates, limit=min(3, len(candidates)))
        return True

    if command == "confirm":
        pending = get_textbook_request(user_id)
        if not pending:
            send_message(chat_id, "No pending textbook request. Start with /textbook request <details>")
            return True

        entry_chat_id = parse_int(str(pending.get("chat_id", "0")), 0)
        if entry_chat_id and entry_chat_id != chat_id:
            send_message(chat_id, "Pending textbook request belongs to another chat context. Start a new /textbook request here.")
            return True

        delivery_email = str(user_record.get("preferred_delivery_email", "")).strip() or str(
            pending.get("delivery_email", "")
        ).strip()
        if not is_valid_email(delivery_email):
            send_message(chat_id, "Please set delivery email first: /textbook email you@example.com")
            return True

        details = str(pending.get("details", "")).strip()
        candidate_summary = str(pending.get("candidate_summary", "")).strip()
        parsed_fields = pending.get("parsed_fields") if isinstance(pending.get("parsed_fields"), dict) else {}
        selected_candidate = pending.get("selected_candidate") if isinstance(pending.get("selected_candidate"), dict) else {}
        options_raw = pending.get("options")
        options = options_raw if isinstance(options_raw, list) else []

        if options and not selected_candidate:
            send_message(chat_id, "Please pick a candidate first: /textbook pick <1-3>")
            return True

        fulfillment_payload = {
            "source": "telegram",
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "tenant_id": f"u_{user_id}",
            "full_name": str(user_record.get("full_name", "")),
            "telegram_username": str(user_record.get("telegram_username", "")),
            "delivery_email": delivery_email,
            "textbook_request": details,
            "parsed_fields": parsed_fields,
            "validation_summary": candidate_summary,
            "selected_candidate": selected_candidate,
            "confirmation": "confirmed_by_user",
            "lawful_sources_only": True,
            "timestamp": int(time.time()),
        }

        reply = "✅ Textbook fulfillment queued."
        result: dict[str, Any] | str | None = None
        try:
            result = call_n8n(TEXTBOOK_WEBHOOK, fulfillment_payload)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                reply = f"⚠️ Textbook fulfillment webhook error: HTTP {exc.code}. Request has been queued to ops."
            ops_note = {
                "source": "telegram",
                "chat_id": chat_id,
                "user_id": user_id,
                "role": "admin",
                "tenant_id": f"u_{user_id}",
                "message": (
                    "TEXTBOOK_FULFILLMENT_REQUEST "
                    f"user_id={user_id} email={delivery_email} details={details}"
                ),
                "timestamp": int(time.time()),
            }
            try:
                _ = call_n8n(OPS_WEBHOOK, ops_note)
            except Exception:
                pass
        except Exception as exc:
            reply = f"⚠️ Textbook fulfillment request queued locally, but downstream delivery failed: {exc}"

        user_record["preferred_delivery_email"] = delivery_email
        user_record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = user_record
        save_user_registry(USER_REGISTRY)
        add_memory_note(
            user_id,
            f"Preferred textbook delivery email: {delivery_email}",
            source="textbook_email_preference",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "textbook_confirm"},
            tier="preference",
        )
        add_memory_note(
            user_id,
            f"Last textbook request: {details[:160]}",
            source="textbook_request",
            confidence=0.85,
            provenance={"channel": "telegram", "command": "textbook_confirm"},
            tier="session",
        )

        result_dict = result if isinstance(result, dict) else {}
        nested = result_dict.get("data") if isinstance(result_dict.get("data"), dict) else {}
        fulfillment_id = str(
            result_dict.get("fulfillment_id")
            or nested.get("fulfillment_id")
            or f"textbook-{user_id}-{int(time.time())}"
        ).strip()
        delivery_status = str(
            result_dict.get("delivery_status")
            or nested.get("delivery_status")
            or ("dispatch_ready" if result_dict.get("file_ready_for_email") else "queued")
        ).strip()
        delivery_mode = str(
            result_dict.get("delivery_mode")
            or nested.get("delivery_mode")
            or "ops_queue"
        ).strip()
        status_timeline_raw = result_dict.get("status_timeline") or nested.get("status_timeline")
        status_timeline = status_timeline_raw if isinstance(status_timeline_raw, list) else []
        file_ready = bool(
            result_dict.get("file_ready_for_email")
            or result_dict.get("can_email")
            or result_dict.get("email_ready")
            or nested.get("file_ready_for_email")
            or nested.get("can_email")
            or nested.get("email_ready")
        )
        ingest_text = str(
            result_dict.get("ingest_text")
            or nested.get("ingest_text")
            or nested.get("text_for_ingest")
            or ""
        ).strip()
        source_file_url = str(
            result_dict.get("file_url")
            or nested.get("file_url")
            or result_dict.get("download_url")
            or nested.get("download_url")
            or ""
        ).strip()
        file_mime = str(
            result_dict.get("file_mime")
            or nested.get("file_mime")
            or result_dict.get("mime_type")
            or nested.get("mime_type")
            or ""
        ).strip()

        previous_entry = get_textbook_last_fulfillment(user_id) or {}
        previous_fulfillment_id = str(previous_entry.get("fulfillment_id", "")).strip()
        previous_attempt_count = parse_int(str(previous_entry.get("dispatch_attempt_count", "0")), 0)
        preserved_attempt_count = previous_attempt_count if previous_fulfillment_id == fulfillment_id else 0
        preserved_last_dispatch_at = str(previous_entry.get("last_dispatch_at", "")).strip() if previous_fulfillment_id == fulfillment_id else ""
        preserved_last_error = str(previous_entry.get("last_error", "")).strip() if previous_fulfillment_id == fulfillment_id else ""

        set_textbook_last_fulfillment(
            user_id,
            {
                "created_at": int(time.time()),
                "fulfillment_id": fulfillment_id,
                "delivery_email": delivery_email,
                "delivery_status": delivery_status,
                "delivery_mode": delivery_mode,
                "status_timeline": status_timeline,
                "dispatch_attempt_count": preserved_attempt_count,
                "last_dispatch_at": preserved_last_dispatch_at,
                "last_error": preserved_last_error,
                "file_url": source_file_url,
                "source_file_url": source_file_url,
                "request_details": details,
                "selected_candidate": selected_candidate,
            },
        )

        if file_ready:
            selected_title = str(selected_candidate.get("title", "")).strip() if isinstance(selected_candidate, dict) else ""
            source_name = selected_title or str(parsed_fields.get("title") or "textbook-material").strip() or "textbook-material"
            if not ingest_text:
                fallback_bits = [
                    f"Textbook request: {details}",
                    f"Candidate summary: {candidate_summary[:2000]}",
                ]
                if isinstance(selected_candidate, dict) and selected_candidate:
                    fallback_bits.append(f"Selected candidate: {json.dumps(selected_candidate, ensure_ascii=False)}")
                ingest_text = "\n\n".join(bit for bit in fallback_bits if bit)

            duplicate_confirm = previous_fulfillment_id == fulfillment_id and previous_attempt_count > 0

            dispatch_ok = False
            dispatch_result = ""
            dispatch_attempt_count = previous_attempt_count
            last_dispatch_at = preserved_last_dispatch_at
            last_error = preserved_last_error
            hosted_download_url = str(previous_entry.get("hosted_download_url", "")).strip()
            hosted_download_expires_at = parse_int(str(previous_entry.get("hosted_download_expires_at", "0")), 0)

            if duplicate_confirm:
                dispatch_result = str(previous_entry.get("dispatch_result", "duplicate_confirm_noop")).strip() or "duplicate_confirm_noop"
                delivery_status = str(previous_entry.get("delivery_status", "dispatch_duplicate_noop")).strip() or "dispatch_duplicate_noop"
            else:
                dispatch_attempt_count = max(0, previous_attempt_count) + 1
                last_dispatch_at = utc_now()
                hosted_download_url, hosted_download_expires_at, link_reason = build_textbook_download_link(
                    user_id=user_id,
                    fulfillment_id=fulfillment_id,
                    source_url=source_file_url,
                    file_mime=file_mime,
                    selected_candidate=selected_candidate,
                )
                if not hosted_download_url:
                    if str(link_reason).startswith("untrusted_source:"):
                        dispatch_result = f"download_link_unavailable:{link_reason}"
                        delivery_status = "dispatch_failed_untrusted_source"
                        last_error = dispatch_result
                    else:
                        hosted_download_url = source_file_url
                        hosted_download_expires_at = 0
                        dispatch_result = f"download_link_fallback_source_url:{link_reason}"
                else:
                    dispatch_ok, dispatch_result = send_textbook_delivery_email(
                        delivery_email=delivery_email,
                        details=details,
                        file_url=hosted_download_url,
                        fulfillment_id=fulfillment_id,
                        selected_candidate=selected_candidate,
                    )
                    if dispatch_ok:
                        delivery_status = "email_dispatched"
                        last_error = ""
                    elif dispatch_result == "smtp_not_configured":
                        delivery_status = "dispatch_skipped_not_configured"
                        last_error = ""
                    else:
                        delivery_status = "dispatch_failed"
                        last_error = dispatch_result

            status_timeline = append_status_timeline(status_timeline, delivery_status)
            set_textbook_last_fulfillment(
                user_id,
                {
                    "created_at": int(time.time()),
                    "fulfillment_id": fulfillment_id,
                    "delivery_email": delivery_email,
                    "delivery_status": delivery_status,
                    "delivery_mode": "smtp_bridge",
                    "status_timeline": status_timeline,
                    "dispatch_result": dispatch_result,
                    "dispatch_attempt_count": dispatch_attempt_count,
                    "last_dispatch_at": last_dispatch_at,
                    "last_error": last_error,
                    "file_url": source_file_url,
                    "source_file_url": source_file_url,
                    "hosted_download_url": hosted_download_url,
                    "hosted_download_expires_at": hosted_download_expires_at,
                    "request_details": details,
                    "selected_candidate": selected_candidate,
                },
            )

            set_textbook_ingest_offer(
                user_id,
                {
                    "created_at": int(time.time()),
                    "chat_id": chat_id,
                    "source_name": source_name,
                    "doc_id": f"textbook-{user_id}-{int(time.time())}",
                    "ingest_text": ingest_text[:12000],
                    "file_url": source_file_url,
                    "file_mime": file_mime,
                    "fulfillment_id": fulfillment_id,
                    "delivery_status": delivery_status,
                },
            )
            status_text = delivery_status
            if duplicate_confirm:
                status_text = "duplicate_confirm_ignored"
            elif delivery_status == "email_dispatched":
                status_text = "email_dispatched"
            elif delivery_status == "dispatch_skipped_not_configured":
                status_text = "email_not_configured"
            elif delivery_status == "dispatch_failed_untrusted_source":
                status_text = "blocked_untrusted_source"
            elif delivery_status.startswith("dispatch_failed"):
                status_text = "dispatch_failed"
            expiry_note = ""
            if hosted_download_expires_at > int(time.time()):
                expiry_note = f"\n⏳ link_expires_at: {datetime.fromtimestamp(hosted_download_expires_at, tz=timezone.utc).isoformat()}"
            reply = (
                f"✅ Textbook queued ({status_text}).\n"
                f"🆔 fulfillment_id: {fulfillment_id}"
                f"\n🔗 download_link: {hosted_download_url or '(unavailable)'}"
                f"{expiry_note}"
            )

        clear_textbook_request(user_id)
        send_message(chat_id, reply)
        return True

    send_message(chat_id, "Unknown /textbook command. Use /textbook help")
    return True


def handle_workspace_command(chat_id: int, user_id: int, text: str, role: str) -> bool:
    parsed = parse_workspace_command(text)
    if parsed is None:
        return False

    command, rest = parsed
    expired_now, removed_docs, failed_docs = cleanup_expired_workspace_for_user(user_id)

    if command in {"help", "?"}:
        send_message(chat_id, workspace_help_text())
        return True

    if command == "create":
        name = " ".join((rest or "").split()).strip()
        if not name:
            send_message(chat_id, "Usage: /workspace create <name>")
            return True

        existing = get_workspace(user_id)
        if existing:
            workspace_id = str(existing.get("workspace_id", "")).strip() or "(unknown)"
            send_message(
                chat_id,
                "A workspace is already active. Use /workspace status or /workspace close first.\n"
                f"- workspace_id: {workspace_id}",
            )
            return True

        now_ts = int(time.time())
        ttl = workspace_ttl_seconds()
        workspace_id = f"ws-{user_id}-{now_ts}"
        entry = {
            "workspace_id": workspace_id,
            "name": name,
            "created_at": now_ts,
            "expires_at": now_ts + ttl,
            "query_mode": "auto",
            "docs": [],
        }
        set_workspace(user_id, entry)
        send_message(
            chat_id,
            "✅ Temporary workspace created.\n"
            f"- workspace_id: {workspace_id}\n"
            f"- name: {name}\n"
            "- query_mode: auto\n"
            f"- expires_in_seconds: {ttl}\n"
            "Add manuals/products with /workspace add <url-or-text>",
        )
        return True

    if command == "mode":
        action = " ".join((rest or "").split()).strip().lower()
        if action == "status":
            entry = get_workspace(user_id)
            if not entry:
                send_message(chat_id, "No active workspace. Create one with /workspace create <name>")
                return True
            send_message(chat_id, f"Workspace query mode: {workspace_query_mode(entry)}")
            return True

        if action not in {"auto", "workspace", "memory"}:
            send_message(chat_id, "Usage: /workspace mode <auto|workspace|memory|status>")
            return True

        entry = get_workspace(user_id)
        if not entry:
            send_message(chat_id, "No active workspace. Create one with /workspace create <name>")
            return True

        entry["query_mode"] = action
        set_workspace(user_id, entry)
        mode_help = {
            "auto": "Auto mode enabled: query uses normal memory + workspace metadata hints.",
            "workspace": "Workspace-only mode enabled: long-term memory is disabled for queries.",
            "memory": "Memory mode enabled: long-term memory is used; workspace scope is advisory only.",
        }
        send_message(chat_id, f"✅ Workspace query mode set to {action}.\n{mode_help.get(action, '')}")
        return True

    if command == "status":
        entry = get_workspace(user_id)
        if not entry:
            if expired_now:
                send_message(
                    chat_id,
                    "No active workspace. Previous workspace expired and cleanup ran.\n"
                    f"- docs_removed: {removed_docs}\n"
                    f"- docs_failed: {failed_docs}",
                )
                return True
            send_message(chat_id, "No active workspace. Create one with /workspace create <name>")
            return True

        now_ts = int(time.time())
        workspace_id = str(entry.get("workspace_id", "")).strip() or "(unknown)"
        name = str(entry.get("name", "")).strip() or "(unnamed)"
        created_at = parse_int(str(entry.get("created_at", "0")), 0)
        expires_at = parse_int(str(entry.get("expires_at", "0")), 0)
        remaining = max(0, expires_at - now_ts) if expires_at > 0 else 0
        docs_raw = entry.get("docs")
        docs = docs_raw if isinstance(docs_raw, list) else []
        lines = [
            "Active workspace:",
            f"- workspace_id: {workspace_id}",
            f"- name: {name}",
            f"- query_mode: {workspace_query_mode(entry)}",
            f"- created_at: {created_at}",
            f"- expires_at: {expires_at}",
            f"- expires_in_seconds: {remaining}",
            f"- doc_count: {len(docs)}",
        ]
        if docs:
            lines.append("- docs:")
            for item in docs[:6]:
                if not isinstance(item, dict):
                    continue
                source_name = str(item.get("source_name", "")).strip() or "(source)"
                doc_id = str(item.get("doc_id", "")).strip() or "(doc)"
                lines.append(f"  - {source_name} [{doc_id}]")
        send_message(chat_id, "\n".join(lines))
        return True

    if command == "close":
        entry = get_workspace(user_id)
        if not entry:
            send_message(chat_id, "No active workspace to close.")
            return True
        removed, failed = clear_workspace(user_id, reason="user_closed")
        send_message(
            chat_id,
            "✅ Workspace closed and cleanup attempted.\n"
            f"- docs_removed: {removed}\n"
            f"- docs_failed: {failed}",
        )
        return True

    if command == "add":
        entry = get_workspace(user_id)
        if not entry:
            send_message(chat_id, "No active workspace. Create one with /workspace create <name>")
            return True

        value = " ".join((rest or "").split()).strip()
        if not value:
            send_message(chat_id, "Usage: /workspace add <url-or-text>")
            return True

        docs_raw = entry.get("docs")
        docs = docs_raw if isinstance(docs_raw, list) else []
        if len(docs) >= max(1, WORKSPACE_MAX_DOCS):
            send_message(chat_id, f"Workspace doc limit reached ({WORKSPACE_MAX_DOCS}). Close or wait for expiry.")
            return True

        workspace_id = str(entry.get("workspace_id", "")).strip() or f"ws-{user_id}-{int(time.time())}"
        expires_at = parse_int(str(entry.get("expires_at", "0")), 0)
        now_ts = int(time.time())
        doc_id = f"workspace-{workspace_id}-{now_ts}"
        is_url = value.startswith(("http://", "https://"))
        source_name = value[:96]
        source_type = "workspace_temp"
        ingest_text = ""

        if is_url:
            try:
                ingest_text = fetch_ingest_text_from_file_url(file_url=value, file_mime="")
            except Exception as exc:
                print(f"[telegram-bridge] workspace file extraction failed: {exc}", flush=True)

        if not ingest_text:
            ingest_text = value

        if not str(ingest_text).strip():
            send_message(chat_id, "Workspace ingest text is empty. Provide readable content or a valid URL.")
            return True

        ingest_payload = {
            "source": "telegram",
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "tenant_id": f"u_{user_id}",
            "text": str(ingest_text)[:16000],
            "source_name": source_name,
            "source_type": source_type,
            "doc_id": doc_id,
            "workspace_id": workspace_id,
            "expires_at": expires_at,
            "timestamp": now_ts,
        }

        try:
            _ = call_n8n(RAG_INGEST_WEBHOOK, ingest_payload)
        except urllib.error.HTTPError as exc:
            send_message(chat_id, f"❌ Workspace ingest webhook error: HTTP {exc.code}")
            return True
        except Exception as exc:
            send_message(chat_id, f"❌ Workspace ingest failed: {exc}")
            return True

        docs.append(
            {
                "doc_id": doc_id,
                "source_name": source_name,
                "source_kind": "url" if is_url else "text",
                "added_at": now_ts,
            }
        )
        entry["docs"] = docs
        set_workspace(user_id, entry)
        remaining = max(0, expires_at - now_ts) if expires_at > 0 else 0
        send_message(
            chat_id,
            "✅ Added to temporary workspace and queued for private RAG ingest.\n"
            f"- workspace_id: {workspace_id}\n"
            f"- doc_id: {doc_id}\n"
            f"- expires_in_seconds: {remaining}",
        )
        return True

    send_message(chat_id, "Unknown /workspace command. Use /workspace help")
    return True


def research_help_text() -> str:
    return (
        "Research commands:\n"
        "/research <query>\n"
        "/research status <run_id>\n"
        "/research report <run_id>\n"
        "\n"
        "Delivery: report links are sent via Nextcloud URL in Telegram reply."
    )


def format_research_status(job: dict[str, Any]) -> str:
    run_id = str(job.get("run_id", "") or "(unknown)")
    status = str(job.get("status", "queued") or "queued")
    created_at = int(job.get("created_at", 0) or 0)
    updated_at = int(job.get("updated_at", 0) or 0)
    report_url = str(job.get("report_url", "") or "").strip()
    report_title = str(job.get("report_title", "") or "").strip()
    error_text = str(job.get("error", "") or "").strip()
    lines = [
        "Research job status:",
        f"- run_id: {run_id}",
        f"- status: {status}",
        f"- created_at: {created_at}",
        f"- updated_at: {updated_at}",
    ]
    if report_title:
        lines.append(f"- title: {report_title}")
    if report_url:
        lines.append(f"- report_link: {report_url}")
    if error_text:
        lines.append(f"- error: {error_text}")
    return "\n".join(lines)


def handle_research_command(chat_id: int, user_id: int, text: str, user_record: dict[str, Any], role: str) -> bool:
    parsed = parse_research_command(text)
    if parsed is None:
        return False

    command, rest = parsed
    if command in {"help", "?"}:
        send_message(chat_id, research_help_text())
        return True

    if command == "start":
        query = " ".join((rest or "").split()).strip()
        if not query:
            send_message(chat_id, "Usage: /research <query>")
            return True
        if len(query) > max(100, RESEARCH_MAX_QUERY_CHARS):
            send_message(chat_id, f"Query is too long. Max chars: {RESEARCH_MAX_QUERY_CHARS}")
            return True

        run_id = generate_research_run_id(user_id=user_id, query=query)
        now_ts = int(time.time())
        job = {
            "run_id": run_id,
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "role": str(role),
            "status": "queued",
            "query": query,
            "created_at": now_ts,
            "updated_at": now_ts,
            "report_url": "",
            "report_title": "",
            "error": "",
            "link_expires_at": now_ts + max(60, RESEARCH_DEFAULT_LINK_TTL_SECONDS),
        }
        with RESEARCH_STATE_LOCK:
            set_research_job(run_id, job)

        payload = {
            "source": "telegram",
            "action": "start",
            "run_id": run_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "tenant_id": f"u_{user_id}",
            "full_name": str(user_record.get("full_name", "")),
            "telegram_username": str(user_record.get("telegram_username", "")),
            "query": query,
            "nextcloud_base_url": RESEARCH_NEXTCLOUD_BASE_URL,
            "nextcloud_user": RESEARCH_NEXTCLOUD_USER,
            "nextcloud_password": RESEARCH_NEXTCLOUD_PASSWORD,
            "nextcloud_folder": RESEARCH_NEXTCLOUD_FOLDER,
            "delivery": {
                "channel": "telegram",
                "mode": "nextcloud_link",
                "link_ttl_seconds": max(60, RESEARCH_DEFAULT_LINK_TTL_SECONDS),
            },
            "timestamp": now_ts,
        }

        try:
            result = call_n8n(RESEARCH_WEBHOOK, payload)
            with RESEARCH_STATE_LOCK:
                updated = apply_research_webhook_result(run_id, result)
            if isinstance(updated, dict) and str(updated.get("status", "")).lower() == "ready" and str(updated.get("report_url", "")).strip():
                send_message(
                    chat_id,
                    (
                        f"✅ Research report ready.\n"
                        f"- run_id: {run_id}\n"
                        f"- report_link: {str(updated.get('report_url', '')).strip()}"
                    ),
                )
                return True
        except urllib.error.HTTPError as exc:
            with RESEARCH_STATE_LOCK:
                failed = get_research_job(run_id) or job
                failed["status"] = "failed"
                failed["error"] = f"http_{exc.code}"
                failed["updated_at"] = int(time.time())
                set_research_job(run_id, failed)
            send_message(chat_id, f"❌ Research start failed: HTTP {exc.code} (run_id={run_id})")
            return True
        except Exception as exc:
            with RESEARCH_STATE_LOCK:
                failed = get_research_job(run_id) or job
                failed["status"] = "failed"
                failed["error"] = str(exc)[:400]
                failed["updated_at"] = int(time.time())
                set_research_job(run_id, failed)
            send_message(chat_id, f"❌ Research start failed: {exc} (run_id={run_id})")
            return True

        send_message(
            chat_id,
            (
                f"🧠 Research queued.\n"
                f"- run_id: {run_id}\n"
                f"Use /research status {run_id} to track progress and /research report {run_id} for the Nextcloud link."
            ),
        )
        return True

    run_id = " ".join((rest or "").split()).strip()
    if not run_id:
        send_message(chat_id, f"Usage: /research {command} <run_id>")
        return True

    with RESEARCH_STATE_LOCK:
        job = get_research_job(run_id)

    if not isinstance(job, dict):
        send_message(chat_id, "Research run id not found.")
        return True

    owner_user_id = int(job.get("user_id", 0) or 0)
    if role != "admin" and owner_user_id != int(user_id):
        send_message(chat_id, "⛔ You can only access your own research jobs.")
        return True

    payload = {
        "source": "telegram",
        "action": "status" if command == "status" else "report",
        "run_id": run_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "role": role,
        "tenant_id": f"u_{user_id}",
        "report_url_hint": str(job.get("report_url", "") or ""),
        "report_title_hint": str(job.get("report_title", "") or ""),
        "link_expires_at_hint": int(job.get("link_expires_at", 0) or 0),
        "timestamp": int(time.time()),
    }
    try:
        result = call_n8n(RESEARCH_WEBHOOK, payload)
        with RESEARCH_STATE_LOCK:
            refreshed = apply_research_webhook_result(run_id, result)
            if isinstance(refreshed, dict):
                job = refreshed
    except Exception as exc:
        print(f"[telegram-bridge] research webhook refresh failed run_id={run_id}: {exc}", flush=True)

    if command == "status":
        send_message(chat_id, format_research_status(job))
        return True

    report_url = str(job.get("report_url", "") or "").strip()
    if report_url:
        send_message(chat_id, f"📄 Research report link\n- run_id: {run_id}\n- report_link: {report_url}")
        return True

    status = str(job.get("status", "queued") or "queued")
    if status == "failed":
        send_message(chat_id, f"❌ Research report failed for run_id={run_id}. Use /research status {run_id} for details.")
        return True

    send_message(chat_id, f"⏳ Research report is not ready yet (status={status}). Use /research status {run_id}.")
    return True


def extract_reply_text(result: dict[str, Any] | str | None) -> str:
    def sanitize_reply_text(raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            return "✅ Received."

        text = re.sub(r"\n\s*\[route:[^\]]+\]\s*$", "", text, flags=re.IGNORECASE)

        if not REPLY_SHOW_SOURCES:
            text = re.sub(r"\n\s*Sources:\s*.*$", "", text, flags=re.IGNORECASE | re.DOTALL)
        else:
            text = re.sub(r"\n{3,}", "\n\n", text)

        lowered = text.lower()
        if any(
            phrase in lowered
            for phrase in (
                "too vague",
                "too short",
                "provide more context",
                "ask a specific question",
                "ask a complete question",
            )
        ):
            text = (
                "Please send a clearer question with a bit more detail.\n"
                "Example: include what system, command, or outcome you want help with."
            )

        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if REPLY_MAX_CHARS > 0 and len(text) > REPLY_MAX_CHARS:
            text = text[: REPLY_MAX_CHARS - 1].rstrip() + "…"

        return text or "✅ Received."

    if result is None:
        return "✅ Received."
    if isinstance(result, str):
        return sanitize_reply_text(result)

    for key in ("reply", "message", "output", "response", "text"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return sanitize_reply_text(value)

    if isinstance(result.get("data"), dict):
        data = result["data"]
        for key in ("reply", "message", "output", "response", "text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return sanitize_reply_text(value)

    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return "✅ Received."


def extract_tone_from_reply_text(reply: str) -> str | None:
    match = re.search(r"\btone:(warm|neutral|concise)\b", str(reply or ""), flags=re.IGNORECASE)
    if not match:
        return None
    return str(match.group(1)).lower()


def extract_tone_target_from_reply_text(reply: str) -> str:
    match = re.search(r"\btone_target:(warm|neutral|concise)\b", str(reply or ""), flags=re.IGNORECASE)
    if not match:
        return ""
    return str(match.group(1)).lower().strip()


def extract_brevity_target_from_reply_text(reply: str) -> str:
    match = re.search(r"\bbrevity:(short|balanced|detailed)\b", str(reply or ""), flags=re.IGNORECASE)
    if not match:
        return ""
    return str(match.group(1)).lower().strip()


def update_persona_drift_metrics(user_id: int, reply: str) -> None:
    record = get_user_record(USER_REGISTRY, user_id)
    if not isinstance(record, dict):
        return

    pref_tone, pref_brevity = get_persona_preferences(record)
    if not pref_tone and not pref_brevity:
        return

    actual_tone = extract_tone_target_from_reply_text(reply)
    actual_brevity = extract_brevity_target_from_reply_text(reply)

    tone_comparable = bool(pref_tone and actual_tone)
    brevity_comparable = bool(pref_brevity and actual_brevity)
    if not tone_comparable and not brevity_comparable:
        return

    mismatch_reasons: list[str] = []
    if tone_comparable and pref_tone != actual_tone:
        mismatch_reasons.append("tone")
    if brevity_comparable and pref_brevity != actual_brevity:
        mismatch_reasons.append("brevity")

    mismatch = bool(mismatch_reasons)

    stats = record.get("persona_drift_stats")
    if not isinstance(stats, dict):
        stats = {}

    total_checks = int(stats.get("total_checks", 0) or 0) + 1
    mismatch_count = int(stats.get("mismatch_count", 0) or 0) + (1 if mismatch else 0)
    match_count = int(stats.get("match_count", 0) or 0) + (0 if mismatch else 1)
    current_streak = int(stats.get("streak", 0) or 0)
    streak = (current_streak + 1) if mismatch else 0
    max_streak = max(int(stats.get("max_streak", 0) or 0), streak)

    stats.update(
        {
            "total_checks": total_checks,
            "mismatch_count": mismatch_count,
            "match_count": match_count,
            "streak": streak,
            "max_streak": max_streak,
            "last_mismatch": mismatch,
            "last_mismatch_reasons": mismatch_reasons,
            "last_pref_tone": pref_tone,
            "last_pref_brevity": pref_brevity,
            "last_actual_tone": actual_tone,
            "last_actual_brevity": actual_brevity,
            "updated_at": utc_now(),
        }
    )
    record["persona_drift_stats"] = stats
    record["persona_drift_streak"] = streak
    record["persona_drift_updated_at"] = utc_now()
    record["updated_at"] = utc_now()

    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)

    if mismatch and streak >= 3:
        print(
            f"[telegram-bridge] persona_drift user_id={user_id} streak={streak} reasons={','.join(mismatch_reasons)}",
            flush=True,
        )


def get_tone_history(record: dict[str, Any] | None) -> list[str]:
    if not isinstance(record, dict):
        return []
    raw = record.get("tone_history")
    if not isinstance(raw, list):
        return []
    return [
        str(item).lower()
        for item in raw
        if str(item).lower() in {"warm", "neutral", "concise"}
    ][-3:]


ALLOWED_PERSONA_TONE_TARGETS = {"warm", "neutral", "concise"}
ALLOWED_PERSONA_BREVITY_TARGETS = {"short", "balanced", "detailed"}
ALLOWED_PERSONA_FEEDBACK_CUES = {"too_short", "too_long", "too_formal", "too_vague", "good"}


def get_persona_preferences(record: dict[str, Any] | None) -> tuple[str, str]:
    if not isinstance(record, dict):
        return "", ""
    tone = str(record.get("persona_pref_tone", "")).strip().lower()
    brevity = str(record.get("persona_pref_brevity", "")).strip().lower()
    if tone not in ALLOWED_PERSONA_TONE_TARGETS:
        tone = ""
    if brevity not in ALLOWED_PERSONA_BREVITY_TARGETS:
        brevity = ""
    return tone, brevity


def apply_persona_feedback(record: dict[str, Any], cue: str) -> tuple[bool, str]:
    signal = str(cue or "").strip().lower()
    if signal not in ALLOWED_PERSONA_FEEDBACK_CUES:
        return False, "Unknown feedback cue. Use: too_short, too_long, too_formal, too_vague, good"

    tone_pref, brevity_pref = get_persona_preferences(record)
    brevity_order = ["short", "balanced", "detailed"]
    current_brevity = brevity_pref or "balanced"
    current_index = brevity_order.index(current_brevity)

    if signal == "too_short" and current_index < (len(brevity_order) - 1):
        record["persona_pref_brevity"] = brevity_order[current_index + 1]
    elif signal == "too_long" and current_index > 0:
        record["persona_pref_brevity"] = brevity_order[current_index - 1]
    elif signal == "too_formal":
        record["persona_pref_tone"] = "warm"
    elif signal == "too_vague":
        record["persona_pref_brevity"] = "detailed"

    stats = record.get("persona_feedback_stats")
    if not isinstance(stats, dict):
        stats = {}
    stats[signal] = int(stats.get(signal, 0) or 0) + 1
    record["persona_feedback_stats"] = stats
    record["persona_feedback_last"] = signal
    record["persona_feedback_updated_at"] = utc_now()
    record["updated_at"] = utc_now()

    new_tone, new_brevity = get_persona_preferences(record)
    return True, (
        f"✅ Feedback recorded ({signal}). "
        f"Current style prefs: tone={new_tone or '(auto)'} brevity={new_brevity or '(auto)'}"
    )


def update_user_tone_history(user_id: int, tone: str | None) -> None:
    normalized = str(tone or "").lower().strip()
    if normalized not in {"warm", "neutral", "concise"}:
        return
    record = get_user_record(USER_REGISTRY, user_id)
    if not record:
        return
    history = get_tone_history(record)
    history = [*history, normalized][-3:]
    record["tone_history"] = history
    record["updated_at"] = utc_now()
    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)


def parse_update(
    update: dict[str, Any],
) -> tuple[
    int,
    int,
    str,
    list[dict[str, Any]],
    dict[str, Any] | None,
    dict[str, Any] | None,
    str,
    str,
    str,
    str,
]:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}

    chat_id = int(chat.get("id", 0))
    user_id = int(sender.get("id", 0))
    text = (message.get("text") or message.get("caption") or "").strip()
    photos = message.get("photo") or []
    voice = message.get("voice")
    audio = message.get("audio")
    chat_type = (chat.get("type") or "").strip()
    username = str(sender.get("username") or "").strip()
    first_name = str(sender.get("first_name") or "").strip()
    last_name = str(sender.get("last_name") or "").strip()

    return chat_id, user_id, text, photos, voice, audio, chat_type, username, first_name, last_name


def file_url_from_file_id(file_id: str | None) -> str | None:
    if not file_id:
        return None

    response = telegram_request("getFile", {"file_id": file_id})
    file_path = ((response.get("result") or {}).get("file_path"))
    if not file_path:
        return None
    return f"{BOT_FILE_BASE}/{file_path}"


def file_url_from_photo_sizes(photo_sizes: list[dict[str, Any]]) -> str | None:
    if not photo_sizes:
        return None
    largest = max(photo_sizes, key=lambda item: item.get("file_size", 0))
    file_id = largest.get("file_id")
    return file_url_from_file_id(file_id)


def extract_audio_info(voice: dict[str, Any] | None, audio: dict[str, Any] | None) -> dict[str, Any]:
    if voice:
        file_id = (voice or {}).get("file_id")
        return {
            "audio_url": file_url_from_file_id(file_id) if file_id else None,
            "audio_kind": "voice",
            "audio_mime": voice.get("mime_type"),
            "audio_duration": voice.get("duration"),
            "audio_file_id": file_id,
            "audio_file_name": None,
        }

    if audio:
        file_id = (audio or {}).get("file_id")
        return {
            "audio_url": file_url_from_file_id(file_id) if file_id else None,
            "audio_kind": "audio",
            "audio_mime": audio.get("mime_type"),
            "audio_duration": audio.get("duration"),
            "audio_file_id": file_id,
            "audio_file_name": audio.get("file_name"),
        }

    return {
        "audio_url": None,
        "audio_kind": None,
        "audio_mime": None,
        "audio_duration": None,
        "audio_file_id": None,
        "audio_file_name": None,
    }


def choose_mode(text: str) -> str:
    token = command_token(text)
    if token == "/ops":
        return "ops"
    if token == "/rag":
        return "rag"
    return DEFAULT_MODE if DEFAULT_MODE in {"rag", "ops"} else "rag"


def strip_mode_prefix(text: str) -> str:
    token = command_token(text)
    if token in {"/ops", "/rag"}:
        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            return ""
        return parts[1].strip()
    return text


def parse_user_admin_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/user":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("help", [])
    command = parts[1].lower()
    return (command, parts[2:])


def parse_approval_command(text: str) -> tuple[str, str] | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    command = command_token(parts[0]) if parts else ""
    if command not in {"/approve", "/deny", "approve", "deny"}:
        return None
    action = "approve" if "approve" in command else "deny"
    return action, parts[1].strip()


def parse_notify_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/notify":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("list", [])
    return (parts[1].lower(), parts[2:])


def parse_incident_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/incident":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("list", [])
    return (parts[1].lower(), parts[2:])


def parse_reqtrack_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/reqtrack":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("list", ["active"])
    return (parts[1].lower(), parts[2:])


def parse_simple_command(text: str, token_name: str) -> list[str] | None:
    if command_token(text) != token_name:
        return None
    parts = text.strip().split()
    return parts[1:]


def parse_memory_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/memory":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("show", [])
    return (parts[1].lower(), parts[2:])


def parse_textbook_command(text: str) -> tuple[str, str] | None:
    token = command_token(text)
    if token not in {"/textbook", "/book"}:
        return None
    raw = (text or "").strip()
    parts = raw.split(maxsplit=2)
    if len(parts) == 1:
        return "help", ""
    command = parts[1].lower().strip()
    rest = parts[2].strip() if len(parts) >= 3 else ""
    return command, rest


def parse_workspace_command(text: str) -> tuple[str, str] | None:
    if command_token(text) != "/workspace":
        return None
    raw = (text or "").strip()
    parts = raw.split(maxsplit=2)
    if len(parts) == 1:
        return "help", ""
    command = parts[1].lower().strip()
    rest = parts[2].strip() if len(parts) >= 3 else ""
    return command, rest


def parse_coding_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/coding":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("help", [])
    return (parts[1].lower(), parts[2:])


def parse_tone_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/tone":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("help", [])
    return (parts[1].lower(), parts[2:])


def parse_profile_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/profile":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("show", [])
    return (parts[1].lower(), parts[2:])


def parse_feedback_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/feedback":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("help", [])
    return (parts[1].lower(), parts[2:])


def parse_discord_command(text: str) -> tuple[str, list[str]] | None:
    if command_token(text) != "/discord":
        return None
    parts = text.strip().split()
    if len(parts) < 2:
        return ("help", [])
    return (parts[1].lower(), parts[2:])


def parse_research_command(text: str) -> tuple[str, str] | None:
    if command_token(text) != "/research":
        return None
    raw = (text or "").strip()
    parts = raw.split(maxsplit=2)
    if len(parts) == 1:
        return ("help", "")

    second = parts[1].lower().strip()
    if second in {"help", "status", "report"}:
        rest = parts[2].strip() if len(parts) >= 3 else ""
        return (second, rest)

    query = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) > 1 else ""
    return ("start", query)


def sanitize_profile_seed(text: str) -> str:
    value = str(text or "").replace("\r\n", "\n").strip()
    value = re.sub(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", "[redacted-token]", value)
    value = re.sub(r"\bsk-[A-Za-z0-9]{20,}\b", "[redacted-key]", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    if len(value) <= max(1, PROFILE_MAX_CHARS):
        return value
    return value[: max(1, PROFILE_MAX_CHARS - 1)].rstrip() + "…"


def resolve_profile_image_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "file://")):
        return value
    if value.startswith("work/discord-seed/"):
        suffix = value.split("work/discord-seed/", 1)[1]
        return f"file:///work/discord-seed/{suffix}"
    if value.startswith("/work/discord-seed/"):
        return f"file://{value}"
    if pathlib.Path(value).is_absolute():
        return f"file://{value}"
    return value


def load_profile_seed_catalog() -> dict[str, dict[str, Any]]:
    if not PROFILE_SEED_PATH.exists():
        return {}
    try:
        data = json.loads(PROFILE_SEED_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        profiles = data.get("profiles")
        if not isinstance(profiles, dict):
            return {}
        cleaned: dict[str, dict[str, Any]] = {}
        for key, value in profiles.items():
            if isinstance(value, dict):
                cleaned[str(key)] = value
        return cleaned
    except Exception as exc:
        print(f"[telegram-bridge] failed to load profile seeds: {exc}", flush=True)
        return {}


def normalize_discord_identity(value: str) -> str:
    base = str(value or "").strip().lower()
    if base.startswith("@"):
        base = base[1:]
    return "".join(ch for ch in base if ch.isalnum())


def collect_discord_aliases(profile: dict[str, Any], discord_user_id: str) -> list[str]:
    aliases: list[str] = [str(discord_user_id)]
    for key in ("username", "display_name", "global_name", "name"):
        value = str(profile.get(key, "")).strip()
        if value:
            aliases.append(value)

    for key in ("aliases", "alias", "nicknames", "names"):
        raw = profile.get(key)
        if isinstance(raw, list):
            for value in raw:
                alias = str(value).strip()
                if alias:
                    aliases.append(alias)

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        marker = alias.lower()
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(alias)
    return deduped


def find_discord_profile_matches(name_or_handle: str, limit: int = 5) -> list[tuple[int, str, dict[str, Any], str]]:
    query_norm = normalize_discord_identity(name_or_handle)
    if not query_norm:
        return []

    profiles = load_profile_seed_catalog()
    matches: list[tuple[int, str, dict[str, Any], str]] = []

    for discord_user_id, profile in profiles.items():
        aliases = collect_discord_aliases(profile, discord_user_id)
        best_score = -1
        best_alias = ""
        for alias in aliases:
            alias_norm = normalize_discord_identity(alias)
            if not alias_norm:
                continue
            score = -1
            if alias_norm == query_norm:
                score = 100
            elif alias_norm.startswith(query_norm):
                score = 80
            elif query_norm in alias_norm and len(query_norm) >= 3:
                score = 70
            elif alias_norm in query_norm and len(alias_norm) >= 3:
                score = 60
            if score > best_score:
                best_score = score
                best_alias = alias
        if best_score > 0:
            matches.append((best_score, discord_user_id, profile, best_alias))

    matches.sort(key=lambda item: (-item[0], item[1]))
    return matches[: max(1, limit)]


def apply_discord_profile_link(record: dict[str, Any], discord_user_id: str, profile: dict[str, Any], matched_alias: str) -> tuple[bool, str]:
    profile_seed = sanitize_profile_seed(str(profile.get("user_profile_seed", "")))
    if not profile_seed:
        return False, "Matched Discord profile has no usable seed text."

    profile_image_url = resolve_profile_image_url(
        str(profile.get("user_profile_image_url") or profile.get("avatar_path") or "")
    )

    preferred_name = str(
        profile.get("display_name")
        or profile.get("global_name")
        or profile.get("username")
        or matched_alias
        or discord_user_id
    ).strip()

    record["linked_discord_user_id"] = str(discord_user_id)
    record["linked_discord_name"] = preferred_name
    record["linked_discord_match"] = str(matched_alias or preferred_name)
    record["linked_discord_updated_at"] = utc_now()
    record["discord_link_state"] = "linked"

    record["user_profile_seed"] = profile_seed
    if profile_image_url:
        record["user_profile_image_url"] = profile_image_url
    else:
        record.pop("user_profile_image_url", None)
    record["profile_enabled"] = True
    record["profile_source"] = f"discord_link:{discord_user_id}"
    record["profile_updated_at"] = utc_now()
    return True, f"✅ Discord profile linked: {preferred_name} ({discord_user_id})."


def attempt_discord_link(chat_id: int, user_id: int, record: dict[str, Any], name_or_handle: str) -> bool:
    query = " ".join(str(name_or_handle or "").split()).strip()
    if not query:
        send_message(chat_id, "Please provide your Discord name. Example: /discord link sooknootv")
        return True

    matches = find_discord_profile_matches(query, limit=5)
    if not matches:
        send_message(
            chat_id,
            "No Discord profile match found. Try a different name/handle (for example username or display name).",
        )
        return True

    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        lines = [
            "I found multiple close Discord matches. Reply with a more specific name, or use /discord link <exact_handle>:",
        ]
        for _, discord_user_id, profile, matched_alias in matches[:5]:
            label = str(
                profile.get("display_name")
                or profile.get("global_name")
                or profile.get("username")
                or discord_user_id
            )
            lines.append(f"- {label} (id={discord_user_id}, match={matched_alias})")
        send_message(chat_id, "\n".join(lines))
        return True

    _, discord_user_id, profile, matched_alias = matches[0]
    ok, message = apply_discord_profile_link(record, discord_user_id, profile, matched_alias)
    if not ok:
        send_message(chat_id, message)
        return True

    record["updated_at"] = utc_now()
    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)
    send_message(chat_id, message)
    return True


def apply_seed_profile_for_user(record: dict[str, Any], user_id: int) -> tuple[bool, str]:
    profiles = load_profile_seed_catalog()
    source = profiles.get(str(user_id))
    if not isinstance(source, dict):
        return False, "No seed profile found for your user id."

    profile_seed = sanitize_profile_seed(str(source.get("user_profile_seed", "")))
    if not profile_seed:
        return False, "Seed profile exists but has no usable profile text."

    profile_image_url = resolve_profile_image_url(
        str(source.get("user_profile_image_url") or source.get("avatar_path") or "")
    )

    record["user_profile_seed"] = profile_seed
    if profile_image_url:
        record["user_profile_image_url"] = profile_image_url
    else:
        record.pop("user_profile_image_url", None)
    record["profile_enabled"] = True
    record["profile_source"] = "discord_seed"
    record["profile_updated_at"] = utc_now()
    return True, "✅ Seed profile applied."


def apply_seed_profile_by_id(record: dict[str, Any], seed_id: str) -> tuple[bool, str]:
    target_id = str(seed_id or "").strip()
    if not target_id:
        return False, "Seed id is required."

    profiles = load_profile_seed_catalog()
    source = profiles.get(target_id)
    if not isinstance(source, dict):
        return False, f"No seed profile found for id={target_id}."

    profile_seed = sanitize_profile_seed(str(source.get("user_profile_seed", "")))
    if not profile_seed:
        return False, f"Seed profile id={target_id} has no usable profile text."

    profile_image_url = resolve_profile_image_url(
        str(source.get("user_profile_image_url") or source.get("avatar_path") or "")
    )

    record["user_profile_seed"] = profile_seed
    if profile_image_url:
        record["user_profile_image_url"] = profile_image_url
    else:
        record.pop("user_profile_image_url", None)
    record["profile_enabled"] = True
    record["profile_source"] = f"discord_seed:{target_id}"
    record["profile_updated_at"] = utc_now()
    return True, f"✅ Seed profile applied from id={target_id}."


def suggest_profile_seed_candidates(record: dict[str, Any], user_id: int, limit: int = 3) -> list[tuple[int, str, str]]:
    queries: list[str] = []
    for key in ("linked_discord_name", "linked_discord_match", "telegram_username", "full_name"):
        value = str(record.get(key, "")).strip()
        if value:
            queries.append(value)

    ranked: dict[str, tuple[int, str]] = {}
    for query in queries:
        for score, discord_user_id, profile, matched_alias in find_discord_profile_matches(query, limit=8):
            label = str(
                profile.get("display_name")
                or profile.get("global_name")
                or profile.get("username")
                or matched_alias
                or discord_user_id
            ).strip()
            existing = ranked.get(discord_user_id)
            if existing is None or score > existing[0]:
                ranked[discord_user_id] = (score, label)

    catalog = load_profile_seed_catalog()
    own_id = str(user_id)
    if own_id in catalog:
        profile = catalog.get(own_id) if isinstance(catalog.get(own_id), dict) else {}
        if isinstance(profile, dict):
            label = str(
                profile.get("display_name")
                or profile.get("global_name")
                or profile.get("username")
                or own_id
            ).strip()
            ranked[own_id] = (1000, label)

    ordered = sorted(((score, sid, label) for sid, (score, label) in ranked.items()), key=lambda item: (-item[0], item[1]))
    return ordered[: max(1, limit)]


def handle_memory_command(chat_id: int, user_id: int, text: str) -> bool:
    parsed = parse_memory_command(text)
    if parsed is None:
        return False

    command, args = parsed
    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Memory commands:\n"
            "/memory show\n"
            "/memory on\n"
            "/memory off\n"
            "/memory add <note>\n"
            "/memory export\n"
            "/memory forget <index>\n"
            "/memory forget source <source>\n"
            "/memory why\n"
            "/memory clear\n"
            "/memory conflicts\n"
            "/memory resolve <index> <keep|drop>",
        )
        return True

    if command == "on":
        set_memory_enabled(user_id, True)
        send_message(chat_id, "✅ Memory enabled for your account.")
        return True

    if command == "off":
        set_memory_enabled(user_id, False)
        send_message(chat_id, "✅ Memory disabled for your account.")
        return True

    if command == "clear":
        clear_memory(user_id)
        send_message(chat_id, "✅ Memory cleared.")
        return True

    if command == "export":
        send_message(chat_id, build_memory_export_text(user_id=user_id, max_chars=REPLY_MAX_CHARS))
        return True

    if command == "forget":
        if not args:
            send_message(chat_id, "Usage: /memory forget <index> | /memory forget source <source>")
            return True
        if str(args[0]).lower() == "source":
            if len(args) < 2:
                send_message(chat_id, "Usage: /memory forget source <source>")
                return True
            ok, removed, remaining, mode = forget_memory_notes(user_id=user_id, source=" ".join(args[1:]))
            if not ok:
                send_message(chat_id, f"⚠️ Forget by source failed. reason={mode} remaining={remaining}")
                return True
            send_message(chat_id, f"✅ Forgot {removed} memory notes by {mode}. remaining={remaining}")
            return True
        try:
            target_index = int(args[0])
        except ValueError:
            send_message(chat_id, "Invalid index. Use /memory export to find note indexes.")
            return True
        ok, removed, remaining, mode = forget_memory_notes(user_id=user_id, index=target_index)
        if not ok:
            send_message(chat_id, f"⚠️ Forget failed. reason={mode} remaining={remaining}")
            return True
        send_message(chat_id, f"✅ Forgot note #{target_index}. removed={removed} remaining={remaining}")
        return True

    if command == "why":
        send_message(chat_id, build_memory_why_text(user_id=user_id, limit=5))
        return True

    if command == "add":
        if not args:
            send_message(chat_id, "Usage: /memory add <note>")
            return True
        saved, count, reason = add_memory_note(
            user_id,
            " ".join(args),
            source="telegram_user_note",
            confidence=1.0,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved:
            send_message(chat_id, f"⚠️ Memory note not saved. reason={reason} total_notes={count}")
            return True
        send_message(chat_id, f"✅ Memory note saved. total_notes={count}")
        return True

    if command == "conflicts":
        conflicts = list_memory_conflicts(user_id)
        if not conflicts:
            send_message(chat_id, "No memory conflict candidates right now.")
            return True
        lines = ["Memory conflict candidates:"]
        reminder_count = 0
        oldest_age_seconds = 0
        for item in conflicts[:10]:
            if not isinstance(item, dict):
                continue
            index = int(item.get("index", 0) or 0)
            tier = str(item.get("tier", "session"))
            source = str(item.get("source", "unknown"))
            text_preview = str(item.get("text", "")).strip()[:120]
            age = str(item.get("age", "unknown"))
            age_seconds = int(item.get("age_seconds", 0) or 0)
            oldest_age_seconds = max(oldest_age_seconds, age_seconds)
            needs_reminder = bool(item.get("needs_reminder", False))
            if needs_reminder:
                reminder_count += 1
            stale_marker = " ⚠️stale" if needs_reminder else ""
            lines.append(f"- #{index} [{tier}/{source}] age={age}{stale_marker} {text_preview}")
        if reminder_count > 0:
            lines.append(
                f"⚠️ {reminder_count} unresolved conflict(s) exceeded reminder threshold ({max(1, MEMORY_CONFLICT_REMINDER_SECONDS // 3600)}h)."
            )
            append_memory_telemetry(
                "conflict_reminder",
                user_id=user_id,
                fields={
                    "reminder_count": reminder_count,
                    "oldest_age_seconds": oldest_age_seconds,
                    "threshold_seconds": MEMORY_CONFLICT_REMINDER_SECONDS,
                },
            )
        lines.append("Resolve with: /memory resolve <index> <keep|drop>")
        send_message(chat_id, "\n".join(lines))
        return True

    if command == "resolve":
        if len(args) < 2:
            send_message(chat_id, "Usage: /memory resolve <index> <keep|drop>")
            return True
        try:
            target_index = int(args[0])
        except ValueError:
            send_message(chat_id, "Invalid conflict index. Use a number from /memory conflicts.")
            return True
        ok, detail = resolve_memory_conflict(user_id=user_id, index=target_index, action=args[1])
        send_message(chat_id, detail)
        return True

    enabled, summary, provenance = get_memory_context(user_id)
    lines = ["Memory profile:", f"- enabled: {'yes' if enabled else 'no'}"]
    lines.append(f"- memory_v2_canary: {'yes' if is_memory_v2_canary_user(user_id) else 'no'}")
    if summary:
        lines.append("- notes:")
        lines.append(summary)
    else:
        lines.append("- notes: (none)")
    if provenance:
        preview = ", ".join(
            f"{str(item.get('tier', 'session'))}:{str(item.get('source', 'unknown'))}:{float(item.get('confidence', 1.0)):.2f}"
            for item in provenance[-3:]
            if isinstance(item, dict)
        )
        if preview:
            lines.append(f"- provenance: {preview}")
    conflict_count = len(list_memory_conflicts(user_id))
    lines.append(f"- conflict_candidates: {conflict_count}")
    send_message(chat_id, "\n".join(lines))
    return True


def handle_tone_command(chat_id: int, requester_id: int, text: str) -> bool:
    parsed = parse_tone_command(text)
    if parsed is None:
        return False

    requester = get_user_record(USER_REGISTRY, requester_id)
    if not requester or requester.get("role") != "admin" or requester.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    command, args = parsed
    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Tone commands (admin):\n"
            "/tone show <telegram_user_id>\n"
            "/tone reset <telegram_user_id>",
        )
        return True

    if command not in {"show", "reset"}:
        send_message(chat_id, "Unknown /tone command. Use /tone help")
        return True

    if not args:
        send_message(chat_id, f"Usage: /tone {command} <telegram_user_id>")
        return True

    try:
        target_user_id = int(args[0])
    except ValueError:
        send_message(chat_id, "Invalid telegram user id.")
        return True

    target_record = get_user_record(USER_REGISTRY, target_user_id)
    if not target_record:
        send_message(chat_id, f"User {target_user_id} not found in registry.")
        return True

    if command == "show":
        history = get_tone_history(target_record)
        history_text = ", ".join(history) if history else "(none)"
        send_message(chat_id, f"Tone history for {target_user_id}: {history_text}")
        return True

    target_record["tone_history"] = []
    target_record["updated_at"] = utc_now()
    USER_REGISTRY.setdefault("users", {})[str(target_user_id)] = target_record
    save_user_registry(USER_REGISTRY)
    send_message(chat_id, f"✅ Tone history reset for {target_user_id}.")
    return True


def handle_profile_command(chat_id: int, user_id: int, text: str) -> bool:
    def log_profile_action(command_name: str, result: str) -> None:
        print(
            f"[telegram-bridge] profile_action user_id={user_id} command={command_name} result={result}",
            flush=True,
        )

    parsed = parse_profile_command(text)
    if parsed is None:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or str(record.get("status", "active")) != "active":
        send_message(chat_id, "⛔ Account disabled.")
        log_profile_action("profile", "account_disabled")
        return True

    command, args = parsed

    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Profile commands:\n"
            "/profile show\n"
            "/profile age show\n"
            "/profile age set <years>\n"
            "/profile age clear\n"
            "/profile apply\n"
            "/profile apply <seed_id>\n"
            "/profile apply text <profile text>\n"
            "/profile style show\n"
            "/profile style set tone <warm|neutral|concise>\n"
            "/profile style set brevity <short|balanced|detailed>\n"
            "/profile style reset\n"
            "/profile clear",
        )
        log_profile_action("help", "shown")
        return True

    if command == "show":
        profile_seed = sanitize_profile_seed(str(record.get("user_profile_seed", "")))
        profile_enabled = bool(record.get("profile_enabled", bool(profile_seed)))
        profile_source = str(record.get("profile_source", "none"))
        profile_image_url = str(record.get("user_profile_image_url", "")).strip()
        updated_at = str(record.get("profile_updated_at", "(never)"))
        account_age = get_record_account_age(record)
        account_class = get_record_account_class(record)
        class_label = "Child" if account_class == "child" else "Adult"

        lines = [
            "Profile personalization:",
            f"- enabled: {'yes' if profile_enabled and profile_seed else 'no'}",
            f"- source: {profile_source}",
            f"- has_image: {'yes' if bool(profile_image_url) else 'no'}",
            f"- updated_at: {updated_at}",
            f"- account_class: {class_label}",
            f"- age: {account_age if isinstance(account_age, int) else '(not set)'}",
        ]
        tone_pref, brevity_pref = get_persona_preferences(record)
        lines.append(
            f"- style_preferences: tone={tone_pref or '(auto)'} brevity={brevity_pref or '(auto)'}"
        )
        drift_stats = record.get("persona_drift_stats") if isinstance(record, dict) else {}
        if isinstance(drift_stats, dict) and int(drift_stats.get("total_checks", 0) or 0) > 0:
            lines.append(
                "- drift: "
                f"streak={int(drift_stats.get('streak', 0) or 0)} "
                f"mismatch={int(drift_stats.get('mismatch_count', 0) or 0)}/"
                f"{int(drift_stats.get('total_checks', 0) or 0)}"
            )
        else:
            lines.append("- drift: (insufficient data)")
        if profile_seed:
            preview = profile_seed
            if len(preview) > max(40, PROFILE_PREVIEW_CHARS):
                preview = preview[: max(40, PROFILE_PREVIEW_CHARS - 1)].rstrip() + "…"
            lines.append("- preview:")
            lines.append(preview)
        else:
            lines.append("- preview: (none)")
        send_message(chat_id, "\n".join(lines))
        log_profile_action("show", "shown")
        return True

    if command == "age":
        sub = str(args[0]).lower() if args else "show"
        if sub in {"show", "status"}:
            account_age = get_record_account_age(record)
            account_class = get_record_account_class(record)
            class_label = "Child" if account_class == "child" else "Adult"
            send_message(
                chat_id,
                (
                    "Account classification:\n"
                    f"- class: {class_label}\n"
                    f"- age: {account_age if isinstance(account_age, int) else '(not set)'}\n"
                    f"- adult_threshold: {CHILD_ACCOUNT_ADULT_MIN_AGE}\n"
                    "Use /profile age set <years> to update."
                ),
            )
            log_profile_action("age_show", "shown")
            return True

        if sub == "clear":
            record.pop("age", None)
            record["account_class"] = "adult"
            record["updated_at"] = utc_now()
            USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
            save_user_registry(USER_REGISTRY)
            send_message(chat_id, "✅ Age cleared. Account class reset to Adult.")
            log_profile_action("age_clear", "updated")
            return True

        if sub == "set":
            if len(args) < 2:
                send_message(chat_id, "Usage: /profile age set <years>")
                log_profile_action("age_set", "usage_error")
                return True
            age = parse_account_age(args[1])
            if age is None:
                send_message(chat_id, "Age must be a number between 1 and 120.")
                log_profile_action("age_set", "invalid_age")
                return True
            record["age"] = int(age)
            record["account_class"] = classify_account_by_age(age)
            if str(record.get("registration_state", "")) == "pending_age":
                record["registration_state"] = "active"
                record["status"] = "active"
            record["updated_at"] = utc_now()
            USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
            save_user_registry(USER_REGISTRY)
            class_label = "Child" if record.get("account_class") == "child" else "Adult"
            send_message(chat_id, f"✅ Age set to {age}. Account class is now {class_label}.")
            log_profile_action("age_set", "updated")
            return True

        send_message(chat_id, "Unknown /profile age command. Use /profile age show|set|clear")
        log_profile_action("age", "unknown_command")
        return True

    if command == "style":
        if not args or args[0].lower() in {"show", "status"}:
            tone_pref, brevity_pref = get_persona_preferences(record)
            send_message(
                chat_id,
                "Profile style preferences:\n"
                f"- tone: {tone_pref or '(auto)'}\n"
                f"- brevity: {brevity_pref or '(auto)'}\n"
                "Use /profile style set tone <warm|neutral|concise>\n"
                "Use /profile style set brevity <short|balanced|detailed>\n"
                "Use /profile style reset",
            )
            log_profile_action("style_show", "shown")
            return True

        sub = str(args[0]).lower()
        if sub == "reset":
            record.pop("persona_pref_tone", None)
            record.pop("persona_pref_brevity", None)
            record["updated_at"] = utc_now()
            USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
            save_user_registry(USER_REGISTRY)
            send_message(chat_id, "✅ Profile style preferences reset to auto.")
            log_profile_action("style_reset", "reset")
            return True

        if sub == "set":
            if len(args) < 3:
                send_message(
                    chat_id,
                    "Usage:\n"
                    "/profile style set tone <warm|neutral|concise>\n"
                    "/profile style set brevity <short|balanced|detailed>",
                )
                log_profile_action("style_set", "usage_error")
                return True

            field = str(args[1]).lower()
            value = str(args[2]).lower()
            if field == "tone":
                if value not in ALLOWED_PERSONA_TONE_TARGETS:
                    send_message(chat_id, "Invalid tone value. Use warm|neutral|concise.")
                    log_profile_action("style_set_tone", "invalid_value")
                    return True
                record["persona_pref_tone"] = value
                record["updated_at"] = utc_now()
                USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
                save_user_registry(USER_REGISTRY)
                send_message(chat_id, f"✅ Tone preference set to {value}.")
                log_profile_action("style_set_tone", "updated")
                return True

            if field == "brevity":
                if value not in ALLOWED_PERSONA_BREVITY_TARGETS:
                    send_message(chat_id, "Invalid brevity value. Use short|balanced|detailed.")
                    log_profile_action("style_set_brevity", "invalid_value")
                    return True
                record["persona_pref_brevity"] = value
                record["updated_at"] = utc_now()
                USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
                save_user_registry(USER_REGISTRY)
                send_message(chat_id, f"✅ Brevity preference set to {value}.")
                log_profile_action("style_set_brevity", "updated")
                return True

            send_message(chat_id, "Unknown style field. Use tone or brevity.")
            log_profile_action("style_set", "unknown_field")
            return True

        send_message(chat_id, "Unknown /profile style command. Use /profile style show|set|reset")
        log_profile_action("style", "unknown_command")
        return True

    if command == "clear":
        record["profile_enabled"] = False
        record.pop("user_profile_seed", None)
        record.pop("user_profile_image_url", None)
        record["profile_source"] = "cleared"
        record["profile_updated_at"] = utc_now()
        record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, "✅ Profile personalization cleared.")
        log_profile_action("clear", "cleared")
        return True

    if command == "apply":
        if args and args[0].lower() == "text":
            custom_text = " ".join(args[1:]).strip()
            if not custom_text:
                send_message(chat_id, "Usage: /profile apply text <profile text>")
                log_profile_action("apply_text", "usage_error")
                return True
            profile_seed = sanitize_profile_seed(custom_text)
            if not profile_seed:
                send_message(chat_id, "Profile text is empty after sanitization.")
                log_profile_action("apply_text", "empty_after_sanitize")
                return True
            record["user_profile_seed"] = profile_seed
            record["profile_enabled"] = True
            record["profile_source"] = "manual"
            record["profile_updated_at"] = utc_now()
            record["updated_at"] = utc_now()
            USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
            save_user_registry(USER_REGISTRY)
            send_message(chat_id, "✅ Manual profile text applied.")
            log_profile_action("apply_text", "applied")
            return True

        if args:
            seed_id = str(args[0]).strip()
            success, message = apply_seed_profile_by_id(record=record, seed_id=seed_id)
            if not success:
                send_message(chat_id, message)
                log_profile_action("apply_seed_id", "not_found")
                return True

            record["updated_at"] = utc_now()
            USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
            save_user_registry(USER_REGISTRY)
            send_message(chat_id, message)
            log_profile_action("apply_seed_id", "applied")
            return True

        success, message = apply_seed_profile_for_user(record=record, user_id=user_id)
        if not success:
            send_message(
                chat_id,
                (
                    f"{message}\n"
                    "Tip: use /profile apply text <profile text> to set one manually."
                ),
            )
            log_profile_action("apply", "seed_missing")
            return True

        record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, message)
        log_profile_action("apply", "seed_applied")
        return True

    send_message(chat_id, "Unknown /profile command. Use /profile help")
    log_profile_action(command, "unknown_command")
    return True


def handle_feedback_command(chat_id: int, user_id: int, text: str) -> bool:
    parsed = parse_feedback_command(text)
    if parsed is None:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or str(record.get("status", "active")) != "active":
        send_message(chat_id, "⛔ Account disabled.")
        return True

    cue, _args = parsed
    if cue in {"help", "?"}:
        send_message(
            chat_id,
            "Feedback commands:\n"
            "/feedback too_short\n"
            "/feedback too_long\n"
            "/feedback too_formal\n"
            "/feedback too_vague\n"
            "/feedback good",
        )
        return True

    ok, message = apply_persona_feedback(record, cue)
    if not ok:
        send_message(chat_id, message)
        return True

    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)
    send_message(chat_id, message)
    print(f"[telegram-bridge] feedback_action user_id={user_id} cue={cue}", flush=True)
    return True


def handle_discord_command(chat_id: int, user_id: int, text: str) -> bool:
    parsed = parse_discord_command(text)
    if parsed is None:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or str(record.get("status", "active")) != "active":
        send_message(chat_id, "⛔ Account disabled.")
        return True

    command, args = parsed
    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Discord link commands:\n"
            "/discord show\n"
            "/discord link\n"
            "/discord link <discord_name_or_handle>\n"
            "/discord unlink",
        )
        return True

    if command == "show":
        linked_id = str(record.get("linked_discord_user_id", "")).strip()
        linked_name = str(record.get("linked_discord_name", "")).strip()
        linked_match = str(record.get("linked_discord_match", "")).strip()
        updated_at = str(record.get("linked_discord_updated_at", "(never)"))
        is_linked = bool(linked_id)
        lines = [
            "Discord link status:",
            f"- linked: {'yes' if is_linked else 'no'}",
            f"- discord_user_id: {linked_id or '(not set)'}",
            f"- discord_name: {linked_name or '(not set)'}",
            f"- matched_on: {linked_match or '(not set)'}",
            f"- updated_at: {updated_at}",
        ]
        if str(record.get("discord_link_state", "")) == "pending_name":
            lines.append("- prompt: waiting for your Discord name")
        send_message(chat_id, "\n".join(lines))
        return True

    if command in {"unlink", "clear", "remove"}:
        record.pop("linked_discord_user_id", None)
        record.pop("linked_discord_name", None)
        record.pop("linked_discord_match", None)
        record.pop("linked_discord_updated_at", None)
        record.pop("discord_link_query", None)
        record["discord_link_state"] = "unlinked"
        record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, "✅ Discord link removed. Your Telegram account is no longer tied to a Discord profile.")
        return True

    if command == "link":
        if args:
            record["discord_link_query"] = " ".join(args).strip()
            return attempt_discord_link(chat_id, user_id, record, " ".join(args))

        record["discord_link_state"] = "pending_name"
        record["discord_link_query"] = ""
        record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        send_message(
            chat_id,
            "Please reply with your Discord account name or handle to link memory (example: sooknootv).",
        )
        return True

    send_message(chat_id, "Unknown /discord command. Use /discord help")
    return True


def format_notify_help() -> str:
    topics = ", ".join(sorted(NOTIFICATION_TOPIC_LABELS.keys()))
    return (
        "Notification commands:\n"
        "/notify me\n"
        "/notify list\n"
        "/notify profile\n"
        "/notify test <topic>\n"
        "/notify validate\n"
        "/notify stats\n"
        "/notify health\n"
        "/notify set <all|none|topic1,topic2>\n"
        "/notify add <topic1,topic2>\n"
        "/notify remove <topic1,topic2>\n"
        "/notify emergency <on|off>\n"
        "/notify quiet <off|HH-HH>\n"
        "/notify quiet <topic> <off|HH-HH>\n"
        "/notify quarantine list\n"
        "/notify quarantine media-bypass-status\n"
        "/notify quarantine clear <telegram_user_id>\n"
        "/notify quarantine media-bypass-once CONFIRM\n"
        "/notify quarantine clear-all CONFIRM\n"
        "/notify delivery list [limit]\n"
        "/notify delivery retry <telegram_user_id|all> [limit]\n"
        "/notify media-first-seen stats [limit]\n"
        "/notify media-first-seen clear <title words>\n"
        "/notify media-first-seen clear all CONFIRM\n"
        f"Available topics: {topics}"
    )


def parse_topics_arg(raw: str) -> set[str] | None:
    requested = {normalize_text(item) for item in raw.split(",") if normalize_text(item)}
    if not requested:
        return set()
    invalid = [topic for topic in requested if topic not in NOTIFICATION_TOPIC_LABELS and topic not in {"all", "none"}]
    if invalid:
        return None
    if "all" in requested:
        return set(NOTIFICATION_TOPIC_LABELS.keys())
    if "none" in requested:
        return set()
    return requested


def parse_quiet_hours_spec(raw: str) -> tuple[int, int] | None:
    value = str(raw or "").strip().lower()
    if not value:
        return None
    match = re.fullmatch(r"([01]?\d|2[0-3])\s*[-:]\s*([01]?\d|2[0-3])", value)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    if start == end:
        return None
    return start, end


def quiet_hours_label(record: dict[str, Any]) -> str:
    if not bool(record.get("quiet_hours_enabled", False)):
        return "off"
    try:
        start = int(record.get("quiet_hours_start_hour", 22))
        end = int(record.get("quiet_hours_end_hour", 7))
    except (TypeError, ValueError):
        return "off"
    if start < 0 or start > 23 or end < 0 or end > 23 or start == end:
        return "off"
    return f"on ({start:02d}-{end:02d} UTC)"


def quiet_hours_topics_label(record: dict[str, Any]) -> str:
    raw = record.get("quiet_hours_topics") if isinstance(record, dict) else {}
    topics = raw if isinstance(raw, dict) else {}
    labels: list[str] = []
    for topic, item in sorted(topics.items()):
        key = normalize_text(topic)
        if key not in NOTIFICATION_TOPIC_LABELS:
            continue
        if not isinstance(item, dict):
            continue
        enabled = bool(item.get("enabled", False))
        if not enabled:
            continue
        try:
            start = int(item.get("start_hour", 22))
            end = int(item.get("end_hour", 7))
        except (TypeError, ValueError):
            continue
        if start < 0 or start > 23 or end < 0 or end > 23 or start == end:
            continue
        labels.append(f"{key}={start:02d}-{end:02d} UTC")
    if not labels:
        return "(none)"
    return ", ".join(labels)


def format_age_from_unix_ts(ts_value: int, now_ts: int | None = None) -> str:
    now = int(now_ts or time.time())
    if ts_value <= 0:
        return "unknown"
    delta = max(0, now - int(ts_value))
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    return f"{delta // 3600}h"


def build_notify_self_snapshot(record: dict[str, Any], user_id: int) -> dict[str, Any]:
    now_ts = int(time.time())
    role = str(record.get("role", "user")).strip().lower() or "user"
    status = str(record.get("status", "active")).strip().lower() or "active"
    selected_topics = normalize_notify_topics(record.get("notify_topics"))
    quiet = quiet_hours_label(record)
    quiet_topics = quiet_hours_topics_label(record)

    delivery_state = load_delivery_state()
    users_raw = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
    users = users_raw if isinstance(users_raw, dict) else {}
    item_raw = users.get(str(user_id))
    item = item_raw if isinstance(item_raw, dict) else {}

    try:
        last_sent_at = int(item.get("notify_delivery_last_sent_at", 0) or 0)
    except (TypeError, ValueError):
        last_sent_at = 0
    try:
        last_failed_at = int(item.get("notify_delivery_last_failed_at", 0) or 0)
    except (TypeError, ValueError):
        last_failed_at = 0
    try:
        quarantine_until = int(item.get("notify_quarantine_until", 0) or 0)
    except (TypeError, ValueError):
        quarantine_until = 0
    fail_streak = int(item.get("notify_delivery_fail_streak", 0) or 0)
    last_reason = str(item.get("notify_delivery_last_reason", "")).strip() or "(none)"

    quarantine_remaining = max(0, quarantine_until - now_ts)
    quarantined = quarantine_remaining > 0

    stats = load_notify_stats_state()
    events_raw = stats.get("events", []) if isinstance(stats, dict) else []
    events = events_raw if isinstance(events_raw, list) else []
    last_event: dict[str, Any] | None = None
    for event in reversed(events):
        if isinstance(event, dict):
            last_event = event
            break

    if status != "active":
        eligibility = f"blocked(account_status={status})"
    elif not NOTIFY_POLICY_ENABLED:
        eligibility = "blocked(global_notifications_disabled)"
    elif not selected_topics:
        eligibility = "blocked(no_topics_selected)"
    elif quarantined:
        eligibility = f"degraded(quarantined {quarantine_remaining}s)"
    else:
        eligibility = "ok"

    return {
        "timestamp": now_ts,
        "user_id": user_id,
        "role": role,
        "account_status": status,
        "eligibility": eligibility,
        "selected_topics": sorted(selected_topics),
        "quiet_hours": quiet,
        "quiet_by_topic": quiet_topics,
        "quarantine_remaining_seconds": quarantine_remaining,
        "last_delivery_sent_age": format_age_from_unix_ts(last_sent_at, now_ts=now_ts) if last_sent_at > 0 else "none",
        "last_delivery_failed_age": format_age_from_unix_ts(last_failed_at, now_ts=now_ts) if last_failed_at > 0 else "none",
        "delivery_fail_streak": fail_streak,
        "last_delivery_reason": last_reason,
        "last_global_event_topic": str(last_event.get("topic", "unknown") or "unknown") if isinstance(last_event, dict) else "unknown",
        "last_global_event_result": str(last_event.get("result", "unknown") or "unknown") if isinstance(last_event, dict) else "unknown",
        "next": "/notify list (admins) or ask an admin to adjust topics/quarantine",
    }


def build_notify_self_report(record: dict[str, Any], user_id: int) -> str:
    snapshot = build_notify_self_snapshot(record=record, user_id=user_id)
    selected = ", ".join(snapshot.get("selected_topics", [])) if snapshot.get("selected_topics") else "none"
    quarantine_remaining = int(snapshot.get("quarantine_remaining_seconds", 0) or 0)
    quarantine_label = "off"
    if quarantine_remaining > 0:
        quarantine_label = f"on ({quarantine_remaining}s remaining)"
    lines = [
        "🔔 Notification status",
        f"• Account: {snapshot.get('account_status', 'unknown')} ({snapshot.get('eligibility', 'unknown')})",
        f"• Role: {snapshot.get('role', 'user')}",
        f"• Topics: {selected}",
        f"• Quiet hours: {snapshot.get('quiet_hours', 'off')}",
        f"• Quiet by topic: {snapshot.get('quiet_by_topic', '(none)')}",
        f"• Quarantine: {quarantine_label}",
        f"• Delivery: sent {snapshot.get('last_delivery_sent_age', 'none')} ago; failed {snapshot.get('last_delivery_failed_age', 'none')} ago; fail streak {int(snapshot.get('delivery_fail_streak', 0) or 0)}",
        f"• Last failure reason: {snapshot.get('last_delivery_reason', '(none)')}",
        f"• Last global event: {snapshot.get('last_global_event_topic', 'unknown')} ({snapshot.get('last_global_event_result', 'unknown')})",
        f"📌 Next step: {snapshot.get('next', '')}",
    ]
    return "\n".join(lines)


def build_notify_self_json_report(record: dict[str, Any], user_id: int) -> str:
    return json.dumps(build_notify_self_snapshot(record=record, user_id=user_id), ensure_ascii=False, sort_keys=True)


def handle_notify_command(chat_id: int, user_id: int, text: str) -> bool:
    parsed = parse_notify_command(text)
    if parsed is None:
        return False

    command, args = parsed
    record = get_user_record(USER_REGISTRY, user_id)
    if not isinstance(record, dict) or str(record.get("status", "")).strip().lower() != "active":
        send_message(chat_id, "⛔ Active account required.")
        return True

    if ensure_notification_settings(record):
        record["updated_at"] = utc_now()
        save_user_registry(USER_REGISTRY)

    current_topics = normalize_notify_topics(record.get("notify_topics"))

    if command == "me":
        mode = normalize_text(args[0]) if args else ""
        if mode in {"", "text"}:
            send_message(chat_id, build_notify_self_report(record=record, user_id=user_id))
            return True
        if mode == "json":
            send_message(chat_id, build_notify_self_report(record=record, user_id=user_id))
            return True
        send_message(chat_id, "Usage: /notify me")
        return True

    if str(record.get("role", "user")) != "admin":
        send_message(chat_id, "⛔ Admin role required. (Tip: use /notify me for your personal delivery status.)")
        return True

    if command in {"help", "?"}:
        send_message(chat_id, format_notify_help())
        return True

    if command == "list":
        selected = ", ".join(sorted(current_topics)) if current_topics else "none"
        emergency = "on" if bool(record.get("emergency_contact", False)) else "off"
        quiet = quiet_hours_label(record)
        quiet_topics = quiet_hours_topics_label(record)
        lines = [
            "Notification settings:",
            f"- selected topics: {selected}",
            f"- emergency contact: {emergency}",
            f"- quiet hours: {quiet}",
            f"- quiet by topic: {quiet_topics}",
            "- available topics:",
        ]
        for topic, label in sorted(NOTIFICATION_TOPIC_LABELS.items()):
            lines.append(f"  - {topic}: {label}")
        send_message(chat_id, "\n".join(lines))
        return True

    if command == "profile":
        selected = ", ".join(sorted(current_topics)) if current_topics else "none"
        emergency = "on" if bool(record.get("emergency_contact", False)) else "off"
        quiet = quiet_hours_label(record)
        quiet_topics = quiet_hours_topics_label(record)
        drop_patterns = ", ".join(NOTIFY_POLICY_DROP_PATTERNS) if NOTIFY_POLICY_DROP_PATTERNS else "(none)"
        dedupe_by_topic = ", ".join(
            f"{topic}={seconds}s" for topic, seconds in sorted(NOTIFY_POLICY_DEDUPE_BY_TOPIC.items())
        ) or "(none)"
        lines = [
            "Notification profile:",
            f"- topics: {selected}",
            f"- emergency contact: {emergency}",
            f"- quiet hours: {quiet}",
            f"- quiet by topic: {quiet_topics}",
            f"- notifications enabled: {'on' if NOTIFY_POLICY_ENABLED else 'off'}",
            f"- critical only mode: {'on' if NOTIFY_POLICY_CRITICAL_ONLY else 'off'}",
            f"- min priority: {NOTIFY_POLICY_MIN_PRIORITY}",
            f"- max message chars: {NOTIFY_POLICY_MAX_MESSAGE_CHARS}",
            f"- dedupe default: {max(1, NOTIFY_POLICY_DEDUPE_WINDOW_SECONDS)}s",
            f"- dedupe by topic: {dedupe_by_topic}",
            f"- drop patterns: {drop_patterns}",
            f"- policy loaded at (UTC): {NOTIFY_POLICY_LOADED_AT}",
        ]
        send_message(chat_id, "\n".join(lines))
        return True

    if command == "test":
        topic = normalize_text(args[0]) if args else "ops"
        if topic not in NOTIFICATION_TOPIC_LABELS:
            send_message(chat_id, "Usage: /notify test <critical|ops|audit|ai|media|maintenance>")
            return True
        if topic == "critical":
            text_out = "\n".join(
                [
                    "🚨 This is a critical test alert.",
                    "If this were real, it would need immediate attention.",
                ]
            )
        elif topic in {"ops", "audit"}:
            text_out = "\n".join(
                [
                    "⚠️ This is an important test alert.",
                    "It represents an issue you should review soon.",
                ]
            )
        else:
            text_out = "ℹ️ This is a routine test update."
        send_message(chat_id, text_out)
        return True

    if command == "stats":
        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key="/notify stats"):
            return True
        send_message(chat_id, build_notify_stats_report())
        return True

    if command == "health":
        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key="/notify stats"):
            return True
        send_message(chat_id, build_notify_health_report())
        return True

    if command == "validate":
        summary = run_notify_validate_probe(request_user_id=user_id)
        send_message(chat_id, format_notify_validate_report(summary))
        return True

    if command in {"set", "add", "remove"}:
        if not args:
            send_message(chat_id, f"Usage: /notify {command} <topic1,topic2>")
            return True
        parsed_topics = parse_topics_arg(args[0])
        if parsed_topics is None:
            send_message(chat_id, "Unknown topic in request. Use /notify list to see available topics.")
            return True

        if command == "set":
            new_topics = set(parsed_topics)
        elif command == "add":
            new_topics = set(current_topics) | set(parsed_topics)
        else:
            new_topics = set(current_topics) - set(parsed_topics)

        record["notify_topics"] = sorted(new_topics)
        record["updated_at"] = utc_now()
        save_user_registry(USER_REGISTRY)
        selected = ", ".join(sorted(new_topics)) if new_topics else "none"
        send_message(chat_id, f"✅ notification topics updated: {selected}")
        return True

    if command == "emergency":
        if not args or args[0].lower() not in {"on", "off"}:
            send_message(chat_id, "Usage: /notify emergency <on|off>")
            return True
        enabled = args[0].lower() == "on"
        record["emergency_contact"] = enabled
        record["updated_at"] = utc_now()
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, f"✅ emergency contact set to {'on' if enabled else 'off'}")
        return True

    if command == "quiet":
        if not args:
            send_message(chat_id, "Usage: /notify quiet <off|HH-HH> | /notify quiet <topic> <off|HH-HH>")
            return True

        if len(args) >= 2:
            topic = normalize_text(args[0])
            if topic not in NOTIFICATION_TOPIC_LABELS:
                send_message(chat_id, "Usage: /notify quiet <topic> <off|HH-HH> (topic=critical|ops|audit|ai|media|maintenance)")
                return True

            value = str(args[1]).strip().lower()
            overrides_raw = record.get("quiet_hours_topics")
            overrides = overrides_raw if isinstance(overrides_raw, dict) else {}

            if value == "off":
                overrides.pop(topic, None)
                if overrides:
                    record["quiet_hours_topics"] = overrides
                else:
                    record.pop("quiet_hours_topics", None)
                record["updated_at"] = utc_now()
                save_user_registry(USER_REGISTRY)
                send_message(chat_id, f"✅ quiet hours disabled for topic {topic}")
                return True

            parsed_window = parse_quiet_hours_spec(value)
            if parsed_window is None:
                send_message(chat_id, "Usage: /notify quiet <topic> <off|HH-HH> (example: /notify quiet media 22-07)")
                return True

            start, end = parsed_window
            overrides[topic] = {
                "enabled": True,
                "start_hour": start,
                "end_hour": end,
            }
            record["quiet_hours_topics"] = overrides
            record["updated_at"] = utc_now()
            save_user_registry(USER_REGISTRY)
            send_message(chat_id, f"✅ quiet hours set for {topic}: {start:02d}-{end:02d} UTC")
            return True

        value = str(args[0]).strip().lower()
        if value == "off":
            record["quiet_hours_enabled"] = False
            record["updated_at"] = utc_now()
            save_user_registry(USER_REGISTRY)
            send_message(chat_id, "✅ quiet hours disabled")
            return True

        parsed_window = parse_quiet_hours_spec(value)
        if parsed_window is None:
            send_message(chat_id, "Usage: /notify quiet <off|HH-HH> (example: /notify quiet 22-07)")
            return True

        start, end = parsed_window
        record["quiet_hours_enabled"] = True
        record["quiet_hours_start_hour"] = start
        record["quiet_hours_end_hour"] = end
        record["updated_at"] = utc_now()
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, f"✅ quiet hours set: {start:02d}-{end:02d} UTC")
        return True

    if command == "delivery":
        action = normalize_text(args[0]) if args else "list"
        if action not in {"list", "show", "retry"}:
            send_message(chat_id, "Usage: /notify delivery list [limit] | /notify delivery retry <telegram_user_id|all> [limit]")
            return True

        if action == "retry":
            if len(args) < 2:
                send_message(chat_id, "Usage: /notify delivery retry <telegram_user_id|all> [limit]")
                return True

            target = normalize_text(args[1])
            limit = 10
            if len(args) >= 3:
                try:
                    limit = int(args[2])
                except ValueError:
                    send_message(chat_id, "Limit must be a number. Example: /notify delivery retry all 12")
                    return True
            limit = max(1, min(50, limit))

            delivery_state = load_delivery_state()
            users_raw = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
            users = users_raw if isinstance(users_raw, dict) else {}
            now_ts = int(time.time())

            candidates: list[tuple[int, dict[str, Any]]] = []
            if target == "all":
                for user_id_raw, item in users.items():
                    if not isinstance(item, dict):
                        continue
                    try:
                        user_id_int = int(user_id_raw)
                    except (TypeError, ValueError):
                        continue
                    candidates.append((user_id_int, item))
            else:
                try:
                    target_id = int(args[1])
                except ValueError:
                    send_message(chat_id, "Invalid telegram user id. Use /notify delivery retry <telegram_user_id|all> [limit]")
                    return True
                item = users.get(str(target_id))
                if not isinstance(item, dict):
                    send_message(chat_id, f"No delivery-state record found for user {target_id}.")
                    return True
                candidates = [(target_id, item)]

            attempted = 0
            sent_ok = 0
            failed_retry = 0
            skipped_nonretryable = 0
            skipped_missing = 0

            sorted_candidates = sorted(candidates, key=lambda row: row[0])
            for user_id_int, item in sorted_candidates:
                if attempted >= limit:
                    break
                reason = str(item.get("notify_delivery_last_reason", "")).strip()
                streak = int(item.get("notify_delivery_fail_streak", 0) or 0)
                try:
                    failed_at = int(item.get("notify_delivery_last_failed_at", 0) or 0)
                except (TypeError, ValueError):
                    failed_at = 0
                if not reason and streak <= 0 and failed_at <= 0:
                    skipped_missing += 1
                    continue
                if not is_retryable_delivery_reason(reason):
                    skipped_nonretryable += 1
                    continue

                attempted += 1
                ok = send_message(
                    user_id_int,
                    "🔁 Delivery retry probe: this confirms Telegram delivery path health for your account.",
                )
                if ok:
                    item["notify_delivery_fail_streak"] = 0
                    item["notify_delivery_last_reason"] = ""
                    item["notify_delivery_last_failed_at"] = 0
                    item["notify_quarantine_until"] = 0
                    item["notify_quarantine_reason"] = ""
                    item["notify_delivery_last_sent_at"] = now_ts
                    item["updated_at"] = utc_now()
                    users[str(user_id_int)] = item
                    sent_ok += 1
                    continue

                item["notify_delivery_fail_streak"] = int(item.get("notify_delivery_fail_streak", 0) or 0) + 1
                item["notify_delivery_last_reason"] = reason or "retry_send_failed"
                item["notify_delivery_last_failed_at"] = now_ts
                item["updated_at"] = utc_now()
                users[str(user_id_int)] = item
                failed_retry += 1

            delivery_state["users"] = users
            delivery_state["updated_at"] = utc_now()
            if not save_delivery_state(delivery_state):
                send_message(chat_id, "Could not update delivery state. Check ntfy-state volume permissions.")
                return True

            send_message(
                chat_id,
                "Delivery retry result:\n"
                f"- target: {args[1]}\n"
                f"- attempted: {attempted}\n"
                f"- sent_ok: {sent_ok}\n"
                f"- failed_retry: {failed_retry}\n"
                f"- skipped_nonretryable: {skipped_nonretryable}\n"
                f"- skipped_no_failure_state: {skipped_missing}",
            )
            return True

        limit = 10
        if len(args) >= 2:
            try:
                limit = int(args[1])
            except ValueError:
                send_message(chat_id, "Limit must be a number. Example: /notify delivery list 12")
                return True
        limit = max(1, min(50, limit))

        delivery_state = load_delivery_state()
        users_raw = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
        users = users_raw if isinstance(users_raw, dict) else {}
        now_ts = int(time.time())
        rows: list[tuple[int, int, dict[str, Any]]] = []
        for user_id_raw, item in users.items():
            if not isinstance(item, dict):
                continue
            try:
                user_id_int = int(user_id_raw)
            except (TypeError, ValueError):
                continue
            try:
                last_failed_at = int(item.get("notify_delivery_last_failed_at", 0) or 0)
            except (TypeError, ValueError):
                last_failed_at = 0
            last_reason = str(item.get("notify_delivery_last_reason", "")).strip()
            fail_streak = int(item.get("notify_delivery_fail_streak", 0) or 0)
            if not last_reason and fail_streak <= 0 and last_failed_at <= 0:
                continue
            rows.append((last_failed_at, user_id_int, item))

        if not rows:
            send_message(chat_id, "Delivery inbox: no recent recipient failures recorded.")
            return True

        rows.sort(key=lambda row: row[0], reverse=True)
        lines = [
            "Delivery inbox:",
            f"- entries: {len(rows)}",
        ]
        for last_failed_at, user_id_int, item in rows[:limit]:
            reason = str(item.get("notify_delivery_last_reason", "")).strip() or "(none)"
            streak = int(item.get("notify_delivery_fail_streak", 0) or 0)
            until_ts = int(item.get("notify_quarantine_until", 0) or 0)
            quarantine_remaining = max(0, until_ts - now_ts)
            age = format_age_from_unix_ts(last_failed_at, now_ts=now_ts)
            lines.append(
                f"- user={user_id_int} reason={reason} streak={streak} failed_age={age} quarantine_remaining={quarantine_remaining}s"
            )
        if len(rows) > limit:
            lines.append(f"- ...and {len(rows) - limit} more")
        send_message(chat_id, "\n".join(lines))
        return True

    if command in {"media-first-seen", "media_first_seen", "mediafirstseen"}:
        action = normalize_text(args[0]) if args else "stats"
        if action not in {"stats", "list", "show", "clear", "remove", "reset"}:
            send_message(chat_id, "Usage: /notify media-first-seen stats [limit] | /notify media-first-seen clear <title|all CONFIRM>")
            return True

        if action in {"clear", "remove", "reset"}:
            if len(args) < 2:
                send_message(chat_id, "Usage: /notify media-first-seen clear <title words> | /notify media-first-seen clear all CONFIRM")
                return True

            target_raw = " ".join(args[1:]).strip()
            target_lower = target_raw.lower()
            clear_all = target_lower.startswith("all")
            if clear_all:
                if len(args) < 3 or str(args[2]).strip() != "CONFIRM":
                    send_message(chat_id, "Usage: /notify media-first-seen clear all CONFIRM")
                    return True
            else:
                target_norm = normalize_media_first_seen_lookup_text(target_raw)
                if len(target_norm) < 3:
                    send_message(chat_id, "Please provide a longer media title. Example: /notify media-first-seen clear interstellar 2014")
                    return True

            removed, total = clear_media_first_seen_entries(clear_all=clear_all, title_query=target_raw)
            if removed <= 0:
                send_message(chat_id, "No matching media-first-seen entries found.")
                return True

            target_note = "all entries" if clear_all else f"title match: {target_raw}"
            send_message(chat_id, f"✅ Cleared {removed} media first-seen entr{'y' if removed == 1 else 'ies'} ({target_note}). Remaining: {max(0, total - removed)}")
            return True

        limit = 10
        if len(args) >= 2:
            try:
                limit = int(args[1])
            except ValueError:
                send_message(chat_id, "Limit must be a number. Example: /notify media-first-seen stats 20")
                return True
        limit = max(1, min(50, limit))

        send_message(chat_id, build_media_first_seen_report(limit=limit))
        return True

    if command == "quarantine":
        action = normalize_text(args[0]) if args else "list"
        delivery_state = load_delivery_state()
        users_raw = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
        users = users_raw if isinstance(users_raw, dict) else {}
        now_ts = int(time.time())

        if action in {"media-bypass-status", "mediabypassstatus", "media-bypass-state", "mediabypassstate"}:
            marker_raw = delivery_state.get("media_quarantine_bypass_once") if isinstance(delivery_state, dict) else None
            marker = marker_raw if isinstance(marker_raw, dict) else {}

            enabled = bool(marker.get("enabled", False))
            try:
                armed_at = int(marker.get("armed_at", 0) or 0)
            except (TypeError, ValueError):
                armed_at = 0
            try:
                armed_by = int(marker.get("armed_by", 0) or 0)
            except (TypeError, ValueError):
                armed_by = 0
            try:
                expires_at = int(marker.get("expires_at", 0) or 0)
            except (TypeError, ValueError):
                expires_at = 0
            try:
                consumed_at = int(marker.get("consumed_at", 0) or 0)
            except (TypeError, ValueError):
                consumed_at = 0
            consume_reason = str(marker.get("consume_reason", "")).strip() or "(none)"

            remaining = max(0, expires_at - now_ts) if expires_at > 0 else 0
            armed_age = format_age_from_unix_ts(armed_at, now_ts=now_ts) if armed_at > 0 else "never"
            consumed_age = format_age_from_unix_ts(consumed_at, now_ts=now_ts) if consumed_at > 0 else "never"

            lines = [
                "Media quarantine bypass status (one-time):",
                f"- enabled: {'yes' if enabled else 'no'}",
                f"- armed_by: {armed_by or 0}",
                f"- armed_age: {armed_age}",
                f"- expires_in: {remaining}s",
                f"- consumed_age: {consumed_age}",
                f"- consume_reason: {consume_reason}",
            ]
            send_message(chat_id, "\n".join(lines))
            return True

        if action in {"list", "show"}:
            active: list[tuple[int, int, str, int, int]] = []
            for user_id_raw, item in users.items():
                if not isinstance(item, dict):
                    continue
                try:
                    user_id_int = int(user_id_raw)
                except (TypeError, ValueError):
                    continue
                try:
                    until_ts = int(item.get("notify_quarantine_until", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if until_ts <= now_ts:
                    continue
                reason = str(item.get("notify_quarantine_reason", "")).strip() or "(unknown)"
                streak = int(item.get("notify_delivery_fail_streak", 0) or 0)
                count = int(item.get("notify_quarantine_count", 0) or 0)
                active.append((user_id_int, until_ts, reason, streak, count))

            if not active:
                send_message(chat_id, "Quarantine status: no active quarantined recipients.")
                return True

            active.sort(key=lambda row: row[1], reverse=True)
            lines = [
                "Quarantine status:",
                f"- active_quarantined: {len(active)}",
            ]
            for user_id_int, until_ts, reason, streak, count in active[:25]:
                remaining = max(0, until_ts - now_ts)
                lines.append(
                    f"- user={user_id_int} remaining={remaining}s streak={streak} count={count} reason={reason}"
                )
            if len(active) > 25:
                lines.append(f"- ...and {len(active) - 25} more")
            send_message(chat_id, "\n".join(lines))
            return True

        if action == "clear":
            if len(args) < 2:
                send_message(chat_id, "Usage: /notify quarantine clear <telegram_user_id>")
                return True
            try:
                target_id = int(args[1])
            except ValueError:
                send_message(chat_id, "Invalid telegram user id.")
                return True

            target = users.get(str(target_id))
            if not isinstance(target, dict):
                send_message(chat_id, f"No delivery-state record found for user {target_id}.")
                return True

            target["notify_quarantine_until"] = 0
            target["notify_quarantine_reason"] = ""
            target["notify_delivery_fail_streak"] = 0
            target["updated_at"] = utc_now()
            users[str(target_id)] = target
            delivery_state["users"] = users
            delivery_state["updated_at"] = utc_now()
            if not save_delivery_state(delivery_state):
                send_message(chat_id, "Could not update delivery state. Check ntfy-state volume permissions.")
                return True
            send_message(chat_id, f"✅ Cleared quarantine for user {target_id}.")
            return True

        if action in {"media-bypass-once", "mediabypassonce", "media-bypass", "mediabypass"}:
            if len(args) < 2 or str(args[1]).strip() != "CONFIRM":
                send_message(chat_id, "Usage: /notify quarantine media-bypass-once CONFIRM")
                return True

            now_ts = int(time.time())
            ttl_seconds = max(60, int(MEDIA_QUARANTINE_BYPASS_TTL_SECONDS or 1800))
            delivery_state["media_quarantine_bypass_once"] = {
                "enabled": True,
                "armed_at": now_ts,
                "armed_by": int(user_id),
                "expires_at": now_ts + ttl_seconds,
                "consumed_at": 0,
            }
            delivery_state["updated_at"] = utc_now()
            if not save_delivery_state(delivery_state):
                send_message(chat_id, "Could not update delivery state. Check ntfy-state volume permissions.")
                return True
            send_message(
                chat_id,
                f"✅ Armed one-time media quarantine bypass (ttl={ttl_seconds}s). Next media alert fanout will include quarantined recipients once.",
            )
            return True

        if action in {"clear-all", "clearall"}:
            if user_id not in QUARANTINE_CLEAR_ALL_ADMINS:
                send_message(chat_id, "⛔ /notify quarantine clear-all is restricted to designated security admins.")
                return True

            if len(args) < 2 or str(args[1]).strip() != "CONFIRM":
                send_message(chat_id, "Usage: /notify quarantine clear-all CONFIRM")
                return True

            cleared = 0
            for user_id_raw, item in users.items():
                if not isinstance(item, dict):
                    continue
                try:
                    until_ts = int(item.get("notify_quarantine_until", 0) or 0)
                except (TypeError, ValueError):
                    until_ts = 0
                if until_ts <= now_ts:
                    continue

                item["notify_quarantine_until"] = 0
                item["notify_quarantine_reason"] = ""
                item["notify_delivery_fail_streak"] = 0
                item["updated_at"] = utc_now()
                users[user_id_raw] = item
                cleared += 1

            delivery_state["users"] = users
            delivery_state["updated_at"] = utc_now()
            if not save_delivery_state(delivery_state):
                send_message(chat_id, "Could not update delivery state. Check ntfy-state volume permissions.")
                return True

            send_message(chat_id, f"✅ Cleared quarantine for {cleared} user(s).")
            return True

        send_message(
            chat_id,
            "Usage: /notify quarantine list | /notify quarantine media-bypass-status | /notify quarantine clear <telegram_user_id> | /notify quarantine media-bypass-once CONFIRM | /notify quarantine clear-all CONFIRM",
        )
        return True

    send_message(chat_id, "Unknown /notify command. Use /notify help")
    return True


def handle_digest_command(chat_id: int, user_id: int, text: str) -> bool:
    token = command_token(text)
    if token not in {"/digest", "digest"}:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or record.get("role") != "admin" or record.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    args = parse_simple_command(text, token_name="/digest") or [] if token == "/digest" else []
    if not args or args[0].lower() in {"help", "?"}:
        send_message(chat_id, "Digest commands:\n/digest now\n/digest stats")
        return True

    if args[0].lower() == "now":
        result = flush_deferred_digests_now()
        send_message(
            chat_id,
            "Digest flush result:\n"
            f"- attempted: {int(result.get('attempted', 0))}\n"
            f"- sent: {int(result.get('sent', 0))}\n"
            f"- failed: {int(result.get('failed', 0))}\n"
            f"- remaining: {int(result.get('remaining', 0))}",
        )
        return True

    if args[0].lower() == "stats":
        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key="/digest stats"):
            return True
        send_message(chat_id, build_digest_stats_report())
        return True

    send_message(chat_id, "Usage: /digest now|stats")
    return True


def handle_incident_command(chat_id: int, user_id: int, text: str) -> bool:
    parsed = parse_incident_command(text)
    if parsed is None:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or record.get("role") != "admin" or record.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    command, args = parsed
    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Incident commands:\n"
            "/incident list\n"
            "/incident show <incident_id>\n"
            "/ack <incident_id>\n"
            "/snooze <incident_id> <minutes>\n"
            "/unsnooze <incident_id>",
        )
        return True

    state = load_incident_state()
    incidents = state.get("incidents")
    if not isinstance(incidents, dict):
        incidents = {}

    now_ts = int(time.time())

    if command == "list":
        rows: list[tuple[int, str, dict[str, Any]]] = []
        for incident_id, incident in incidents.items():
            if not isinstance(incident, dict):
                continue
            try:
                last_seen = int(incident.get("last_seen", 0) or 0)
            except (TypeError, ValueError):
                last_seen = 0
            rows.append((last_seen, str(incident_id), incident))

        if not rows:
            send_message(chat_id, "No incidents recorded yet.")
            return True

        rows.sort(key=lambda row: row[0], reverse=True)
        limit = max(1, INCIDENT_LIST_LIMIT)
        lines = ["Recent incidents:"]
        for _, incident_id, incident in rows[:limit]:
            status = incident_status(incident, now_ts=now_ts)
            topic = str(incident.get("topic", "-"))
            summary = incident_brief(incident, max_chars=72)
            lines.append(f"- {incident_id}: {status}, topic={topic}, {summary}")
        send_message(chat_id, "\n".join(lines))
        return True

    if command == "show":
        if not args:
            send_message(chat_id, "Usage: /incident show <incident_id>")
            return True
        incident_id = normalize_incident_id(args[0])
        incident = incidents.get(incident_id)
        if not isinstance(incident, dict):
            send_message(chat_id, f"Incident not found: {incident_id}")
            return True

        status = incident_status(incident, now_ts=now_ts)
        lines = [
            "Incident details:",
            f"- id: {incident_id}",
            f"- status: {status}",
            f"- topic: {incident.get('topic', '-')}",
            f"- category: {incident.get('category', '-')}",
            f"- priority: {incident.get('priority', '-')}",
            f"- critical: {incident.get('critical', False)}",
            f"- first_seen: {incident.get('first_seen', '-')}",
            f"- last_seen: {incident.get('last_seen', '-')}",
            f"- acked_at: {incident.get('acked_at', '-')}",
            f"- acked_by: {incident.get('acked_by', '-')}",
            f"- snoozed_until: {incident.get('snoozed_until', '-')}",
            f"- snoozed_by: {incident.get('snoozed_by', '-')}",
            f"- events: {incident.get('event_count', 0)}",
            f"- summary: {incident_brief(incident, max_chars=180)}",
        ]
        send_message(chat_id, "\n".join(lines))
        return True

    send_message(chat_id, "Unknown /incident command. Use /incident help")
    return True


def handle_incident_control_commands(chat_id: int, user_id: int, text: str) -> bool:
    token = command_token(text)
    if token not in {"/ack", "/snooze", "/unsnooze"}:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or record.get("role") != "admin" or record.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    args = parse_simple_command(text, token_name=token) or []
    if token == "/ack":
        if not args:
            send_message(chat_id, "Usage: /ack <incident_id>")
            return True
        incident_id = normalize_incident_id(args[0])
        state = load_incident_state()
        incidents = state.get("incidents")
        if not isinstance(incidents, dict):
            incidents = {}
            state["incidents"] = incidents
        incident = incidents.get(incident_id)
        if not isinstance(incident, dict):
            send_message(chat_id, f"Incident not found: {incident_id}")
            return True

        incident["acked_at"] = int(time.time())
        incident["acked_by"] = user_id
        incident["snoozed_until"] = 0
        incident["snoozed_by"] = 0
        incident["updated_at"] = utc_now()
        state["updated_at"] = utc_now()
        if not save_incident_state(state):
            send_message(chat_id, "Could not update incident state. Check bridge volume permissions.")
            return True
        send_message(chat_id, f"✅ Incident {incident_id} acknowledged for {max(60, INCIDENT_ACK_TTL_SECONDS)}s.")
        return True

    if token == "/snooze":
        if len(args) < 2:
            send_message(chat_id, "Usage: /snooze <incident_id> <minutes>")
            return True
        incident_id = normalize_incident_id(args[0])
        try:
            minutes = int(args[1])
        except ValueError:
            send_message(chat_id, "Minutes must be a number.")
            return True
        minutes = min(1440, max(1, minutes))

        state = load_incident_state()
        incidents = state.get("incidents")
        if not isinstance(incidents, dict):
            incidents = {}
            state["incidents"] = incidents
        incident = incidents.get(incident_id)
        if not isinstance(incident, dict):
            send_message(chat_id, f"Incident not found: {incident_id}")
            return True

        snoozed_until = int(time.time()) + (minutes * 60)
        incident["snoozed_until"] = snoozed_until
        incident["snoozed_by"] = user_id
        incident["updated_at"] = utc_now()
        state["updated_at"] = utc_now()
        if not save_incident_state(state):
            send_message(chat_id, "Could not update incident state. Check bridge volume permissions.")
            return True
        send_message(chat_id, f"✅ Incident {incident_id} snoozed for {minutes} minute(s).")
        return True

    if not args:
        send_message(chat_id, "Usage: /unsnooze <incident_id>")
        return True
    incident_id = normalize_incident_id(args[0])
    state = load_incident_state()
    incidents = state.get("incidents")
    if not isinstance(incidents, dict):
        incidents = {}
        state["incidents"] = incidents
    incident = incidents.get(incident_id)
    if not isinstance(incident, dict):
        send_message(chat_id, f"Incident not found: {incident_id}")
        return True

    incident["snoozed_until"] = 0
    incident["snoozed_by"] = 0
    incident["updated_at"] = utc_now()
    state["updated_at"] = utc_now()
    if not save_incident_state(state):
        send_message(chat_id, "Could not update incident state. Check bridge volume permissions.")
        return True
    send_message(chat_id, f"✅ Incident {incident_id} is no longer snoozed.")
    return True


def handle_reqtrack_command(chat_id: int, user_id: int, text: str) -> bool:
    parsed = parse_reqtrack_command(text)
    if parsed is None:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or record.get("role") != "admin" or record.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    command, args = parsed
    actor_username = normalize_text(record.get("telegram_username", ""))
    actor = f"tg:{user_id}:{actor_username}" if actor_username else f"tg:{user_id}"

    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Reqtrack commands:\n"
            "/reqtrack list [active|resolved|all]\n"
            "/reqtrack kpi [hours] [json|pretty]\n"
            "/reqtrack kpiweekly [json|pretty]\n"
            "/reqtrack ack <incident_key> [note]\n"
            "/reqtrack snooze <incident_key> [minutes] [note]\n"
            "/reqtrack unsnooze <incident_key> [note]\n"
            "/reqtrack close <incident_key> [note]\n"
            "/reqtrack state",
        )
        return True

    if command == "state":
        send_message(
            chat_id,
            (
                f"Reqtrack state path: {REQTRACK_STATE_PATH}\n"
                f"exists: {'yes' if REQTRACK_STATE_PATH.exists() else 'no'}"
            ),
        )
        return True

    if command == "list":
        status_filter = "active"
        if args:
            candidate = str(args[0]).strip().lower()
            if candidate not in {"active", "resolved", "all"}:
                send_message(chat_id, "Usage: /reqtrack list [active|resolved|all]")
                return True
            status_filter = candidate

        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key=f"/reqtrack list {status_filter}"):
            return True

        state = load_reqtrack_state()
        rows = list_reqtrack_incidents(state=state, status_filter=status_filter)
        if not rows:
            send_message(chat_id, f"No reqtrack incidents matched filter={status_filter}.")
            return True

        lines = [f"Reqtrack incidents (filter={status_filter}):"]
        now_ts = int(time.time())
        for item in rows[: max(1, REQTRACK_INCIDENT_LIST_LIMIT)]:
            flags: list[str] = []
            if bool(item.get("acked")):
                flags.append("acked")
            if int(item.get("snoozed_until") or 0) > now_ts:
                flags.append("snoozed")
            flag_str = f" [{' '.join(flags)}]" if flags else ""
            summary = str(item.get("title") or "(no-title)")
            req_id = str(item.get("request_id") or "-")
            media_type = str(item.get("type") or "-")
            lines.append(
                f"- {item.get('key')}: {item.get('status')} lvl={item.get('last_notified_level')} req={req_id} type={media_type}{flag_str} {summary}"
            )
        send_message(chat_id, "\n".join(lines))
        return True

    if command in {"kpi", "kpiweekly"}:
        window_hours = max(1, REQTRACK_DEFAULT_KPI_WINDOW_HOURS)
        output_mode = "pretty"
        if command == "kpiweekly":
            window_hours = max(1, REQTRACK_WEEKLY_KPI_WINDOW_HOURS)
            if args:
                first = str(args[0]).strip().lower()
                if first not in {"json", "pretty"}:
                    send_message(chat_id, "Usage: /reqtrack kpiweekly [json|pretty]")
                    return True
                output_mode = first
        else:
            for token in args:
                value = str(token).strip().lower()
                if not value:
                    continue
                if value in {"json", "pretty"}:
                    output_mode = value
                    continue
                if re.fullmatch(r"\d+", value):
                    window_hours = max(1, int(value))
                    continue
                send_message(chat_id, "Usage: /reqtrack kpi [hours] [json|pretty]")
                return True

        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key=f"/reqtrack {command} {window_hours}"):
            return True

        state = load_reqtrack_state()
        kpi = build_reqtrack_kpi_digest(state=state, now_ts=int(time.time()), window_hours=window_hours)
        if output_mode == "json":
            payload = {
                "state_file": str(REQTRACK_STATE_PATH),
                "kpi": kpi,
            }
            send_reqtrack_json_payload(chat_id, payload)
            return True

        send_message(chat_id, render_reqtrack_kpi_digest_text(kpi=kpi, state_path=REQTRACK_STATE_PATH))
        return True

    if command not in {"ack", "snooze", "unsnooze", "close"}:
        send_message(chat_id, "Unknown /reqtrack command. Use /reqtrack help")
        return True

    if not args:
        send_message(chat_id, f"Usage: /reqtrack {command} <incident_key>{' [minutes] [note]' if command == 'snooze' else ' [note]'}")
        return True

    incident_key = str(args[0]).strip()
    if not incident_key:
        send_message(chat_id, "Incident key is required.")
        return True

    note = ""
    snooze_minutes = max(1, REQTRACK_DEFAULT_SNOOZE_MINUTES)
    if command == "snooze":
        remainder = args[1:]
        if remainder:
            first = str(remainder[0]).strip()
            if re.fullmatch(r"\d+", first):
                snooze_minutes = min(1440, max(1, int(first)))
                remainder = remainder[1:]
        note = " ".join(remainder).strip()
    else:
        note = " ".join(args[1:]).strip()

    state = load_reqtrack_state()
    ok, detail, row = apply_reqtrack_incident_action(
        state=state,
        action=command,
        incident_key=incident_key,
        actor=actor,
        note=note,
        snooze_minutes=snooze_minutes,
    )
    if not ok:
        if detail.startswith("incident_not_found:"):
            send_message(chat_id, f"Reqtrack incident not found: {incident_key}")
            return True
        send_message(chat_id, f"Reqtrack action failed: {detail}")
        return True

    if not save_reqtrack_state(state):
        send_message(chat_id, "Could not update reqtrack state. Check bridge volume permissions.")
        return True

    line = f"✅ Reqtrack {command} applied: {row.get('key')} (status={row.get('status')})"
    if command == "snooze":
        line += f" until={row.get('snoozed_until')}"
    send_message(chat_id, line)
    return True


def cleanup_expired_approvals() -> int:
    now = int(time.time())
    pending = APPROVALS_STATE.get("pending") or {}
    expired_ids = [approval_id for approval_id, item in pending.items() if int(item.get("expires_at", 0)) <= now]
    for approval_id in expired_ids:
        pending.pop(approval_id, None)
    if expired_ids:
        APPROVALS_STATE["pending"] = pending
        save_approvals(APPROVALS_STATE)
    return len(expired_ids)


def list_active_admin_user_ids(exclude_user_id: int = 0) -> list[int]:
    users = USER_REGISTRY.get("users") or {}
    out: list[int] = []
    for user_id_raw, record in users.items():
        if not isinstance(record, dict):
            continue
        if str(record.get("role", "user")) != "admin":
            continue
        if str(record.get("status", "active")) != "active":
            continue
        try:
            admin_user_id = int(user_id_raw)
        except (TypeError, ValueError):
            continue
        if exclude_user_id and admin_user_id == exclude_user_id:
            continue
        out.append(admin_user_id)
    out.sort()
    return out


def find_pending_coding_access_request(user_id: int) -> str:
    pending = APPROVALS_STATE.get("pending") or {}
    for approval_id, item in pending.items():
        payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            continue
        if str(payload.get("approval_type", "")) != "coding_help_access":
            continue
        try:
            target_user_id = int(payload.get("target_user_id", 0) or 0)
        except (TypeError, ValueError):
            target_user_id = 0
        if target_user_id == user_id:
            return str(approval_id)
    return ""


def set_user_coding_help_enabled(user_id: int, enabled: bool) -> bool:
    record = get_user_record(USER_REGISTRY, user_id)
    if not record: return False
    record["coding_help_enabled"] = bool(enabled)
    record["updated_at"] = utc_now()
    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)
    return True


def append_coding_access_audit(
    *,
    action: str,
    approval_id: str,
    actor_user_id: int,
    target_user_id: int,
    status: str,
    note: str = "",
) -> None:
    entry = {
        "ts": utc_now(),
        "timestamp": int(time.time()),
        "action": str(action),
        "approval_id": str(approval_id),
        "actor_user_id": int(actor_user_id),
        "target_user_id": int(target_user_id),
        "status": str(status),
        "note": str(note or ""),
    }
    try:
        CODING_ACCESS_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CODING_ACCESS_AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[telegram-bridge] coding_access_audit_write_failed: {exc}", flush=True)


def get_recent_coding_access_audit(limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if not CODING_ACCESS_AUDIT_PATH.exists():
        return []
    try:
        lines = CODING_ACCESS_AUDIT_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in reversed(lines):
        line = str(raw_line or "").strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
        if len(rows) >= limit:
            break
    return rows


def is_risky_ops_command(text: str) -> bool:
    lowered = text.lower().strip()
    risky_patterns = [
        r"\brestart\b",
        r"\bstop\b",
        r"\bstart\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bdelete\b",
        r"\bremove\b",
        r"\bpurge\b",
        r"\breset\b",
        r"\bupdate\b",
        r"\bupgrade\b",
        r"\brollback\b",
        r"\brestore\b",
        r"\bdeploy\b",
    ]
    return any(re.search(pattern, lowered) for pattern in risky_patterns)


def is_coding_help_request(text: str) -> bool:
    lowered = str(text or "").lower().strip()
    if not lowered:
        return False
    coding_patterns = [
        r"\bcoding\b",
        r"\bprogram(?:ming)?\b",
        r"\bscript\b",
        r"\bpython\b",
        r"\bjavascript\b",
        r"\btypescript\b",
        r"\bbash\b",
        r"\bshell\b",
        r"\bregex\b",
        r"\bsql\b",
        r"\bdebug\b",
        r"\bstack\s*trace\b",
        r"\bexception\b",
        r"\bcompile\b",
        r"\brefactor\b",
        r"\balgorithm\b",
        r"\bfunction\b",
        r"\bclass\b",
        r"\bapi\s+integration\b",
        r"\bwrite\s+code\b",
    ]
    return any(re.search(pattern, lowered) for pattern in coding_patterns)


def create_pending_approval(
    chat_id: int,
    user_id: int,
    command_text: str,
    payload: dict[str, Any],
) -> str | None:
    cleanup_expired_approvals()
    next_id = int(APPROVALS_STATE.get("next_id", 1))
    now = int(time.time())
    pending = APPROVALS_STATE.setdefault("pending", {})
    requester_pending = 0
    for item in pending.values():
        if not isinstance(item, dict):
            continue
        try:
            requester_user_id = int(item.get("requester_user_id", 0) or 0)
            expires_at = int(item.get("expires_at", 0) or 0)
        except (TypeError, ValueError):
            continue
        if requester_user_id == user_id and expires_at > now:
            requester_pending += 1

    if requester_pending >= max(1, APPROVAL_MAX_PENDING_PER_USER):
        return None

    approval_id = str(next_id)
    item = {
        "approval_id": approval_id,
        "chat_id": chat_id,
        "requester_user_id": user_id,
        "command_text": command_text,
        "payload": payload,
        "created_at": now,
        "expires_at": now + APPROVAL_TTL_SECONDS,
    }
    pending[approval_id] = item
    APPROVALS_STATE["next_id"] = next_id + 1
    save_approvals(APPROVALS_STATE)
    return approval_id


def handle_approval_command(chat_id: int, user_id: int, text: str) -> bool:
    if command_token(text) in {"/pending", "pending"}:
        record = get_user_record(USER_REGISTRY, user_id)
        if not record or record.get("role") != "admin" or record.get("status") != "active":
            send_message(chat_id, "⛔ Admin role required.")
            return True

        cleanup_expired_approvals()
        pending = APPROVALS_STATE.get("pending") or {}
        if not pending:
            send_message(chat_id, "No pending approvals.")
            return True

        now = int(time.time())
        lines = ["Pending approvals:"]
        items = sorted(
            pending.values(),
            key=lambda item: int(item.get("created_at", 0)),
        )
        for item in items[:25]:
            approval_id = str(item.get("approval_id", "?"))
            requester_user_id = int(item.get("requester_user_id", 0))
            command_text = str(item.get("command_text", ""))
            expires_at = int(item.get("expires_at", 0))
            remaining = max(0, expires_at - now)
            lines.append(
                f"- id={approval_id} user={requester_user_id} ttl={remaining}s cmd={command_text[:80]}"
            )
        send_message(chat_id, "\n".join(lines))
        return True

    parsed = parse_approval_command(text)
    if parsed is None:
        return False

    record = get_user_record(USER_REGISTRY, user_id)
    if not record or record.get("role") != "admin" or record.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    cleanup_expired_approvals()
    action, approval_id = parsed
    pending = APPROVALS_STATE.get("pending") or {}
    item = pending.get(approval_id)
    if not item:
        send_message(chat_id, f"No pending approval with id={approval_id}.")
        return True

    requester_chat_id = int(item.get("chat_id", chat_id))
    requester_user_id = int(item.get("requester_user_id", 0))
    command_text = str(item.get("command_text", ""))
    payload = item.get("payload") or {}
    approval_type = str(payload.get("approval_type", "ops_command")).strip().lower()

    if action == "deny":
        target_user_id = requester_user_id
        if approval_type == "coding_help_access":
            try:
                target_user_id = int(payload.get("target_user_id", requester_user_id) or requester_user_id)
            except (TypeError, ValueError):
                target_user_id = requester_user_id
        pending.pop(approval_id, None)
        APPROVALS_STATE["pending"] = pending
        save_approvals(APPROVALS_STATE)
        if approval_type == "coding_help_access":
            append_coding_access_audit(
                action="deny",
                approval_id=approval_id,
                actor_user_id=user_id,
                target_user_id=target_user_id,
                status="denied",
            )
        send_message(chat_id, f"❌ Denied approval id={approval_id}")
        if requester_chat_id:
            if approval_type == "coding_help_access":
                send_message(requester_chat_id, f"❌ Coding help access request denied (id={approval_id}).")
            else:
                send_message(requester_chat_id, f"❌ /ops request denied (id={approval_id}).")
        return True

    if approval_type == "coding_help_access":
        target_user_id = requester_user_id
        try:
            target_user_id = int(payload.get("target_user_id", requester_user_id) or requester_user_id)
        except (TypeError, ValueError):
            target_user_id = requester_user_id

        pending.pop(approval_id, None)
        APPROVALS_STATE["pending"] = pending
        save_approvals(APPROVALS_STATE)

        if set_user_coding_help_enabled(target_user_id, True):
            append_coding_access_audit(
                action="approve",
                approval_id=approval_id,
                actor_user_id=user_id,
                target_user_id=target_user_id,
                status="approved",
            )
            send_message(chat_id, f"✅ Approved coding help access id={approval_id} for user={target_user_id}")
            if requester_chat_id:
                send_message(
                    requester_chat_id,
                    (
                        f"✅ Coding help access approved (id={approval_id}).\n"
                        "You can now ask coding questions in /rag mode."
                    ),
                )
        else:
            append_coding_access_audit(
                action="approve",
                approval_id=approval_id,
                actor_user_id=user_id,
                target_user_id=target_user_id,
                status="failed",
                note="target_user_not_found",
            )
            send_message(chat_id, f"⚠️ Approval id={approval_id} applied, but target user {target_user_id} was not found.")
            if requester_chat_id:
                send_message(
                    requester_chat_id,
                    "⚠️ Your coding help access request was approved, but your account record could not be updated. Contact an admin.",
                )
        return True

    try:
        result = call_n8n(OPS_WEBHOOK, payload)
        reply = extract_reply_text(result)
    except urllib.error.HTTPError as exc:
        reply = f"❌ n8n webhook error: HTTP {exc.code}"
    except Exception as exc:
        reply = f"❌ bridge error: {exc}"

    pending.pop(approval_id, None)
    APPROVALS_STATE["pending"] = pending
    save_approvals(APPROVALS_STATE)

    send_message(chat_id, f"✅ Approved id={approval_id} for user={requester_user_id}\nCommand: {command_text}")
    if requester_chat_id:
        send_message(requester_chat_id, f"✅ /ops approved (id={approval_id})\n{reply}")
    return True


def handle_coding_command(chat_id: int, user_id: int, text: str, user_record: dict[str, Any], role: str) -> bool:
    parsed = parse_coding_command(text)
    if parsed is None:
        return False

    command, _args = parsed
    enabled = role == "admin" or bool(user_record.get("coding_help_enabled", False))

    if command in {"help", "?"}:
        send_message(
            chat_id,
            "Coding access commands:\n"
            "/coding status\n"
            "/coding on  (user request -> admin approval)\n"
            "/coding off\n"
            "/coding audit <n>  (admin)",
        )
        return True

    if command == "status":
        send_message(chat_id, f"coding_help_enabled={'yes' if enabled else 'no'}")
        return True

    if command in {"on", "enable", "request"}:
        if role == "admin":
            send_message(chat_id, "✅ Coding help is already enabled for admin accounts.")
            return True

        if enabled:
            send_message(chat_id, "✅ Coding help is already enabled for your account.")
            return True

        cleanup_expired_approvals()
        existing_request_id = find_pending_coding_access_request(user_id)
        if existing_request_id:
            send_message(chat_id, f"⏳ A coding help access request is already pending (id={existing_request_id}).")
            return True

        approval_payload = {
            "approval_type": "coding_help_access",
            "target_user_id": user_id,
            "requested_by": user_id,
        }
        approval_id = create_pending_approval(
            chat_id=chat_id,
            user_id=user_id,
            command_text=f"coding access request user={user_id}",
            payload=approval_payload,
        )
        if not approval_id:
            send_message(
                chat_id,
                (
                    "⛔ Approval queue is full for your account right now. "
                    "Please wait for an admin to approve or deny existing requests, then try again."
                ),
            )
            return True

        admin_ids = list_active_admin_user_ids(exclude_user_id=0)
        requester_name = str(user_record.get("full_name", "") or "").strip() or str(user_id)
        for admin_id in admin_ids:
            send_message(
                admin_id,
                (
                    "🔐 Coding help access request\n"
                    f"- id: {approval_id}\n"
                    f"- requester: {requester_name} (user_id={user_id})\n"
                    f"- action: /approve {approval_id} or /deny {approval_id}"
                ),
            )

        if admin_ids:
            send_message(chat_id, f"⏳ Request submitted (id={approval_id}). Admins have been notified for approval.")
        else:
            send_message(
                chat_id,
                (
                    f"⏳ Request submitted (id={approval_id}), but no active admin accounts were found to notify. "
                    "Ask an admin to run /pending and approve it."
                ),
            )
        return True

    if command in {"off", "disable"}:
        if role == "admin":
            send_message(chat_id, "ℹ️ Coding help remains enabled for admin accounts.")
            return True
        if set_user_coding_help_enabled(user_id, False):
            send_message(chat_id, "✅ Coding help disabled for your account.")
        else:
            send_message(chat_id, "⚠️ Could not update coding help setting for your account.")
        return True

    if command == "audit":
        if role != "admin":
            send_message(chat_id, "⛔ Admin role required.")
            return True
        limit = 10
        if _args:
            try:
                limit = int(_args[0])
            except ValueError:
                send_message(chat_id, "Usage: /coding audit <n>")
                return True
        limit = min(25, max(1, limit))
        rows = get_recent_coding_access_audit(limit)
        if not rows:
            send_message(chat_id, "No coding access audit entries found.")
            return True

        lines = [f"Coding access audit (latest {len(rows)}):"]
        for item in rows:
            ts = str(item.get("ts", "-") or "-")
            approval_id = str(item.get("approval_id", "-") or "-")
            action = str(item.get("action", "-") or "-")
            status = str(item.get("status", "-") or "-")
            actor = str(item.get("actor_user_id", "-") or "-")
            target = str(item.get("target_user_id", "-") or "-")
            note = str(item.get("note", "") or "").strip()
            line = f"- {ts} id={approval_id} action={action} status={status} actor={actor} target={target}"
            if note:
                line += f" note={note}"
            lines.append(line)
        send_message(chat_id, "\n".join(lines))
        return True

    send_message(chat_id, "Unknown /coding command. Use /coding help")
    return True


def handle_user_admin_command(chat_id: int, requester_id: int, text: str) -> bool:
    parsed = parse_user_admin_command(text)
    if parsed is None:
        return False

    requester = get_user_record(USER_REGISTRY, requester_id)
    if not requester or requester.get("role") != "admin" or requester.get("status") != "active":
        send_message(chat_id, "⛔ Admin role required.")
        return True

    command, args = parsed

    if command == "help":
        send_message(
            chat_id,
            "User admin commands:\n"
            "/user add <telegram_user_id> <admin|user>\n"
            "/user role <telegram_user_id> <admin|user>\n"
            "/user disable <telegram_user_id>\n"
            "/user enable <telegram_user_id>\n"
            "/user list\n"
            "/user linked-discord",
        )
        return True

    if command in {"add", "role"}:
        if len(args) < 2:
            send_message(chat_id, "Usage: /user add <telegram_user_id> <admin|user>")
            return True
        try:
            target_id = int(args[0])
        except ValueError:
            send_message(chat_id, "Invalid telegram user id.")
            return True
        role = args[1].lower()
        if role not in {"admin", "user"}:
            send_message(chat_id, "Role must be 'admin' or 'user'.")
            return True
        set_user_record(USER_REGISTRY, target_id, role, status="active")
        updated = get_user_record(USER_REGISTRY, target_id)
        if updated and ensure_notification_settings(updated):
            updated["updated_at"] = utc_now()
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, f"✅ user {target_id} set to role={role}, status=active")
        return True

    if command in {"disable", "enable"}:
        if len(args) < 1:
            send_message(chat_id, f"Usage: /user {command} <telegram_user_id>")
            return True
        try:
            target_id = int(args[0])
        except ValueError:
            send_message(chat_id, "Invalid telegram user id.")
            return True
        existing = get_user_record(USER_REGISTRY, target_id)
        if not existing:
            send_message(chat_id, "User not found in registry.")
            return True
        role = str(existing.get("role", "user"))
        status = "active" if command == "enable" else "disabled"
        set_user_record(USER_REGISTRY, target_id, role, status=status)
        updated = get_user_record(USER_REGISTRY, target_id)
        if updated and ensure_notification_settings(updated):
            updated["updated_at"] = utc_now()
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, f"✅ user {target_id} status={status}")
        return True

    if command == "list":
        users = USER_REGISTRY.get("users", {})
        if not users:
            send_message(chat_id, "No registered users.")
            return True
        lines = ["Registered users:"]
        for user_id, rec in sorted(users.items(), key=lambda item: int(item[0])):
            role = rec.get("role", "user")
            status = rec.get("status", "active")
            full_name = rec.get("full_name", "")
            telegram_username = rec.get("telegram_username", "")
            reg_state = rec.get("registration_state", "active")
            age = get_record_account_age(rec)
            account_class = get_record_account_class(rec)
            class_label = "Child" if account_class == "child" else "Adult"
            lines.append(
                f"- {user_id}: role={role}, status={status}, reg={reg_state}, class={class_label}, age={age if isinstance(age, int) else '-'}, name={full_name or '-'}, user={telegram_username or '-'}"
            )
        send_message(chat_id, "\n".join(lines[:50]))
        return True

    if command in {"linked-discord", "discord-links", "discord"}:
        users = USER_REGISTRY.get("users", {})
        if not users:
            send_message(chat_id, "No registered users.")
            return True

        linked_lines: list[str] = []
        unlinked_lines: list[str] = []

        for user_id, rec in sorted(users.items(), key=lambda item: int(item[0])):
            if not isinstance(rec, dict):
                continue
            discord_id = str(rec.get("linked_discord_user_id", "")).strip()
            discord_name = str(rec.get("linked_discord_name", "")).strip() or "-"
            telegram_username = str(rec.get("telegram_username", "")).strip() or "-"
            role = str(rec.get("role", "user"))
            status = str(rec.get("status", "active"))
            if discord_id:
                linked_lines.append(
                    f"- {user_id}: discord={discord_name} ({discord_id}), tg={telegram_username}, role={role}, status={status}"
                )
            else:
                unlinked_lines.append(
                    f"- {user_id}: tg={telegram_username}, role={role}, status={status}"
                )

        lines = [
            "Discord link report:",
            f"- total_users: {len(users)}",
            f"- linked_users: {len(linked_lines)}",
            f"- unlinked_users: {len(unlinked_lines)}",
        ]

        if linked_lines:
            lines.append("Linked:")
            lines.extend(linked_lines[:30])
        else:
            lines.append("Linked: (none)")

        if unlinked_lines:
            lines.append("Unlinked:")
            lines.extend(unlinked_lines[:30])
        else:
            lines.append("Unlinked: (none)")

        send_message(chat_id, "\n".join(lines))
        return True

    send_message(chat_id, "Unknown /user command. Use /user help")
    return True


def prompt_registration_name(chat_id: int) -> None:
    send_message(chat_id, "Welcome. Please reply with your full name to register your account.")


def prompt_registration_age(chat_id: int) -> None:
    send_message(
        chat_id,
        (
            "Step 2/2: Please reply with your age as a number (for example: 15 or 32).\n"
            f"Accounts under {CHILD_ACCOUNT_ADULT_MIN_AGE} are classified as Child and use stricter content guardrails."
        ),
    )


def complete_registration_age_step(chat_id: int, user_id: int, record: dict[str, Any]) -> None:
    account_class = get_record_account_class(record)
    age = get_record_account_age(record)
    role = str(record.get("role", "user"))
    class_label = "Child" if account_class == "child" else "Adult"
    age_label = str(age) if isinstance(age, int) else "(unknown)"
    if role == "admin":
        send_message(
            chat_id,
            (
                f"✅ Admin verification complete. Your account role is admin.\n"
                f"Classification: {class_label} (age={age_label}).\n"
                "Use /notify list to review and customize your notification feed."
            ),
        )
    else:
        send_message(
            chat_id,
            (
                "✅ Registration complete. Your account role is user.\n"
                f"Classification: {class_label} (age={age_label})."
            ),
        )
    send_message(chat_id, "Optional: link your Discord profile with /discord link")


def complete_standard_registration(chat_id: int, user_id: int, full_name: str, username: str) -> None:
    set_user_record(USER_REGISTRY, user_id, "user", status="pending_registration")
    record = get_user_record(USER_REGISTRY, user_id) or {}
    record["full_name"] = full_name
    record["telegram_username"] = normalize_text(username)
    record["registration_state"] = "pending_age"
    ensure_notification_settings(record)
    record["updated_at"] = utc_now()
    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)
    prompt_registration_age(chat_id)


def begin_james_admin_challenge(chat_id: int, user_id: int, full_name: str, username: str) -> None:
    set_user_record(USER_REGISTRY, user_id, "user", status="pending_admin_verification")
    record = get_user_record(USER_REGISTRY, user_id) or {}
    profile = expected_admin_profile()
    record["full_name"] = full_name
    record["telegram_username"] = normalize_text(username)
    record["registration_state"] = "pending_admin_q1"
    record["challenge_expected_last_name"] = profile["last_name"]
    record["challenge_expected_username"] = profile["username"]
    ensure_notification_settings(record)
    record["updated_at"] = utc_now()
    USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
    save_user_registry(USER_REGISTRY)
    send_message(chat_id, "Admin verification required. Challenge 1/2: What is your last name?")


def process_registration_flow(
    chat_id: int,
    user_id: int,
    text: str,
    username: str,
    first_name: str,
    last_name: str,
    existing: dict[str, Any] | None,
) -> bool:
    record = existing
    if not record:
        set_user_record(USER_REGISTRY, user_id, "user", status="pending_registration")
        record = get_user_record(USER_REGISTRY, user_id) or {}
        record["registration_state"] = "pending_name"
        record["telegram_username"] = normalize_text(username)
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        prompt_registration_name(chat_id)
        return True

    reg_state = str(record.get("registration_state", ""))
    if reg_state == "pending_name" or not record.get("full_name"):
        if text.strip().startswith("/"):
            prompt_registration_name(chat_id)
            return True
        full_name = text.strip()
        if not full_name:
            prompt_registration_name(chat_id)
            return True

        profile = expected_admin_profile()
        first_from_input = normalize_text(full_name.split(" ")[0] if full_name else "")
        sender_first = normalize_text(first_name)
        sender_last = normalize_text(last_name)
        sender_user = normalize_text(username)

        is_james_candidate = (
            first_from_input == profile["first_name"]
            or sender_first == profile["first_name"]
        )

        if is_james_candidate:
            begin_james_admin_challenge(chat_id, user_id, full_name, username)
            return True

        complete_standard_registration(chat_id, user_id, full_name, username)
        return True

    if reg_state == "pending_admin_q1":
        if text.strip().startswith("/"):
            send_message(chat_id, "Challenge 1/2: What is your last name?")
            return True
        expected_last = normalize_text(record.get("challenge_expected_last_name", "hunsaker"))
        if normalize_text(text) != expected_last:
            send_message(chat_id, "Challenge 1 incorrect. Try again: What is your last name?")
            return True
        record["registration_state"] = "pending_admin_q2"
        record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        send_message(chat_id, "Challenge 2/2: What is your username?")
        return True

    if reg_state == "pending_admin_q2":
        if text.strip().startswith("/"):
            send_message(chat_id, "Challenge 2/2: What is your username?")
            return True
        expected_user = normalize_text(record.get("challenge_expected_username", "<your_admin_username>"))
        if normalize_text(text) != expected_user:
            send_message(chat_id, "Challenge 2 incorrect. Try again: What is your username?")
            return True
        set_user_record(USER_REGISTRY, user_id, "admin", status="pending_registration")
        upgraded = get_user_record(USER_REGISTRY, user_id) or {}
        upgraded["full_name"] = record.get("full_name", "")
        upgraded["telegram_username"] = normalize_text(username) or normalize_text(record.get("telegram_username", ""))
        upgraded["registration_state"] = "pending_age"
        ensure_notification_settings(upgraded)
        upgraded["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = upgraded
        save_user_registry(USER_REGISTRY)
        prompt_registration_age(chat_id)
        return True

    if reg_state == "pending_age":
        if text.strip().startswith("/"):
            prompt_registration_age(chat_id)
            return True
        age = parse_account_age(text)
        if age is None:
            send_message(chat_id, "Please reply with a valid age number between 1 and 120.")
            return True
        record["age"] = int(age)
        record["account_class"] = classify_account_by_age(age)
        record["registration_state"] = "active"
        record["status"] = "active"
        ensure_notification_settings(record)
        record["updated_at"] = utc_now()
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        save_user_registry(USER_REGISTRY)
        complete_registration_age_step(chat_id, user_id, record)
        return True

    return False


def build_payload(
    chat_id: int,
    user_id: int,
    role: str,
    full_name: str,
    telegram_username: str,
    text: str,
    image_url: str | None,
    audio_info: dict[str, Any],
    memory_enabled: bool,
    memory_summary: str,
    memory_provenance: list[dict[str, Any]],
    workspace_context: dict[str, Any],
    tone_history: list[str],
    persona_pref_tone: str,
    persona_pref_brevity: str,
    user_profile_seed: str,
    user_profile_image_url: str,
    account_age: int | None = None,
    account_class: str = "",
    child_guardrails_enabled: bool = False,
) -> dict[str, Any]:
    tenant_id = f"u_{user_id}"
    voice_memory_opt_in = bool(memory_enabled) if POLICY_MEMORY_VOICE_OPT_IN_REQUIRED else True
    role_key = str(role or "user").strip().lower() or "user"
    role_allowlist = sorted(list(ROLE_COMMAND_ALLOWLIST.get(role_key, set())))
    policy_rate_limit_rpm = POLICY_TELEGRAM_SETTINGS.get("rate_limit_requests_per_minute")
    policy_rate_limit_burst = POLICY_TELEGRAM_SETTINGS.get("rate_limit_burst")
    payload = {
        "source": "telegram",
        "chat_id": chat_id,
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "full_name": full_name,
        "telegram_username": telegram_username,
        "message": text,
        "image_url": image_url,
        "has_image": bool(image_url),
        "audio_url": audio_info.get("audio_url"),
        "audio_kind": audio_info.get("audio_kind"),
        "audio_mime": audio_info.get("audio_mime"),
        "audio_duration": audio_info.get("audio_duration"),
        "audio_file_id": audio_info.get("audio_file_id"),
        "audio_file_name": audio_info.get("audio_file_name"),
        "has_audio": bool(audio_info.get("audio_url")),
        "memory_enabled": bool(memory_enabled),
        "memory_summary": memory_summary,
        "memory_provenance": memory_provenance,
        "voice_memory_opt_in": voice_memory_opt_in,
        "memory_write_mode": POLICY_MEMORY_WRITE_MODE,
        "raw_audio_persist": POLICY_RETENTION_RAW_AUDIO_PERSIST,
        "memory_low_confidence_policy": POLICY_MEMORY_LOW_CONFIDENCE_WRITE_POLICY,
        "memory_min_speaker_confidence": MEMORY_MIN_CONFIDENCE,
        "memory_write_allowed": True,
        "workspace_mode": str(workspace_context.get("workspace_mode", "auto")),
        "workspace_active": bool(workspace_context.get("workspace_active", False)),
        "workspace_id": str(workspace_context.get("workspace_id", "")),
        "workspace_expires_at": int(workspace_context.get("workspace_expires_at", 0) or 0),
        "workspace_doc_ids": workspace_context.get("workspace_doc_ids") if isinstance(workspace_context.get("workspace_doc_ids"), list) else [],
        "workspace_context_only": bool(workspace_context.get("workspace_context_only", False)),
        "memory_context_only": bool(workspace_context.get("memory_context_only", False)),
        "memory_enabled_effective": bool(workspace_context.get("memory_enabled_effective", bool(memory_enabled))),
        "memory_summary_effective": str(workspace_context.get("memory_summary_effective", memory_summary)),
        "memory_provenance_effective": memory_provenance,
        "tone_history": tone_history,
        "persona_pref_tone": str(persona_pref_tone or ""),
        "persona_pref_brevity": str(persona_pref_brevity or ""),
        "policy_role_command_allowlist": role_allowlist,
        "policy_rate_limit_window_seconds": int(RATE_LIMIT_WINDOW_SECONDS),
        "policy_rate_limit_max_requests": int(RATE_LIMIT_MAX_REQUESTS),
        "policy_rate_limit_requests_per_minute": int(policy_rate_limit_rpm) if isinstance(policy_rate_limit_rpm, int) and policy_rate_limit_rpm > 0 else None,
        "policy_rate_limit_burst": int(policy_rate_limit_burst) if isinstance(policy_rate_limit_burst, int) and policy_rate_limit_burst >= 0 else None,
        "user_profile_seed": user_profile_seed,
        "user_profile_image_url": user_profile_image_url,
        "account_age": int(account_age) if isinstance(account_age, int) else None,
        "account_class": normalize_account_class(account_class),
        "child_guardrails_enabled": bool(child_guardrails_enabled),
        "child_media_allowed_ratings": sorted(CHILD_MEDIA_ALLOWED_RATINGS),
        "child_media_allowed_ratings_under_13": sorted(CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13),
        "child_media_allowed_ratings_13_15": sorted(CHILD_MEDIA_ALLOWED_RATINGS_13_15),
        "child_media_allowed_ratings_16_17": sorted(CHILD_MEDIA_ALLOWED_RATINGS_16_17),
        "child_media_block_if_adult_flag": bool(CHILD_MEDIA_BLOCK_IF_ADULT_FLAG),
        "child_media_blocked_genre_ids": sorted(CHILD_MEDIA_BLOCKED_GENRE_IDS),
        "child_media_blocked_keywords": sorted(CHILD_MEDIA_BLOCKED_KEYWORDS),
        "timestamp": int(time.time()),
    }
    return payload


def process_update(update: dict[str, Any]) -> None:
    chat_id, user_id, text, photos, voice, audio, chat_type, username, first_name, last_name = parse_update(update)

    cleanup_expired_approvals()

    if chat_id == 0 or user_id == 0:
        return

    if chat_type not in {"private", "group", "supergroup"}:
        return

    token = command_token(text)
    if token.startswith("/") and token in ALLOWED_SLASH_COMMAND_TOKENS:
        precheck_record = get_user_record(USER_REGISTRY, user_id)
        if isinstance(precheck_record, dict) and str(precheck_record.get("status", "active")) == "active":
            precheck_role = str(precheck_record.get("role", "user"))
            if not is_role_command_allowed(precheck_role, token):
                send_message(chat_id, role_command_denied_message(token))
                return

    if handle_user_admin_command(chat_id, user_id, text):
        return

    if handle_notify_command(chat_id, user_id, text):
        return

    if handle_digest_command(chat_id, user_id, text):
        return

    if handle_incident_command(chat_id, user_id, text):
        return

    if handle_incident_control_commands(chat_id, user_id, text):
        return

    if handle_reqtrack_command(chat_id, user_id, text):
        return

    if handle_tone_command(chat_id, user_id, text):
        return

    if handle_approval_command(chat_id, user_id, text):
        return

    user_record = get_user_record(USER_REGISTRY, user_id)

    if not user_record and ALLOWED_IDS and user_id in ALLOWED_IDS:
        role = "admin" if user_id in BOOTSTRAP_ADMINS else "user"
        set_user_record(USER_REGISTRY, user_id, role, status="pending_registration")
        seeded = get_user_record(USER_REGISTRY, user_id) or {}
        seeded["registration_state"] = "pending_name"
        seeded["telegram_username"] = normalize_text(username)
        USER_REGISTRY.setdefault("users", {})[str(user_id)] = seeded
        save_user_registry(USER_REGISTRY)
        user_record = seeded

    if process_registration_flow(
        chat_id=chat_id,
        user_id=user_id,
        text=text,
        username=username,
        first_name=first_name,
        last_name=last_name,
        existing=user_record,
    ):
        return

    user_record = get_user_record(USER_REGISTRY, user_id)
    if not user_record:
        send_message(chat_id, "⛔ Access denied.")
        return

    if str(user_record.get("status", "active")) != "active":
        send_message(chat_id, "⛔ Account disabled.")
        return

    if handle_memory_command(chat_id, user_id, text):
        return

    if handle_profile_command(chat_id, user_id, text):
        return

    if handle_feedback_command(chat_id, user_id, text):
        return

    if handle_discord_command(chat_id, user_id, text):
        return

    role = str(user_record.get("role", "user"))
    tenant_id = f"u_{user_id}"
    account_age = get_record_account_age(user_record)
    account_class = get_record_account_class(user_record)
    child_guardrails_for_user = is_child_guardrails_account(user_record)
    mode = choose_mode(text)

    if command_token(text) == "/start":
        if role == "admin":
            notify_note = " Admin notifications: /notify list. Bridge health: /health or /status. Digest: /digest now|stats"
        else:
            notify_note = ""
        guardrail_note = " Child guardrails are active for media/content access." if child_guardrails_for_user else ""
        send_message(
            chat_id,
            (
                f"Bridge online. role={role}. "
                "Use /media <movie|tv> <title> [year] to start a media request. "
                "If multiple matches appear, use /media pick <n>. "
                "Use /textbook request <details> for lawful textbook fulfillment. "
                "Use /workspace create <name> for temporary 24h manual/product context. "
                "Use /coding on to request coding-help access. "
                "Use /research <query> for deep research reports (Nextcloud link delivery). "
                "Use /rag <message> for assistant queries. /ops is admin-only."
                f"{guardrail_note}"
                f"{notify_note} Incident controls: /incident list. Profile: /profile show. Discord link: /discord link"
            ),
        )
        return

    if command_token(text) in {"/whoami", "whoami"}:
        registration_state = str(user_record.get("registration_state", "active"))
        account_status = str(user_record.get("status", "active"))
        full_name = str(user_record.get("full_name", "") or "(not set)")
        telegram_username = normalize_text(username) or normalize_text(user_record.get("telegram_username", "")) or "(not set)"
        linked_discord_user_id = str(user_record.get("linked_discord_user_id", "") or "(not linked)")
        linked_discord_name = str(user_record.get("linked_discord_name", "") or "(not linked)")
        send_message(
            chat_id,
            "\n".join(
                [
                    "Account profile:",
                    f"- user_id: {user_id}",
                    f"- role: {role}",
                    f"- status: {account_status}",
                    f"- registration: {registration_state}",
                    f"- account_class: {'Child' if account_class == 'child' else 'Adult'}",
                    f"- age: {account_age if isinstance(account_age, int) else '(not set)'}",
                    f"- tenant: {tenant_id}",
                    f"- full_name: {full_name}",
                    f"- username: {telegram_username}",
                    f"- discord_user_id: {linked_discord_user_id}",
                    f"- discord_name: {linked_discord_name}",
                ]
            ),
        )
        return

    if command_token(text) in {"/status", "status"}:
        if role != "admin":
            send_message(chat_id, "⛔ Admin role required.")
            return
        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key="/status"):
            return
        token = command_token(text)
        args = parse_simple_command(text, token_name="/status") or [] if token == "/status" else []
        if args:
            if args[0].lower() == "json":
                send_message(chat_id, build_status_json_report())
            else:
                send_message(chat_id, "Usage: /status [json]")
            return
        send_message(chat_id, build_status_report())
        return

    if command_token(text) in {"/health", "health"}:
        if role != "admin":
            send_message(chat_id, "⛔ Admin role required.")
            return
        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key="/health"):
            return
        token = command_token(text)
        args = parse_simple_command(text, token_name="/health") or [] if token == "/health" else []
        include_validate_probe = True
        if args:
            arg0 = args[0].lower()
            if arg0 == "json":
                send_message(chat_id, build_health_json_report(request_user_id=user_id, include_validate_probe=include_validate_probe))
            elif arg0 == "quick":
                send_message(chat_id, build_health_report(request_user_id=user_id, include_validate_probe=False))
            else:
                send_message(chat_id, "Usage: /health [json|quick]")
            return
        send_message(chat_id, build_health_report(request_user_id=user_id, include_validate_probe=include_validate_probe))
        return

    if str(user_record.get("discord_link_state", "")) == "pending_name" and text and not text.strip().startswith("/"):
        user_record["discord_link_query"] = text.strip()
        attempt_discord_link(chat_id, user_id, user_record, text)
        return

    if command_token(text) in {"/ratelimit", "ratelimit"}:
        if role != "admin":
            send_message(chat_id, "⛔ Admin role required.")
            return
        if enforce_admin_command_cooldown(chat_id=chat_id, user_id=user_id, command_key="/ratelimit"):
            return
        send_message(chat_id, build_rate_limit_report())
        return

    if command_token(text) == "/selftest":
        checks: list[str] = []
        account_status = str(user_record.get("status", "active"))
        registration_state = str(user_record.get("registration_state", "active"))
        checks.append(f"account_status={'ok' if account_status == 'active' else 'fail'}({account_status})")
        checks.append(f"registration={'ok' if registration_state == 'active' else 'fail'}({registration_state})")

        rag_payload = {
            "source": "telegram",
            "chat_id": chat_id,
            "user_id": user_id,
            "role": role,
            "tenant_id": tenant_id,
            "full_name": str(user_record.get("full_name", "")),
            "telegram_username": normalize_text(username) or normalize_text(user_record.get("telegram_username", "")),
            "message": "selftest ping",
            "timestamp": int(time.time()),
        }

        try:
            _ = call_n8n(RAG_WEBHOOK, rag_payload)
            checks.append("rag_webhook=ok")
        except Exception as exc:
            checks.append(f"rag_webhook=fail({exc})")

        tenant_collection = f"day4_rag_{tenant_id}"
        try:
            with urllib.request.urlopen(
                f"http://qdrant:6333/collections/{tenant_collection}", timeout=8
            ) as response:
                data = json.loads(response.read().decode("utf-8", errors="ignore"))
            points = int(((data.get("result") or {}).get("points_count") or 0))
            checks.append(f"tenant_points=ok({points})")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                checks.append("tenant_points=ok(0)")
            else:
                checks.append(f"tenant_points=fail({exc})")
        except Exception as exc:
            checks.append(f"tenant_points=fail({exc})")

        try:
            with urllib.request.urlopen(
                "http://qdrant:6333/collections/day4_rag_shared_public", timeout=8
            ) as response:
                shared_data = json.loads(response.read().decode("utf-8", errors="ignore"))
            shared_points = int(((shared_data.get("result") or {}).get("points_count") or 0))
            checks.append(f"shared_points=ok({shared_points})")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                checks.append("shared_points=ok(0)")
            else:
                checks.append(f"shared_points=fail({exc})")
        except Exception as exc:
            checks.append(f"shared_points=fail({exc})")

        if role == "admin":
            ops_payload = dict(rag_payload)
            ops_payload["message"] = "selftest ops ping"
            try:
                _ = call_n8n(OPS_WEBHOOK, ops_payload)
                checks.append("ops_webhook=ok")
            except Exception as exc:
                checks.append(f"ops_webhook=fail({exc})")

        send_message(chat_id, "Selftest:\n- " + "\n- ".join(checks))
        return

    if handle_media_request_command(chat_id, user_id, text):
        return

    if handle_textbook_command(chat_id, user_id, text, user_record, role):
        return

    if handle_workspace_command(chat_id, user_id, text, role):
        return

    if handle_coding_command(chat_id, user_id, text, user_record, role):
        return

    if handle_research_command(chat_id, user_id, text, user_record, role):
        return

    if mode == "ops" and role != "admin":
        send_message(chat_id, "⛔ /ops is admin-only.")
        return

    cleaned_text = strip_mode_prefix(text)
    image_url = file_url_from_photo_sizes(photos) if photos else None
    audio_info = extract_audio_info(voice=voice, audio=audio)
    token = command_token(text)
    memory_intent_scope = infer_memory_intent_scope(cleaned_text, mode=mode, user_id=user_id)
    append_memory_telemetry(
        "scope_infer",
        user_id=user_id,
        fields={
            "mode": mode,
            "scope": str(memory_intent_scope or ""),
            "memory_v2_canary": is_memory_v2_canary_user(user_id),
            "has_text": bool(cleaned_text),
            "text_len": len(cleaned_text or ""),
        },
    )
    memory_enabled, memory_summary, memory_provenance = get_memory_context(user_id, intent_scope=memory_intent_scope)
    workspace_context = resolve_workspace_query_context(user_id, memory_enabled, memory_summary)
    memory_enabled_effective = bool(workspace_context.get("memory_enabled_effective", memory_enabled))
    memory_summary_effective = str(workspace_context.get("memory_summary_effective", memory_summary))
    tone_history = get_tone_history(user_record)
    persona_pref_tone, persona_pref_brevity = get_persona_preferences(user_record)
    profile_seed = sanitize_profile_seed(str(user_record.get("user_profile_seed", "")))
    profile_enabled = bool(user_record.get("profile_enabled", bool(profile_seed)))
    profile_image_url = str(user_record.get("user_profile_image_url", "")).strip() if profile_enabled else ""
    if not profile_enabled:
        profile_seed = ""

    if not cleaned_text and not image_url and not audio_info.get("audio_url"):
        send_message(chat_id, "Send text, a photo, or an audio/voice clip.")
        return

    if token in UTILITY_COMMAND_TOKENS:
        usage_messages = {
            "/approve": "Usage: /approve <id>",
            "/deny": "Usage: /deny <id>",
            "/pending": "Usage: /pending",
            "/ratelimit": "Usage: /ratelimit",
            "/whoami": "Usage: /whoami",
            "/status": "Usage: /status [json]",
            "/health": "Usage: /health [json|quick]",
            "/digest": "Usage: /digest now|stats",
            "/selftest": "Usage: /selftest",
            "/notify": "Usage: /notify me [json]|list|profile|test|validate|stats|set|add|remove|emergency|quiet|quarantine|delivery",
            "/incident": "Usage: /incident list|show <incident_id>",
            "/ack": "Usage: /ack <incident_id>",
            "/snooze": "Usage: /snooze <incident_id> <minutes>",
            "/unsnooze": "Usage: /unsnooze <incident_id>",
            "/reqtrack": "Usage: /reqtrack list [active|resolved|all]|kpi [hours] [json|pretty]|kpiweekly [json|pretty]|ack <incident_key> [note]|snooze <incident_key> [minutes] [note]|unsnooze <incident_key> [note]|close <incident_key> [note]|state",
            "/profile": "Usage: /profile show|age show|age set <years>|age clear|apply|apply text <profile>|style show|style set tone <warm|neutral|concise>|style set brevity <short|balanced|detailed>|style reset|clear",
            "/feedback": "Usage: /feedback too_short|too_long|too_formal|too_vague|good",
            "/discord": "Usage: /discord show|link|link <name>|unlink",
            "/tone": "Usage: /tone show <user_id>|reset <user_id>",
            "/user": "Usage: /user help",
            "/media": "Use /media <movie|tv> <title> [year] (then /media pick <n> if prompted)",
            "/request": "Use /request <movie|tv> <title> [year] (then /media pick <n> if prompted)",
            "/textbook": "Usage: /textbook request|confirm|cancel|status|email",
            "/workspace": "Usage: /workspace create|add|mode|status|close",
            "/coding": "Usage: /coding status|on|off|audit <n>",
            "/research": "Usage: /research <query>|status <run_id>|report <run_id>",
            "/textbook": "Usage: /textbook request|pick|confirm|ingest|resend|delivered|failed|cancel|status|email",
        }
        send_message(chat_id, usage_messages.get(token, "Command received."))
        return

    if token.startswith("/") and token not in ALLOWED_SLASH_COMMAND_TOKENS:
        print(f"[telegram-bridge] unknown_command token={token} user_id={user_id}", flush=True)
        send_message(
            chat_id,
            (
                "Unknown command.\n"
                "Use /media <movie|tv> <title>, /textbook request <details>, /workspace create <name>, /coding on, /research <query>, /rag <question>, or /ops <command> (admin).\n"
                "Other commands: /start, /whoami, /health (admin), /status (admin), /digest now|stats (admin), /profile show, /discord show, /notify list, /tone help"
            ),
        )
        return

    if not image_url and not audio_info.get("audio_url") and is_low_signal_text(cleaned_text):
        send_message(chat_id, "Please add more detail so I can help.")
        return

    coding_help_enabled = role == "admin" or bool(user_record.get("coding_help_enabled", False))
    if mode == "rag" and not coding_help_enabled and cleaned_text and is_coding_help_request(cleaned_text):
        send_message(
            chat_id,
            (
                "Coding help is not enabled for your account yet. "
                "Use /coding on to request admin approval. "
                "I can still help with runbook/docs questions, media requests, weather, and other non-coding topics."
            ),
        )
        return

    if (
        not image_url
        and not audio_info.get("audio_url")
        and cleaned_text
        and len(cleaned_text) < max(1, SHORT_INPUT_MIN_CHARS)
    ):
        send_message(chat_id, "Please add more detail so I can help.")
        return

    if mode == "rag" and not image_url and not audio_info.get("audio_url"):
        quick_reply = build_local_quick_reply(cleaned_text, user_record, user_id=user_id)
        if quick_reply:
            send_message(chat_id, quick_reply)
            return
        return

    allowed, retry_after, should_notify_rate_limit = check_and_record_rate_limit(user_id)
    if not allowed:
        if should_notify_rate_limit:
            send_message(
                chat_id,
                (
                    "⏱️ Too many requests right now. "
                    f"Try again in about {retry_after}s "
                    f"(limit {RATE_LIMIT_MAX_REQUESTS}/{RATE_LIMIT_WINDOW_SECONDS}s)."
                ),
            )
        return

    payload = build_payload(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        full_name=str(user_record.get("full_name", "")),
        telegram_username=normalize_text(username) or normalize_text(user_record.get("telegram_username", "")),
        text=cleaned_text,
        image_url=image_url,
        audio_info=audio_info,
        memory_enabled=memory_enabled_effective,
        memory_summary=memory_summary_effective,
        memory_provenance=memory_provenance,
        workspace_context=workspace_context,
        tone_history=tone_history,
        persona_pref_tone=persona_pref_tone,
        persona_pref_brevity=persona_pref_brevity,
        user_profile_seed=profile_seed,
        user_profile_image_url=profile_image_url,
        account_age=account_age,
        account_class=account_class,
        child_guardrails_enabled=child_guardrails_for_user,
    )

    if mode == "ops" and is_risky_ops_command(cleaned_text):
        approval_id = create_pending_approval(
            chat_id=chat_id,
            user_id=user_id,
            command_text=cleaned_text,
            payload=payload,
        )
        if not approval_id:
            send_message(
                chat_id,
                (
                    "🛑 Approval queue is currently full for your account. "
                    "Wait for pending approvals to clear, then retry the command."
                ),
            )
            return
        send_message(
            chat_id,
            (
                f"🛑 Approval required for risky /ops command (id={approval_id}).\n"
                f"Command: {cleaned_text}\n"
                f"Approve with: /approve {approval_id}\n"
                f"Deny with: /deny {approval_id}\n"
                f"Expires in {APPROVAL_TTL_SECONDS}s."
            ),
        )
        return

    webhook_path = RAG_WEBHOOK if mode == "rag" else OPS_WEBHOOK

    try:
        result = call_n8n(webhook_path, payload)
        reply = extract_reply_text(result)
    except urllib.error.HTTPError as exc:
        reply = f"❌ n8n webhook error: HTTP {exc.code}"
    except Exception as exc:
        reply = f"❌ bridge error: {exc}"

    if mode == "rag":
        update_user_tone_history(user_id, extract_tone_from_reply_text(reply))
        update_persona_drift_metrics(user_id, reply)

    send_message(chat_id, reply)


def main() -> None:
    start_textbook_download_server()
    print(
        f"[telegram-bridge] started (registered_users={len(USER_REGISTRY.get('users', {}))}, default_mode={DEFAULT_MODE})",
        flush=True,
    )
    offset = load_offset()

    while True:
        try:
            now_ts = int(time.time())
            global WORKSPACE_LAST_CLEANUP_TS
            if WORKSPACE_LAST_CLEANUP_TS <= 0 or (now_ts - WORKSPACE_LAST_CLEANUP_TS) >= max(60, WORKSPACE_CLEANUP_INTERVAL_SECONDS):
                cleaned, removed_docs, failed_docs = cleanup_expired_workspaces(now_ts=now_ts)
                WORKSPACE_LAST_CLEANUP_TS = now_ts
                if cleaned > 0:
                    print(
                        f"[telegram-bridge] workspace cleanup cleared={cleaned} docs_removed={removed_docs} docs_failed={failed_docs}",
                        flush=True,
                    )

            global TEXTBOOK_DOWNLOAD_LAST_CLEANUP_TS
            if TEXTBOOK_DOWNLOAD_LAST_CLEANUP_TS <= 0 or (
                now_ts - TEXTBOOK_DOWNLOAD_LAST_CLEANUP_TS
            ) >= max(60, TEXTBOOK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS):
                removed_entries, removed_files = cleanup_expired_textbook_downloads(now_ts=now_ts)
                TEXTBOOK_DOWNLOAD_LAST_CLEANUP_TS = now_ts
                if removed_entries > 0:
                    print(
                        f"[telegram-bridge] textbook download cleanup entries_removed={removed_entries} files_removed={removed_files}",
                        flush=True,
                    )

            response = telegram_request(
                "getUpdates",
                {
                    "offset": offset + 1,
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": ["message", "edited_message"],
                },
            )
            updates = response.get("result", [])
            for update in updates:
                update_id = int(update.get("update_id", 0))
                if update_id <= 0:
                    continue
                process_update(update)
                offset = max(offset, update_id)
                save_offset(offset)
        except Exception as exc:
            print(f"[telegram-bridge] poll error: {exc}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
