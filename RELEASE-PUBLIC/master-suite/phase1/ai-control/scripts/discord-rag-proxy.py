#!/usr/bin/env python3
import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib import request


def normalize_id(value: Any) -> str:
    return str(value or "").strip()


def parse_active_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_id(v) for v in value if normalize_id(v)]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def parse_id_csv(value: str) -> set[str]:
    return {normalize_id(part) for part in str(value or "").split(",") if normalize_id(part)}


def parse_role_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_id(v) for v in value if normalize_id(v)]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


DEFAULT_POLICY_FILE = str((Path(__file__).resolve().parent.parent / "policy" / "policy.v1.yaml").resolve())


def load_policy_telegram_settings(policy_path: str) -> dict[str, Any]:
    policy_loader_path = (Path(__file__).resolve().parent.parent / "bridge" / "policy_loader.py").resolve()
    if not policy_loader_path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("discord_policy_loader", str(policy_loader_path))
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return {}

    loader = getattr(module, "load_policy_telegram_settings", None)
    if not callable(loader):
        return {}

    try:
        settings = loader(policy_path)
    except Exception:
        return {}

    return settings if isinstance(settings, dict) else {}


def resolve_voice_cooldown_seconds(cli_cooldown_seconds: int | None, policy_file: str) -> int:
    if cli_cooldown_seconds is not None:
        return max(0, int(cli_cooldown_seconds))

    settings = load_policy_telegram_settings(policy_file)
    policy_value = settings.get("rate_limit_voice_session_cooldown_seconds")
    if isinstance(policy_value, int) and policy_value > 0:
        return policy_value

    return 30


DEFAULT_MEMORY_MIN_SPEAKER_CONFIDENCE = 0.8


def policy_bool(settings: dict[str, Any], key: str, default: bool) -> bool:
    value = settings.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def policy_float(settings: dict[str, Any], key: str, default: float) -> float:
    value = settings.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return default
    return default


def resolve_memory_policy(policy_file: str, cli_min_speaker_confidence: float | None) -> dict[str, Any]:
    settings = load_policy_telegram_settings(policy_file)
    min_conf = (
        float(cli_min_speaker_confidence)
        if cli_min_speaker_confidence is not None
        else policy_float(settings, "memory_min_speaker_confidence", DEFAULT_MEMORY_MIN_SPEAKER_CONFIDENCE)
    )
    min_conf = max(0.0, min(1.0, min_conf))
    return {
        "enabled_by_default": policy_bool(settings, "memory_enabled_by_default", False),
        "voice_opt_in_required": policy_bool(settings, "memory_voice_opt_in_required", True),
        "low_confidence_write_policy": str(settings.get("memory_low_confidence_write_policy") or "deny").strip().lower(),
        "clear_requires_confirmation": policy_bool(settings, "memory_clear_requires_confirmation", True),
        "raw_audio_persist": policy_bool(settings, "retention_raw_audio_persist", False),
        "min_speaker_confidence": min_conf,
    }


VOICE_COMMANDS = {"join", "leave", "listen_on", "listen_off", "voice_status", "voice_stop"}


def is_voice_command(command: str) -> bool:
    return command in VOICE_COMMANDS


def is_voice_cooldown_exempt_command(command: str) -> bool:
    return command == "voice_status"


def parse_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    lowered = str(value or "").strip().lower()
    return lowered in {"1", "true", "yes", "on"}


def should_route_voice_loop_event(event: dict[str, Any], command: str) -> bool:
    if command == "memory":
        return False
    if is_voice_command(command):
        return False
    if str(event.get("audio_url") or "").strip():
        return True
    if parse_boolish(event.get("has_audio")):
        return True
    if parse_boolish(event.get("voice_mode")):
        return True
    return False


def validate_voice_loop_transport(event: dict[str, Any]) -> tuple[bool, str]:
    voice_session_id = str(event.get("voice_session_id") or "").strip()
    if not voice_session_id:
        return False, "voice_loop_missing_session_id"

    has_audio_url = bool(str(event.get("audio_url") or "").strip())
    has_transcript = bool(str(event.get("transcript") or "").strip())
    has_audio_flag = parse_boolish(event.get("has_audio"))
    if not (has_audio_url or has_transcript or has_audio_flag):
        return False, "voice_loop_missing_audio_or_transcript"

    return True, "voice_loop_contract_ok"


