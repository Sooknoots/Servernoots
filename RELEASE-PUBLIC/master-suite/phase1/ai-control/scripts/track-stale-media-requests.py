#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUEST_STATUS_MAP = {
    1: "PENDING",
    2: "APPROVED",
    3: "DECLINED",
    4: "PROCESSING",
    5: "COMPLETED",
}

MEDIA_STATUS_MAP = {
    1: "UNKNOWN",
    2: "PENDING",
    3: "PROCESSING",
    4: "PARTIAL",
    5: "AVAILABLE",
}


def request_json(url: str, api_key: str, timeout: int = 20, method: str = "GET") -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="ignore")
        return json.loads(body) if body else {}


def resolve_overseerr_base(base: str, api_key: str, timeout: int) -> str:
    candidates: list[str] = []
    normalized = (base or "").strip().rstrip("/")
    if normalized:
        candidates.append(normalized)
    if "http://127.0.0.1:5055" not in candidates:
        candidates.append("http://127.0.0.1:5055")

    for candidate in candidates:
        try:
            request_json(f"{candidate}/api/v1/status", api_key=api_key, timeout=timeout)
            return candidate
        except Exception:
            continue
    raise RuntimeError("Unable to reach Overseerr API with current OVERSEERR_URL/OVERSEERR_API_KEY")


