#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import traceback
import time
import hashlib
from datetime import datetime, timezone
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from policy_loader import load_policy_alert_settings

NTFY_BASE = os.getenv("NTFY_BASE", "http://ntfy")
N8N_BASE = os.getenv("N8N_BASE", "http://n8n:5678")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "65"))
POLL_REQUEST_TIMEOUT_SECONDS = int(os.getenv("POLL_REQUEST_TIMEOUT_SECONDS", "4"))
STATE_FILE = os.getenv("STATE_FILE", "/state/bridge_state.json")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_USER_REGISTRY = os.getenv("TELEGRAM_USER_REGISTRY", "/telegram-state/telegram_users.json")
TELEGRAM_NOTIFICATIONS_ENABLED = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_NOTIFY_CRITICAL_ONLY = os.getenv("TELEGRAM_NOTIFY_CRITICAL_ONLY", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_NOTIFY_MIN_PRIORITY = int(os.getenv("TELEGRAM_NOTIFY_MIN_PRIORITY", "3"))
TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS = int(os.getenv("TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS", "280"))
TELEGRAM_FANOUT_MESSAGE_REVIEW_ENABLED = os.getenv("TELEGRAM_FANOUT_MESSAGE_REVIEW_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_NOTIFY_DROP_PATTERNS = [
    item.strip().lower()
    for item in os.getenv("TELEGRAM_NOTIFY_DROP_PATTERNS", "smoke test,direct fanout,log check").split(",")
    if item.strip()
]
TELEGRAM_MEDIA_NOISE_FILTER_ENABLED = os.getenv("TELEGRAM_MEDIA_NOISE_FILTER_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_MEDIA_NOISE_MARKERS = [
    item.strip().lower()
    for item in os.getenv(
        "TELEGRAM_MEDIA_NOISE_MARKERS",
        "synthetic_id=,media synthetic check media-synthetic-,media sweep probe,media cursor probe,cursor_probe=,verification_run=,quiet_topic_drill=,media ready verification",
    ).split(",")
    if item.strip()
]
TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED = os.getenv("TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_MEDIA_FIRST_SEEN_STATE = os.getenv("TELEGRAM_MEDIA_FIRST_SEEN_STATE", "/state/telegram_media_first_seen.json")
TELEGRAM_MEDIA_FIRST_SEEN_RETENTION_SECONDS = int(os.getenv("TELEGRAM_MEDIA_FIRST_SEEN_RETENTION_SECONDS", "31536000"))
TELEGRAM_DEDUPE_STATE = os.getenv("TELEGRAM_DEDUPE_STATE", "/state/telegram_dedupe_state.json")
TELEGRAM_DEDUPE_WINDOW_SECONDS = int(os.getenv("TELEGRAM_DEDUPE_WINDOW_SECONDS", "120"))
TELEGRAM_DEDUPE_WINDOW_SECONDS_BY_TOPIC_RAW = os.getenv("TELEGRAM_DEDUPE_WINDOW_SECONDS_BY_TOPIC", "")
TELEGRAM_NOTIFY_STATS_STATE = os.getenv("TELEGRAM_NOTIFY_STATS_STATE", "/state/telegram_notify_stats.json")
TELEGRAM_NOTIFY_STATS_RETENTION_SECONDS = int(os.getenv("TELEGRAM_NOTIFY_STATS_RETENTION_SECONDS", "86400"))
TELEGRAM_SEND_MAX_RETRIES = int(os.getenv("TELEGRAM_SEND_MAX_RETRIES", "2"))
TELEGRAM_SEND_BACKOFF_SECONDS = float(os.getenv("TELEGRAM_SEND_BACKOFF_SECONDS", "1.0"))
TELEGRAM_SEND_BACKOFF_MAX_SECONDS = float(os.getenv("TELEGRAM_SEND_BACKOFF_MAX_SECONDS", "8.0"))
TELEGRAM_AUTO_QUARANTINE_ENABLED = os.getenv("TELEGRAM_AUTO_QUARANTINE_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_AUTO_QUARANTINE_THRESHOLD = int(os.getenv("TELEGRAM_AUTO_QUARANTINE_THRESHOLD", "3"))
TELEGRAM_AUTO_QUARANTINE_SECONDS = int(os.getenv("TELEGRAM_AUTO_QUARANTINE_SECONDS", "86400"))
TELEGRAM_DELIVERY_STATE = os.getenv("TELEGRAM_DELIVERY_STATE", "/state/telegram_delivery_state.json")
TELEGRAM_DIGEST_QUEUE_STATE = os.getenv("TELEGRAM_DIGEST_QUEUE_STATE", "/state/telegram_digest_queue.json")
TELEGRAM_QUIET_HOURS_UTC_OFFSET_HOURS = int(os.getenv("TELEGRAM_QUIET_HOURS_UTC_OFFSET_HOURS", "0"))
TELEGRAM_DIGEST_MAX_ITEMS_PER_USER = int(os.getenv("TELEGRAM_DIGEST_MAX_ITEMS_PER_USER", "50"))
TELEGRAM_DIGEST_LINE_MAX_CHARS = int(os.getenv("TELEGRAM_DIGEST_LINE_MAX_CHARS", "120"))
TELEGRAM_INCIDENT_STATE = os.getenv("TELEGRAM_INCIDENT_STATE", "/state/telegram_incidents.json")
TELEGRAM_INCIDENT_ACK_TTL_SECONDS = int(os.getenv("TELEGRAM_INCIDENT_ACK_TTL_SECONDS", "21600"))
TELEGRAM_INCIDENT_RETENTION_SECONDS = int(os.getenv("TELEGRAM_INCIDENT_RETENTION_SECONDS", "604800"))
TELEGRAM_INCIDENT_COLLAPSE_ENABLED = os.getenv("TELEGRAM_INCIDENT_COLLAPSE_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_INCIDENT_COLLAPSE_WINDOW_SECONDS = int(os.getenv("TELEGRAM_INCIDENT_COLLAPSE_WINDOW_SECONDS", "900"))
TELEGRAM_STATE_BACKEND = os.getenv("TELEGRAM_STATE_BACKEND", "json").strip().lower()
TELEGRAM_STATE_SQLITE_PATH = os.getenv("TELEGRAM_STATE_SQLITE_PATH", "/state/telegram_state.db").strip()
OVERSEERR_URL = os.getenv("OVERSEERR_URL", "http://host.docker.internal:5055").strip().rstrip("/")
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY", "").strip()
TELEGRAM_MEDIA_READY_GATE_ENABLED = os.getenv("TELEGRAM_MEDIA_READY_GATE_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_MEDIA_READY_STATUS_REQUIRED = int(os.getenv("TELEGRAM_MEDIA_READY_STATUS_REQUIRED", "5"))
POLICY_FILE = os.getenv("POLICY_FILE", "/app/policy/policy.v1.yaml").strip()

TOPICS = {
    "ai-chat": "/webhook/rag-query",
    "ai-replies": "/webhook/rag-query",
    "ops-commands": "/webhook/ops-commands-ingest",
    "ops-audit": "/webhook/ops-audit-review",
}


TELEGRAM_NOTIFICATION_TOPICS = {
    "ops-alerts": "ops",
    "ops-validate": "ops",
    "ops-audit": "audit",
    "ai-audit": "audit",
    "media-alerts": "media",
    "media-recommendations": "media",
    "ai-replies": "ai",
    "system-maintenance": "maintenance",
}

POLICY_REQUIRED_TOPICS, POLICY_TOPIC_CATEGORIES = load_policy_alert_settings(POLICY_FILE)
if POLICY_TOPIC_CATEGORIES:
    TELEGRAM_NOTIFICATION_TOPICS = {
        topic: POLICY_TOPIC_CATEGORIES.get(topic, category)
        for topic, category in TELEGRAM_NOTIFICATION_TOPICS.items()
    }
if POLICY_REQUIRED_TOPICS:
    filtered_topics = {
        topic: category
        for topic, category in TELEGRAM_NOTIFICATION_TOPICS.items()
        if topic in POLICY_REQUIRED_TOPICS
    }
    if filtered_topics:
        TELEGRAM_NOTIFICATION_TOPICS = filtered_topics
        print(
            f"[bridge] policy required_topics applied from {POLICY_FILE}: {sorted(TELEGRAM_NOTIFICATION_TOPICS.keys())}",
            flush=True,
        )
    else:
        print(
            f"[bridge] policy required_topics from {POLICY_FILE} matched none of TELEGRAM_NOTIFICATION_TOPICS; keeping defaults",
            flush=True,
        )

ALL_WATCHED_TOPICS = sorted(set(TOPICS.keys()) | set(TELEGRAM_NOTIFICATION_TOPICS.keys()))

CRITICAL_KEYWORDS = {
    "critical",
    "urgent",
    "sev1",
    "severity 1",
    "emergency",
    "outage",
    "down",
    "non responsive",
    "non-responsive",
}
NEGATED_CRITICAL_PATTERNS = (
    r"\bnon[-\s]?critical\b",
    r"\bnot\s+critical\b",
    r"\bno\s+outage\b",
)

IGNORE_REPLY_TITLES = {
    title.strip()
    for title in os.getenv("IGNORE_REPLY_TITLES", "AI Reply,AI RAG Reply").split(",")
    if title.strip()
}

MEDIA_READY_SIGNAL_PATTERNS = (
    r"\bis\s+now\s+available\s+in\s+plex\b",
    r"\bis\s+available\s+in\s+plex\b",
    r"\bready\s+in\s+plex\b",
    r"\bnow\s+available\b",
)


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


TELEGRAM_DEDUPE_WINDOW_OVERRIDES = parse_topic_window_overrides(TELEGRAM_DEDUPE_WINDOW_SECONDS_BY_TOPIC_RAW)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def should_ignore_reply_event(title: str, message: str) -> bool:
    if title in IGNORE_REPLY_TITLES:
        return True

    normalized = message.strip()
    if normalized == "No trusted source found":
        return True
    if "\n\nSources:" in normalized:
        return True

    return False


def use_sqlite_state_backend() -> bool:
    return TELEGRAM_STATE_BACKEND == "sqlite"


def ensure_sqlite_parent_dir() -> None:
    directory = os.path.dirname(TELEGRAM_STATE_SQLITE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)


def ensure_sqlite_state_table() -> None:
    if not use_sqlite_state_backend():
        return
    ensure_sqlite_parent_dir()
    conn = sqlite3.connect(TELEGRAM_STATE_SQLITE_PATH)
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
        conn.commit()
    finally:
        conn.close()


def load_sqlite_state(key: str, default: dict) -> dict:
    if not use_sqlite_state_backend():
        return default
    try:
        ensure_sqlite_state_table()
        conn = sqlite3.connect(TELEGRAM_STATE_SQLITE_PATH)
        try:
            row = conn.execute("SELECT payload FROM state_kv WHERE key = ?", (key,)).fetchone()
        finally:
            conn.close()
        if not row:
            return default
        data = json.loads(str(row[0]))
        if isinstance(data, dict):
            return data
        return default
    except Exception:
        return default


def save_sqlite_state(key: str, state: dict) -> None:
    ensure_sqlite_state_table()
    payload = json.dumps(state, ensure_ascii=False)
    conn = sqlite3.connect(TELEGRAM_STATE_SQLITE_PATH)
    try:
        conn.execute(
            """
            INSERT INTO state_kv(key, payload, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
            """,
            (key, payload, utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def load_user_registry() -> dict:
    if not os.path.exists(TELEGRAM_USER_REGISTRY):
        return {"users": {}}
    try:
        with open(TELEGRAM_USER_REGISTRY, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"users": {}}
        users = data.get("users")
        if not isinstance(users, dict):
            return {"users": {}}
        return data
    except Exception:
        return {"users": {}}


def load_delivery_state() -> dict:
    if use_sqlite_state_backend():
        data = load_sqlite_state("delivery", {"users": {}, "updated_at": utc_now()})
        users = data.get("users") if isinstance(data, dict) else None
        if not isinstance(users, dict):
            return {"users": {}, "updated_at": utc_now()}
        return data
    if not os.path.exists(TELEGRAM_DELIVERY_STATE):
        return {"users": {}, "updated_at": utc_now()}
    try:
        with open(TELEGRAM_DELIVERY_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"users": {}, "updated_at": utc_now()}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data
    except Exception:
        return {"users": {}, "updated_at": utc_now()}


def save_delivery_state(state: dict) -> None:
    if use_sqlite_state_backend():
        save_sqlite_state("delivery", state)
        return
    os.makedirs(os.path.dirname(TELEGRAM_DELIVERY_STATE), exist_ok=True)
    with open(TELEGRAM_DELIVERY_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_dedupe_state() -> dict:
    if use_sqlite_state_backend():
        data = load_sqlite_state("dedupe", {"items": {}})
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, dict):
            return {"items": {}}
        return data
    if not os.path.exists(TELEGRAM_DEDUPE_STATE):
        return {"items": {}}
    try:
        with open(TELEGRAM_DEDUPE_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"items": {}}
        items = data.get("items")
        if not isinstance(items, dict):
            data["items"] = {}
        return data
    except Exception:
        return {"items": {}}


def save_dedupe_state(state: dict):
    if use_sqlite_state_backend():
        save_sqlite_state("dedupe", state)
        return
    os.makedirs(os.path.dirname(TELEGRAM_DEDUPE_STATE), exist_ok=True)
    with open(TELEGRAM_DEDUPE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def load_media_first_seen_state() -> dict:
    if use_sqlite_state_backend():
        data = load_sqlite_state("media_first_seen", {"items": {}, "updated_at": utc_now()})
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, dict):
            return {"items": {}, "updated_at": utc_now()}
        return data
    if not os.path.exists(TELEGRAM_MEDIA_FIRST_SEEN_STATE):
        return {"items": {}, "updated_at": utc_now()}
    try:
        with open(TELEGRAM_MEDIA_FIRST_SEEN_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"items": {}, "updated_at": utc_now()}
        items = data.get("items")
        if not isinstance(items, dict):
            data["items"] = {}
        return data
    except Exception:
        return {"items": {}, "updated_at": utc_now()}


def save_media_first_seen_state(state: dict) -> None:
    if use_sqlite_state_backend():
        save_sqlite_state("media_first_seen", state)
        return
    os.makedirs(os.path.dirname(TELEGRAM_MEDIA_FIRST_SEEN_STATE), exist_ok=True)
    with open(TELEGRAM_MEDIA_FIRST_SEEN_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def load_notify_stats_state() -> dict:
    if use_sqlite_state_backend():
        data = load_sqlite_state("notify_stats", {"events": [], "updated_at": utc_now()})
        events = data.get("events") if isinstance(data, dict) else None
        if not isinstance(events, list):
            return {"events": [], "updated_at": utc_now()}
        return data
    if not os.path.exists(TELEGRAM_NOTIFY_STATS_STATE):
        return {"events": [], "updated_at": utc_now()}
    try:
        with open(TELEGRAM_NOTIFY_STATS_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"events": [], "updated_at": utc_now()}
        events = data.get("events")
        if not isinstance(events, list):
            data["events"] = []
        return data
    except Exception:
        return {"events": [], "updated_at": utc_now()}


def save_notify_stats_state(state: dict):
    if use_sqlite_state_backend():
        save_sqlite_state("notify_stats", state)
        return
    os.makedirs(os.path.dirname(TELEGRAM_NOTIFY_STATS_STATE), exist_ok=True)
    with open(TELEGRAM_NOTIFY_STATS_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def load_digest_queue_state() -> dict:
    if use_sqlite_state_backend():
        data = load_sqlite_state("digest_queue", {"users": {}, "updated_at": utc_now()})
        users = data.get("users") if isinstance(data, dict) else None
        if not isinstance(users, dict):
            return {"users": {}, "updated_at": utc_now()}
        return data
    if not os.path.exists(TELEGRAM_DIGEST_QUEUE_STATE):
        return {"users": {}, "updated_at": utc_now()}
    try:
        with open(TELEGRAM_DIGEST_QUEUE_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"users": {}, "updated_at": utc_now()}
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data
    except Exception:
        return {"users": {}, "updated_at": utc_now()}


def save_digest_queue_state(state: dict):
    if use_sqlite_state_backend():
        save_sqlite_state("digest_queue", state)
        return
    os.makedirs(os.path.dirname(TELEGRAM_DIGEST_QUEUE_STATE), exist_ok=True)
    with open(TELEGRAM_DIGEST_QUEUE_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def load_incident_state() -> dict:
    if use_sqlite_state_backend():
        data = load_sqlite_state("incidents", {"incidents": {}, "updated_at": utc_now()})
        incidents = data.get("incidents") if isinstance(data, dict) else None
        if not isinstance(incidents, dict):
            return {"incidents": {}, "updated_at": utc_now()}
        return data
    if not os.path.exists(TELEGRAM_INCIDENT_STATE):
        return {"incidents": {}, "updated_at": utc_now()}
    try:
        with open(TELEGRAM_INCIDENT_STATE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"incidents": {}, "updated_at": utc_now()}
        incidents = data.get("incidents")
        if not isinstance(incidents, dict):
            data["incidents"] = {}
        return data
    except Exception:
        return {"incidents": {}, "updated_at": utc_now()}


def save_incident_state(state: dict):
    if use_sqlite_state_backend():
        save_sqlite_state("incidents", state)
        return
    os.makedirs(os.path.dirname(TELEGRAM_INCIDENT_STATE), exist_ok=True)
    with open(TELEGRAM_INCIDENT_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def build_incident_id(topic: str, category: str, title: str, message: str) -> str:
    normalized = "|".join(
        [
            str(topic or "").strip().lower(),
            str(category or "").strip().lower(),
            " ".join(str(title or "").strip().lower().split()),
            " ".join(str(message or "").strip().lower().split()),
        ]
    )
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10].upper()
    return f"INC-{digest}"


def upsert_incident(
    incident_state: dict,
    incident_id: str,
    topic: str,
    category: str,
    title: str,
    message: str,
    priority: int,
    critical: bool,
) -> dict[str, Any]:
    now_ts = int(time.time())
    retention = max(3600, TELEGRAM_INCIDENT_RETENTION_SECONDS)
    threshold = now_ts - retention

    incidents_raw = incident_state.get("incidents")
    if not isinstance(incidents_raw, dict):
        incidents_raw = {}

    incidents: dict[str, dict[str, Any]] = {}
    for key, item in incidents_raw.items():
        if not isinstance(item, dict):
            continue
        try:
            last_seen = int(item.get("last_seen", 0))
        except (TypeError, ValueError):
            continue
        if last_seen >= threshold:
            incidents[str(key)] = item

    entry = incidents.get(incident_id)
    if not isinstance(entry, dict):
        entry = {
            "id": incident_id,
            "topic": str(topic),
            "category": str(category),
            "title": str(title),
            "message": str(message),
            "priority": int(priority),
            "critical": bool(critical),
            "first_seen": now_ts,
            "event_count": 0,
            "message_targets": {},
        }
    else:
        entry["topic"] = str(topic)
        entry["category"] = str(category)
        entry["title"] = str(title)
        entry["message"] = str(message)
        entry["priority"] = int(priority)
        entry["critical"] = bool(critical)

    entry["last_seen"] = now_ts
    entry["event_count"] = int(entry.get("event_count", 0)) + 1
    targets = entry.get("message_targets")
    if not isinstance(targets, dict):
        entry["message_targets"] = {}
    incidents[incident_id] = entry

    incident_state["incidents"] = incidents
    incident_state["updated_at"] = utc_now()
    return entry


def incident_suppression_reason(incident: dict[str, Any], now_ts: int) -> str:
    try:
        snoozed_until = int(incident.get("snoozed_until", 0) or 0)
    except (TypeError, ValueError):
        snoozed_until = 0
    if snoozed_until > now_ts:
        return "incident_snoozed"

    try:
        acked_at = int(incident.get("acked_at", 0) or 0)
    except (TypeError, ValueError):
        acked_at = 0
    if acked_at > 0:
        ttl = max(60, TELEGRAM_INCIDENT_ACK_TTL_SECONDS)
        if now_ts - acked_at <= ttl:
            return "incident_acked"

    return ""


def record_notify_event(
    topic: str,
    result: str,
    reason: str,
    priority: int,
    critical: bool,
    recipients: int,
    probe_id: str = "",
):
    now = int(time.time())
    retention = max(60, TELEGRAM_NOTIFY_STATS_RETENTION_SECONDS)
    threshold = now - retention

    state = load_notify_stats_state()
    events_raw = state.get("events", [])
    if not isinstance(events_raw, list):
        events_raw = []

    kept: list[dict[str, Any]] = []
    for event in events_raw:
        if not isinstance(event, dict):
            continue
        try:
            ts = int(event.get("ts", 0))
        except (TypeError, ValueError):
            continue
        if ts >= threshold:
            kept.append(event)

    event = {
        "ts": now,
        "topic": str(topic),
        "result": str(result),
        "reason": str(reason),
        "priority": int(priority),
        "critical": bool(critical),
        "recipients": int(recipients),
    }
    if str(probe_id or "").strip():
        event["probe_id"] = str(probe_id).strip()

    kept.append(event)

    state["events"] = kept[-5000:]
    state["updated_at"] = utc_now()
    save_notify_stats_state(state)


def dedupe_window_for_topic(topic: str) -> int:
    return max(1, TELEGRAM_DEDUPE_WINDOW_OVERRIDES.get(topic, TELEGRAM_DEDUPE_WINDOW_SECONDS))


def extract_notify_validate_probe_id(title: str, message: str) -> str:
    blob = f"{title}\n{message}"
    match = re.search(r"notify_validate_probe_id=([A-Za-z0-9_-]{8,80})", blob)
    if not match:
        return ""
    return str(match.group(1)).strip()


def build_dedupe_key(topic: str, category: str, title: str, message: str, priority: int, critical: bool) -> str:
    normalized = "|".join(
        [
            str(topic or "").strip().lower(),
            str(category or "").strip().lower(),
            str(priority),
            "1" if critical else "0",
            " ".join(str(title or "").strip().lower().split()),
            " ".join(str(message or "").strip().lower().split()),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def should_skip_dedup(topic: str, key: str) -> tuple[bool, int]:
    current_window = dedupe_window_for_topic(topic)
    now = int(time.time())
    state = load_dedupe_state()
    items = state.setdefault("items", {})

    cleaned: dict[str, dict[str, Any]] = {}
    for item_key, payload in items.items():
        item_topic = ""
        ts_int = 0

        if isinstance(payload, dict):
            item_topic = str(payload.get("topic", "")).strip()
            try:
                ts_int = int(payload.get("ts", 0))
            except (TypeError, ValueError):
                continue
        else:
            try:
                ts_int = int(payload)
            except (TypeError, ValueError):
                continue

        if ts_int <= 0:
            continue

        item_window = dedupe_window_for_topic(item_topic) if item_topic else max(1, TELEGRAM_DEDUPE_WINDOW_SECONDS)
        if now - ts_int <= item_window:
            cleaned[item_key] = {"ts": ts_int, "topic": item_topic}

    last_seen = cleaned.get(key)
    cleaned[key] = {"ts": now, "topic": topic}
    state["items"] = cleaned
    save_dedupe_state(state)

    if last_seen is None:
        return False, 0

    if isinstance(last_seen, dict):
        last_seen_ts = int(last_seen.get("ts", 0))
    else:
        last_seen_ts = int(last_seen)
    if last_seen_ts <= 0:
        return False, 0

    remaining = max(1, current_window - (now - last_seen_ts))
    return True, remaining


def telegram_request(method: str, payload: dict):
    if not TELEGRAM_BOT_TOKEN:
        return {}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8", errors="ignore")
    if not body.strip():
        return {}
    try:
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def classify_telegram_send_error(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            return "rate_limited", True
        if 500 <= int(exc.code) <= 599:
            return f"telegram_http_{exc.code}", True
        return f"telegram_http_{exc.code}", False

    if isinstance(exc, urllib.error.URLError):
        return "network_error", True

    text = str(exc).strip().lower()
    if "too many requests" in text or "http error 429" in text:
        return "rate_limited", True
    if "timed out" in text or "timeout" in text:
        return "timeout", True
    if "connection reset" in text or "temporarily unavailable" in text:
        return "network_error", True

    return "send_error", False


def review_outbound_telegram_fanout_text(text: str) -> str:
    candidate = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
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
        lines.append(line)

    reviewed = "\n".join(lines)
    reviewed = re.sub(r"\n{3,}", "\n\n", reviewed).strip()
    if not reviewed:
        reviewed = "(no message content)"
    hard_cap = max(80, TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS)
    if len(reviewed) > hard_cap:
        reviewed = reviewed[: hard_cap - 1].rstrip() + "…"
    return reviewed


def send_telegram_message_with_id(chat_id: int, text: str) -> tuple[bool, str, int | None]:
    max_retries = max(0, TELEGRAM_SEND_MAX_RETRIES)
    attempts = max_retries + 1
    base_backoff = max(0.1, TELEGRAM_SEND_BACKOFF_SECONDS)
    max_backoff = max(base_backoff, TELEGRAM_SEND_BACKOFF_MAX_SECONDS)
    last_reason = "send_error"
    outbound_text = str(text or "")
    if TELEGRAM_FANOUT_MESSAGE_REVIEW_ENABLED:
        outbound_text = review_outbound_telegram_fanout_text(outbound_text)

    for attempt in range(1, attempts + 1):
        try:
            response = telegram_request(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": outbound_text,
                    "disable_web_page_preview": True,
                },
            )
            result = response.get("result") if isinstance(response, dict) else {}
            message_id: int | None = None
            if isinstance(result, dict):
                try:
                    parsed_id = int(result.get("message_id", 0) or 0)
                    message_id = parsed_id if parsed_id > 0 else None
                except (TypeError, ValueError):
                    message_id = None
            return True, "sent", message_id
        except Exception as exc:
            reason, retryable = classify_telegram_send_error(exc)
            last_reason = reason
            if not retryable or attempt >= attempts:
                print(
                    f"telegram fanout failed chat_id={chat_id} attempt={attempt}/{attempts} reason={reason}: {exc}",
                    flush=True,
                )
                return False, reason, None

            sleep_for = min(max_backoff, base_backoff * (2 ** (attempt - 1)))
            print(
                f"telegram fanout retry chat_id={chat_id} attempt={attempt}/{attempts} reason={reason} sleep={sleep_for:.1f}s",
                flush=True,
            )
            time.sleep(sleep_for)

    return False, last_reason, None


def send_telegram_message(chat_id: int, text: str) -> tuple[bool, str]:
    sent, reason, _message_id = send_telegram_message_with_id(chat_id=chat_id, text=text)
    return sent, reason


def send_or_edit_telegram_message(chat_id: int, text: str, edit_message_id: int | None = None) -> tuple[bool, str, int | None, bool]:
    outbound_text = str(text or "")
    if TELEGRAM_FANOUT_MESSAGE_REVIEW_ENABLED:
        outbound_text = review_outbound_telegram_fanout_text(outbound_text)

    if edit_message_id and int(edit_message_id) > 0:
        try:
            response = telegram_request(
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": int(edit_message_id),
                    "text": outbound_text,
                    "disable_web_page_preview": True,
                },
            )
            result = response.get("result") if isinstance(response, dict) else {}
            if isinstance(result, dict):
                try:
                    return True, "sent", int(result.get("message_id", edit_message_id) or edit_message_id), True
                except (TypeError, ValueError):
                    return True, "sent", int(edit_message_id), True
            return True, "sent", int(edit_message_id), True
        except Exception as exc:
            reason, _retryable = classify_telegram_send_error(exc)
            if reason != "telegram_http_400":
                print(
                    f"telegram fanout edit failed chat_id={chat_id} message_id={edit_message_id} reason={reason}: {exc}",
                    flush=True,
                )
                return False, reason, None, True

    sent, reason, message_id = send_telegram_message_with_id(chat_id=chat_id, text=outbound_text)
    if not sent:
        return False, reason, None, False
    return True, "sent", message_id, False


def is_quarantine_reason(reason: str) -> bool:
    normalized = str(reason or "").strip().lower()
    return normalized == "telegram_http_400"


def quarantine_threshold_for_reason(reason: str) -> int:
    normalized = str(reason or "").strip().lower()
    if normalized == "telegram_http_400":
        return 1
    return max(1, TELEGRAM_AUTO_QUARANTINE_THRESHOLD)


def user_quarantine_until_ts(record: dict[str, Any]) -> int:
    try:
        return int(record.get("notify_quarantine_until", 0) or 0)
    except (TypeError, ValueError):
        return 0


def update_delivery_state(delivery_state: dict, user_id: int, sent: bool, reason: str) -> bool:
    users = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
    if not isinstance(users, dict):
        return False
    record = users.get(str(user_id))
    if not isinstance(record, dict):
        record = {}

    changed = False
    now_ts = int(time.time())

    if sent:
        if int(record.get("notify_delivery_fail_streak", 0) or 0) != 0:
            record["notify_delivery_fail_streak"] = 0
            changed = True
        if record.get("notify_delivery_last_reason"):
            record["notify_delivery_last_reason"] = ""
            changed = True
        if int(record.get("notify_delivery_last_failed_at", 0) or 0) != 0:
            record["notify_delivery_last_failed_at"] = 0
            changed = True
        record["notify_delivery_last_sent_at"] = now_ts
        changed = True
        if user_quarantine_until_ts(record) <= now_ts and user_quarantine_until_ts(record) > 0:
            record["notify_quarantine_until"] = 0
            record["notify_quarantine_reason"] = ""
            changed = True
    else:
        previous = int(record.get("notify_delivery_fail_streak", 0) or 0)
        record["notify_delivery_fail_streak"] = previous + 1
        record["notify_delivery_last_reason"] = str(reason or "send_error")
        record["notify_delivery_last_failed_at"] = now_ts
        changed = True

        if TELEGRAM_AUTO_QUARANTINE_ENABLED and is_quarantine_reason(reason):
            threshold = quarantine_threshold_for_reason(reason)
            if int(record.get("notify_delivery_fail_streak", 0) or 0) >= threshold:
                until_ts = now_ts + max(300, TELEGRAM_AUTO_QUARANTINE_SECONDS)
                record["notify_quarantine_until"] = until_ts
                record["notify_quarantine_reason"] = f"{reason}:streak={record.get('notify_delivery_fail_streak', 0)}"
                record["notify_quarantine_count"] = int(record.get("notify_quarantine_count", 0) or 0) + 1
                changed = True

    if changed:
        record["updated_at"] = utc_now()
        users[str(user_id)] = record
        delivery_state["users"] = users
        delivery_state["updated_at"] = utc_now()
    return changed


def is_user_quarantined(record: dict[str, Any], now_ts: int) -> bool:
    until_ts = user_quarantine_until_ts(record)
    return until_ts > now_ts


def consume_media_quarantine_bypass_once(delivery_state: dict[str, Any], now_ts: int) -> tuple[bool, bool]:
    if not isinstance(delivery_state, dict):
        return False, False

    marker_raw = delivery_state.get("media_quarantine_bypass_once")
    marker = marker_raw if isinstance(marker_raw, dict) else None
    if not isinstance(marker, dict):
        return False, False

    changed = False
    try:
        expires_at = int(marker.get("expires_at", 0) or 0)
    except (TypeError, ValueError):
        expires_at = 0

    if expires_at > 0 and expires_at <= now_ts:
        if bool(marker.get("enabled", False)):
            marker["enabled"] = False
            marker["consumed_at"] = now_ts
            marker["consume_reason"] = "expired"
            changed = True
        if changed:
            delivery_state["media_quarantine_bypass_once"] = marker
            delivery_state["updated_at"] = utc_now()
        return False, changed

    enabled = bool(marker.get("enabled", False))
    if not enabled:
        return False, False

    marker["enabled"] = False
    marker["consumed_at"] = now_ts
    marker["consume_reason"] = "used"
    delivery_state["media_quarantine_bypass_once"] = marker
    delivery_state["updated_at"] = utc_now()
    return True, True


def is_critical_event(priority: int, title: str, message: str) -> bool:
    if int(priority or 0) >= 5:
        return True
    blob = f"{title} {message}".strip().lower()
    for pattern in NEGATED_CRITICAL_PATTERNS:
        if re.search(pattern, blob):
            return False
    for keyword in CRITICAL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", blob):
            return True
    return False


def normalize_topics(raw_topics) -> set[str]:
    if not isinstance(raw_topics, list):
        return set()
    return {str(item).strip().lower() for item in raw_topics if str(item).strip()}


def parse_quiet_hours(record: dict) -> tuple[bool, int, int]:
    if not isinstance(record, dict):
        return False, 22, 7

    enabled = bool(record.get("quiet_hours_enabled", False))
    try:
        start = int(record.get("quiet_hours_start_hour", 22))
        end = int(record.get("quiet_hours_end_hour", 7))
    except (TypeError, ValueError):
        return False, 22, 7

    if start < 0 or start > 23 or end < 0 or end > 23:
        return False, 22, 7
    if start == end:
        return False, start, end
    return enabled, start, end


def parse_quiet_hours_for_category(record: dict, category: str) -> tuple[bool, int, int]:
    enabled, start, end = parse_quiet_hours(record)
    if not isinstance(record, dict):
        return enabled, start, end

    overrides_raw = record.get("quiet_hours_topics")
    overrides = overrides_raw if isinstance(overrides_raw, dict) else {}
    topic_key = str(category or "").strip().lower()
    if not topic_key:
        return enabled, start, end

    override = overrides.get(topic_key)
    if not isinstance(override, dict):
        return enabled, start, end

    override_enabled = bool(override.get("enabled", False))
    try:
        override_start = int(override.get("start_hour", 22))
        override_end = int(override.get("end_hour", 7))
    except (TypeError, ValueError):
        return enabled, start, end

    if override_start < 0 or override_start > 23 or override_end < 0 or override_end > 23 or override_start == override_end:
        return enabled, start, end
    return override_enabled, override_start, override_end


def current_local_hour(now_ts: int | None = None) -> int:
    base = datetime.fromtimestamp(int(now_ts or time.time()), tz=timezone.utc)
    return (base.hour + TELEGRAM_QUIET_HOURS_UTC_OFFSET_HOURS) % 24


def is_quiet_now(start_hour: int, end_hour: int, now_ts: int | None = None) -> bool:
    hour = current_local_hour(now_ts=now_ts)
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def truncate(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def importance_from_event(priority: int, critical: bool) -> str:
    if critical or int(priority or 0) >= 5:
        return "urgent"
    if int(priority or 0) >= 4:
        return "important"
    return "normal"


def summarize_for_humans(title: str, message: str, limit: int = 220) -> str:
    clean_title = truncate(title, 100)
    clean_message = truncate(message, limit)
    if clean_title and clean_message:
        if clean_message.lower().startswith(clean_title.lower()):
            return clean_message
        return f"{clean_title}: {clean_message}"
    if clean_message:
        return clean_message
    if clean_title:
        return clean_title
    return "There is a system update."


def digest_line(topic: str, title: str, message: str) -> str:
    summary = summarize_for_humans(title=title, message=message, limit=max(40, TELEGRAM_DIGEST_LINE_MAX_CHARS))
    clean_topic = str(topic or "unknown").strip()
    return f"[{clean_topic}] {summary}"


def should_skip_deferred_digest_item(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return True
    category = str(item.get("category", "")).strip().lower()
    if category != "media":
        return False
    blob = f"{item.get('title', '')} {item.get('message', '')}".strip().lower()
    if not blob:
        return False
    return any(marker in blob for marker in TELEGRAM_MEDIA_NOISE_MARKERS)


def deferred_digest_item_key(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    topic = str(item.get("topic", "")).strip().lower()
    category = str(item.get("category", "")).strip().lower()
    title = str(item.get("title", ""))
    message = str(item.get("message", ""))
    if category == "media" and is_ready_signal_message(title=title, message=message):
        normalized = normalize_media_name(extract_media_title_for_ready_check(title=title, message=message))
        if normalized:
            return f"{topic}|{category}|ready|{normalized}"
    normalized_summary = normalize_media_name(summarize_for_humans(title=title, message=message, limit=220))
    if normalized_summary:
        return f"{topic}|{category}|summary|{normalized_summary}"
    return ""


def queue_deferred_digest_item(user_id: int, topic: str, category: str, title: str, message: str, priority: int, incident_id: str):
    state = load_digest_queue_state()
    users = state.get("users")
    if not isinstance(users, dict):
        users = {}

    key = str(user_id)
    entry = users.get(key)
    if not isinstance(entry, dict):
        entry = {"items": [], "updated_at": utc_now()}

    items = entry.get("items")
    if not isinstance(items, list):
        items = []

    items.append(
        {
            "ts": int(time.time()),
            "topic": str(topic),
            "category": str(category),
            "title": str(title),
            "message": str(message),
            "priority": int(priority),
            "incident_id": str(incident_id),
        }
    )
    max_items = max(10, TELEGRAM_DIGEST_MAX_ITEMS_PER_USER)
    entry["items"] = items[-max_items:]
    entry["updated_at"] = utc_now()
    users[key] = entry

    state["users"] = users
    state["updated_at"] = utc_now()
    save_digest_queue_state(state)


def flush_deferred_digests(registry: dict):
    users_raw = registry.get("users") if isinstance(registry, dict) else {}
    if not isinstance(users_raw, dict) or not users_raw:
        return

    state = load_digest_queue_state()
    user_entries = state.get("users")
    if not isinstance(user_entries, dict) or not user_entries:
        return

    changed = False
    delivery_state = load_delivery_state()
    delivery_changed = False
    for user_id_raw, rec in users_raw.items():
        if not isinstance(rec, dict):
            continue
        if str(rec.get("status", "active")) != "active":
            continue
        if str(rec.get("role", "user")) != "admin":
            continue

        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            continue

        queue_entry = user_entries.get(str(user_id))
        if not isinstance(queue_entry, dict):
            continue
        items = queue_entry.get("items")
        if not isinstance(items, list) or not items:
            continue

        send_items: list[dict[str, Any]] = []
        keep_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_category = str(item.get("category", "")).strip().lower()
            enabled, start_hour, end_hour = parse_quiet_hours_for_category(rec, category=item_category)
            if enabled and is_quiet_now(start_hour=start_hour, end_hour=end_hour):
                keep_items.append(item)
            else:
                send_items.append(item)

        if not send_items:
            continue

        filtered_send_items: list[dict[str, Any]] = []
        skipped_noise = 0
        deduped = 0
        seen_keys: set[str] = set()
        for item in send_items:
            if not isinstance(item, dict):
                continue
            if should_skip_deferred_digest_item(item):
                skipped_noise += 1
                continue
            item_key = deferred_digest_item_key(item)
            if item_key and item_key in seen_keys:
                deduped += 1
                continue
            if item_key:
                seen_keys.add(item_key)
            filtered_send_items.append(item)

        if not filtered_send_items:
            if keep_items:
                queue_entry["items"] = keep_items
                queue_entry["updated_at"] = utc_now()
                user_entries[str(user_id)] = queue_entry
            else:
                user_entries.pop(str(user_id), None)
            changed = True
            continue

        lines = [
            f"🕘 Deferred alert digest ({len(filtered_send_items)} item{'s' if len(filtered_send_items) != 1 else ''})",
            "Queued during quiet hours:",
        ]
        preview_limit = 12
        for item in filtered_send_items[:preview_limit]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {digest_line(topic=str(item.get('topic', '')), title=str(item.get('title', '')), message=str(item.get('message', '')))}"
            )
        if len(filtered_send_items) > preview_limit:
            lines.append(f"- …and {len(filtered_send_items) - preview_limit} more")
        if deduped > 0:
            lines.append(f"- condensed duplicates: {deduped}")
        if skipped_noise > 0:
            lines.append(f"- hidden low-signal updates: {skipped_noise}")

        sent, reason = send_telegram_message(user_id, "\n".join(lines))
        if update_delivery_state(delivery_state=delivery_state, user_id=user_id, sent=sent, reason=reason):
            delivery_changed = True
        if sent:
            if keep_items:
                queue_entry["items"] = keep_items
                queue_entry["updated_at"] = utc_now()
                user_entries[str(user_id)] = queue_entry
            else:
                user_entries.pop(str(user_id), None)
            changed = True
        else:
            print(f"telegram digest flush failed user_id={user_id} reason={reason}", flush=True)

    if delivery_changed:
        save_delivery_state(delivery_state)

    if changed:
        state["users"] = user_entries
        state["updated_at"] = utc_now()
        save_digest_queue_state(state)


def strip_markdown_noise(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"[`*_>#\[\]]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_media_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())


def is_ready_signal_message(title: str, message: str) -> bool:
    blob = f"{title} {message}".strip().lower()
    return any(re.search(pattern, blob) for pattern in MEDIA_READY_SIGNAL_PATTERNS)


def extract_media_title_for_ready_check(title: str, message: str) -> str:
    body = strip_markdown_noise(message)
    patterns = (
        r"^(.+?)\s+is\s+now\s+available\s+in\s+plex\b",
        r"^(.+?)\s+is\s+available\s+in\s+plex\b",
        r"^(.+?)\s+now\s+available\b",
        r"^ready[:\-]\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = strip_markdown_noise(match.group(1))
        if candidate:
            return candidate

    title_clean = strip_markdown_noise(title)
    if title_clean and not re.search(r"\b(media\s+ready|ready\s+test|service\s+status|service\s+recovered)\b", title_clean, flags=re.IGNORECASE):
        return title_clean
    return ""


def extract_media_year(text: str) -> str:
    value = strip_markdown_noise(text)
    if not value:
        return ""
    match = re.search(r"\b((?:19|20)\d{2})\b", value)
    if not match:
        return ""
    return str(match.group(1))


def media_first_seen_key(topic: str, title: str, message: str) -> str:
    candidate_title = extract_media_title_for_ready_check(title=title, message=message)
    if not candidate_title:
        candidate_title = strip_markdown_noise(title) or strip_markdown_noise(message)
    title_norm = normalize_media_name(candidate_title)
    if not title_norm:
        return ""

    year = extract_media_year(candidate_title) or extract_media_year(title) or extract_media_year(message)
    blob = f"{title} {message}".lower()
    media_kind = "media"
    if re.search(r"\b(tv|series|show|season|episode|s\d{1,2}e\d{1,2})\b", blob):
        media_kind = "tv"
    elif re.search(r"\b(movie|film)\b", blob):
        media_kind = "movie"

    return f"{str(topic or '').strip().lower()}|{media_kind}|{title_norm}|{year}"


def media_first_seen_decision(topic: str, title: str, message: str) -> tuple[bool, str]:
    if topic != "media-alerts":
        return True, "not_media_topic"
    if not TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED:
        return True, "media_first_seen_disabled"
    if not is_ready_signal_message(title=title, message=message):
        return True, "not_ready_signal"

    key = media_first_seen_key(topic=topic, title=title, message=message)
    if not key:
        return True, "media_first_seen_no_key"

    now_ts = int(time.time())
    retention = max(0, TELEGRAM_MEDIA_FIRST_SEEN_RETENTION_SECONDS)
    keep_after = now_ts - retention if retention > 0 else 0

    state = load_media_first_seen_state()
    items_raw = state.get("items") if isinstance(state, dict) else None
    items = items_raw if isinstance(items_raw, dict) else {}

    cleaned: dict[str, dict[str, Any]] = {}
    for item_key, payload in items.items():
        if not isinstance(item_key, str) or not isinstance(payload, dict):
            continue
        try:
            first_seen = int(payload.get("first_seen", 0) or 0)
            last_seen = int(payload.get("last_seen", first_seen) or first_seen)
            event_count = int(payload.get("event_count", 1) or 1)
        except (TypeError, ValueError):
            continue
        if retention > 0 and max(first_seen, last_seen) < keep_after:
            continue
        cleaned[item_key] = {
            "first_seen": max(0, first_seen),
            "last_seen": max(0, last_seen),
            "event_count": max(1, event_count),
        }

    existing = cleaned.get(key)
    if isinstance(existing, dict):
        existing["last_seen"] = now_ts
        existing["event_count"] = int(existing.get("event_count", 1) or 1) + 1
        cleaned[key] = existing
        state["items"] = cleaned
        state["updated_at"] = utc_now()
        save_media_first_seen_state(state)
        return False, "media_first_seen_repeat"

    cleaned[key] = {
        "first_seen": now_ts,
        "last_seen": now_ts,
        "event_count": 1,
    }
    state["items"] = cleaned
    state["updated_at"] = utc_now()
    save_media_first_seen_state(state)
    return True, "media_first_seen_new"


def overseerr_request(method: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    final_path = path if path.startswith("/") else f"/{path}"
    url = f"{OVERSEERR_URL}{final_path}"
    if query:
        encoded = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        if encoded:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}{encoded}"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Api-Key": OVERSEERR_API_KEY,
        },
        method=method.upper(),
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="ignore")
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def overseerr_ready_match(query_title: str) -> tuple[bool, str]:
    data = overseerr_request(
        method="GET",
        path="/api/v1/search",
        query={"query": query_title, "page": 1, "language": "en"},
    )
    results_raw = data.get("results")
    results = results_raw if isinstance(results_raw, list) else []
    if not results:
        return False, "ready_gate_no_search_results"

    query_norm = normalize_media_name(query_title)
    best_score = -1
    best_status = -1
    matched_title = ""

    for item in results:
        if not isinstance(item, dict):
            continue
        candidate_title = str(item.get("title") or item.get("name") or "").strip()
        if not candidate_title:
            continue
        candidate_norm = normalize_media_name(candidate_title)
        if not candidate_norm:
            continue

        score = 0
        if query_norm and candidate_norm == query_norm:
            score = 3
        elif query_norm and (query_norm in candidate_norm or candidate_norm in query_norm):
            score = 2
        elif candidate_title.lower() == query_title.lower().strip():
            score = 2
        else:
            continue

        media_info_raw = item.get("mediaInfo")
        media_info = media_info_raw if isinstance(media_info_raw, dict) else {}
        try:
            status = int(media_info.get("status", 0) or 0)
        except (TypeError, ValueError):
            status = 0

        if score > best_score or (score == best_score and status > best_status):
            best_score = score
            best_status = status
            matched_title = candidate_title

    if best_score < 0:
        return False, "ready_gate_no_matching_title"
    if best_status >= max(1, TELEGRAM_MEDIA_READY_STATUS_REQUIRED):
        return True, f"ready_verified:{matched_title}:status={best_status}"
    return False, f"ready_not_confirmed:{matched_title}:status={best_status}"


def media_ready_gate_decision(topic: str, title: str, message: str) -> tuple[bool, str]:
    if topic != "media-alerts":
        return True, "not_media_topic"
    if not TELEGRAM_MEDIA_READY_GATE_ENABLED:
        return True, "ready_gate_disabled"
    if not is_ready_signal_message(title=title, message=message):
        return True, "not_ready_signal"
    if not OVERSEERR_URL or not OVERSEERR_API_KEY:
        return False, "ready_gate_missing_overseerr_config"

    query_title = extract_media_title_for_ready_check(title=title, message=message)
    if not query_title:
        return False, "ready_gate_no_title"

    try:
        return overseerr_ready_match(query_title=query_title)
    except Exception as exc:
        return False, f"ready_gate_lookup_error:{exc}"


def should_skip_media_noise_event(title: str, message: str, critical: bool) -> bool:
    if critical:
        return False
    if not TELEGRAM_MEDIA_NOISE_FILTER_ENABLED:
        return False
    blob = f"{title} {message}".strip().lower()
    if not blob:
        return False
    return any(marker in blob for marker in TELEGRAM_MEDIA_NOISE_MARKERS)


def extract_target_user_ids_from_message(message: str) -> tuple[set[int], str]:
    lines = str(message or "").splitlines()
    targets: set[int] = set()
    kept_lines: list[str] = []

    for raw_line in lines:
        line = str(raw_line or "").strip()
        lowered = line.lower()
        if lowered.startswith("notify_targets=") or lowered.startswith("notify_target="):
            raw_values = line.split("=", 1)[1] if "=" in line else ""
            for token in re.split(r"[,\s]+", raw_values.strip()):
                if not token:
                    continue
                try:
                    parsed = int(token)
                except ValueError:
                    continue
                if parsed > 0:
                    targets.add(parsed)
            continue
        kept_lines.append(raw_line)

    cleaned = "\n".join(kept_lines).strip()
    return targets, cleaned


def pick_recipients(
    registry: dict,
    delivery_state: dict,
    category: str,
    critical: bool,
    target_user_ids: set[int] | None = None,
) -> tuple[list[int], int, bool]:
    users = registry.get("users") if isinstance(registry, dict) else {}
    if not isinstance(users, dict):
        return [], 0, False

    normal_targets: set[int] = set()
    emergency_targets: set[int] = set()
    quarantined_count = 0
    cleared_quarantine = False
    delivery_users = delivery_state.get("users") if isinstance(delivery_state, dict) else {}
    if not isinstance(delivery_users, dict):
        delivery_users = {}
    now_ts = int(time.time())
    bypass_media_quarantine = False
    if str(category or "").strip().lower() == "media":
        bypass_media_quarantine, bypass_state_changed = consume_media_quarantine_bypass_once(
            delivery_state=delivery_state,
            now_ts=now_ts,
        )
        if bypass_state_changed:
            cleared_quarantine = True

    for user_id, rec in users.items():
        if not isinstance(rec, dict):
            continue
        if str(rec.get("status", "active")) != "active":
            continue

        try:
            numeric_user_id = int(user_id)
        except (TypeError, ValueError):
            continue

        if target_user_ids is not None and numeric_user_id not in target_user_ids:
            continue

        delivery_record = delivery_users.get(str(numeric_user_id))
        if not isinstance(delivery_record, dict):
            delivery_record = {}

        if TELEGRAM_AUTO_QUARANTINE_ENABLED and not bypass_media_quarantine:
            last_reason = str(delivery_record.get("notify_delivery_last_reason", "")).strip().lower()
            fail_streak = int(delivery_record.get("notify_delivery_fail_streak", 0) or 0)
            threshold = quarantine_threshold_for_reason(last_reason)
            until_ts = user_quarantine_until_ts(delivery_record)
            if is_quarantine_reason(last_reason) and until_ts <= now_ts and fail_streak >= threshold:
                delivery_record["notify_quarantine_until"] = now_ts + max(300, TELEGRAM_AUTO_QUARANTINE_SECONDS)
                delivery_record["notify_quarantine_reason"] = f"{last_reason}:preemptive_streak={fail_streak}"
                delivery_record["notify_quarantine_count"] = int(delivery_record.get("notify_quarantine_count", 0) or 0) + 1
                delivery_record["updated_at"] = utc_now()
                delivery_users[str(numeric_user_id)] = delivery_record
                delivery_state["users"] = delivery_users
                delivery_state["updated_at"] = utc_now()
                quarantined_count += 1
                continue

        if not bypass_media_quarantine and is_user_quarantined(delivery_record, now_ts=now_ts):
            quarantined_count += 1
            continue

        until_ts = user_quarantine_until_ts(delivery_record)
        if until_ts > 0 and until_ts <= now_ts:
            delivery_record["notify_quarantine_until"] = 0
            delivery_record["notify_quarantine_reason"] = ""
            delivery_record["updated_at"] = utc_now()
            delivery_users[str(numeric_user_id)] = delivery_record
            delivery_state["users"] = delivery_users
            delivery_state["updated_at"] = utc_now()
            cleared_quarantine = True

        selected = normalize_topics(rec.get("notify_topics"))
        if target_user_ids is not None:
            wants_category = True
        else:
            wants_category = (
                category == "media"
                or "all" in selected
                or category in selected
                or (critical and "critical" in selected)
            )
        if wants_category:
            normal_targets.add(numeric_user_id)

        if critical and bool(rec.get("emergency_contact", False)):
            emergency_targets.add(numeric_user_id)

    if critical:
        return sorted(normal_targets | emergency_targets), quarantined_count, cleared_quarantine
    return sorted(normal_targets), quarantined_count, cleared_quarantine


def format_telegram_alert(
    topic: str,
    category: str,
    title: str,
    message: str,
    priority: int,
    critical: bool,
    incident_id: str,
    event_count: int,
    collapsed_update: bool,
) -> str:
    importance = importance_from_event(priority=priority, critical=critical)
    summary = summarize_for_humans(
        title=title,
        message=message,
        limit=TELEGRAM_NOTIFY_MAX_MESSAGE_CHARS,
    )
    update_suffix = f"Updates: {max(1, int(event_count or 1))}" if int(event_count or 1) > 1 else ""

    if collapsed_update:
        lines = [
            "🔁 Incident update:",
            summary,
        ]
        if update_suffix:
            lines.append(update_suffix)
        lines.append(f"Incident ID: {incident_id}")
        return "\n".join(lines)

    if importance == "urgent":
        lines = [
            "🚨 This needs attention now.",
            summary,
            "Please check the system as soon as you can.",
        ]
        if update_suffix:
            lines.append(update_suffix)
        lines.append(f"Incident ID: {incident_id}")
        return "\n".join(lines)

    if importance == "important":
        lines = [
            "⚠️ Important update:",
            summary,
        ]
        if update_suffix:
            lines.append(update_suffix)
        lines.append(f"Incident ID: {incident_id}")
        return "\n".join(lines)

    lines = [
        "ℹ️ Quick update:",
        summary,
    ]
    if update_suffix:
        lines.append(update_suffix)
    lines.append(f"Incident ID: {incident_id}")
    return "\n".join(lines)


def incident_message_target(incident: dict[str, Any], chat_id: int, now_ts: int) -> int | None:
    if not TELEGRAM_INCIDENT_COLLAPSE_ENABLED:
        return None

    try:
        event_count = int(incident.get("event_count", 0) or 0)
    except (TypeError, ValueError):
        event_count = 0
    if event_count <= 1:
        return None

    try:
        last_notified_at = int(incident.get("last_notified_at", 0) or 0)
    except (TypeError, ValueError):
        last_notified_at = 0
    if last_notified_at <= 0:
        return None
    if now_ts - last_notified_at > max(60, TELEGRAM_INCIDENT_COLLAPSE_WINDOW_SECONDS):
        return None

    targets = incident.get("message_targets")
    if not isinstance(targets, dict):
        return None
    target = targets.get(str(chat_id))
    if not isinstance(target, dict):
        return None
    try:
        message_id = int(target.get("message_id", 0) or 0)
    except (TypeError, ValueError):
        message_id = 0
    return message_id if message_id > 0 else None


def update_incident_message_target(incident: dict[str, Any], chat_id: int, message_id: int, now_ts: int) -> None:
    if message_id <= 0:
        return
    targets = incident.get("message_targets")
    if not isinstance(targets, dict):
        targets = {}
    targets[str(chat_id)] = {
        "message_id": int(message_id),
        "updated_at": int(now_ts),
    }
    if len(targets) > 200:
        ordered = sorted(
            (
                (key, value)
                for key, value in targets.items()
                if isinstance(value, dict)
            ),
            key=lambda item: int(item[1].get("updated_at", 0) or 0),
            reverse=True,
        )
        targets = {key: value for key, value in ordered[:200]}
    incident["message_targets"] = targets


def fanout_to_telegram(topic: str, title: str, message: str, priority: int):
    target_user_ids, cleaned_message = extract_target_user_ids_from_message(message)
    message = cleaned_message

    probe_id = extract_notify_validate_probe_id(title=title, message=message)
    if not TELEGRAM_NOTIFICATIONS_ENABLED:
        print(f"telegram fanout skipped topic={topic} reason=notifications_disabled", flush=True)
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="notifications_disabled",
            priority=priority,
            critical=False,
            recipients=0,
            probe_id=probe_id,
        )
        return

    if not TELEGRAM_BOT_TOKEN:
        print(f"telegram fanout skipped topic={topic} reason=missing_token", flush=True)
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="missing_token",
            priority=priority,
            critical=False,
            recipients=0,
            probe_id=probe_id,
        )
        return
    category = TELEGRAM_NOTIFICATION_TOPICS.get(topic)
    if not category:
        return

    title_snippet = " ".join(str(title or "").split())[:40]
    blob = f"{title} {message}".strip().lower()
    if any(pattern in blob for pattern in TELEGRAM_NOTIFY_DROP_PATTERNS):
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason=drop_pattern title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="drop_pattern",
            priority=priority,
            critical=False,
            recipients=0,
            probe_id=probe_id,
        )
        return

    critical = is_critical_event(priority=priority, title=title, message=message)
    media_category = category == "media"
    if media_category and should_skip_media_noise_event(title=title, message=message, critical=critical):
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason=media_noise title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="media_noise",
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
        return

    ready_allowed, ready_reason = media_ready_gate_decision(topic=topic, title=title, message=message)
    if not ready_allowed:
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason={ready_reason} title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason=ready_reason,
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
        return

    first_seen_allowed, first_seen_reason = media_first_seen_decision(topic=topic, title=title, message=message)
    if not first_seen_allowed:
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason={first_seen_reason} title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason=first_seen_reason,
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
        return

    incident_id = build_incident_id(topic=topic, category=category, title=title, message=message)

    incident_state = load_incident_state()
    incident = upsert_incident(
        incident_state=incident_state,
        incident_id=incident_id,
        topic=topic,
        category=category,
        title=title,
        message=message,
        priority=priority,
        critical=critical,
    )
    suppression_reason = incident_suppression_reason(incident=incident, now_ts=int(time.time()))
    if suppression_reason:
        save_incident_state(incident_state)
        print(
            f"telegram fanout skipped topic={topic} incident_id={incident_id} category={category} priority={priority} reason={suppression_reason} title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason=suppression_reason,
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
        return

    if TELEGRAM_NOTIFY_CRITICAL_ONLY and not critical and not media_category:
        save_incident_state(incident_state)
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason=critical_only title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="critical_only",
            priority=priority,
            critical=False,
            recipients=0,
            probe_id=probe_id,
        )
        return

    if priority < TELEGRAM_NOTIFY_MIN_PRIORITY and not critical and not media_category:
        save_incident_state(incident_state)
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason=min_priority<{TELEGRAM_NOTIFY_MIN_PRIORITY} title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="min_priority",
            priority=priority,
            critical=False,
            recipients=0,
            probe_id=probe_id,
        )
        return

    dedupe_key = build_dedupe_key(
        topic=topic,
        category=category,
        title=title,
        message=message,
        priority=priority,
        critical=critical,
    )
    deduped, remaining = should_skip_dedup(topic=topic, key=dedupe_key)
    if deduped:
        save_incident_state(incident_state)
        print(
            f"telegram fanout skipped topic={topic} category={category} priority={priority} reason=dedupe ttl={remaining}s title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason="dedupe",
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
        return

    registry = load_user_registry()
    delivery_state = load_delivery_state()
    recipients, quarantined_count, cleared_quarantine = pick_recipients(
        registry=registry,
        delivery_state=delivery_state,
        category=category,
        critical=critical,
        target_user_ids=target_user_ids if target_user_ids else None,
    )
    if cleared_quarantine:
        save_delivery_state(delivery_state)

    if not recipients:
        no_recipient_reason = "no_recipients"
        if quarantined_count > 0:
            no_recipient_reason = "no_recipients_quarantined"
        print(
            f"telegram fanout topic={topic} category={category} priority={priority} critical={critical} recipients=0 quarantined={quarantined_count} title='{title_snippet}'",
            flush=True,
        )
        record_notify_event(
            topic=topic,
            result="skipped",
            reason=no_recipient_reason,
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
        save_incident_state(incident_state)
        return

    event_count_value = int(incident.get("event_count", 1) or 1)
    alert_text = format_telegram_alert(
        topic=topic,
        category=category,
        title=title,
        message=message,
        priority=priority,
        critical=critical,
        incident_id=incident_id,
        event_count=event_count_value,
        collapsed_update=False,
    )
    update_alert_text = format_telegram_alert(
        topic=topic,
        category=category,
        title=title,
        message=message,
        priority=priority,
        critical=critical,
        incident_id=incident_id,
        event_count=event_count_value,
        collapsed_update=True,
    )

    immediate_recipients: list[int] = []
    deferred_recipients: list[int] = []
    users_raw = registry.get("users") if isinstance(registry, dict) else {}
    users = users_raw if isinstance(users_raw, dict) else {}
    for chat_id in recipients:
        record = users.get(str(chat_id))
        enabled, start_hour, end_hour = parse_quiet_hours_for_category(record if isinstance(record, dict) else {}, category=category)
        if enabled and not critical and is_quiet_now(start_hour=start_hour, end_hour=end_hour):
            deferred_recipients.append(chat_id)
        else:
            immediate_recipients.append(chat_id)

    for chat_id in deferred_recipients:
        queue_deferred_digest_item(
            user_id=chat_id,
            topic=topic,
            category=category,
            title=title,
            message=message,
            priority=priority,
            incident_id=incident_id,
        )

    sent_count = 0
    failure_reasons: dict[str, int] = {}
    delivery_changed = False
    now_ts = int(time.time())
    for chat_id in immediate_recipients:
        edit_message_id = incident_message_target(incident=incident, chat_id=chat_id, now_ts=now_ts)
        message_text = update_alert_text if edit_message_id else alert_text
        sent, failure_reason, message_id, _used_edit = send_or_edit_telegram_message(
            chat_id=chat_id,
            text=message_text,
            edit_message_id=edit_message_id,
        )
        if update_delivery_state(delivery_state=delivery_state, user_id=chat_id, sent=sent, reason=failure_reason):
            delivery_changed = True
        if sent:
            sent_count += 1
            if message_id is not None:
                update_incident_message_target(incident=incident, chat_id=chat_id, message_id=message_id, now_ts=now_ts)
            continue
        failure_reasons[failure_reason] = failure_reasons.get(failure_reason, 0) + 1

    if delivery_changed:
        save_delivery_state(delivery_state)

    top_failure_reason = "send_error"
    if failure_reasons:
        top_failure_reason = sorted(failure_reasons.items(), key=lambda item: (-item[1], item[0]))[0][0]

    if sent_count <= 0:
        result = "rate_limited" if top_failure_reason == "rate_limited" else "failed"
        if deferred_recipients:
            result = "deferred"
            top_failure_reason = "quiet_hours"
        record_notify_event(
            topic=topic,
            result=result,
            reason=top_failure_reason,
            priority=priority,
            critical=critical,
            recipients=0,
            probe_id=probe_id,
        )
    elif sent_count < len(immediate_recipients):
        record_notify_event(
            topic=topic,
            result="sent_partial",
            reason=top_failure_reason,
            priority=priority,
            critical=critical,
            recipients=sent_count,
            probe_id=probe_id,
        )
        incident["last_notified_at"] = int(time.time())
    elif deferred_recipients:
        record_notify_event(
            topic=topic,
            result="sent_partial",
            reason="quiet_hours",
            priority=priority,
            critical=critical,
            recipients=sent_count,
            probe_id=probe_id,
        )
        incident["last_notified_at"] = int(time.time())
    else:
        record_notify_event(
            topic=topic,
            result="sent",
            reason="",
            priority=priority,
            critical=critical,
            recipients=sent_count,
            probe_id=probe_id,
        )
        incident["last_notified_at"] = int(time.time())

    save_incident_state(incident_state)

    print(
        f"telegram fanout topic={topic} incident_id={incident_id} category={category} priority={priority} critical={critical} recipients={sent_count} deferred={len(deferred_recipients)} quarantined={quarantined_count} title='{title_snippet}'",
        flush=True,
    )

def http_get(url: str, max_lines: int = 80):
    lines: list[str] = []
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
        for _ in range(max(1, max_lines)):
            raw = response.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            lines.append(line)
    return "\n".join(lines)

def http_post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as response:
        response.read()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {}

    now_ts = int(time.time())
    for topic in ALL_WATCHED_TOPICS:
        if topic not in state:
            state[topic] = {"last_time": now_ts, "last_id": ""}

    return state

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def parse_events(text: str):
    events: list[dict[str, Any]] = []
    blob = str(text or "").strip()
    if not blob:
        return events

    decoder = json.JSONDecoder()
    index = 0
    length = len(blob)
    while index < length:
        while index < length and blob[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            parsed, next_index = decoder.raw_decode(blob, index)
        except json.JSONDecodeError:
            newline_index = blob.find("\n", index)
            if newline_index == -1:
                break
            line = blob[index:newline_index].strip()
            index = newline_index + 1
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("event") == "message":
                events.append(parsed)
            continue

        index = next_index
        if isinstance(parsed, dict) and parsed.get("event") == "message":
            events.append(parsed)
    return events


def main():
    state = load_state()
    poll_timeout = max(2, min(30, POLL_REQUEST_TIMEOUT_SECONDS))
    while True:
        try:
            flush_deferred_digests(load_user_registry())
        except Exception as exc:
            print(f"bridge digest flush error: {exc}", flush=True)

        for topic in ALL_WATCHED_TOPICS:
            try:
                topic_state = state.get(topic, {}) if isinstance(state.get(topic, {}), dict) else {}
                try:
                    last_time = int(topic_state.get("last_time", 0) or 0)
                except (TypeError, ValueError):
                    last_time = 0

                if last_time > 0:
                    poll_url = f"{NTFY_BASE}/{topic}/json?since={last_time}&poll=1&timeout={poll_timeout}s"
                else:
                    poll_url = f"{NTFY_BASE}/{topic}/json?poll=1&timeout={poll_timeout}s"

                text = http_get(poll_url)
                events = parse_events(text)
                last_time = state.get(topic, {}).get("last_time", 0)
                last_id = state.get(topic, {}).get("last_id", "")

                for ev in events:
                    ev_time = int(ev.get("time", 0))
                    ev_id = ev.get("id", "")
                    if ev_time < last_time or (ev_time == last_time and ev_id == last_id):
                        continue

                    title = str(ev.get("title", "")).strip()
                    message = str(ev.get("message", ""))
                    if topic == "ai-replies" and should_ignore_reply_event(title, message):
                        state[topic] = {"last_time": ev_time, "last_id": ev_id}
                        save_state(state)
                        last_time = ev_time
                        last_id = ev_id
                        continue

                    priority = int(ev.get("priority", 3) or 3)

                    webhook_path = TOPICS.get(topic)
                    if webhook_path:
                        payload = {
                            "topic": topic,
                            "id": ev_id,
                            "time": ev_time,
                            "title": title,
                            "message": message,
                            "priority": priority,
                        }
                        http_post_json(f"{N8N_BASE}{webhook_path}", payload)

                    fanout_to_telegram(
                        topic=topic,
                        title=title,
                        message=message,
                        priority=priority,
                    )

                    state[topic] = {"last_time": ev_time, "last_id": ev_id}
                    save_state(state)
                    last_time = ev_time
                    last_id = ev_id
            except Exception as exc:
                if isinstance(exc, TimeoutError):
                    continue
                if isinstance(exc, urllib.error.URLError) and isinstance(getattr(exc, "reason", None), TimeoutError):
                    continue
                if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                    time.sleep(1)
                    continue
                print(f"bridge error topic={topic}: {exc}", flush=True)
                traceback.print_exc()

        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