def infer_command_and_message(event: dict[str, Any]) -> tuple[str, str]:
    raw_command = str(event.get("command") or "").strip().lower()
    message = str(event.get("message") or event.get("question") or "").strip()

    if raw_command:
        normalized = raw_command.lstrip("/")
        if normalized == "listen":
            sub = str(event.get("subcommand") or message).strip().lower()
            if sub.startswith("on"):
                return "listen_on", ""
            if sub.startswith("off"):
                return "listen_off", ""
        if normalized == "voice":
            sub = str(event.get("subcommand") or message).strip().lower()
            if sub.startswith("status"):
                return "voice_status", ""
            if sub.startswith("stop"):
                return "voice_stop", ""
        if normalized in {"join", "leave", "listen_on", "listen_off", "voice_status", "voice_stop"}:
            return normalized, message
        if normalized == "memory":
            return "memory", message
        if normalized in {"ask", "ops", "status"}:
            return normalized, message

    lowered = message.lower()
    if lowered.startswith("/ask"):
        return "ask", message[4:].strip()
    if lowered.startswith("/ops"):
        return "ops", message[4:].strip()
    if lowered.startswith("/status"):
        return "status", message[7:].strip()
    if lowered.startswith("/join"):
        return "join", message[5:].strip()
    if lowered.startswith("/leave"):
        return "leave", message[6:].strip()
    if lowered.startswith("/listen on"):
        return "listen_on", message[10:].strip()
    if lowered.startswith("/listen off"):
        return "listen_off", message[11:].strip()
    if lowered.startswith("/voice status"):
        return "voice_status", message[13:].strip()
    if lowered.startswith("/voice stop"):
        return "voice_stop", message[11:].strip()
    if lowered.startswith("/memory"):
        return "memory", message[7:].strip()
    return "ask", message


def load_memory_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"users": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            if not isinstance(obj.get("users"), dict):
                obj["users"] = {}
            return obj
    except Exception:
        pass
    return {"users": {}}


def save_memory_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def get_speaker_confidence(event: dict[str, Any]) -> float | None:
    value = event.get("speaker_confidence")
    if value is None:
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return parsed


def memory_context_for_event(
    event: dict[str, Any],
    user_id: str,
    memory_state: dict[str, Any],
    memory_policy: dict[str, Any],
) -> dict[str, Any]:
    users = memory_state.setdefault("users", {})
    record = users.get(user_id) if isinstance(users.get(user_id), dict) else {}
    voice_opt_in = bool(record.get("voice_opt_in", memory_policy.get("enabled_by_default", False)))
    speaker_confidence = get_speaker_confidence(event)
    min_conf = float(memory_policy.get("min_speaker_confidence", DEFAULT_MEMORY_MIN_SPEAKER_CONFIDENCE))
    low_conf_policy = str(memory_policy.get("low_confidence_write_policy") or "deny").strip().lower()
    confidence_ok = speaker_confidence is None or speaker_confidence >= min_conf
    if low_conf_policy == "allow":
        write_allowed = True
    else:
        write_allowed = confidence_ok
    return {
        "memory_enabled": bool(voice_opt_in),
        "voice_memory_opt_in": bool(voice_opt_in),
        "memory_write_mode": "summary_only",
        "raw_audio_persist": bool(memory_policy.get("raw_audio_persist", False)),
        "speaker_confidence": speaker_confidence,
        "memory_min_speaker_confidence": min_conf,
        "memory_write_allowed": bool(write_allowed),
        "memory_low_confidence_policy": low_conf_policy,
        "memory_summary": str(record.get("memory_summary") or event.get("memory_summary") or ""),
        "memory_updated_at": str(record.get("updated_at") or ""),
    }


def infer_memory_action(event: dict[str, Any], message: str) -> tuple[str, bool]:
    raw = str(event.get("subcommand") or message or "show").strip().lower()
    normalized = " ".join(raw.replace("_", "-").split())
    if normalized in {"", "show", "status"}:
        return "show", False
    if normalized in {"opt-in", "opt in", "enable", "on", "optin"}:
        return "opt_in", False
    if normalized in {"opt-out", "opt out", "disable", "off", "optout"}:
        return "opt_out", False
    if normalized.startswith("clear"):
        confirm = bool(re.search(r"\b(confirm|yes)\b", normalized))
        return "clear", confirm
    return "show", False