def parse_iso_ts_to_epoch(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return 0


def request_status_label(code: Any) -> str:
    try:
        numeric = int(code)
    except Exception:
        return f"UNKNOWN({code})"
    return REQUEST_STATUS_MAP.get(numeric, f"UNKNOWN({code})")


def media_status_label(code: Any) -> str:
    try:
        numeric = int(code)
    except Exception:
        return f"S{code}"
    return MEDIA_STATUS_MAP.get(numeric, f"S{code}")


def post_ntfy(base: str, topic: str, title: str, message: str, priority: str = "default") -> tuple[bool, str]:
    url = f"{base.rstrip('/')}/{topic.lstrip('/')}"
    payload = message.encode("utf-8", errors="ignore")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": "warning,clock1",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            return True, "sent"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def utc_now_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def parse_bool_env(value: Any, default: bool) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def parse_fix_actions(raw: str) -> set[str]:
    return {chunk.strip().lower() for chunk in str(raw or "").split(",") if chunk.strip()}


def load_fix_proposals(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {"version": 1, "updated_at": utc_now_ts(), "proposals": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "updated_at": utc_now_ts(), "proposals": []}

    proposals = payload.get("proposals") if isinstance(payload, dict) else None
    if not isinstance(proposals, list):
        proposals = []
    return {
        "version": 1,
        "updated_at": int(payload.get("updated_at") or utc_now_ts()) if isinstance(payload, dict) else utc_now_ts(),
        "proposals": proposals,
    }


def save_fix_proposals(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = utc_now_ts()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_fix_candidate_key(row: dict[str, Any], action: str) -> str:
    req_id = str(row.get("request_id") or "").strip()
    if req_id:
        return f"{action}:request:{req_id}"
    return f"{action}:{incident_key(row)}"


def build_fix_plan_key(candidate_keys: list[str], plan_meta: dict[str, Any]) -> str:
    payload = {
        "candidate_keys": sorted(candidate_keys),
        "plan_meta": plan_meta,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def build_fix_approval_token(proposal_id: str, secret: str) -> str:
    raw = f"{proposal_id}:{secret}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:24]


def append_audit_events(path: Path, events: list[dict[str, Any]]) -> int:
    if not events:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return len(events)


def select_fix_action(row: dict[str, Any], auto_approve_pending: bool, fix_retry_enabled: bool) -> str:
    req_code = int(row.get("request_status_code") or 0)
    if auto_approve_pending and req_code == 1:
        return "approve_pending"
    if fix_retry_enabled and req_code in {2, 4}:
        return "retry_request"
    return "none"


def evaluate_fix_candidate(
    row: dict[str, Any],
    diagnosis: dict[str, Any],
    auto_approve_pending: bool,
    fix_retry_enabled: bool,
    allowed_actions: set[str],
    fix_min_age_minutes: int,
    fix_retry_min_since_update_minutes: int,
    fix_require_admin_target: bool,
) -> dict[str, Any]:
    req_id = row.get("request_id")
    age_minutes = int(row.get("age_minutes") or 0)
    since_update_minutes = int(row.get("since_update_minutes") or 0)
    escalation_target = str(diagnosis.get("escalation_target") or "admin")
    action = select_fix_action(
        row=row,
        auto_approve_pending=auto_approve_pending,
        fix_retry_enabled=fix_retry_enabled,
    )

    if action == "none":
        return {"candidate": False, "action": action, "detail": "no_safe_fix_available"}

    if action not in allowed_actions:
        return {"candidate": False, "action": action, "detail": "guardrail_action_not_allowed"}
    if fix_require_admin_target and escalation_target != "admin":
        return {"candidate": False, "action": action, "detail": "guardrail_target_not_admin"}
    if age_minutes < max(1, int(fix_min_age_minutes or 1)):
        return {"candidate": False, "action": action, "detail": "guardrail_age_below_min"}

    if action == "retry_request":
        if str(diagnosis.get("reason") or "") != "approved_but_not_available":
            return {"candidate": False, "action": action, "detail": "no_safe_fix_available"}
        if since_update_minutes < max(1, int(fix_retry_min_since_update_minutes or 1)):
            return {"candidate": False, "action": action, "detail": "guardrail_retry_update_below_min"}

    if action == "approve_pending" and not auto_approve_pending:
        return {"candidate": False, "action": action, "detail": "no_safe_fix_available"}
    if req_id is None:
        return {"candidate": False, "action": action, "detail": "missing_request_id"}
    return {"candidate": True, "action": action, "detail": "candidate"}


def parse_escalation_levels(raw: str, fallback_min: int) -> list[int]:
    parts = [chunk.strip() for chunk in str(raw or "").split(",")]
    values: list[int] = []
    for part in parts:
        if not part:
            continue
        try:
            minute = int(part)
        except Exception:
            continue
        if minute > 0:
            values.append(minute)

    if not values:
        values = [max(1, fallback_min), max(120, fallback_min * 2), max(240, fallback_min * 4)]

    deduped = sorted(set(values))
    return deduped


def age_level(age_minutes: int, levels: list[int]) -> int:
    level = 0
    for threshold in levels:
        if age_minutes >= threshold:
            level += 1
    return level


def incident_key(row: dict[str, Any]) -> str:
    req_id = str(row.get("request_id") or "").strip()
    if req_id:
        return f"request:{req_id}"

    raw = "|".join(
        [
            str(row.get("type") or "").strip().lower(),
            str(row.get("title") or "").strip().lower(),
            str(row.get("requester_id") or row.get("requester") or "").strip().lower(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"synthetic:{digest}"


def load_tracker_state(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {
                "version": 1,
                "updated_at": utc_now_ts(),
                "incidents": {},
                "suppression_windows": {
                    "requester_last_notified_ts": {},
                    "title_last_notified_ts": {},
                },
            }
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": 1,
            "updated_at": utc_now_ts(),
            "incidents": {},
            "suppression_windows": {
                "requester_last_notified_ts": {},
                "title_last_notified_ts": {},
            },
        }

    incidents = payload.get("incidents") if isinstance(payload, dict) else None
    if not isinstance(incidents, dict):
        incidents = {}

    suppression_raw = payload.get("suppression_windows") if isinstance(payload, dict) else None
    suppression = suppression_raw if isinstance(suppression_raw, dict) else {}

    requester_raw = suppression.get("requester_last_notified_ts") if isinstance(suppression, dict) else None
    requester_map = requester_raw if isinstance(requester_raw, dict) else {}

    title_raw = suppression.get("title_last_notified_ts") if isinstance(suppression, dict) else None
    title_map = title_raw if isinstance(title_raw, dict) else {}

    return {
        "version": 1,
        "updated_at": int(payload.get("updated_at") or utc_now_ts()) if isinstance(payload, dict) else utc_now_ts(),
        "incidents": incidents,
        "suppression_windows": {
            "requester_last_notified_ts": requester_map,
            "title_last_notified_ts": title_map,
        },
    }


def save_tracker_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_ts()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_suppression_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return " ".join(text.split())


def suppression_requester_key(item: dict[str, Any]) -> str:
    requester_id = normalize_suppression_value(item.get("requester_id"))
    if requester_id:
        return f"id:{requester_id}"
    requester = normalize_suppression_value(item.get("requester"))
    if requester:
        return f"name:{requester}"
    return ""


def suppression_title_key(item: dict[str, Any]) -> str:
    title = normalize_suppression_value(item.get("title"))
    if not title:
        return ""
    media_type = normalize_suppression_value(item.get("type"))
    return f"{media_type}:{title}" if media_type else title


def get_suppression_maps(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    suppression_raw = state.get("suppression_windows")
    suppression = suppression_raw if isinstance(suppression_raw, dict) else {}

    requester_raw = suppression.get("requester_last_notified_ts")
    requester_map: dict[str, Any] = requester_raw if isinstance(requester_raw, dict) else {}

    title_raw = suppression.get("title_last_notified_ts")
    title_map: dict[str, Any] = title_raw if isinstance(title_raw, dict) else {}

    state["suppression_windows"] = {
        "requester_last_notified_ts": requester_map,
        "title_last_notified_ts": title_map,
    }
    return requester_map, title_map


def apply_notify_suppression_windows(
    items: list[dict[str, Any]],
    state: dict[str, Any],
    now_ts: int,
    suppress_by_requester_minutes: int,
    suppress_by_title_minutes: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    requester_window_seconds = max(0, int(suppress_by_requester_minutes or 0)) * 60
    title_window_seconds = max(0, int(suppress_by_title_minutes or 0)) * 60
    if requester_window_seconds <= 0 and title_window_seconds <= 0:
        return items, {"requester": 0, "title": 0}

    requester_map, title_map = get_suppression_maps(state)
    filtered: list[dict[str, Any]] = []
    suppressed = {"requester": 0, "title": 0}

    for item in items:
        incident_raw = item.get("incident")
        incident = incident_raw if isinstance(incident_raw, dict) else {}

        suppress_reason = ""
        if requester_window_seconds > 0:
            requester_key = suppression_requester_key(item)
            if requester_key:
                last_ts = int(requester_map.get(requester_key) or 0)
                if last_ts > 0 and (now_ts - last_ts) < requester_window_seconds:
                    suppress_reason = "requester_window_active"
                    suppressed["requester"] += 1

        if not suppress_reason and title_window_seconds > 0:
            title_key = suppression_title_key(item)
            if title_key:
                last_ts = int(title_map.get(title_key) or 0)
                if last_ts > 0 and (now_ts - last_ts) < title_window_seconds:
                    suppress_reason = "title_window_active"
                    suppressed["title"] += 1

        if suppress_reason:
            incident["should_notify"] = False
            incident["suppress_reason"] = str(incident.get("suppress_reason") or suppress_reason)
            item["incident"] = incident
            continue

        filtered.append(item)

    return filtered, suppressed


def apply_suppression_markers(
    items: list[dict[str, Any]],
    state: dict[str, Any],
    now_ts: int,
    suppress_by_requester_minutes: int,
    suppress_by_title_minutes: int,
) -> None:
    requester_window_seconds = max(0, int(suppress_by_requester_minutes or 0)) * 60
    title_window_seconds = max(0, int(suppress_by_title_minutes or 0)) * 60
    if requester_window_seconds <= 0 and title_window_seconds <= 0:
        return

    requester_map, title_map = get_suppression_maps(state)

    for item in items:
        if requester_window_seconds > 0:
            requester_key = suppression_requester_key(item)
            if requester_key:
                requester_map[requester_key] = now_ts
        if title_window_seconds > 0:
            title_key = suppression_title_key(item)
            if title_key:
                title_map[title_key] = now_ts

    prune_before_ts = now_ts - max(86400, max(requester_window_seconds, title_window_seconds) * 4)
    for key, value in list(requester_map.items()):
        if int(value or 0) < prune_before_ts:
            requester_map.pop(key, None)
    for key, value in list(title_map.items()):
        if int(value or 0) < prune_before_ts:
            title_map.pop(key, None)

    state["suppression_windows"] = {
        "requester_last_notified_ts": requester_map,
        "title_last_notified_ts": title_map,
    }


def update_state_for_stale(
    stale_items: list[dict[str, Any]],
    state: dict[str, Any],
    levels: list[int],
    now_ts: int,
    min_realert_minutes: int,
) -> tuple[list[dict[str, Any]], int]:
    incidents = state.setdefault("incidents", {})
    if not isinstance(incidents, dict):
        incidents = {}
        state["incidents"] = incidents

    active_keys: set[str] = set()

    for item in stale_items:
        key = incident_key(item)
        active_keys.add(key)
        current_level = age_level(int(item.get("age_minutes") or 0), levels)

        record_raw = incidents.get(key)
        record: dict[str, Any] = record_raw if isinstance(record_raw, dict) else {}

        prior_status = str(record.get("status") or "new")
        prior_notified_level = int(record.get("last_notified_level") or 0)
        last_notified_ts = int(record.get("last_notified_ts") or 0)
        snoozed_until = int(record.get("snoozed_until") or 0)

        if prior_status != "active":
            record["first_seen_ts"] = now_ts
            record["reopened_ts"] = now_ts if prior_status == "resolved" else record.get("reopened_ts")
            record["acked"] = False
            record["acked_ts"] = 0
            record["acked_by"] = ""
            record["ack_note"] = ""
            record["snoozed_until"] = 0
            record["snoozed_by"] = ""
            record["snooze_note"] = ""
        else:
            record["first_seen_ts"] = int(record.get("first_seen_ts") or now_ts)

        should_notify = prior_status != "active" or current_level > prior_notified_level
        suppress_reason = ""
        cooldown_seconds = max(0, int(min_realert_minutes or 0)) * 60
        if should_notify and prior_status == "active" and cooldown_seconds > 0 and last_notified_ts > 0:
            if (now_ts - last_notified_ts) < cooldown_seconds:
                should_notify = False
                suppress_reason = "cooldown_active"
        if snoozed_until > now_ts:
            should_notify = False
            suppress_reason = "snoozed"

        record["status"] = "active"
        record["last_seen_ts"] = now_ts
        record["resolved_ts"] = 0
        record["title"] = str(item.get("title") or "")
        record["type"] = str(item.get("type") or "")
        record["request_id"] = str(item.get("request_id") or "")
        record["requester"] = str(item.get("requester") or "")
        record["max_level_seen"] = max(int(record.get("max_level_seen") or 0), current_level)

        incidents[key] = record

        item["incident"] = {
            "key": key,
            "status_before": prior_status,
            "current_level": current_level,
            "last_notified_level": prior_notified_level,
            "should_notify": should_notify,
            "snoozed_until": snoozed_until,
            "acked": bool(record.get("acked")),
            "suppress_reason": suppress_reason,
            "last_notified_ts": last_notified_ts,
        }

    resolved_count = 0
    for key, value in list(incidents.items()):
        record = value if isinstance(value, dict) else {}
        if str(record.get("status") or "") != "active":
            continue
        if key in active_keys:
            continue
        record["status"] = "resolved"
        record["resolved_ts"] = now_ts
        incidents[key] = record
        resolved_count += 1

    return stale_items, resolved_count


def apply_notification_markers(items: list[dict[str, Any]], state: dict[str, Any], now_ts: int) -> None:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    for item in items:
        incident_raw = item.get("incident")
        incident: dict[str, Any] = incident_raw if isinstance(incident_raw, dict) else {}
        key = str(incident.get("key") or "")
        if not key:
            continue
        record_raw = incidents.get(key)
        if not isinstance(record_raw, dict):
            continue
        current_level = int(incident.get("current_level") or 0)
        record_raw["last_notified_level"] = max(int(record_raw.get("last_notified_level") or 0), current_level)
        record_raw["last_notified_ts"] = now_ts
        record_raw["notify_count"] = int(record_raw.get("notify_count") or 0) + 1
        incidents[key] = record_raw
    state["incidents"] = incidents


def prune_resolved_incidents(state: dict[str, Any], now_ts: int, retention_days: int) -> int:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    retention_seconds = max(1, retention_days) * 86400
    removed = 0
    for key, value in list(incidents.items()):
        record = value if isinstance(value, dict) else {}
        if str(record.get("status") or "") != "resolved":
            continue
        resolved_ts = int(record.get("resolved_ts") or 0)
        if resolved_ts <= 0:
            continue
        if (now_ts - resolved_ts) > retention_seconds:
            incidents.pop(key, None)
            removed += 1
    state["incidents"] = incidents
    return removed


def list_incidents(state: dict[str, Any], status_filter: str) -> list[dict[str, Any]]:
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
                "key": key,
                "status": status,
                "title": str(record.get("title") or ""),
                "type": str(record.get("type") or ""),
                "request_id": str(record.get("request_id") or ""),
                "requester": str(record.get("requester") or ""),
                "first_seen_ts": int(record.get("first_seen_ts") or 0),
                "last_seen_ts": int(record.get("last_seen_ts") or 0),
                "resolved_ts": int(record.get("resolved_ts") or 0),
                "last_notified_level": int(record.get("last_notified_level") or 0),
                "max_level_seen": int(record.get("max_level_seen") or 0),
                "notify_count": int(record.get("notify_count") or 0),
                "acked": bool(record.get("acked")),
                "acked_ts": int(record.get("acked_ts") or 0),
                "acked_by": str(record.get("acked_by") or ""),
                "ack_note": str(record.get("ack_note") or ""),
                "snoozed_until": int(record.get("snoozed_until") or 0),
                "snoozed_by": str(record.get("snoozed_by") or ""),
                "snooze_note": str(record.get("snooze_note") or ""),
            }
        )

    rows.sort(key=lambda item: int(item.get("last_seen_ts") or 0), reverse=True)
    return rows


def perform_incident_action(
    state: dict[str, Any],
    action: str,
    incident_key_value: str,
    now_ts: int,
    actor: str,
    note: str,
    snooze_minutes: int,
) -> tuple[bool, str, dict[str, Any]]:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    record_raw = incidents.get(incident_key_value)
    if not isinstance(record_raw, dict):
        return False, f"incident_not_found:{incident_key_value}", {}

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

    incidents[incident_key_value] = record
    state["incidents"] = incidents

    response = {
        "key": incident_key_value,
        "status": str(record.get("status") or ""),
        "acked": bool(record.get("acked")),
        "acked_ts": int(record.get("acked_ts") or 0),
        "snoozed_until": int(record.get("snoozed_until") or 0),
        "resolved_ts": int(record.get("resolved_ts") or 0),
        "closed_manually": bool(record.get("closed_manually")),
    }
    return True, "ok", response


def build_kpi_digest(state: dict[str, Any], now_ts: int, window_hours: int) -> dict[str, Any]:
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


def render_kpi_digest_text(kpi: dict[str, Any], state_file: str) -> str:
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
        f"- state_file: {state_file}",
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


def build_history_export_rows(state: dict[str, Any], now_ts: int, window_hours: int, limit: int) -> list[dict[str, Any]]:
    incidents_raw = state.get("incidents")
    incidents: dict[str, Any] = incidents_raw if isinstance(incidents_raw, dict) else {}
    window_start = now_ts - (max(1, window_hours) * 3600)

    rows: list[dict[str, Any]] = []
    for key, value in incidents.items():
        record = value if isinstance(value, dict) else {}
        first_seen_ts = int(record.get("first_seen_ts") or 0)
        last_seen_ts = int(record.get("last_seen_ts") or 0)
        resolved_ts = int(record.get("resolved_ts") or 0)
        acked_ts = int(record.get("acked_ts") or 0)
        last_notified_ts = int(record.get("last_notified_ts") or 0)
        reopened_ts = int(record.get("reopened_ts") or 0)

        last_event_ts = max(first_seen_ts, last_seen_ts, resolved_ts, acked_ts, last_notified_ts, reopened_ts)
        if last_event_ts <= 0 or last_event_ts < window_start:
            continue

        rows.append(
            {
                "exported_ts": now_ts,
                "window_hours": max(1, window_hours),
                "key": str(key),
                "status": str(record.get("status") or ""),
                "title": str(record.get("title") or ""),
                "type": str(record.get("type") or ""),
                "request_id": str(record.get("request_id") or ""),
                "requester": str(record.get("requester") or ""),
                "first_seen_ts": first_seen_ts,
                "last_seen_ts": last_seen_ts,
                "resolved_ts": resolved_ts,
                "reopened_ts": reopened_ts,
                "acked": bool(record.get("acked")),
                "acked_ts": acked_ts,
                "snoozed_until": int(record.get("snoozed_until") or 0),
                "last_notified_level": int(record.get("last_notified_level") or 0),
                "max_level_seen": int(record.get("max_level_seen") or 0),
                "notify_count": int(record.get("notify_count") or 0),
                "last_notified_ts": last_notified_ts,
                "closed_manually": bool(record.get("closed_manually")),
                "age_minutes_since_first_seen": int(max(0, now_ts - first_seen_ts) / 60) if first_seen_ts > 0 else 0,
                "age_minutes_since_last_seen": int(max(0, now_ts - last_seen_ts) / 60) if last_seen_ts > 0 else 0,
                "last_event_ts": last_event_ts,
            }
        )

    rows.sort(key=lambda row: int(row.get("last_event_ts") or 0), reverse=True)
    return rows[: max(1, int(limit or 1))]


def write_history_export(path: Path, export_format: str, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if export_format == "ndjson":
        text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        if text:
            text += "\n"
        path.write_text(text, encoding="utf-8")
        return

    if export_format == "csv":
        fieldnames = [
            "exported_ts",
            "window_hours",
            "key",
            "status",
            "title",
            "type",
            "request_id",
            "requester",
            "first_seen_ts",
            "last_seen_ts",
            "resolved_ts",
            "reopened_ts",
            "acked",
            "acked_ts",
            "snoozed_until",
            "last_notified_level",
            "max_level_seen",
            "notify_count",
            "last_notified_ts",
            "closed_manually",
            "age_minutes_since_first_seen",
            "age_minutes_since_last_seen",
            "last_event_ts",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key) for key in fieldnames})
        return

    raise ValueError(f"Unsupported export format: {export_format}")


def build_rows(base: str, api_key: str, take: int, timeout: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"take": max(1, take), "skip": 0, "sort": "added"})
    payload = request_json(f"{base}/api/v1/request?{query}", api_key=api_key, timeout=timeout)
    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list):
        results = []

    now = int(datetime.now(tz=timezone.utc).timestamp())
    rows: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue

        media_raw = item.get("media")
        requested_by_raw = item.get("requestedBy")
        media: dict[str, Any] = media_raw if isinstance(media_raw, dict) else {}
        requested_by: dict[str, Any] = requested_by_raw if isinstance(requested_by_raw, dict) else {}

        req_code = int(item.get("status") or 0)
        media_code = int(media.get("status") or 0)
        created_ts = parse_iso_ts_to_epoch(item.get("createdAt"))
        updated_ts = parse_iso_ts_to_epoch(item.get("updatedAt"))

        unresolved = req_code in {1, 2, 4} and media_code != 5
        age_minutes = int(max(0, now - created_ts) / 60) if created_ts > 0 else 0
        since_update_minutes = int(max(0, now - updated_ts) / 60) if updated_ts > 0 else 0

        title = str(
            media.get("title")
            or media.get("name")
            or media.get("tmdbId")
            or "unknown"
        )

        requester = str(
            requested_by.get("displayName")
            or requested_by.get("username")
            or requested_by.get("email")
            or "unknown"
        )

        rows.append(
            {
                "request_id": item.get("id"),
                "title": title,
                "type": str(item.get("type") or media.get("mediaType") or "unknown"),
                "request_status_code": req_code,
                "request_status": request_status_label(req_code),
                "media_status_code": media_code,
                "media_status": media_status_label(media_code),
                "created_at": item.get("createdAt"),
                "updated_at": item.get("updatedAt"),
                "created_ts": created_ts,
                "updated_ts": updated_ts,
                "age_minutes": age_minutes,
                "since_update_minutes": since_update_minutes,
                "requester": requester,
                "requester_id": requested_by.get("id"),
                "is_unresolved": unresolved,
            }
        )

    return rows


def diagnose(row: dict[str, Any], stale_minutes: int, arr_health: dict[str, Any]) -> dict[str, Any]:
    req_code = int(row.get("request_status_code") or 0)
    media_code = int(row.get("media_status_code") or 0)
    age_minutes = int(row.get("age_minutes") or 0)
    since_update_minutes = int(row.get("since_update_minutes") or 0)

    target = "admin"
    reason = "pipeline_delayed"
    suggested_actions: list[str] = []

    if req_code == 1:
        reason = "awaiting_admin_approval"
        target = "admin"
        suggested_actions = [
            "Admin: review queue in Overseerr or Telegram /pending",
            "Admin: approve request if valid (/approve <id> in Telegram, or Overseerr UI)",
        ]
    elif req_code in {2, 4} and media_code in {2, 3, 4}:
        reason = "approved_but_not_available"
        if not arr_health.get("arr_config_ok", False):
            target = "admin"
            suggested_actions = [
                "Admin: fix Radarr/Sonarr configuration in Overseerr settings",
                "Admin: verify download client/indexers are healthy",
            ]
        elif since_update_minutes >= max(stale_minutes * 2, 120):
            target = "admin"
            suggested_actions = [
                "Admin: inspect stalled queue in Radarr/Sonarr/qBittorrent",
                "Admin: trigger search or restart stuck import jobs",
            ]
        else:
            target = "user"
            suggested_actions = [
                "User: verify title/year quality expectations are correct",
                "Admin: inspect queue if request remains stalled",
            ]
    else:
        reason = "unknown_stale_state"
        target = "admin"
        suggested_actions = ["Admin: inspect request status and logs manually"]

    if age_minutes >= max(stale_minutes * 4, 240):
        suggested_actions.append("Admin: treat as incident if still unresolved after manual check")

    return {
        "reason": reason,
        "escalation_target": target,
        "suggested_actions": suggested_actions,
    }


def probe_arr_health(base: str, api_key: str, timeout: int) -> dict[str, Any]:
    status = {
        "radarr_count": 0,
        "sonarr_count": 0,
        "arr_config_ok": False,
        "error": "",
    }
    try:
        radarr = request_json(f"{base}/api/v1/settings/radarr", api_key=api_key, timeout=timeout)
        sonarr = request_json(f"{base}/api/v1/settings/sonarr", api_key=api_key, timeout=timeout)

        radarr_items = radarr if isinstance(radarr, list) else []
        sonarr_items = sonarr if isinstance(sonarr, list) else []

        status["radarr_count"] = len(radarr_items)
        status["sonarr_count"] = len(sonarr_items)
        status["arr_config_ok"] = (len(radarr_items) + len(sonarr_items)) > 0
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"
    return status


def try_auto_fix(
    base: str,
    api_key: str,
    row: dict[str, Any],
    diagnosis: dict[str, Any],
    auto_approve_pending: bool,
    fix_retry_enabled: bool,
    timeout: int,
    allowed_actions: set[str],
    max_fixes_per_run: int,
    fixes_attempted_so_far: int,
    fix_min_age_minutes: int,
    fix_retry_min_since_update_minutes: int,
    fix_require_admin_target: bool,
    fix_dry_run: bool,
) -> dict[str, Any]:
    req_id = row.get("request_id")
    age_minutes = int(row.get("age_minutes") or 0)
    since_update_minutes = int(row.get("since_update_minutes") or 0)
    escalation_target = str(diagnosis.get("escalation_target") or "admin")

    action = select_fix_action(
        row=row,
        auto_approve_pending=auto_approve_pending,
        fix_retry_enabled=fix_retry_enabled,
    )

    if action == "none":
        return {
            "attempted": False,
            "applied": False,
            "action": action,
            "detail": "no_safe_fix_available",
        }

    if fixes_attempted_so_far >= max(1, int(max_fixes_per_run or 1)):
        return {
            "attempted": False,
            "applied": False,
            "action": action,
            "detail": "guardrail_fix_cap_reached",
        }

    if action not in allowed_actions:
        return {
            "attempted": False,
            "applied": False,
            "action": action,
            "detail": "guardrail_action_not_allowed",
        }

    if fix_require_admin_target and escalation_target != "admin":
        return {
            "attempted": False,
            "applied": False,
            "action": action,
            "detail": "guardrail_target_not_admin",
        }

    if age_minutes < max(1, int(fix_min_age_minutes or 1)):
        return {
            "attempted": False,
            "applied": False,
            "action": action,
            "detail": "guardrail_age_below_min",
        }

    if action == "retry_request":
        if str(diagnosis.get("reason") or "") != "approved_but_not_available":
            return {
                "attempted": False,
                "applied": False,
                "action": action,
                "detail": "no_safe_fix_available",
            }
        if since_update_minutes < max(1, int(fix_retry_min_since_update_minutes or 1)):
            return {
                "attempted": False,
                "applied": False,
                "action": action,
                "detail": "guardrail_retry_update_below_min",
            }

    if action == "approve_pending" and not auto_approve_pending:
        return {
            "attempted": False,
            "applied": False,
            "action": action,
            "detail": "no_safe_fix_available",
        }

    if req_id is None:
        return {
            "attempted": True,
            "applied": False,
            "action": action,
            "detail": "missing_request_id",
        }

    if fix_dry_run:
        if action == "retry_request":
            return {
                "attempted": True,
                "applied": False,
                "action": action,
                "detail": "dry_run_would_retry",
            }
        return {
            "attempted": True,
            "applied": False,
            "action": action,
            "detail": "dry_run_would_approve",
        }

    try:
        endpoint = "approve" if action == "approve_pending" else "retry"
        request_json(
            f"{base}/api/v1/request/{req_id}/{endpoint}",
            api_key=api_key,
            timeout=timeout,
            method="POST",
        )
        return {
            "attempted": True,
            "applied": True,
            "action": action,
            "detail": "approved" if action == "approve_pending" else "retried",
        }
    except Exception as exc:
        return {
            "attempted": True,
            "applied": False,
            "action": action,
            "detail": f"{type(exc).__name__}: {exc}",
        }


def build_dry_drill_items(
    stale_minutes: int,
    arr_health: dict[str, Any],
    admin_age_minutes: int,
    user_age_minutes: int,
) -> list[dict[str, Any]]:
    admin_row = {
        "request_id": "DRILL-A1",
        "title": "Dry Drill Admin Approval",
        "type": "movie",
        "request_status_code": 1,
        "request_status": request_status_label(1),
        "media_status_code": 2,
        "media_status": media_status_label(2),
        "created_at": "dry-drill",
        "updated_at": "dry-drill",
        "created_ts": 0,
        "updated_ts": 0,
        "age_minutes": max(1, admin_age_minutes),
        "since_update_minutes": 10,
        "requester": "dry-admin-requester",
        "requester_id": "dry-admin",
        "is_unresolved": True,
    }
    user_row = {
        "request_id": "DRILL-U1",
        "title": "Dry Drill User Clarification",
        "type": "tv",
        "request_status_code": 2,
        "request_status": request_status_label(2),
        "media_status_code": 3,
        "media_status": media_status_label(3),
        "created_at": "dry-drill",
        "updated_at": "dry-drill",
        "created_ts": 0,
        "updated_ts": 0,
        "age_minutes": max(1, user_age_minutes),
        "since_update_minutes": 30,
        "requester": "dry-user-requester",
        "requester_id": "dry-user",
        "is_unresolved": True,
    }

    items: list[dict[str, Any]] = []
    for row in (admin_row, user_row):
        diagnosis = diagnose(row=row, stale_minutes=max(1, stale_minutes), arr_health=arr_health)
        items.append(
            {
                **row,
                "diagnosis": diagnosis,
                "fix": {
                    "attempted": False,
                    "applied": False,
                    "action": "none",
                    "detail": "dry_drill",
                },
            }
        )
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Track stale unresolved Overseerr requests and diagnose/escalate")
    parser.add_argument("--take", type=int, default=100, help="How many recent requests to inspect (default: 100)")
    parser.add_argument("--stale-minutes", type=int, default=60, help="Pending age threshold in minutes (default: 60)")
    parser.add_argument("--timeout", type=int, default=20, help="Overseerr API timeout seconds (default: 20)")
    parser.add_argument("--attempt-fixes", action="store_true", help="Attempt configured safe remediations")
    parser.add_argument(
        "--auto-approve-pending",
        action="store_true",
        help="When --attempt-fixes is enabled, auto-approve stale requests in PENDING status",
    )
    parser.add_argument(
        "--fix-actions",
        default=os.getenv("REQTRACK_FIX_ACTIONS", "approve_pending"),
        help="Comma-separated remediation actions allowed for --attempt-fixes (default: approve_pending; optional: retry_request)",
    )
    parser.add_argument(
        "--fix-retry-enabled",
        dest="fix_retry_enabled",
        action="store_true",
        help="Enable safe retry remediation class for stale approved/processing requests",
    )
    parser.add_argument(
        "--no-fix-retry-enabled",
        dest="fix_retry_enabled",
        action="store_false",
        help="Disable safe retry remediation class",
    )
    parser.add_argument(
        "--max-fixes-per-run",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_MAX_FIXES_PER_RUN", "3") or "3")),
        help="Maximum remediation attempts per tracker run when --attempt-fixes is enabled (default: 3)",
    )
    parser.add_argument(
        "--fix-min-age-minutes",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_FIX_MIN_AGE_MINUTES", "120") or "120")),
        help="Minimum request age required before remediation is attempted (default: 120)",
    )
    parser.add_argument(
        "--fix-retry-min-since-update-minutes",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_FIX_RETRY_MIN_SINCE_UPDATE_MINUTES", "180") or "180")),
        help="Minimum minutes since request update required for retry_request remediation (default: 180)",
    )
    parser.add_argument(
        "--fix-require-admin-target",
        dest="fix_require_admin_target",
        action="store_true",
        help="Require diagnosis escalation target=admin before remediation attempts",
    )
    parser.add_argument(
        "--no-fix-require-admin-target",
        dest="fix_require_admin_target",
        action="store_false",
        help="Allow remediation attempts regardless of diagnosis escalation target",
    )
    parser.add_argument(
        "--fix-dry-run",
        dest="fix_dry_run",
        action="store_true",
        help="Evaluate remediation eligibility and report would-fix actions without mutating Overseerr",
    )
    parser.add_argument(
        "--no-fix-dry-run",
        dest="fix_dry_run",
        action="store_false",
        help="Disable remediation dry-run mode",
    )
    parser.add_argument(
        "--fix-approval-mode",
        choices=["direct", "propose", "apply"],
        default=os.getenv("REQTRACK_FIX_APPROVAL_MODE", "direct"),
        help="Remediation approval mode when --attempt-fixes is enabled (default: direct)",
    )
    parser.add_argument(
        "--fix-approval-token",
        default=os.getenv("REQTRACK_FIX_APPROVAL_TOKEN", ""),
        help="Approval token for --fix-approval-mode apply",
    )
    parser.add_argument(
        "--fix-approval-secret",
        default=os.getenv("REQTRACK_FIX_APPROVAL_SECRET", ""),
        help="Signing secret for remediation proposal/apply token validation",
    )
    parser.add_argument(
        "--fix-proposal-ttl-minutes",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_FIX_PROPOSAL_TTL_MINUTES", "60") or "60")),
        help="TTL minutes for remediation proposals in propose/apply mode (default: 60)",
    )
    parser.add_argument(
        "--fix-proposal-file",
        default=os.getenv("REQTRACK_FIX_PROPOSAL_FILE", "logs/media-request-tracker-fix-proposals.json"),
        help="Proposal state file used by remediation approval flow",
    )
    parser.add_argument(
        "--fix-audit-file",
        default=os.getenv("REQTRACK_FIX_AUDIT_FILE", "logs/media-request-tracker-fix-audit.ndjson"),
        help="NDJSON audit sink for remediation decision events",
    )
    parser.add_argument(
        "--fix-audit-enabled",
        dest="fix_audit_enabled",
        action="store_true",
        help="Enable remediation audit NDJSON writes",
    )
    parser.add_argument(
        "--no-fix-audit-enabled",
        dest="fix_audit_enabled",
        action="store_false",
        help="Disable remediation audit NDJSON writes",
    )
    parser.add_argument(
        "--fix-actor",
        default=os.getenv("REQTRACK_FIX_ACTOR", "reqtrack"),
        help="Actor label attached to remediation audit events",
    )
    parser.add_argument("--emit-ntfy", action="store_true", help="Send stale summary to ntfy admin/user topics")
    parser.add_argument("--dry-drill", action="store_true", help="Inject synthetic stale items for alert-path validation")
    parser.add_argument(
        "--dry-drill-stateful",
        action="store_true",
        help="When used with --dry-drill, apply normal incident dedupe/escalation state logic",
    )
    parser.add_argument(
        "--dry-drill-admin-age-minutes",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_DRY_DRILL_ADMIN_AGE_MINUTES", "70") or "70")),
        help="Synthetic admin-item age for dry drill (default: 70)",
    )
    parser.add_argument(
        "--dry-drill-user-age-minutes",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_DRY_DRILL_USER_AGE_MINUTES", "80") or "80")),
        help="Synthetic user-item age for dry drill (default: 80)",
    )
    parser.add_argument(
        "--escalation-levels",
        default=os.getenv("REQTRACK_ESCALATION_LEVELS", "60,120,240"),
        help="Comma-separated minute thresholds for alert ladder levels (default: 60,120,240)",
    )
    parser.add_argument(
        "--min-realert-minutes",
        type=int,
        default=max(0, int(os.getenv("REQTRACK_MIN_REALERT_MINUTES", "0") or "0")),
        help="Minimum minutes between repeat alerts for an already-active incident (default: 0)",
    )
    parser.add_argument(
        "--max-notify-candidates",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_MAX_NOTIFY_CANDIDATES", "25") or "25")),
        help="Maximum incidents to notify per run after sorting by level/age (default: 25)",
    )
    parser.add_argument(
        "--max-admin-lines",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_MAX_ADMIN_LINES", "20") or "20")),
        help="Maximum incident lines included in admin ntfy body (default: 20)",
    )
    parser.add_argument(
        "--max-user-lines",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_MAX_USER_LINES", "10") or "10")),
        help="Maximum incident lines included in user ntfy body (default: 10)",
    )
    parser.add_argument(
        "--min-user-notify-level",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_MIN_USER_NOTIFY_LEVEL", "1") or "1")),
        help="Minimum escalation level required before user-topic ntfy is sent for an incident (default: 1)",
    )
    parser.add_argument(
        "--suppress-by-requester-minutes",
        type=int,
        default=max(0, int(os.getenv("REQTRACK_SUPPRESS_BY_REQUESTER_MINUTES", "0") or "0")),
        help="Suppress notifications for same requester within this many minutes (default: 0 disabled)",
    )
    parser.add_argument(
        "--suppress-by-title-minutes",
        type=int,
        default=max(0, int(os.getenv("REQTRACK_SUPPRESS_BY_TITLE_MINUTES", "0") or "0")),
        help="Suppress notifications for same title/type within this many minutes (default: 0 disabled)",
    )
    parser.add_argument(
        "--state-file",
        default=os.getenv("REQTRACK_STATE_FILE", "logs/media-request-tracker-state.json"),
        help="State file path for dedupe/escalation tracking",
    )
    parser.add_argument(
        "--state-retention-days",
        type=int,
        default=int(os.getenv("REQTRACK_STATE_RETENTION_DAYS", "30") or "30"),
        help="Days to retain resolved incidents in state before pruning (default: 30)",
    )
    parser.add_argument(
        "--incident-action",
        choices=["list", "ack", "snooze", "unsnooze", "close"],
        help="Operate on tracker incidents stored in state file",
    )
    parser.add_argument("--incident-key", help="Incident key for incident action (required for ack/snooze/unsnooze/close)")
    parser.add_argument(
        "--incident-filter",
        choices=["active", "resolved", "all"],
        default="active",
        help="Status filter for --incident-action list (default: active)",
    )
    parser.add_argument(
        "--incident-by",
        default=os.getenv("REQTRACK_INCIDENT_BY", "operator"),
        help="Actor name for incident actions",
    )
    parser.add_argument("--incident-note", default="", help="Optional note for incident actions")
    parser.add_argument(
        "--snooze-minutes",
        type=int,
        default=int(os.getenv("REQTRACK_SNOOZE_MINUTES", "120") or "120"),
        help="Snooze duration for --incident-action snooze (default: 120)",
    )
    parser.add_argument(
        "--kpi-report",
        action="store_true",
        help="Emit KPI digest from tracker state only (no Overseerr API calls)",
    )
    parser.add_argument(
        "--kpi-window-hours",
        type=int,
        default=int(os.getenv("REQTRACK_KPI_WINDOW_HOURS", "24") or "24"),
        help="Time window in hours for KPI rollups (default: 24)",
    )
    parser.add_argument(
        "--emit-kpi-ntfy",
        action="store_true",
        help="When used with --kpi-report, send KPI digest to admin topic",
    )
    parser.add_argument(
        "--export-history-format",
        choices=["ndjson", "csv"],
        help="When used with --kpi-report, export incident history rows in the selected format",
    )
    parser.add_argument(
        "--export-history-file",
        default=os.getenv("REQTRACK_EXPORT_HISTORY_FILE", ""),
        help="Output file path for --export-history-format",
    )
    parser.add_argument(
        "--export-history-window-hours",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_EXPORT_HISTORY_WINDOW_HOURS", "168") or "168")),
        help="Window in hours for export row inclusion based on last event timestamp (default: 168)",
    )
    parser.add_argument(
        "--export-history-limit",
        type=int,
        default=max(1, int(os.getenv("REQTRACK_EXPORT_HISTORY_LIMIT", "1000") or "1000")),
        help="Maximum number of export rows to write (default: 1000)",
    )
    parser.add_argument("--ntfy-base", default=os.getenv("NTFY_BASE", "http://localhost:8091"), help="ntfy base URL")
    parser.add_argument("--admin-topic", default=os.getenv("NTFY_ALERT_TOPIC", "ops-alerts"), help="Admin ntfy topic")
    parser.add_argument("--user-topic", default=os.getenv("MEDIA_ALERTS_TOPIC", "media-alerts"), help="User ntfy topic")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.set_defaults(
        fix_retry_enabled=parse_bool_env(os.getenv("REQTRACK_FIX_RETRY_ENABLED", "false"), False),
        fix_require_admin_target=parse_bool_env(os.getenv("REQTRACK_FIX_REQUIRE_ADMIN_TARGET", "true"), True),
        fix_dry_run=parse_bool_env(os.getenv("REQTRACK_FIX_DRY_RUN", "false"), False),
        fix_audit_enabled=parse_bool_env(os.getenv("REQTRACK_FIX_AUDIT_ENABLED", "true"), True),
    )
    args = parser.parse_args()

    levels = parse_escalation_levels(raw=args.escalation_levels, fallback_min=max(1, args.stale_minutes))
    fix_actions = parse_fix_actions(args.fix_actions)
    now_ts = utc_now_ts()
    state_path = Path(args.state_file)

    if args.kpi_report:
        state = load_tracker_state(state_path)
        kpi = build_kpi_digest(state=state, now_ts=now_ts, window_hours=max(1, args.kpi_window_hours))
        export_history_format = str(args.export_history_format or "").strip().lower()
        export_history_file_raw = str(args.export_history_file or "").strip()
        export_history_file = Path(export_history_file_raw) if export_history_file_raw else None
        export_result: dict[str, Any] = {
            "enabled": False,
            "format": "",
            "file": "",
            "rows": 0,
            "window_hours": max(1, int(args.export_history_window_hours or 1)),
            "limit": max(1, int(args.export_history_limit or 1)),
            "detail": "not_requested",
        }

        if export_history_file and not export_history_format:
            suffix = export_history_file.suffix.lower()
            if suffix in {".ndjson", ".jsonl"}:
                export_history_format = "ndjson"
            elif suffix == ".csv":
                export_history_format = "csv"

        if export_history_format and not export_history_file:
            print("ERROR: --export-history-file is required when --export-history-format is set")
            return 2

        if export_history_file and not export_history_format:
            print("ERROR: could not infer export format from file extension; set --export-history-format")
            return 2

        if export_history_format and export_history_file:
            rows = build_history_export_rows(
                state=state,
                now_ts=now_ts,
                window_hours=max(1, int(args.export_history_window_hours or 1)),
                limit=max(1, int(args.export_history_limit or 1)),
            )
            write_history_export(path=export_history_file, export_format=export_history_format, rows=rows)
            export_result = {
                "enabled": True,
                "format": export_history_format,
                "file": str(export_history_file),
                "rows": len(rows),
                "window_hours": max(1, int(args.export_history_window_hours or 1)),
                "limit": max(1, int(args.export_history_limit or 1)),
                "detail": "written",
            }

        output = {
            "state_file": str(state_path),
            "kpi": kpi,
            "history_export": export_result,
            "ntfy": {
                "sent": False,
                "detail": "not_requested",
            },
        }

        if args.emit_kpi_ntfy:
            body = render_kpi_digest_text(kpi=kpi, state_file=str(state_path))
            sent, detail = post_ntfy(
                base=args.ntfy_base,
                topic=args.admin_topic,
                title="Media Request Tracker KPI digest",
                message=body,
                priority="default",
            )
            output["ntfy"] = {"sent": sent, "detail": detail}

        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        print(render_kpi_digest_text(kpi=kpi, state_file=str(state_path)))
        if export_result.get("enabled"):
            print(
                "history_export="
                + f"format={export_result.get('format')} "
                + f"file={export_result.get('file')} "
                + f"rows={export_result.get('rows')}"
            )
        if args.emit_kpi_ntfy:
            print(f"ntfy_sent={output['ntfy']['sent']} detail={output['ntfy']['detail']}")
        return 0

    if args.incident_action:
        state = load_tracker_state(state_path)
        if args.incident_action == "list":
            rows = list_incidents(state=state, status_filter=args.incident_filter)
            output = {
                "state_file": str(state_path),
                "action": "list",
                "filter": args.incident_filter,
                "count": len(rows),
                "incidents": rows,
            }
            if args.json:
                print(json.dumps(output, ensure_ascii=False, indent=2))
                return 0

            print(f"state_file={state_path}")
            print(f"incident_count={len(rows)} filter={args.incident_filter}")
            if not rows:
                print("No incidents matched filter.")
                return 0

            print(f"{'status':<9} {'acked':<5} {'snooze':<10} {'lvl':<4} {'key':<28} {'title':<30}")
            print("-" * 110)
            for item in rows[:200]:
                snoozed_until = int(item.get("snoozed_until") or 0)
                print(
                    f"{str(item.get('status')):<9} "
                    f"{'Y' if item.get('acked') else 'N':<5} "
                    f"{str(snoozed_until):<10} "
                    f"{str(item.get('last_notified_level')):<4} "
                    f"{str(item.get('key'))[:28]:<28} "
                    f"{str(item.get('title'))[:30]:<30}"
                )
            return 0

        if not args.incident_key:
            print("ERROR: --incident-key is required for incident actions other than list")
            return 2

        ok, detail, row = perform_incident_action(
            state=state,
            action=args.incident_action,
            incident_key_value=args.incident_key,
            now_ts=now_ts,
            actor=str(args.incident_by or "operator"),
            note=str(args.incident_note or ""),
            snooze_minutes=max(1, args.snooze_minutes),
        )
        if not ok:
            if args.json:
                print(json.dumps({"ok": False, "detail": detail, "state_file": str(state_path)}, ensure_ascii=False, indent=2))
            else:
                print(f"ERROR: {detail}")
            return 1

        save_tracker_state(state_path, state)
        output = {
            "ok": True,
            "detail": detail,
            "action": args.incident_action,
            "state_file": str(state_path),
            "incident": row,
        }
        if args.json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        print(f"state_file={state_path}")
        print(f"action={args.incident_action} key={row.get('key')}")
        print(
            "updated="
            + f"status={row.get('status')} "
            + f"acked={row.get('acked')} "
            + f"snoozed_until={row.get('snoozed_until')} "
            + f"resolved_ts={row.get('resolved_ts')}"
        )
        return 0

    rows: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    base = os.getenv("OVERSEERR_URL", "http://127.0.0.1:5055").strip().rstrip("/") or "http://127.0.0.1:5055"
    fix_approval_mode = str(args.fix_approval_mode or "direct")
    fix_approval_token = str(args.fix_approval_token or "").strip()
    fix_approval_secret = str(args.fix_approval_secret or "").strip()
    fix_proposal_path = Path(str(args.fix_proposal_file or "logs/media-request-tracker-fix-proposals.json"))
    fix_audit_path = Path(str(args.fix_audit_file or "logs/media-request-tracker-fix-audit.ndjson"))
    fix_actor = str(args.fix_actor or "reqtrack")
    approval_flow: dict[str, Any] = {
        "mode": fix_approval_mode,
        "token_required": fix_approval_mode == "apply",
        "token_provided": bool(fix_approval_token),
        "proposal_file": str(fix_proposal_path),
        "proposal_created": False,
        "proposal_applied": False,
        "detail": "not_requested",
        "proposal_id": "",
        "proposal_expires_ts": 0,
        "candidate_count": 0,
    }
    fix_audit_summary: dict[str, Any] = {
        "enabled": bool(args.fix_audit_enabled),
        "file": str(fix_audit_path),
        "events_written": 0,
        "detail": "not_requested",
    }
    arr_health = {
        "radarr_count": 0,
        "sonarr_count": 0,
        "arr_config_ok": True,
        "error": "",
    }

    if args.dry_drill:
        stale = build_dry_drill_items(
            stale_minutes=max(1, args.stale_minutes),
            arr_health=arr_health,
            admin_age_minutes=max(1, args.dry_drill_admin_age_minutes),
            user_age_minutes=max(1, args.dry_drill_user_age_minutes),
        )
    else:
        api_key = os.getenv("OVERSEERR_API_KEY", "").strip()
        if not api_key:
            print("ERROR: OVERSEERR_API_KEY is not set")
            return 1

        base = resolve_overseerr_base(os.getenv("OVERSEERR_URL", "http://127.0.0.1:5055"), api_key=api_key, timeout=args.timeout)
        arr_health = probe_arr_health(base=base, api_key=api_key, timeout=args.timeout)
        rows = build_rows(base=base, api_key=api_key, take=max(1, args.take), timeout=args.timeout)

        for row in rows:
            if not bool(row.get("is_unresolved")):
                continue
            if int(row.get("age_minutes") or 0) < max(1, args.stale_minutes):
                continue

            diagnosis = diagnose(row=row, stale_minutes=max(1, args.stale_minutes), arr_health=arr_health)
            fix_result = {
                "attempted": False,
                "applied": False,
                "action": "none",
                "detail": "not_requested",
            }
            if args.attempt_fixes:
                eval_result = evaluate_fix_candidate(
                    row=row,
                    diagnosis=diagnosis,
                    auto_approve_pending=bool(args.auto_approve_pending),
                    fix_retry_enabled=bool(args.fix_retry_enabled),
                    allowed_actions=fix_actions,
                    fix_min_age_minutes=max(1, int(args.fix_min_age_minutes or 1)),
                    fix_retry_min_since_update_minutes=max(1, int(args.fix_retry_min_since_update_minutes or 1)),
                    fix_require_admin_target=bool(args.fix_require_admin_target),
                )
                fix_result = {
                    "attempted": False,
                    "applied": False,
                    "action": str(eval_result.get("action") or "approve_pending"),
                    "detail": str(eval_result.get("detail") or "not_requested"),
                }

            stale.append(
                {
                    **row,
                    "diagnosis": diagnosis,
                    "fix": fix_result,
                    "_fix_candidate": bool(fix_result.get("detail") == "candidate"),
                }
            )

        if args.attempt_fixes:
            if fix_approval_mode in {"propose", "apply"} and not fix_approval_secret:
                print("ERROR: --fix-approval-secret (or REQTRACK_FIX_APPROVAL_SECRET) is required for propose/apply mode")
                return 2

            candidate_items = [item for item in stale if bool(item.get("_fix_candidate"))]
            candidate_keys = [make_fix_candidate_key(item, str((item.get("fix") or {}).get("action") or "approve_pending")) for item in candidate_items]
            approval_flow["candidate_count"] = len(candidate_items)

            plan_meta = {
                "auto_approve_pending": bool(args.auto_approve_pending),
                "fix_retry_enabled": bool(args.fix_retry_enabled),
                "fix_actions": sorted(fix_actions),
                "max_fixes_per_run": max(1, int(args.max_fixes_per_run or 1)),
                "fix_min_age_minutes": max(1, int(args.fix_min_age_minutes or 1)),
                "fix_retry_min_since_update_minutes": max(1, int(args.fix_retry_min_since_update_minutes or 1)),
                "fix_require_admin_target": bool(args.fix_require_admin_target),
            }
            plan_key = build_fix_plan_key(candidate_keys=candidate_keys, plan_meta=plan_meta)

            if fix_approval_mode == "propose":
                if not candidate_items:
                    approval_flow["detail"] = "proposal_not_needed_no_candidates"
                else:
                    proposals_payload = load_fix_proposals(fix_proposal_path)
                    proposals_raw = proposals_payload.get("proposals")
                    proposals = proposals_raw if isinstance(proposals_raw, list) else []

                    proposal_id = hashlib.sha256(
                        f"{now_ts}:{plan_key}:{len(candidate_keys)}".encode("utf-8", errors="ignore")
                    ).hexdigest()[:20]
                    expires_ts = now_ts + (max(1, int(args.fix_proposal_ttl_minutes or 1)) * 60)
                    token = build_fix_approval_token(proposal_id=proposal_id, secret=fix_approval_secret)
                    proposals.append(
                        {
                            "id": proposal_id,
                            "created_ts": now_ts,
                            "expires_ts": expires_ts,
                            "used_ts": 0,
                            "plan_key": plan_key,
                            "candidate_keys": sorted(candidate_keys),
                        }
                    )
                    proposals_payload["proposals"] = proposals[-200:]
                    save_fix_proposals(fix_proposal_path, proposals_payload)

                    for item in candidate_items:
                        fix_raw = item.get("fix")
                        fix = dict(fix_raw) if isinstance(fix_raw, dict) else {}
                        fix["detail"] = "approval_proposed_pending_token"
                        item["fix"] = fix

                    approval_flow.update(
                        {
                            "proposal_created": True,
                            "detail": "proposal_created",
                            "proposal_id": proposal_id,
                            "proposal_expires_ts": expires_ts,
                            "approval_token": token,
                            "plan_key": plan_key,
                        }
                    )

            elif fix_approval_mode == "apply":
                if not fix_approval_token:
                    for item in candidate_items:
                        fix_raw = item.get("fix")
                        fix = dict(fix_raw) if isinstance(fix_raw, dict) else {}
                        fix["detail"] = "guardrail_approval_token_required"
                        item["fix"] = fix
                    approval_flow["detail"] = "approval_token_required"
                else:
                    proposals_payload = load_fix_proposals(fix_proposal_path)
                    proposals_raw = proposals_payload.get("proposals")
                    proposals = proposals_raw if isinstance(proposals_raw, list) else []
                    matched: dict[str, Any] | None = None
                    for proposal in proposals:
                        if not isinstance(proposal, dict):
                            continue
                        if int(proposal.get("used_ts") or 0) > 0:
                            continue
                        if int(proposal.get("expires_ts") or 0) < now_ts:
                            continue
                        proposal_id = str(proposal.get("id") or "")
                        if not proposal_id:
                            continue
                        expected = build_fix_approval_token(proposal_id=proposal_id, secret=fix_approval_secret)
                        if expected == fix_approval_token:
                            matched = proposal
                            break

                    if not matched:
                        for item in candidate_items:
                            fix_raw = item.get("fix")
                            fix = dict(fix_raw) if isinstance(fix_raw, dict) else {}
                            fix["detail"] = "guardrail_approval_token_invalid"
                            item["fix"] = fix
                        approval_flow["detail"] = "approval_token_invalid"
                    elif str(matched.get("plan_key") or "") != plan_key:
                        for item in candidate_items:
                            fix_raw = item.get("fix")
                            fix = dict(fix_raw) if isinstance(fix_raw, dict) else {}
                            fix["detail"] = "guardrail_approval_plan_mismatch"
                            item["fix"] = fix
                        approval_flow["detail"] = "approval_plan_mismatch"
                    else:
                        fixes_attempted_so_far = 0
                        for item in stale:
                            if not bool(item.get("_fix_candidate")):
                                continue
                            diagnosis_raw = item.get("diagnosis")
                            diagnosis = diagnosis_raw if isinstance(diagnosis_raw, dict) else {}
                            fix_result = try_auto_fix(
                                base=base,
                                api_key=api_key,
                                row=item,
                                diagnosis=diagnosis,
                                auto_approve_pending=bool(args.auto_approve_pending),
                                fix_retry_enabled=bool(args.fix_retry_enabled),
                                timeout=args.timeout,
                                allowed_actions=fix_actions,
                                max_fixes_per_run=max(1, int(args.max_fixes_per_run or 1)),
                                fixes_attempted_so_far=fixes_attempted_so_far,
                                fix_min_age_minutes=max(1, int(args.fix_min_age_minutes or 1)),
                                fix_retry_min_since_update_minutes=max(1, int(args.fix_retry_min_since_update_minutes or 1)),
                                fix_require_admin_target=bool(args.fix_require_admin_target),
                                fix_dry_run=False,
                            )
                            item["fix"] = fix_result
                            if bool(fix_result.get("attempted")):
                                fixes_attempted_so_far += 1

                        matched["used_ts"] = now_ts
                        proposals_payload["proposals"] = proposals
                        save_fix_proposals(fix_proposal_path, proposals_payload)
                        approval_flow.update(
                            {
                                "proposal_applied": True,
                                "detail": "approval_token_applied",
                                "proposal_id": str(matched.get("id") or ""),
                                "plan_key": plan_key,
                            }
                        )

            else:
                fixes_attempted_so_far = 0
                for item in stale:
                    if not bool(item.get("_fix_candidate")):
                        continue
                    diagnosis_raw = item.get("diagnosis")
                    diagnosis = diagnosis_raw if isinstance(diagnosis_raw, dict) else {}
                    fix_result = try_auto_fix(
                        base=base,
                        api_key=api_key,
                        row=item,
                        diagnosis=diagnosis,
                        auto_approve_pending=bool(args.auto_approve_pending),
                        fix_retry_enabled=bool(args.fix_retry_enabled),
                        timeout=args.timeout,
                        allowed_actions=fix_actions,
                        max_fixes_per_run=max(1, int(args.max_fixes_per_run or 1)),
                        fixes_attempted_so_far=fixes_attempted_so_far,
                        fix_min_age_minutes=max(1, int(args.fix_min_age_minutes or 1)),
                        fix_retry_min_since_update_minutes=max(1, int(args.fix_retry_min_since_update_minutes or 1)),
                        fix_require_admin_target=bool(args.fix_require_admin_target),
                        fix_dry_run=bool(args.fix_dry_run),
                    )
                    item["fix"] = fix_result
                    if bool(fix_result.get("attempted")):
                        fixes_attempted_so_far += 1
                approval_flow["detail"] = "direct_mode"

    admin_items = [item for item in stale if item.get("diagnosis", {}).get("escalation_target") == "admin"]
    user_items = [item for item in stale if item.get("diagnosis", {}).get("escalation_target") == "user"]

    resolved_count = 0
    pruned_count = 0
    state = {"version": 1, "updated_at": now_ts, "incidents": {}}
    notify_candidates: list[dict[str, Any]] = []
    suppressed_by_window = {"requester": 0, "title": 0}

    if args.dry_drill and not args.dry_drill_stateful:
        for item in stale:
            item["incident"] = {
                "key": incident_key(item),
                "status_before": "dry_drill",
                "current_level": age_level(int(item.get("age_minutes") or 0), levels),
                "last_notified_level": 0,
                "should_notify": True,
            }
        notify_candidates = list(stale)
    else:
        state = load_tracker_state(state_path)
        stale, resolved_count = update_state_for_stale(
            stale_items=stale,
            state=state,
            levels=levels,
            now_ts=now_ts,
            min_realert_minutes=max(0, int(args.min_realert_minutes or 0)),
        )
        notify_candidates = [
            item
            for item in stale
            if isinstance(item.get("incident"), dict) and bool(item.get("incident", {}).get("should_notify"))
        ]
        notify_candidates, suppressed_by_window = apply_notify_suppression_windows(
            items=notify_candidates,
            state=state,
            now_ts=now_ts,
            suppress_by_requester_minutes=max(0, int(args.suppress_by_requester_minutes or 0)),
            suppress_by_title_minutes=max(0, int(args.suppress_by_title_minutes or 0)),
        )

    notify_candidates = sorted(
        notify_candidates,
        key=lambda item: (
            int((item.get("incident") or {}).get("current_level") or 0),
            int(item.get("age_minutes") or 0),
        ),
        reverse=True,
    )
    dropped_due_cap = 0
    if len(notify_candidates) > max(1, int(args.max_notify_candidates or 1)):
        dropped_due_cap = len(notify_candidates) - max(1, int(args.max_notify_candidates or 1))
        notify_candidates = notify_candidates[: max(1, int(args.max_notify_candidates or 1))]

    notify_admin_items = [item for item in notify_candidates]
    notify_user_items = [
        item
        for item in notify_candidates
        if item.get("diagnosis", {}).get("escalation_target") == "user"
        and int((item.get("incident") or {}).get("current_level") or 0) >= max(1, int(args.min_user_notify_level or 1))
    ]

    ntfy = {
        "admin": {"sent": False, "detail": "not_requested"},
        "user": {"sent": False, "detail": "not_requested"},
    }
    fix_attempted_count = sum(
        1
        for item in stale
        if isinstance(item.get("fix"), dict) and bool(item.get("fix", {}).get("attempted"))
    )
    fix_applied_count = sum(
        1
        for item in stale
        if isinstance(item.get("fix"), dict) and bool(item.get("fix", {}).get("applied"))
    )
    if args.emit_ntfy and notify_admin_items:
        admin_lines = [
            f"stale_count={len(stale)} newly_notified={len(notify_admin_items)} threshold_minutes={args.stale_minutes}",
            f"overseerr={base}",
            f"levels={','.join(str(x) for x in levels)}",
            "",
        ]
        for item in notify_admin_items[: max(1, int(args.max_admin_lines or 1))]:
            fix = item.get("fix", {}) if isinstance(item.get("fix"), dict) else {}
            diagnosis = item.get("diagnosis", {}) if isinstance(item.get("diagnosis"), dict) else {}
            incident = item.get("incident", {}) if isinstance(item.get("incident"), dict) else {}
            admin_lines.append(
                " - "
                + f"id={item.get('request_id')} title={item.get('title')} "
                + f"req={item.get('request_status')} media={item.get('media_status')} "
                + f"age_min={item.get('age_minutes')} escalate={diagnosis.get('escalation_target')} "
                + f"reason={diagnosis.get('reason')} level={incident.get('current_level')} "
                + f"fix={fix.get('action')}:{fix.get('detail')}"
            )

        sent, detail = post_ntfy(
            base=args.ntfy_base,
            topic=args.admin_topic,
            title="Media Request Tracker: stale pending detected",
            message="\n".join(admin_lines),
            priority="high",
        )
        ntfy["admin"] = {"sent": sent, "detail": detail}

        if notify_user_items:
            user_lines = [
                "Some media requests are still processing.",
                "If your request details changed, resend with exact title/year.",
                "",
            ]
            for item in notify_user_items[: max(1, int(args.max_user_lines or 1))]:
                user_lines.append(
                    f"- {item.get('title')} ({item.get('type')}) status={item.get('request_status')}/{item.get('media_status')} age={item.get('age_minutes')}m"
                )
            sent, detail = post_ntfy(
                base=args.ntfy_base,
                topic=args.user_topic,
                title="Media request update",
                message="\n".join(user_lines),
                priority="default",
            )
            ntfy["user"] = {"sent": sent, "detail": detail}

    if (not args.dry_drill) or args.dry_drill_stateful:
        if ntfy["admin"]["sent"]:
            apply_notification_markers(items=notify_admin_items, state=state, now_ts=now_ts)
            apply_suppression_markers(
                items=notify_admin_items,
                state=state,
                now_ts=now_ts,
                suppress_by_requester_minutes=max(0, int(args.suppress_by_requester_minutes or 0)),
                suppress_by_title_minutes=max(0, int(args.suppress_by_title_minutes or 0)),
            )
        pruned_count = prune_resolved_incidents(state=state, now_ts=now_ts, retention_days=max(1, args.state_retention_days))
        save_tracker_state(state_path, state)

    if bool(args.attempt_fixes) and bool(args.fix_audit_enabled):
        audit_events: list[dict[str, Any]] = []
        for item in stale:
            fix_raw = item.get("fix")
            fix = fix_raw if isinstance(fix_raw, dict) else {}
            diagnosis_raw = item.get("diagnosis")
            diagnosis = diagnosis_raw if isinstance(diagnosis_raw, dict) else {}
            audit_events.append(
                {
                    "event_type": "remediation_decision",
                    "ts": now_ts,
                    "actor": fix_actor,
                    "overseerr_base": base,
                    "approval_mode": fix_approval_mode,
                    "request_id": str(item.get("request_id") or ""),
                    "title": str(item.get("title") or ""),
                    "type": str(item.get("type") or ""),
                    "request_status": str(item.get("request_status") or ""),
                    "media_status": str(item.get("media_status") or ""),
                    "age_minutes": int(item.get("age_minutes") or 0),
                    "diagnosis_target": str(diagnosis.get("escalation_target") or ""),
                    "diagnosis_reason": str(diagnosis.get("reason") or ""),
                    "fix_action": str(fix.get("action") or ""),
                    "fix_detail": str(fix.get("detail") or ""),
                    "fix_attempted": bool(fix.get("attempted")),
                    "fix_applied": bool(fix.get("applied")),
                    "state_file": str(state_path),
                    "dry_drill": bool(args.dry_drill),
                }
            )

        if approval_flow.get("proposal_created"):
            audit_events.append(
                {
                    "event_type": "remediation_proposal_created",
                    "ts": now_ts,
                    "actor": fix_actor,
                    "approval_mode": fix_approval_mode,
                    "proposal_id": str(approval_flow.get("proposal_id") or ""),
                    "proposal_expires_ts": int(approval_flow.get("proposal_expires_ts") or 0),
                    "candidate_count": int(approval_flow.get("candidate_count") or 0),
                    "detail": str(approval_flow.get("detail") or ""),
                    "state_file": str(state_path),
                }
            )

        if approval_flow.get("proposal_applied"):
            audit_events.append(
                {
                    "event_type": "remediation_proposal_applied",
                    "ts": now_ts,
                    "actor": fix_actor,
                    "approval_mode": fix_approval_mode,
                    "proposal_id": str(approval_flow.get("proposal_id") or ""),
                    "candidate_count": int(approval_flow.get("candidate_count") or 0),
                    "detail": str(approval_flow.get("detail") or ""),
                    "state_file": str(state_path),
                }
            )

        written = append_audit_events(fix_audit_path, audit_events)
        fix_audit_summary = {
            "enabled": True,
            "file": str(fix_audit_path),
            "events_written": written,
            "detail": "written" if written > 0 else "no_events",
        }

    for item in stale:
        item.pop("_fix_candidate", None)

    output = {
        "overseerr_base": base,
        "dry_drill": bool(args.dry_drill),
        "dry_drill_stateful": bool(args.dry_drill_stateful),
        "stale_threshold_minutes": args.stale_minutes,
        "escalation_levels": levels,
        "inspected": len(rows),
        "stale_count": len(stale),
        "notify_candidate_count": len(notify_candidates),
        "notify_candidate_dropped_due_cap": dropped_due_cap,
        "notify_candidate_suppressed_requester": int(suppressed_by_window.get("requester") or 0),
        "notify_candidate_suppressed_title": int(suppressed_by_window.get("title") or 0),
        "admin_escalations": len(admin_items),
        "user_prompts": len(user_items),
        "resolved_since_last_run": resolved_count,
        "state_pruned": pruned_count,
        "state_file": str(state_path),
        "arr_health": arr_health,
        "ntfy": ntfy,
        "noise_controls": {
            "min_realert_minutes": max(0, int(args.min_realert_minutes or 0)),
            "max_notify_candidates": max(1, int(args.max_notify_candidates or 1)),
            "max_admin_lines": max(1, int(args.max_admin_lines or 1)),
            "max_user_lines": max(1, int(args.max_user_lines or 1)),
            "min_user_notify_level": max(1, int(args.min_user_notify_level or 1)),
            "suppress_by_requester_minutes": max(0, int(args.suppress_by_requester_minutes or 0)),
            "suppress_by_title_minutes": max(0, int(args.suppress_by_title_minutes or 0)),
        },
        "remediation_guardrails": {
            "attempt_fixes": bool(args.attempt_fixes),
            "fix_approval_mode": fix_approval_mode,
            "auto_approve_pending": bool(args.auto_approve_pending),
            "fix_retry_enabled": bool(args.fix_retry_enabled),
            "fix_actions": sorted(fix_actions),
            "max_fixes_per_run": max(1, int(args.max_fixes_per_run or 1)),
            "fix_min_age_minutes": max(1, int(args.fix_min_age_minutes or 1)),
            "fix_retry_min_since_update_minutes": max(1, int(args.fix_retry_min_since_update_minutes or 1)),
            "fix_require_admin_target": bool(args.fix_require_admin_target),
            "fix_dry_run": bool(args.fix_dry_run),
        },
        "approval_flow": approval_flow,
        "fix_audit": fix_audit_summary,
        "fix_summary": {
            "attempted": fix_attempted_count,
            "applied": fix_applied_count,
        },
        "items": stale,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    print(f"overseerr_base={base}")
    print(f"inspected={len(rows)} stale_count={len(stale)} threshold_minutes={args.stale_minutes}")
    print(f"notify_candidates={len(notify_candidates)} levels={','.join(str(x) for x in levels)}")
    print(
        "arr_health="
        + f"radarr={arr_health.get('radarr_count')} "
        + f"sonarr={arr_health.get('sonarr_count')} "
        + f"ok={arr_health.get('arr_config_ok')}"
    )
    print(
        "fix_summary="
        + f"attempted={fix_attempted_count} "
        + f"applied={fix_applied_count} "
        + f"actions={','.join(sorted(fix_actions)) if fix_actions else 'none'}"
    )
    print(
        "approval_flow="
        + f"mode={fix_approval_mode} "
        + f"detail={approval_flow.get('detail')} "
        + f"candidate_count={approval_flow.get('candidate_count')}"
    )
    print(
        "fix_audit="
        + f"enabled={fix_audit_summary.get('enabled')} "
        + f"events_written={fix_audit_summary.get('events_written')} "
        + f"file={fix_audit_summary.get('file')}"
    )
    if arr_health.get("error"):
        print(f"arr_health_error={arr_health.get('error')}")

    if (not args.dry_drill) or args.dry_drill_stateful:
        print(f"state_file={state_path} resolved_since_last_run={resolved_count} state_pruned={pruned_count}")

    if not stale:
        print("No stale pending media requests.")
        return 0

    print("")
    print(f"{'id':<4} {'type':<6} {'request':<10} {'media':<10} {'age_m':<6} {'target':<6} {'reason':<26} {'title':<28} {'requester':<20}")
    print("-" * 140)
    for item in stale:
        diagnosis = item.get("diagnosis", {}) if isinstance(item.get("diagnosis"), dict) else {}
        print(
            f"{str(item.get('request_id')):<4} "
            f"{str(item.get('type')):<6} "
            f"{str(item.get('request_status')):<10} "
            f"{str(item.get('media_status')):<10} "
            f"{str(item.get('age_minutes')):<6} "
            f"{str(diagnosis.get('escalation_target', 'admin')):<6} "
            f"{str(diagnosis.get('reason', 'unknown'))[:26]:<26} "
            f"{str(item.get('title'))[:28]:<28} "
            f"{str(item.get('requester'))[:20]:<20}"
        )

    print("")
    print("Suggested actions:")
    for item in stale:
        diagnosis = item.get("diagnosis", {}) if isinstance(item.get("diagnosis"), dict) else {}
        actions = diagnosis.get("suggested_actions") if isinstance(diagnosis.get("suggested_actions"), list) else []
        if not actions:
            continue
        print(f"- id={item.get('request_id')} title={item.get('title')}")
        for action in actions[:3]:
            print(f"  * {action}")

    if args.emit_ntfy:
        print("")
        print(f"ntfy_admin_sent={ntfy['admin']['sent']} detail={ntfy['admin']['detail']}")
        print(f"ntfy_user_sent={ntfy['user']['sent']} detail={ntfy['user']['detail']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
