from __future__ import annotations

from pathlib import Path
from typing import Any


def _parse_bool(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _read_policy_lines(policy_path: str) -> list[str]:
    if not policy_path:
        return []
    path = Path(policy_path)
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


def load_policy_alert_settings(policy_path: str) -> tuple[set[str], dict[str, str]]:
    required_topics: set[str] = set()
    topic_categories: dict[str, str] = {}

    lines = _read_policy_lines(policy_path)
    if not lines:
        return required_topics, topic_categories

    in_alerts = False
    in_required_topics = False
    in_topic_categories = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")

        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if not in_alerts:
            if line.strip() == "alerts:":
                in_alerts = True
            continue

        if in_alerts and not line.startswith(" "):
            break

        if line.startswith("  topic_categories:"):
            in_topic_categories = True
            in_required_topics = False
            continue

        if in_topic_categories and line.startswith("    "):
            item = line.strip()
            if ":" in item:
                key, value = item.split(":", 1)
                key = key.strip()
                value = value.strip().strip("\"'").lower()
                if key and value:
                    topic_categories[key] = value
            continue

        if in_topic_categories and line.startswith("  ") and not line.startswith("    "):
            in_topic_categories = False

        if not in_required_topics:
            if line.startswith("  required_topics:"):
                in_required_topics = True
            continue

        if line.startswith("  ") and not line.startswith("    - "):
            break

        if line.startswith("    - "):
            topic = line[6:].strip()
            if topic:
                required_topics.add(topic)

    return required_topics, topic_categories


def load_policy_telegram_settings(policy_path: str) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "role_command_allowlist": {},
        "default_admin_notify_topics": [],
        "topic_labels": {},
        "child_guardrails_enabled": None,
        "child_account_adult_min_age": None,
        "child_media_allowed_ratings": [],
        "child_media_allowed_ratings_under_13": [],
        "child_media_allowed_ratings_13_15": [],
        "child_media_allowed_ratings_16_17": [],
        "child_media_deny_unknown_ratings": None,
        "child_media_block_if_adult_flag": None,
        "child_media_blocked_genre_ids": [],
        "child_media_blocked_keywords": [],
        "dedupe_default_window_seconds": None,
        "dedupe_by_topic": {},
        "approval_default_ttl_seconds": None,
        "approval_max_pending_per_user": None,
        "rate_limit_requests_per_minute": None,
        "rate_limit_burst": None,
        "rate_limit_voice_session_cooldown_seconds": None,
        "retention_raw_audio_persist": None,
        "memory_enabled_by_default": None,
        "memory_voice_opt_in_required": None,
        "memory_low_confidence_write_policy": None,
        "memory_clear_requires_confirmation": None,
        "memory_min_speaker_confidence": None,
    }

    lines = _read_policy_lines(policy_path)
    if not lines:
        return settings

    in_channels = False
    in_telegram = False
    in_tg_default_topics = False
    in_tg_topic_labels = False
    in_tg_role_command_allowlist = False
    in_tg_child_guardrails = False
    in_tg_child_allowed_ratings = False
    in_tg_child_allowed_ratings_under_13 = False
    in_tg_child_allowed_ratings_13_15 = False
    in_tg_child_allowed_ratings_16_17 = False
    in_tg_child_blocked_genre_ids = False
    in_tg_child_blocked_keywords = False
    current_role_allowlist_key = ""
    in_dedupe = False
    in_dedupe_topics = False
    in_approval = False
    in_rate_limit = False
    in_rate_limit_default = False
    in_retention = False
    in_memory = False
    current_topic = ""

    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if line.startswith("channels:"):
            in_channels = True
            in_telegram = False
            continue

        if in_channels and not line.startswith(" "):
            in_channels = False

        if in_channels and line.startswith("  telegram:"):
            in_telegram = True
            in_tg_default_topics = False
            in_tg_topic_labels = False
            continue

        if in_telegram and line.startswith("  ") and not line.startswith("    "):
            in_telegram = False
            in_tg_default_topics = False
            in_tg_topic_labels = False
            in_tg_role_command_allowlist = False
            in_tg_child_guardrails = False
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = False
            current_role_allowlist_key = ""

        if in_telegram and line.startswith("    role_command_allowlist:"):
            in_tg_role_command_allowlist = True
            in_tg_default_topics = False
            in_tg_topic_labels = False
            current_role_allowlist_key = ""
            continue

        if in_tg_role_command_allowlist and line.startswith("    ") and not line.startswith("      "):
            in_tg_role_command_allowlist = False
            current_role_allowlist_key = ""

        if in_tg_role_command_allowlist and line.startswith("      ") and not line.startswith("        "):
            role_item = line.strip()
            if ":" in role_item:
                role_key, role_tail = role_item.split(":", 1)
                role_key = role_key.strip().lower()
                current_role_allowlist_key = role_key
                settings["role_command_allowlist"].setdefault(role_key, [])
                role_tail = role_tail.strip()
                if role_tail.startswith("[") and role_tail.endswith("]"):
                    values = [item.strip().strip("\"'").lower() for item in role_tail[1:-1].split(",") if item.strip()]
                    settings["role_command_allowlist"][role_key] = [value for value in values if value]
            continue

        if in_tg_role_command_allowlist and current_role_allowlist_key and line.startswith("        - "):
            command = line[10:].strip().strip("\"'").lower()
            if command:
                settings["role_command_allowlist"].setdefault(current_role_allowlist_key, []).append(command)
            continue

        if in_telegram and line.startswith("    default_admin_notify_topics:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_default_topics = True
            in_tg_topic_labels = False
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                settings["default_admin_notify_topics"] = [v.lower() for v in values if v]
            continue

        if in_tg_default_topics and line.startswith("      - "):
            settings["default_admin_notify_topics"].append(line[8:].strip().strip("\"'").lower())
            continue

        if in_tg_default_topics and line.startswith("    ") and not line.startswith("      - "):
            in_tg_default_topics = False

        if in_telegram and line.startswith("    topic_labels:"):
            in_tg_topic_labels = True
            in_tg_default_topics = False
            continue

        if in_tg_topic_labels and line.startswith("      "):
            item = line.strip()
            if ":" in item:
                key, value = item.split(":", 1)
                key = key.strip().lower()
                value = value.strip().strip("\"'")
                if key and value:
                    settings["topic_labels"][key] = value
            continue

        if in_tg_topic_labels and line.startswith("    ") and not line.startswith("      "):
            in_tg_topic_labels = False

        if in_telegram and line.startswith("    child_guardrails:"):
            in_tg_child_guardrails = True
            in_tg_child_allowed_ratings = False
            continue

        if in_tg_child_guardrails and line.startswith("    ") and not line.startswith("      "):
            in_tg_child_guardrails = False
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = False

        if in_tg_child_guardrails and line.startswith("      enabled:"):
            parsed = _parse_bool(line.split(":", 1)[1].strip())
            if isinstance(parsed, bool):
                settings["child_guardrails_enabled"] = parsed
            continue

        if in_tg_child_guardrails and line.startswith("      adult_min_age:"):
            value = line.split(":", 1)[1].strip()
            try:
                age = int(value)
            except ValueError:
                age = 0
            if age > 0:
                settings["child_account_adult_min_age"] = age
            continue

        if in_tg_child_guardrails and line.startswith("      media_deny_unknown_ratings:"):
            parsed = _parse_bool(line.split(":", 1)[1].strip())
            if isinstance(parsed, bool):
                settings["child_media_deny_unknown_ratings"] = parsed
            continue

        if in_tg_child_guardrails and line.startswith("      media_block_if_adult_flag:"):
            parsed = _parse_bool(line.split(":", 1)[1].strip())
            if isinstance(parsed, bool):
                settings["child_media_block_if_adult_flag"] = parsed
            continue

        if in_tg_child_guardrails and line.startswith("      media_allowed_ratings:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_child_allowed_ratings = True
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = False
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                settings["child_media_allowed_ratings"] = [v.upper() for v in values if v]
            continue

        if in_tg_child_guardrails and line.startswith("      media_allowed_ratings_under_13:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = True
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = False
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                settings["child_media_allowed_ratings_under_13"] = [v.upper() for v in values if v]
            continue

        if in_tg_child_guardrails and line.startswith("      media_allowed_ratings_13_15:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = True
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = False
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                settings["child_media_allowed_ratings_13_15"] = [v.upper() for v in values if v]
            continue

        if in_tg_child_guardrails and line.startswith("      media_allowed_ratings_16_17:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = True
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = False
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                settings["child_media_allowed_ratings_16_17"] = [v.upper() for v in values if v]
            continue

        if in_tg_child_guardrails and line.startswith("      media_blocked_genre_ids:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = True
            in_tg_child_blocked_keywords = False
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                parsed_ids: list[int] = []
                for item in values:
                    try:
                        parsed_ids.append(int(item))
                    except ValueError:
                        continue
                settings["child_media_blocked_genre_ids"] = parsed_ids
            continue

        if in_tg_child_guardrails and line.startswith("      media_blocked_keywords:"):
            tail = line.split(":", 1)[1].strip()
            in_tg_child_allowed_ratings = False
            in_tg_child_allowed_ratings_under_13 = False
            in_tg_child_allowed_ratings_13_15 = False
            in_tg_child_allowed_ratings_16_17 = False
            in_tg_child_blocked_genre_ids = False
            in_tg_child_blocked_keywords = True
            if tail.startswith("[") and tail.endswith("]"):
                values = [item.strip().strip("\"'") for item in tail[1:-1].split(",") if item.strip()]
                settings["child_media_blocked_keywords"] = [v.lower() for v in values if v]
            continue

        if in_tg_child_allowed_ratings and line.startswith("        - "):
            rating = line[10:].strip().strip("\"'").upper()
            if rating:
                settings["child_media_allowed_ratings"].append(rating)
            continue

        if in_tg_child_allowed_ratings_under_13 and line.startswith("        - "):
            rating = line[10:].strip().strip("\"'").upper()
            if rating:
                settings["child_media_allowed_ratings_under_13"].append(rating)
            continue

        if in_tg_child_allowed_ratings_13_15 and line.startswith("        - "):
            rating = line[10:].strip().strip("\"'").upper()
            if rating:
                settings["child_media_allowed_ratings_13_15"].append(rating)
            continue

        if in_tg_child_allowed_ratings_16_17 and line.startswith("        - "):
            rating = line[10:].strip().strip("\"'").upper()
            if rating:
                settings["child_media_allowed_ratings_16_17"].append(rating)
            continue

        if in_tg_child_blocked_genre_ids and line.startswith("        - "):
            raw_value = line[10:].strip().strip("\"'")
            try:
                parsed_id = int(raw_value)
            except ValueError:
                parsed_id = None
            if isinstance(parsed_id, int):
                settings["child_media_blocked_genre_ids"].append(parsed_id)
            continue

        if in_tg_child_blocked_keywords and line.startswith("        - "):
            keyword = line[10:].strip().strip("\"'").lower()
            if keyword:
                settings["child_media_blocked_keywords"].append(keyword)
            continue

        if in_tg_child_allowed_ratings and line.startswith("      ") and not line.startswith("        - "):
            in_tg_child_allowed_ratings = False

        if in_tg_child_allowed_ratings_under_13 and line.startswith("      ") and not line.startswith("        - "):
            in_tg_child_allowed_ratings_under_13 = False

        if in_tg_child_allowed_ratings_13_15 and line.startswith("      ") and not line.startswith("        - "):
            in_tg_child_allowed_ratings_13_15 = False

        if in_tg_child_allowed_ratings_16_17 and line.startswith("      ") and not line.startswith("        - "):
            in_tg_child_allowed_ratings_16_17 = False

        if in_tg_child_blocked_genre_ids and line.startswith("      ") and not line.startswith("        - "):
            in_tg_child_blocked_genre_ids = False

        if in_tg_child_blocked_keywords and line.startswith("      ") and not line.startswith("        - "):
            in_tg_child_blocked_keywords = False

        if line.startswith("dedupe:"):
            in_dedupe = True
            in_dedupe_topics = False
            current_topic = ""
            continue

        if in_dedupe and not line.startswith(" "):
            in_dedupe = False
            in_dedupe_topics = False
            current_topic = ""

        if in_dedupe and line.startswith("  default_window_seconds:"):
            value = line.split(":", 1)[1].strip()
            try:
                seconds = int(value)
            except ValueError:
                seconds = None
            if seconds and seconds > 0:
                settings["dedupe_default_window_seconds"] = seconds
            continue

        if in_dedupe and line.startswith("  topics:"):
            in_dedupe_topics = True
            current_topic = ""
            continue

        if in_dedupe_topics and line.startswith("    ") and line.endswith(":") and not line.startswith("      "):
            topic_key = line.strip().rstrip(":")
            current_topic = topic_key.replace("_", "-")
            continue

        if in_dedupe_topics and current_topic and line.startswith("      window_seconds:"):
            value = line.split(":", 1)[1].strip()
            try:
                seconds = int(value)
            except ValueError:
                seconds = 0
            if seconds > 0:
                settings["dedupe_by_topic"][current_topic] = seconds
            continue

        if line.startswith("approval:"):
            in_approval = True
            continue

        if in_approval and not line.startswith(" "):
            in_approval = False

        if in_approval and line.startswith("  default_ttl_seconds:"):
            value = line.split(":", 1)[1].strip()
            try:
                ttl = int(value)
            except ValueError:
                ttl = 0
            if ttl > 0:
                settings["approval_default_ttl_seconds"] = ttl
            continue

        if in_approval and line.startswith("  max_pending_per_user:"):
            value = line.split(":", 1)[1].strip()
            try:
                max_pending = int(value)
            except ValueError:
                max_pending = 0
            if max_pending > 0:
                settings["approval_max_pending_per_user"] = max_pending
            continue

        if line.startswith("rate_limit:"):
            in_rate_limit = True
            in_rate_limit_default = False
            continue

        if in_rate_limit and not line.startswith(" "):
            in_rate_limit = False
            in_rate_limit_default = False

        if in_rate_limit and line.startswith("  default:"):
            in_rate_limit_default = True
            continue

        if in_rate_limit_default and line.startswith("    requests_per_minute:"):
            value = line.split(":", 1)[1].strip()
            try:
                rpm = int(value)
            except ValueError:
                rpm = 0
            if rpm > 0:
                settings["rate_limit_requests_per_minute"] = rpm
            continue

        if in_rate_limit and line.startswith("  burst:"):
            value = line.split(":", 1)[1].strip()
            try:
                burst = int(value)
            except ValueError:
                burst = -1
            if burst >= 0:
                settings["rate_limit_burst"] = burst
            continue

        if in_rate_limit and line.startswith("  voice_session_cooldown_seconds:"):
            value = line.split(":", 1)[1].strip()
            try:
                cooldown = int(value)
            except ValueError:
                cooldown = 0
            if cooldown > 0:
                settings["rate_limit_voice_session_cooldown_seconds"] = cooldown
            continue

        if line.startswith("retention:"):
            in_retention = True
            continue

        if in_retention and not line.startswith(" "):
            in_retention = False

        if in_retention and line.startswith("  raw_audio_persist:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"true", "yes", "on", "1"}:
                settings["retention_raw_audio_persist"] = True
            elif value in {"false", "no", "off", "0"}:
                settings["retention_raw_audio_persist"] = False
            continue

        if line.startswith("memory:"):
            in_memory = True
            continue

        if in_memory and not line.startswith(" "):
            in_memory = False

        if in_memory and line.startswith("  enabled_by_default:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"true", "yes", "on", "1"}:
                settings["memory_enabled_by_default"] = True
            elif value in {"false", "no", "off", "0"}:
                settings["memory_enabled_by_default"] = False
            continue

        if in_memory and line.startswith("  voice_opt_in_required:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"true", "yes", "on", "1"}:
                settings["memory_voice_opt_in_required"] = True
            elif value in {"false", "no", "off", "0"}:
                settings["memory_voice_opt_in_required"] = False
            continue

        if in_memory and line.startswith("  low_confidence_write_policy:"):
            value = line.split(":", 1)[1].strip().strip("\"'").lower()
            if value:
                settings["memory_low_confidence_write_policy"] = value
            continue

        if in_memory and line.startswith("  clear_requires_confirmation:"):
            value = line.split(":", 1)[1].strip().lower()
            if value in {"true", "yes", "on", "1"}:
                settings["memory_clear_requires_confirmation"] = True
            elif value in {"false", "no", "off", "0"}:
                settings["memory_clear_requires_confirmation"] = False
            continue

        if in_memory and line.startswith("  min_speaker_confidence:"):
            value = line.split(":", 1)[1].strip()
            try:
                confidence = float(value)
            except ValueError:
                confidence = None
            if confidence is not None:
                settings["memory_min_speaker_confidence"] = confidence
            continue

    return settings