def build_memory_response(
    *,
    action: str,
    confirm_clear: bool,
    user_id: str,
    event: dict[str, Any],
    memory_state: dict[str, Any],
    memory_state_path: Path,
    memory_policy: dict[str, Any],
) -> tuple[dict[str, Any], str, str]:
    users = memory_state.setdefault("users", {})
    record = users.get(user_id)
    if not isinstance(record, dict):
        record = {}
        users[user_id] = record

    default_enabled = bool(memory_policy.get("enabled_by_default", False))
    if "voice_opt_in" not in record:
        record["voice_opt_in"] = default_enabled
    if "memory_summary" not in record:
        record["memory_summary"] = ""

    if action == "opt_in":
        record["voice_opt_in"] = True
        record["updated_at"] = utc_now_iso()
        save_memory_state(memory_state_path, memory_state)
        ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
        return ({
            "reply": "Voice memory is now opt-in enabled for your account.",
            "route": "discord-memory-updated",
            "memory": ctx,
        }, "ok", "memory_opt_in")

    if action == "opt_out":
        record["voice_opt_in"] = False
        record["updated_at"] = utc_now_iso()
        save_memory_state(memory_state_path, memory_state)
        ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
        return ({
            "reply": "Voice memory is now opt-out disabled for your account.",
            "route": "discord-memory-updated",
            "memory": ctx,
        }, "ok", "memory_opt_out")

    if action == "clear":
        if bool(memory_policy.get("clear_requires_confirmation", True)) and not confirm_clear:
            ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
            return ({
                "reply": "Memory clear requires confirmation. Run /memory clear confirm.",
                "route": "discord-memory-confirm-required",
                "memory": ctx,
            }, "denied", "memory_clear_confirmation_required")
        record["memory_summary"] = ""
        record["updated_at"] = utc_now_iso()
        save_memory_state(memory_state_path, memory_state)
        ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
        return ({
            "reply": "Memory summary cleared for your account.",
            "route": "discord-memory-cleared",
            "memory": ctx,
        }, "ok", "memory_clear")

    ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
    return ({
        "reply": "Memory status retrieved.",
        "route": "discord-memory-status",
        "memory": ctx,
    }, "ok", "memory_show")


def persist_memory_summary_if_allowed(
    *,
    event: dict[str, Any],
    user_id: str,
    memory_state: dict[str, Any],
    memory_state_path: Path,
    memory_policy: dict[str, Any],
    summary_text: str | None = None,
) -> bool:
    incoming_summary = str(summary_text if summary_text is not None else (event.get("memory_summary") or "")).strip()
    if not incoming_summary:
        return False

    users = memory_state.setdefault("users", {})
    record = users.get(user_id)
    if not isinstance(record, dict):
        record = {}
        users[user_id] = record

    default_enabled = bool(memory_policy.get("enabled_by_default", False))
    if "voice_opt_in" not in record:
        record["voice_opt_in"] = default_enabled
    if "memory_summary" not in record:
        record["memory_summary"] = ""

    voice_opt_in_required = bool(memory_policy.get("voice_opt_in_required", True))
    if voice_opt_in_required and not bool(record.get("voice_opt_in", False)):
        return False

    memory_ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
    if not bool(memory_ctx.get("memory_write_allowed", False)):
        return False

    trimmed_summary = incoming_summary[:1200]
    if str(record.get("memory_summary") or "") == trimmed_summary:
        return False

    record["memory_summary"] = trimmed_summary
    record["updated_at"] = utc_now_iso()
    save_memory_state(memory_state_path, memory_state)
    return True


def extract_memory_summary_from_result(result: Any) -> str:
    if not isinstance(result, dict):
        return ""

    candidates: list[Any] = [
        result.get("memory_summary"),
        result.get("memorySummary"),
        result.get("summary_memory"),
        result.get("summary"),
    ]

    memory_obj = result.get("memory")
    if isinstance(memory_obj, dict):
        candidates.extend(
            [
                memory_obj.get("memory_summary"),
                memory_obj.get("summary"),
                memory_obj.get("summary_text"),
            ]
        )

    debug_obj = result.get("debug")
    if isinstance(debug_obj, dict):
        debug_memory = debug_obj.get("memory")
        if isinstance(debug_memory, dict):
            candidates.extend(
                [
                    debug_memory.get("memory_summary"),
                    debug_memory.get("summary"),
                    debug_memory.get("summary_text"),
                ]
            )

    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value[:1200]
    return ""


def allowlist_decision(
    event: dict[str, Any],
    *,
    allowed_guild_ids: set[str],
    allowed_channel_ids: set[str],
    allowed_role_ids: set[str],
) -> tuple[bool, str]:
    guild_id = normalize_id(event.get("guild_id"))
    channel_id = normalize_id(event.get("channel_id") or event.get("chat_id") or event.get("voice_channel_id"))
    role_ids = set(parse_role_ids(event.get("role_ids") or event.get("discord_role_ids")))
    role_id = normalize_id(event.get("role_id"))
    if role_id:
        role_ids.add(role_id)

    if allowed_guild_ids and guild_id not in allowed_guild_ids:
        return False, "guild_not_allowlisted"
    if allowed_channel_ids and channel_id not in allowed_channel_ids:
        return False, "channel_not_allowlisted"
    if allowed_role_ids and not (role_ids & allowed_role_ids):
        return False, "role_not_allowlisted"
    return True, "allowlisted"


def tenant_scope_allowed(event: dict[str, Any], user_id: str) -> tuple[bool, str]:
    tenant_id = str(event.get("tenant_id") or "").strip().lower()
    expected = f"u_{normalize_id(user_id).lower()}"
    if tenant_id and tenant_id != expected:
        return False, "tenant_scope_denied"
    return True, "tenant_scope_ok"


def append_audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def load_voice_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"cooldowns": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            if not isinstance(obj.get("cooldowns"), dict):
                obj["cooldowns"] = {}
            return obj
    except Exception:
        pass
    return {"cooldowns": {}}


def save_voice_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def role_ids_from_event(event: dict[str, Any]) -> set[str]:
    role_ids = set(parse_role_ids(event.get("role_ids") or event.get("discord_role_ids")))
    role_id = normalize_id(event.get("role_id"))
    if role_id:
        role_ids.add(role_id)
    return role_ids


def is_moderator_override(event: dict[str, Any], moderator_role_ids: set[str]) -> bool:
    role = str(event.get("role") or "user").lower()
    if role == "admin":
        return True
    if not moderator_role_ids:
        return False
    return bool(role_ids_from_event(event) & moderator_role_ids)


def voice_cooldown_check(
    *,
    state: dict[str, Any],
    event: dict[str, Any],
    command: str,
    cooldown_seconds: int,
    moderator_role_ids: set[str],
) -> tuple[bool, int]:
    if cooldown_seconds <= 0 or is_voice_cooldown_exempt_command(command) or is_moderator_override(event, moderator_role_ids):
        return True, 0

    guild_id = normalize_id(event.get("guild_id") or "noguild")
    channel_id = normalize_id(event.get("channel_id") or event.get("chat_id") or event.get("voice_channel_id") or "nochannel")
    key = f"{guild_id}:{channel_id}:{command}"
    cooldowns = state.setdefault("cooldowns", {})
    now_ts = int(time.time())
    last_ts = int(cooldowns.get(key, {}).get("last_ts", 0)) if isinstance(cooldowns.get(key), dict) else 0
    delta = now_ts - last_ts
    if delta < cooldown_seconds:
        return False, max(1, cooldown_seconds - delta)
    return True, 0


def voice_cooldown_mark(state: dict[str, Any], event: dict[str, Any], command: str) -> None:
    guild_id = normalize_id(event.get("guild_id") or "noguild")
    channel_id = normalize_id(event.get("channel_id") or event.get("chat_id") or event.get("voice_channel_id") or "nochannel")
    key = f"{guild_id}:{channel_id}:{command}"
    cooldowns = state.setdefault("cooldowns", {})
    cooldowns[key] = {
        "last_ts": int(time.time()),
        "user_id": normalize_id(event.get("user_id")),
    }


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_status_payload(event: dict[str, Any], n8n_base: str, health_path: str, timeout_sec: int) -> dict[str, Any]:
    health_url = n8n_base.rstrip("/") + health_path
    health = {"url": health_url, "ok": False}
    try:
        req = request.Request(health_url, method="GET")
        with request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            health["status_code"] = int(getattr(resp, "status", 200))
            health["ok"] = 200 <= health["status_code"] < 300
            health["body"] = raw[:300]
    except Exception as exc:
        health["error"] = str(exc)

    reply = "Discord proxy is healthy."
    if not health.get("ok"):
        reply = "Discord proxy is up, but n8n health probe failed."

    return {
        "reply": reply,
        "route": "discord-status",
        "status": {
            "proxy": "ok",
            "n8n_health": health,
            "role": str(event.get("role") or "user").lower(),
        },
    }


def build_voice_scaffold_payload(event: dict[str, Any], command: str, voice_webhook_url: str, voice_forward: bool) -> dict[str, Any]:
    labels = {
        "join": "join",
        "leave": "leave",
        "listen_on": "listen on",
        "listen_off": "listen off",
        "voice_status": "voice status",
        "voice_stop": "voice stop",
    }
    action = labels.get(command, command)
    forward_state = "enabled" if voice_forward else "disabled"
    return {
        "reply": f"Voice command scaffold received: {action} (voice workflow forwarding {forward_state}).",
        "route": "discord-voice-scaffold",
        "voice": {
            "command": command,
            "forward_enabled": voice_forward,
            "voice_webhook": voice_webhook_url,
            "guild_id": normalize_id(event.get("guild_id")),
            "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id") or event.get("voice_channel_id")),
            "user_id": normalize_id(event.get("user_id")),
        },
    }


def load_profiles(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    profiles = obj.get("profiles") if isinstance(obj, dict) else None
    if not isinstance(profiles, dict):
        raise ValueError("profiles JSON missing top-level 'profiles' object")
    return profiles


def build_profile_context(
    profiles: dict[str, Any],
    user_id: str,
    interaction_user_id: str,
    active_user_ids: list[str],
    allow_force: bool,
) -> dict[str, Any]:
    profile = profiles.get(user_id) or {}
    profile_seed = str(profile.get("user_profile_seed") or "").strip()
    profile_image = str(profile.get("avatar_path") or "").strip()

    allowed = bool(
        allow_force
        or (interaction_user_id and interaction_user_id == user_id)
        or (user_id in active_user_ids)
    )

    return {
        "profile_context_allowed": allowed,
        "user_profile_seed": profile_seed if allowed else "",
        "user_profile_image_url": profile_image if allowed else "",
        "profile_present": bool(profile),
    }


def build_payload(
    event: dict[str, Any],
    profile_ctx: dict[str, Any],
    *,
    command: str,
    message: str,
    memory_ctx: dict[str, Any],
) -> dict[str, Any]:
    user_id = normalize_id(event.get("user_id"))
    interaction_user_id = normalize_id(event.get("interaction_user_id") or user_id)
    active_user_ids = parse_active_ids(event.get("active_user_ids"))
    tenant_id = str(event.get("tenant_id") or f"u_{user_id}")
    role_ids = parse_role_ids(event.get("role_ids") or event.get("discord_role_ids"))
    role_id = normalize_id(event.get("role_id"))
    if role_id and role_id not in role_ids:
        role_ids.append(role_id)

    return {
        "source": "discord",
        "chat_id": str(event.get("chat_id") or event.get("channel_id") or event.get("voice_channel_id") or "discord"),
        "user_id": user_id,
        "role": str(event.get("role") or "user"),
        "tenant_id": tenant_id,
        "full_name": str(event.get("full_name") or event.get("display_name") or event.get("username") or "").strip(),
        "telegram_username": str(event.get("username") or "").strip().lower(),
        "message": message,
        "command": command,
        "discord_guild_id": normalize_id(event.get("guild_id")),
        "discord_channel_id": normalize_id(event.get("channel_id") or event.get("chat_id") or event.get("voice_channel_id")),
        "discord_user_id": user_id,
        "discord_role_ids": role_ids,
        "interaction_user_id": interaction_user_id,
        "active_user_ids": active_user_ids,
        "profile_context_allowed": bool(profile_ctx.get("profile_context_allowed")),
        "user_profile_seed": str(profile_ctx.get("user_profile_seed") or ""),
        "user_profile_image_url": str(profile_ctx.get("user_profile_image_url") or ""),
        "memory_enabled": bool(memory_ctx.get("memory_enabled", False)),
        "voice_memory_opt_in": bool(memory_ctx.get("voice_memory_opt_in", False)),
        "memory_summary": str(memory_ctx.get("memory_summary") or ""),
        "memory_write_mode": str(memory_ctx.get("memory_write_mode") or "summary_only"),
        "raw_audio_persist": bool(memory_ctx.get("raw_audio_persist", False)),
        "speaker_confidence": memory_ctx.get("speaker_confidence"),
        "memory_min_speaker_confidence": memory_ctx.get("memory_min_speaker_confidence"),
        "memory_write_allowed": bool(memory_ctx.get("memory_write_allowed", False)),
        "memory_low_confidence_policy": str(memory_ctx.get("memory_low_confidence_policy") or "deny"),
        "memory_updated_at": str(memory_ctx.get("memory_updated_at") or ""),
        "audio_url": event.get("audio_url"),
        "has_audio": bool(event.get("audio_url") or event.get("has_audio")),
        "image_url": event.get("image_url"),
        "has_image": bool(event.get("image_url") or event.get("has_image")),
    }


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


def post_json(url: str, payload: dict[str, Any], timeout_sec: int = 20) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except Exception:
        return {"raw": body}


def read_event(args: argparse.Namespace) -> dict[str, Any]:
    if args.event_file:
        return json.loads(Path(args.event_file).read_text(encoding="utf-8"))
    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if text:
            return json.loads(text)
    raise SystemExit("Provide --event-file <path> or pipe event JSON on stdin")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discord text command proxy with server-side context and allowlists")
    parser.add_argument("--event-file", default="", help="Input event JSON file path")
    parser.add_argument("--profiles", default="work/discord-seed/discord_user_profiles.json", help="Path to profile map")
    parser.add_argument("--n8n-base", default="http://127.0.0.1:5678", help="n8n base URL")
    parser.add_argument("--rag-webhook", default="/webhook/rag-query", help="RAG webhook path for /ask")
    parser.add_argument("--webhook", default="", help="Deprecated alias for --rag-webhook")
    parser.add_argument("--ops-webhook", default="/webhook/ops-commands-ingest", help="Ops webhook path for /ops")
    parser.add_argument("--voice-webhook", default="/webhook/discord-voice-command", help="Voice webhook path for M6 commands")
    parser.add_argument("--voice-forward", action="store_true", help="Forward voice commands to --voice-webhook")
    parser.add_argument("--voice-state-file", default="logs/discord-voice-state.json", help="State file for voice cooldown tracking")
    parser.add_argument("--voice-cooldown-seconds", type=int, default=None, help="Cooldown window for voice control commands (default from policy)")
    parser.add_argument("--policy-file", default=os.getenv("POLICY_FILE", DEFAULT_POLICY_FILE), help="Policy file path for policy-backed runtime defaults")
    parser.add_argument("--voice-moderator-role-ids", default="", help="Comma-separated Discord role IDs that bypass voice cooldown")
    parser.add_argument("--memory-state-file", default="logs/discord-memory-state.json", help="State file for per-user voice memory opt-in/status")
    parser.add_argument("--memory-min-speaker-confidence", type=float, default=None, help="Minimum speaker confidence required for memory write_allowed=true (default from policy or 0.8)")
    parser.add_argument("--n8n-health-path", default="/healthz", help="n8n health probe path for /status")
    parser.add_argument("--allow-guild-ids", default="", help="Comma-separated Discord guild IDs allowlist")
    parser.add_argument("--allow-channel-ids", default="", help="Comma-separated Discord channel IDs allowlist")
    parser.add_argument("--allow-role-ids", default="", help="Comma-separated Discord role IDs allowlist")
    parser.add_argument("--audit-log", default="logs/discord-command-audit.jsonl", help="JSONL audit log output path")
    parser.add_argument("--allow-force", action="store_true", help="Force profile context allowed")
    parser.add_argument("--print-payload", action="store_true", help="Print final sanitized webhook payload")
    parser.add_argument("--timeout", type=int, default=20, help="Webhook timeout in seconds")
    args = parser.parse_args()

    event = read_event(args)
    user_id = normalize_id(event.get("user_id"))
    if not user_id:
        raise SystemExit("event.user_id is required")

    interaction_user_id = normalize_id(event.get("interaction_user_id") or user_id)
    active_user_ids = parse_active_ids(event.get("active_user_ids"))

    profiles = load_profiles(Path(args.profiles))
    command, normalized_message = infer_command_and_message(event)
    voice_cooldown_seconds = resolve_voice_cooldown_seconds(args.voice_cooldown_seconds, str(args.policy_file or ""))
    memory_policy = resolve_memory_policy(str(args.policy_file or ""), args.memory_min_speaker_confidence)
    memory_state_path = Path(args.memory_state_file)

    allowlisted, allow_reason = allowlist_decision(
        event,
        allowed_guild_ids=parse_id_csv(args.allow_guild_ids),
        allowed_channel_ids=parse_id_csv(args.allow_channel_ids),
        allowed_role_ids=parse_id_csv(args.allow_role_ids),
    )
    if not allowlisted:
        result = {
            "reply": "Access denied: this Discord scope is not allowlisted.",
            "route": "discord-scope-denied",
            "reason": allow_reason,
        }
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": command,
                "decision": "denied",
                "reason": allow_reason,
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    if command == "status":
        result = build_status_payload(event, args.n8n_base, args.n8n_health_path, max(5, int(args.timeout)))
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": command,
                "decision": "ok",
                "reason": "status_report",
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    voice_webhook_url = args.n8n_base.rstrip("/") + args.voice_webhook
    voice_state_path = Path(args.voice_state_file)
    moderator_role_ids = parse_id_csv(args.voice_moderator_role_ids)

    if is_voice_command(command):
        voice_state = load_voice_state(voice_state_path)
        allowed, retry_after = voice_cooldown_check(
            state=voice_state,
            event=event,
            command=command,
            cooldown_seconds=voice_cooldown_seconds,
            moderator_role_ids=moderator_role_ids,
        )
        if not allowed:
            result = {
                "reply": f"Voice command is on cooldown. Retry in {retry_after}s.",
                "route": "discord-voice-cooldown",
                "retry_after_seconds": retry_after,
                "voice": {
                    "command": command,
                    "cooldown_seconds": voice_cooldown_seconds,
                },
            }
            append_audit(
                Path(args.audit_log),
                {
                    "ts": utc_now_iso(),
                    "command": command,
                    "decision": "denied",
                    "reason": "voice_cooldown",
                    "retry_after_seconds": retry_after,
                    "guild_id": normalize_id(event.get("guild_id")),
                    "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                    "user_id": user_id,
                    "role": str(event.get("role") or "user"),
                },
            )
            print(json.dumps(result, ensure_ascii=False))
            return

        profile_ctx = build_profile_context(
            profiles=profiles,
            user_id=user_id,
            interaction_user_id=interaction_user_id,
            active_user_ids=active_user_ids,
            allow_force=bool(args.allow_force),
        )
        memory_state = load_memory_state(memory_state_path)
        memory_ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)
        payload = build_payload(event, profile_ctx, command=command, message=normalized_message, memory_ctx=memory_ctx)
        memory_persisted = False
        if args.voice_forward:
            result = post_json(voice_webhook_url, payload, timeout_sec=max(5, int(args.timeout)))
            memory_persisted = persist_memory_summary_if_allowed(
                event=event,
                user_id=user_id,
                memory_state=memory_state,
                memory_state_path=memory_state_path,
                memory_policy=memory_policy,
                summary_text=extract_memory_summary_from_result(result),
            )
            decision = "forwarded"
            reason = "voice_forwarded"
        else:
            result = build_voice_scaffold_payload(event, command, voice_webhook_url, bool(args.voice_forward))
            decision = "ok"
            reason = "voice_scaffold"

        voice_cooldown_mark(voice_state, event, command)
        save_voice_state(voice_state_path, voice_state)

        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": command,
                "decision": decision,
                "reason": reason,
                "webhook_url": voice_webhook_url,
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
                "role": str(event.get("role") or "user"),
                "memory_summary_persisted": memory_persisted,
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    if command == "memory":
        memory_state = load_memory_state(memory_state_path)
        action, confirm_clear = infer_memory_action(event, normalized_message)
        result, decision, reason = build_memory_response(
            action=action,
            confirm_clear=confirm_clear,
            user_id=user_id,
            event=event,
            memory_state=memory_state,
            memory_state_path=memory_state_path,
            memory_policy=memory_policy,
        )
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": "memory",
                "decision": decision,
                "reason": reason,
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
                "role": str(event.get("role") or "user"),
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    tenant_ok, tenant_reason = tenant_scope_allowed(event, user_id)
    if not tenant_ok:
        result = {
            "reply": "⛔ Access denied: your account can only access its own tenant memory.",
            "route": "discord-tenant-scope-denied",
            "reason": tenant_reason,
        }
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": command,
                "decision": "denied",
                "reason": tenant_reason,
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
                "role": str(event.get("role") or "user"),
                "tenant_id": str(event.get("tenant_id") or ""),
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    profile_ctx = build_profile_context(
        profiles=profiles,
        user_id=user_id,
        interaction_user_id=interaction_user_id,
        active_user_ids=active_user_ids,
        allow_force=bool(args.allow_force),
    )
    memory_state = load_memory_state(memory_state_path)
    memory_ctx = memory_context_for_event(event, user_id, memory_state, memory_policy)

    payload = build_payload(event, profile_ctx, command=command, message=normalized_message, memory_ctx=memory_ctx)

    if should_route_voice_loop_event(event, command):
        valid_voice_loop, voice_loop_reason = validate_voice_loop_transport(event)
        if not valid_voice_loop:
            result = {
                "reply": "Voice loop event rejected: missing required transport fields.",
                "route": "discord-voice-loop-invalid",
                "reason": voice_loop_reason,
            }
            append_audit(
                Path(args.audit_log),
                {
                    "ts": utc_now_iso(),
                    "command": "voice_loop",
                    "decision": "denied",
                    "reason": voice_loop_reason,
                    "guild_id": normalize_id(event.get("guild_id")),
                    "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                    "user_id": user_id,
                    "role": str(payload.get("role") or "user"),
                },
            )
            print(json.dumps(result, ensure_ascii=False))
            return
        payload["command"] = "voice_loop"
        payload["voice_mode"] = True
        payload["voice_session_id"] = str(event.get("voice_session_id") or "")
        payload["transcript"] = str(event.get("transcript") or "")
        result = post_json(voice_webhook_url, payload, timeout_sec=max(5, int(args.timeout)))
        memory_persisted = persist_memory_summary_if_allowed(
            event=event,
            user_id=user_id,
            memory_state=memory_state,
            memory_state_path=memory_state_path,
            memory_policy=memory_policy,
            summary_text=extract_memory_summary_from_result(result),
        )
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": "voice_loop",
                "decision": "forwarded",
                "reason": "voice_loop_forwarded",
                "webhook_url": voice_webhook_url,
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
                "role": str(payload.get("role") or "user"),
                "memory_summary_persisted": memory_persisted,
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    if command == "ops" and str(payload.get("role") or "user").lower() != "admin":
        result = {"reply": "Ops command denied: admin role required.", "route": "discord-ops-admin-only"}
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": command,
                "decision": "denied",
                "reason": "ops_admin_only",
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
                "role": str(payload.get("role") or "user"),
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    if str(payload.get("role") or "user").lower() != "admin" and is_coding_help_request(str(payload.get("message") or "")):
        result = {
            "reply": "Coding help is currently available for admin accounts only. I can still help with runbook/docs, media requests, weather, and other non-coding topics.",
            "route": "coding-admin-only",
        }
        append_audit(
            Path(args.audit_log),
            {
                "ts": utc_now_iso(),
                "command": command,
                "decision": "denied",
                "reason": "coding_admin_only",
                "guild_id": normalize_id(event.get("guild_id")),
                "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
                "user_id": user_id,
            },
        )
        print(json.dumps(result, ensure_ascii=False))
        return

    if args.print_payload:
        print(json.dumps(payload, ensure_ascii=False))
        return

    rag_webhook = args.webhook or args.rag_webhook
    webhook_url = args.n8n_base.rstrip("/") + (rag_webhook if command == "ask" else args.ops_webhook)
    result = post_json(webhook_url, payload, timeout_sec=max(5, int(args.timeout)))
    memory_persisted = False
    if command == "ask":
        memory_persisted = persist_memory_summary_if_allowed(
            event=event,
            user_id=user_id,
            memory_state=memory_state,
            memory_state_path=memory_state_path,
            memory_policy=memory_policy,
            summary_text=extract_memory_summary_from_result(result),
        )
    append_audit(
        Path(args.audit_log),
        {
            "ts": utc_now_iso(),
            "command": command,
            "decision": "forwarded",
            "reason": "ok",
            "webhook_url": webhook_url,
            "guild_id": normalize_id(event.get("guild_id")),
            "channel_id": normalize_id(event.get("channel_id") or event.get("chat_id")),
            "user_id": user_id,
            "role": str(payload.get("role") or "user"),
            "memory_summary_persisted": memory_persisted,
        },
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
