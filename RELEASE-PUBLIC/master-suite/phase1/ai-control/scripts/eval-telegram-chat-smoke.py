#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from path_safety import ensure_writable_env_path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PATH = ROOT / "bridge" / "telegram_to_n8n.py"
NTFY_BRIDGE_PATH = ROOT / "bridge" / "ntfy_to_n8n.py"
WEBHOOK_URL = os.getenv("N8N_RAG_QUERY_URL", "http://127.0.0.1:5678/webhook/rag-query")
RAG_INGEST_URL = os.getenv("N8N_RAG_INGEST_URL", "http://127.0.0.1:5678/webhook/rag-ingest")
TEXTBOOK_WEBHOOK_URL = os.getenv(
    "N8N_TEXTBOOK_URL", "http://127.0.0.1:5678/webhook/textbook-fulfillment"
)
DENY_TOKEN = "access denied"


def ensure_writable_memory_telemetry_path() -> None:
    ensure_writable_env_path(
        "TELEGRAM_MEMORY_TELEMETRY_PATH",
        "/state/telegram_memory_telemetry.jsonl",
        ROOT / "logs" / "telegram_memory_telemetry.jsonl",
    )


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8", errors="ignore")
    return json.loads(raw)


def check_webhook_basic() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 700,
        "user_id": 9001,
        "role": "user",
        "tenant_id": "u_9001",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "message": "healthcheck ping",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"
    return True, "ok"


def check_workspace_mode_live_webhook() -> tuple[bool, str]:
    suffix = str(int(time.time() * 1000))
    user_id = 900000 + int(suffix[-6:])
    tenant_id = f"u_{user_id}"
    workspace_doc_id = f"workspace-live-{suffix}"
    memory_doc_id = f"memory-live-{suffix}"
    workspace_source = f"workspace-live-source-{suffix}"
    memory_source = f"memory-live-source-{suffix}"
    workspace_value = f"WS-ONLY-{suffix}"
    memory_value = f"MEM-ONLY-{suffix}"

    workspace_ingest_payload = {
        "source": "telegram",
        "chat_id": 790,
        "user_id": user_id,
        "role": "admin",
        "tenant_id": tenant_id,
        "text": f"workspace mode probe document. mode probe key is {workspace_value}.",
        "source_name": workspace_source,
        "source_type": "workspace_temp",
        "doc_id": workspace_doc_id,
        "timestamp": int(time.time()),
    }
    memory_ingest_payload = {
        "source": "telegram",
        "chat_id": 790,
        "user_id": user_id,
        "role": "admin",
        "tenant_id": tenant_id,
        "text": f"memory mode probe document. mode probe key is {memory_value}.",
        "source_name": memory_source,
        "source_type": "manual",
        "doc_id": memory_doc_id,
        "timestamp": int(time.time()),
    }

    try:
        _ = post_json(RAG_INGEST_URL, workspace_ingest_payload)
        _ = post_json(RAG_INGEST_URL, memory_ingest_payload)
    except urllib.error.HTTPError as exc:
        return False, f"ingest_http_{exc.code}"
    except Exception as exc:
        return False, f"ingest_error:{exc}"

    time.sleep(0.8)

    question = "From docs, what is the mode probe key?"
    base_query = {
        "source": "telegram",
        "chat_id": 790,
        "user_id": user_id,
        "role": "admin",
        "tenant_id": tenant_id,
        "full_name": "Workspace Smoke",
        "telegram_username": "ws_smoke",
        "message": question,
        "memory_enabled": True,
        "memory_summary": "live-smoke-memory-enabled",
        "timestamp": int(time.time()),
    }

    workspace_query = dict(base_query)
    workspace_query.update(
        {
            "workspace_mode": "workspace",
            "workspace_active": True,
            "workspace_id": f"ws-live-{suffix}",
            "workspace_doc_ids": [workspace_doc_id],
            "workspace_context_only": True,
            "memory_context_only": False,
            "memory_enabled_effective": False,
            "memory_summary_effective": "",
        }
    )

    memory_query = dict(base_query)
    memory_query.update(
        {
            "workspace_mode": "memory",
            "workspace_active": True,
            "workspace_id": f"ws-live-{suffix}",
            "workspace_doc_ids": [workspace_doc_id],
            "workspace_context_only": False,
            "memory_context_only": True,
            "memory_enabled_effective": True,
            "memory_summary_effective": "live-smoke-memory-enabled",
        }
    )

    last_error = ""
    for _ in range(5):
        try:
            workspace_result = post_json(WEBHOOK_URL, workspace_query)
            memory_result = post_json(WEBHOOK_URL, memory_query)
        except urllib.error.HTTPError as exc:
            last_error = f"query_http_{exc.code}"
            time.sleep(0.6)
            continue
        except Exception as exc:
            last_error = f"query_error:{exc}"
            time.sleep(0.6)
            continue

        workspace_reply = str(workspace_result.get("reply", ""))
        memory_reply = str(memory_result.get("reply", ""))

        workspace_ok = workspace_source in workspace_reply and memory_source not in workspace_reply
        memory_ok = workspace_source not in memory_reply and memory_reply != workspace_reply
        if workspace_ok and memory_ok:
            return True, "ok"

        if workspace_source not in workspace_reply:
            last_error = "workspace_mode_source_missing"
        elif memory_source in workspace_reply:
            last_error = "workspace_mode_unexpected_memory_source"
        elif workspace_source in memory_reply:
            last_error = "memory_mode_unexpected_workspace_source"
        elif memory_reply == workspace_reply:
            last_error = "mode_responses_not_differentiated"
        else:
            last_error = "workspace_mode_assertion_failed"
        time.sleep(0.6)

    return False, last_error or "workspace_mode_live_check_failed"


def check_tenant_isolation() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 700,
        "user_id": 9001,
        "role": "admin",
        "tenant_id": "u_24680",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "message": "Use internal docs: what is redwood-42?",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).lower()
    if DENY_TOKEN in reply:
        return True, "denied"
    return False, "not_denied"


def check_profile_seed_fallback_route() -> tuple[bool, str]:
    base_payload = {
        "source": "telegram",
        "chat_id": 701,
        "user_id": 701,
        "role": "user",
        "tenant_id": "u_701",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "user_profile_seed": (
            "Private user seed profile for Discord user Weezy (id=379165603249782794).\n"
            "- Primary username: starweezy\n"
            "- Display/global name: Weezy\n"
            "- Activity observed: 5 messages\n"
            "- Frequent channels: general, unknown\n"
            "- Common topics/keywords: im a, restart\n"
            "- Use this as private personalization context."
        ),
        "memory_enabled": False,
    }
    prompt_cases = [
        {
            "message": "Whats my profile name and where did i come from?",
            "require_display": True,
            "require_primary": False,
        },
        {
            "message": "What is my discord display/global name and primary username?",
            "require_display": True,
            "require_primary": True,
        },
    ]

    for case in prompt_cases:
        payload = dict(base_payload)
        payload["message"] = str(case.get("message", "")).strip()

        try:
            data = post_json(WEBHOOK_URL, payload)
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except Exception as exc:
            return False, str(exc)

        reply = str(data.get("reply", "")).strip()
        if not reply:
            return False, "missing_reply"
        if "Error in workflow" in reply:
            return False, "workflow_error_reply"

        route_match = re.search(r"\[route:([^\]]+)\]", reply, re.S)
        route = route_match.group(1) if route_match else ""
        if "profile-seed-fallback-rag" not in route:
            return False, "route_mismatch"
        lowered_reply = reply.lower()
        if bool(case.get("require_display", False)) and "weezy" not in lowered_reply:
            return False, "seed_identity_missing"
        if bool(case.get("require_primary", False)) and "starweezy" not in lowered_reply:
            return False, "seed_primary_missing"

        has_seed_source = "sources: private_profile_seed" in lowered_reply
        has_seed_limited_response = (
            ("don't have enough information" in lowered_reply or "not enough information" in lowered_reply)
            and has_seed_source
        )
        if not has_seed_source and not has_seed_limited_response:
            return False, "seed_source_missing"

    return True, "ok"


def check_personality_correction_ack_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 702,
        "user_id": 9005,
        "role": "user",
        "tenant_id": "u_9005",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "message": "what do you know about me? that's wrong",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    if "thanks for the correction." not in lowered_reply:
        return False, "missing_correction_ack"

    return True, "ok"


def check_personality_uncertainty_no_hallucination_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 703,
        "user_id": 9006,
        "role": "user",
        "tenant_id": "u_9006",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "memory_enabled": False,
        "message": "What is my exact favorite color from your saved memory?",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    uncertainty_markers = [
        "don't have enough information",
        "do not have enough information",
        "not enough information",
        "i don't have",
        "i do not have",
        "i use current message context",
        "store durable facts",
        "memory_limits",
    ]
    if not any(marker in lowered_reply for marker in uncertainty_markers):
        return False, "missing_uncertainty_language"

    if "favorite color is" in lowered_reply and "don't" not in lowered_reply and "not enough" not in lowered_reply:
        return False, "possible_hallucinated_memory"

    return True, "ok"


def check_personality_low_confidence_tier_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 704,
        "user_id": 9007,
        "role": "user",
        "tenant_id": "u_9007",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "message": "From runbook docs, summarize redwood-42 incident timeline from internal checklist",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    if "conf:low" not in lowered_reply:
        return False, "missing_low_conf_marker"

    uncertainty_markers = [
        "based on available context",
        "may be missing details",
        "not enough information",
        "insufficient information",
        "strong rag matches were not found",
    ]
    if not any(marker in lowered_reply for marker in uncertainty_markers):
        return False, "missing_low_conf_uncertainty_language"

    return True, "ok"


def check_personality_recovery_mode_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 705,
        "user_id": 9008,
        "role": "user",
        "tenant_id": "u_9008",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "message": "that's wrong, try again, this is frustrating",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    if "i hear your frustration." not in lowered_reply:
        return False, "missing_recovery_ack"
    if "next step:" not in lowered_reply:
        return False, "missing_recovery_next_step"
    if "rm:on" not in lowered_reply:
        return False, "missing_recovery_marker"

    return True, "ok"


def check_personality_smalltalk_budget_marker_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 706,
        "user_id": 9009,
        "role": "user",
        "tenant_id": "u_9009",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "persona_pref_brevity": "short",
        "message": "hello",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    if "route:smalltalk:" not in lowered_reply:
        return False, "missing_smalltalk_route"
    if "brevity:short" not in lowered_reply:
        return False, "missing_short_brevity_marker"
    if "rb:220" not in lowered_reply:
        return False, "missing_smalltalk_budget_marker"

    return True, "ok"


def check_personality_rag_budget_marker_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 707,
        "user_id": 9010,
        "role": "user",
        "tenant_id": "u_9010",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "persona_pref_brevity": "short",
        "message": "From runbook docs, summarize Day 5 checklist progress",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    if "route:explicit-rag" not in lowered_reply and "route:rag-request-low-confidence-web-fallback" not in lowered_reply:
        return False, "missing_rag_route"
    if "brevity:short" not in lowered_reply:
        return False, "missing_short_brevity_marker"
    if "rb:320" not in lowered_reply:
        return False, "missing_rag_budget_marker"

    return True, "ok"


def check_personality_ops_budget_marker_live() -> tuple[bool, str]:
    payload = {
        "source": "telegram",
        "chat_id": 708,
        "user_id": 9011,
        "role": "admin",
        "tenant_id": "u_9011",
        "full_name": "Smoke User",
        "telegram_username": "smokeuser",
        "persona_pref_brevity": "short",
        "message": "Give ops bridge health summary right now",
    }
    try:
        data = post_json(WEBHOOK_URL, payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    reply = str(data.get("reply", "")).strip()
    if not reply:
        return False, "missing_reply"

    lowered_reply = reply.lower()
    if "route:default-web-first" not in lowered_reply and "route:weather-web-first" not in lowered_reply:
        return False, "missing_general_route"
    if "brevity:short" not in lowered_reply:
        return False, "missing_short_brevity_marker"
    if "rb:320" not in lowered_reply:
        return False, "missing_ops_budget_marker"

    return True, "ok"


def check_profile_commands_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-") as tmp:
        tmp_path = Path(tmp)
        seed_catalog = {
            "profiles": {
                "9001": {
                    "user_profile_seed": "Preferred name: Smoke User. Style: concise.",
                    "user_profile_image_url": "file:///tmp/smoke-avatar.png",
                }
            }
        }
        (tmp_path / "seed.json").write_text(json.dumps(seed_catalog), encoding="utf-8")

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_MAX_ITEMS"] = "10"
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_MAX_ITEMS"] = "8"
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "true"
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_MAX_ITEMS"] = "8"
        os.environ["TELEGRAM_PROFILE_SEED_PATH"] = str(tmp_path / "seed.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        chat_id = 700
        user_id = 9001
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "user", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)
        setattr(bridge, "send_message", lambda _cid, _txt: None)

        if not bridge.handle_profile_command(chat_id, user_id, "/profile apply"):
            return False, "profile_apply_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if str(record.get("profile_source", "")) != "discord_seed":
            return False, "profile_source_mismatch"
        if not bool(record.get("user_profile_seed")):
            return False, "profile_seed_missing"

        if not bridge.handle_profile_command(chat_id, user_id, "/profile clear"):
            return False, "profile_clear_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if bool(record.get("user_profile_seed")):
            return False, "profile_clear_failed"

        if not bridge.handle_profile_command(chat_id, user_id, "/profile style set tone concise"):
            return False, "profile_style_tone_not_handled"
        if not bridge.handle_profile_command(chat_id, user_id, "/profile style set brevity short"):
            return False, "profile_style_brevity_not_handled"

        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if str(record.get("persona_pref_tone", "")) != "concise":
            return False, "profile_style_tone_not_saved"
        if str(record.get("persona_pref_brevity", "")) != "short":
            return False, "profile_style_brevity_not_saved"

        payload = bridge.build_payload(
            chat_id=chat_id,
            user_id=user_id,
            role="user",
            full_name="Smoke User",
            telegram_username="smokeuser",
            text="test",
            image_url=None,
            audio_info={},
            memory_enabled=False,
            memory_summary="",
            memory_provenance=[],
            workspace_context={},
            tone_history=[],
            persona_pref_tone=str(record.get("persona_pref_tone", "")),
            persona_pref_brevity=str(record.get("persona_pref_brevity", "")),
            user_profile_seed="",
            user_profile_image_url="",
            account_age=None,
            account_class="adult",
            child_guardrails_enabled=False,
        )
        if str(payload.get("persona_pref_tone", "")) != "concise":
            return False, "payload_style_tone_missing"
        if str(payload.get("persona_pref_brevity", "")) != "short":
            return False, "payload_style_brevity_missing"
        if "memory_provenance" not in payload:
            return False, "payload_memory_provenance_missing"
        if not isinstance(payload.get("memory_provenance"), list):
            return False, "payload_memory_provenance_type_mismatch"
        if "memory_provenance_effective" not in payload:
            return False, "payload_memory_provenance_effective_missing"
        if not isinstance(payload.get("memory_provenance_effective"), list):
            return False, "payload_memory_provenance_effective_type_mismatch"

        if not bridge.handle_profile_command(chat_id, user_id, "/profile style reset"):
            return False, "profile_style_reset_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if bool(record.get("persona_pref_tone")) or bool(record.get("persona_pref_brevity")):
            return False, "profile_style_reset_failed"

        if not bridge.handle_feedback_command(chat_id, user_id, "/feedback too_short"):
            return False, "feedback_too_short_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if str(record.get("persona_pref_brevity", "")) != "detailed":
            return False, "feedback_too_short_not_applied"

        if not bridge.handle_feedback_command(chat_id, user_id, "/feedback too_long"):
            return False, "feedback_too_long_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if str(record.get("persona_pref_brevity", "")) != "balanced":
            return False, "feedback_too_long_not_applied"

        if not bridge.handle_feedback_command(chat_id, user_id, "/feedback too_formal"):
            return False, "feedback_too_formal_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if str(record.get("persona_pref_tone", "")) != "warm":
            return False, "feedback_too_formal_not_applied"

        stats = record.get("persona_feedback_stats") if isinstance(record, dict) else {}
        if not isinstance(stats, dict):
            return False, "feedback_stats_missing"
        if int(stats.get("too_short", 0) or 0) < 1:
            return False, "feedback_stats_too_short_missing"
        if int(stats.get("too_long", 0) or 0) < 1:
            return False, "feedback_stats_too_long_missing"
        if int(stats.get("too_formal", 0) or 0) < 1:
            return False, "feedback_stats_too_formal_missing"

        bridge.update_persona_drift_metrics(
            user_id,
            "[route:test tone_target:neutral brevity:short conf:medium sg:pass sgr:ok]",
        )
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        drift = record.get("persona_drift_stats") if isinstance(record, dict) else {}
        if not isinstance(drift, dict):
            return False, "drift_stats_missing"
        if int(drift.get("total_checks", 0) or 0) < 1:
            return False, "drift_total_checks_missing"
        if int(drift.get("mismatch_count", 0) or 0) < 1:
            return False, "drift_mismatch_count_missing"

        bridge.update_persona_drift_metrics(
            user_id,
            "[route:test tone_target:warm brevity:balanced conf:medium sg:pass sgr:ok]",
        )
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        drift = record.get("persona_drift_stats") if isinstance(record, dict) else {}
        if int((drift or {}).get("streak", 0) or 0) != 0:
            return False, "drift_streak_not_reset"

    return True, "ok"


def check_memory_regression_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "100"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        chat_id = 702
        user_id = 9102
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "user", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)
        bridge.set_memory_enabled(user_id, True)

        saved, _count, reason = bridge.add_memory_note(
            user_id,
            "Remember this low-confidence preference.",
            source="telegram_user_note",
            confidence=0.25,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if saved or str(reason) != "low_confidence":
            return False, "memory_gate_low_confidence_mismatch"

        saved, _count, reason = bridge.add_memory_note(
            user_id,
            "I like black coffee.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram"},
            tier="preference",
        )
        if saved or str(reason) != "explicit_intent_required":
            return False, "memory_gate_explicit_intent_mismatch"

        saved, count, reason = bridge.add_memory_note(
            user_id,
            "Remember I prefer oat milk.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved or count < 1 or str(reason) != "pass":
            return False, "memory_add_primary_failed"

        saved, count, reason = bridge.add_memory_note(
            user_id,
            "Remember I prefer almond milk.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved or count < 2 or str(reason) != "pass":
            return False, "memory_add_conflict_candidate_failed"

        conflicts = bridge.list_memory_conflicts(user_id)
        if not conflicts:
            return False, "memory_conflict_candidate_missing"
        if len(conflicts) < 2:
            return False, f"memory_conflict_pair_missing:{len(conflicts)}"

        gated_enabled, gated_summary, _gated_provenance = bridge.get_memory_context(user_id)
        if not gated_enabled:
            return False, "memory_conflict_gated_context_disabled"
        gated_lower = str(gated_summary).lower()
        if "conflict candidate" not in gated_lower and "need confirmation" not in gated_lower:
            return False, "memory_conflict_gated_prompt_missing"
        if "oat milk" in gated_lower or "almond milk" in gated_lower:
            return False, "memory_conflict_gated_note_leak"

        conflict_index = int(conflicts[0].get("index", 0) or 0)
        if conflict_index < 1:
            return False, "memory_conflict_index_invalid"

        resolved, detail = bridge.resolve_memory_conflict(user_id, conflict_index, "keep")
        if not resolved:
            return False, f"memory_conflict_resolve_failed:{detail}"
        if bridge.list_memory_conflicts(user_id):
            return False, "memory_conflict_not_cleared"

        enabled, summary, provenance = bridge.get_memory_context(user_id)
        if not enabled:
            return False, "memory_context_disabled_unexpected"
        if not str(summary).strip():
            return False, "memory_context_summary_missing"
        if not isinstance(provenance, list) or not provenance:
            return False, "memory_context_provenance_missing"
        if "score" not in provenance[0]:
            return False, "memory_context_score_missing"

        why_text = bridge.build_memory_why_text(user_id, limit=3)
        if "Ranking formula:" not in why_text:
            return False, "memory_why_formula_missing"

        export_text = bridge.build_memory_export_text(user_id)
        if "\"total_notes\":" not in export_text:
            return False, "memory_export_total_missing"

        messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, txt: messages.append(str(txt)))

        if not bridge.handle_memory_command(chat_id, user_id, "/memory add Remember I prefer green tea"):
            return False, "memory_command_add_not_handled"
        if not messages or "saved" not in messages[-1].lower():
            return False, "memory_command_add_ack_missing"

        if not bridge.handle_memory_command(chat_id, user_id, "/memory why"):
            return False, "memory_command_why_not_handled"
        if "Memory influence report:" not in messages[-1]:
            return False, "memory_command_why_output_missing"

        if not bridge.handle_memory_command(chat_id, user_id, "/memory export"):
            return False, "memory_command_export_not_handled"
        if "Memory export" not in messages[-1]:
            return False, "memory_command_export_output_missing"

        if not bridge.handle_memory_command(chat_id, user_id, "/memory forget source telegram_user_note"):
            return False, "memory_command_forget_not_handled"
        if "Forgot" not in messages[-1]:
            return False, "memory_command_forget_ack_missing"

        synth_user_id = 9103
        bridge.set_user_record(bridge.USER_REGISTRY, synth_user_id, "user", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)
        bridge.set_memory_enabled(synth_user_id, True)

        saved, _count, _reason = bridge.add_memory_note(
            synth_user_id,
            "Remember my favorite color is blue.",
            source="telegram_user_note",
            confidence=0.8,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved:
            return False, "memory_synthesis_seed_add1_failed"

        saved, _count, _reason = bridge.add_memory_note(
            synth_user_id,
            "Remember my favorite color is blue.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved:
            return False, "memory_synthesis_seed_add2_failed"

        saved, _count, _reason = bridge.add_memory_note(
            synth_user_id,
            "Remember my favorite movie is Interstellar.",
            source="telegram_user_note",
            confidence=0.9,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved:
            return False, "memory_synthesis_seed_add3_failed"

        synth_enabled, synth_summary, synth_provenance = bridge.get_memory_context(synth_user_id)
        if not synth_enabled:
            return False, "memory_synthesis_context_disabled"

        synth_lines = [line for line in str(synth_summary).splitlines() if line.strip().startswith("- ")]
        if len(synth_lines) != 2:
            return False, f"memory_synthesis_summary_line_count_mismatch:{len(synth_lines)}"

        color_lines = [line for line in synth_lines if "favorite color" in line.lower()]
        if len(color_lines) != 1:
            return False, f"memory_synthesis_color_dedupe_mismatch:{len(color_lines)}"

        if not isinstance(synth_provenance, list) or len(synth_provenance) != 2:
            return False, f"memory_synthesis_provenance_count_mismatch:{len(synth_provenance) if isinstance(synth_provenance, list) else -1}"

        synth_export = bridge.build_memory_export_text(synth_user_id)
        if '"total_notes": 3' not in synth_export:
            return False, "memory_synthesis_export_total_notes_mismatch"

    return True, "ok"


def check_child_account_guardrails_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-child-guardrails-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_CHILD_GUARDRAILS_ENABLED"] = "true"
        os.environ["TELEGRAM_CHILD_ACCOUNT_ADULT_MIN_AGE"] = "18"
        os.environ["TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS"] = "G,PG,TV-Y,TV-Y7,TV-G,TV-PG"
        os.environ["TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_UNDER_13"] = "G,PG,TV-Y,TV-Y7,TV-G,TV-PG"
        os.environ["TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_13_15"] = "G,PG,PG-13,TV-Y,TV-Y7,TV-G,TV-PG,TV-14"
        os.environ["TELEGRAM_CHILD_MEDIA_ALLOWED_RATINGS_16_17"] = "G,PG,PG-13,TV-Y,TV-Y7,TV-G,TV-PG,TV-14"
        os.environ["TELEGRAM_CHILD_MEDIA_DENY_UNKNOWN_RATINGS"] = "true"
        os.environ["TELEGRAM_CHILD_MEDIA_BLOCK_IF_ADULT_FLAG"] = "true"
        os.environ["TELEGRAM_CHILD_MEDIA_BLOCKED_GENRE_IDS"] = "27"
        os.environ["TELEGRAM_CHILD_MEDIA_BLOCKED_KEYWORDS"] = "nudity,sexual content,gore,drug use,self-harm,suicide"

        spec = importlib.util.spec_from_file_location("telegram_bridge_child_guardrails", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        chat_id = 733
        user_id = 9333
        messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: messages.append(str(text)) or True)

        bridge.USER_REGISTRY.setdefault("users", {})[str(user_id)] = {
            "role": "user",
            "status": "pending_registration",
            "registration_state": "pending_age",
            "full_name": "Smoke Child",
            "telegram_username": "smoke_child",
        }
        bridge.save_user_registry(bridge.USER_REGISTRY)

        handled_registration = bridge.process_registration_flow(
            chat_id=chat_id,
            user_id=user_id,
            text="12",
            username="smoke_child",
            first_name="Smoke",
            last_name="Child",
            existing=bridge.get_user_record(bridge.USER_REGISTRY, user_id),
        )
        if not handled_registration:
            return False, "child_registration_not_handled"

        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if int(record.get("age", 0) or 0) != 12:
            return False, "child_age_not_saved"
        if str(record.get("account_class", "")) != "child":
            return False, "child_class_not_assigned"
        if str(record.get("registration_state", "")) != "active":
            return False, "child_registration_state_not_active"

        messages.clear()
        genre_violations = bridge.child_media_guardrail_violations(
            {
                "title": "Horror Genre Test",
                "content_rating": "PG",
                "genre_ids": [27],
            },
            bridge.get_user_record(bridge.USER_REGISTRY, user_id),
        )
        if not any("genre guardrail hit" in entry for entry in genre_violations):
            return False, "child_genre_guardrail_helper_missing"
        bridge.MEDIA_SELECTION_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "options": [
                {
                    "media_type": "movie",
                    "media_id": 42,
                    "title": "Restricted Test",
                    "year": "2024",
                    "current_status": "unknown",
                    "content_rating": "R",
                }
            ],
        }
        submit_blocked_called = {"value": False}

        def fake_submit_blocked(*_args, **_kwargs):
            submit_blocked_called["value"] = True
            return True

        setattr(bridge, "submit_media_request", fake_submit_blocked)
        handled_blocked = bridge.handle_media_pick_command(chat_id=chat_id, user_id=user_id, text="/media pick 1")
        if not handled_blocked:
            return False, "child_blocked_pick_not_handled"
        if submit_blocked_called["value"]:
            return False, "child_blocked_pick_submitted"
        if not messages or "blocked by Child account media guardrails" not in messages[-1]:
            return False, "child_blocked_pick_message_missing"

        messages.clear()
        bridge.MEDIA_SELECTION_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "options": [
                {
                    "media_type": "movie",
                    "media_id": 45,
                    "title": "Adult Metadata Test",
                    "year": "2024",
                    "current_status": "unknown",
                    "content_rating": "PG",
                    "adult_flag": True,
                }
            ],
        }
        handled_adult_flag = bridge.handle_media_pick_command(chat_id=chat_id, user_id=user_id, text="/media pick 1")
        if not handled_adult_flag:
            return False, "child_adult_flag_pick_not_handled"
        if not messages or "marked adult" not in messages[-1]:
            return False, "child_adult_flag_block_message_missing"

        messages.clear()
        bridge.MEDIA_SELECTION_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "options": [
                {
                    "media_type": "movie",
                    "media_id": 46,
                    "title": "Horror Genre Test",
                    "year": "2024",
                    "current_status": "unknown",
                    "content_rating": "PG",
                    "genre_ids": [27],
                }
            ],
        }
        handled_genre_block = bridge.handle_media_pick_command(chat_id=chat_id, user_id=user_id, text="/media pick 1")
        if not handled_genre_block:
            return False, "child_genre_block_pick_not_handled"
        if not messages or "blocked by Child account media guardrails" not in messages[-1]:
            return False, "child_genre_block_message_missing"

        messages.clear()
        keyword_violations = bridge.child_media_guardrail_violations(
            {
                "title": "Descriptor Test",
                "content_rating": "PG",
                "overview": "Contains graphic gore and disturbing scenes.",
            },
            bridge.get_user_record(bridge.USER_REGISTRY, user_id),
        )
        if not any("blocked keyword" in entry for entry in keyword_violations):
            return False, "child_keyword_guardrail_helper_missing"
        bridge.MEDIA_SELECTION_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "options": [
                {
                    "media_type": "movie",
                    "media_id": 47,
                    "title": "Descriptor Test",
                    "year": "2024",
                    "current_status": "unknown",
                    "content_rating": "PG",
                    "overview": "Contains graphic gore and disturbing scenes.",
                }
            ],
        }
        handled_keyword_block = bridge.handle_media_pick_command(chat_id=chat_id, user_id=user_id, text="/media pick 1")
        if not handled_keyword_block:
            return False, "child_keyword_block_pick_not_handled"
        if not messages or "blocked by Child account media guardrails" not in messages[-1]:
            return False, "child_keyword_block_message_missing"

        messages.clear()
        bridge.MEDIA_SELECTION_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "options": [
                {
                    "media_type": "movie",
                    "media_id": 43,
                    "title": "Allowed Test",
                    "year": "2024",
                    "current_status": "unknown",
                    "content_rating": "PG",
                    "adult_flag": False,
                    "genre_ids": [18],
                    "overview": "A wholesome family adventure.",
                }
            ],
        }
        submit_allowed_called = {"value": False}

        def fake_submit_allowed(*_args, **_kwargs):
            submit_allowed_called["value"] = True
            return True

        setattr(bridge, "submit_media_request", fake_submit_allowed)
        handled_allowed = bridge.handle_media_pick_command(chat_id=chat_id, user_id=user_id, text="/media pick 1")
        if not handled_allowed:
            return False, "child_allowed_pick_not_handled"
        if not submit_allowed_called["value"]:
            return False, "child_allowed_pick_not_submitted"

        # Adults (age >= threshold) must bypass child guardrails, even if stale class says "child".
        adult_id = user_id + 1
        bridge.USER_REGISTRY.setdefault("users", {})[str(adult_id)] = {
            "role": "user",
            "status": "active",
            "registration_state": "active",
            "full_name": "Smoke Adult",
            "telegram_username": "smoke_adult",
            "age": 21,
            "account_class": "child",
        }
        bridge.save_user_registry(bridge.USER_REGISTRY)

        messages.clear()
        bridge.MEDIA_SELECTION_STATE.setdefault("pending", {})[str(adult_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "options": [
                {
                    "media_type": "movie",
                    "media_id": 44,
                    "title": "Adult Bypass Test",
                    "year": "2024",
                    "current_status": "unknown",
                    "content_rating": "R",
                }
            ],
        }
        submit_adult_called = {"value": False}

        def fake_submit_adult(*_args, **_kwargs):
            submit_adult_called["value"] = True
            return True

        setattr(bridge, "submit_media_request", fake_submit_adult)
        handled_adult = bridge.handle_media_pick_command(chat_id=chat_id, user_id=adult_id, text="/media pick 1")
        if not handled_adult:
            return False, "adult_pick_not_handled"
        if not submit_adult_called["value"]:
            return False, "adult_pick_unexpectedly_blocked"
        if any("blocked by Child account media guardrails" in msg for msg in messages):
            return False, "adult_guardrail_block_unexpected"

        messages.clear()
        handled_age_show = bridge.handle_profile_command(chat_id, user_id, "/profile age show")
        if not handled_age_show:
            return False, "profile_age_show_not_handled"
        output = messages[-1] if messages else ""
        if "- class: Child" not in output or "- age: 12" not in output:
            return False, "profile_age_show_content_mismatch"

    return True, "ok"


def check_memory_tier_decay_order_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-tier-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "100"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")
        os.environ["TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS_PROFILE"] = "120"
        os.environ["TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS_PREFERENCE"] = "30"
        os.environ["TELEGRAM_MEMORY_RECENCY_HALF_LIFE_DAYS_SESSION"] = "2"

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory_tier", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9011
        now_ts = int(time.time())
        aged_ts = now_ts - (7 * 86400)

        entry = bridge.get_memory_entry(user_id)
        entry["enabled"] = True
        entry["notes"] = [
            {
                "text": "Remember my legal name is Alex Smith.",
                "source": "telegram_user_note",
                "tier": "profile",
                "confidence": 0.9,
                "ts": aged_ts,
                "last_used_ts": aged_ts,
            },
            {
                "text": "Remember I prefer concise responses.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.9,
                "ts": aged_ts,
                "last_used_ts": aged_ts,
            },
            {
                "text": "Remember today's temp topic is retries.",
                "source": "telegram_user_note",
                "tier": "session",
                "confidence": 0.9,
                "ts": aged_ts,
                "last_used_ts": aged_ts,
            },
        ]
        bridge.save_memory_state(bridge.MEMORY_STATE)

        score_profile = bridge.memory_note_rank_score(entry["notes"][0], now_ts=now_ts)
        score_preference = bridge.memory_note_rank_score(entry["notes"][1], now_ts=now_ts)
        score_session = bridge.memory_note_rank_score(entry["notes"][2], now_ts=now_ts)

        if not (score_profile > score_preference > score_session):
            return (
                False,
                "memory_tier_decay_score_order_mismatch:"
                f"profile={score_profile},preference={score_preference},session={score_session}",
            )

        enabled, _summary, provenance = bridge.get_memory_context(user_id)
        if not enabled:
            return False, "memory_tier_context_disabled"
        if not isinstance(provenance, list) or len(provenance) < 3:
            return False, "memory_tier_context_provenance_missing"

        top_tiers = [str(item.get("tier", "")) for item in provenance[:3]]
        if top_tiers != ["profile", "preference", "session"]:
            return False, f"memory_tier_context_order_mismatch:{','.join(top_tiers)}"

    return True, "ok"


def check_memory_intent_scope_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-intent-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "100"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CONFLICT_PROMPT_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_INTENT_SCOPE_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory_intent", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9012
        now_ts = int(time.time())
        entry = bridge.get_memory_entry(user_id)
        entry["enabled"] = True
        entry["notes"] = [
            {
                "text": "Remember my legal name is Alex Smith.",
                "source": "telegram_user_note",
                "tier": "profile",
                "confidence": 0.95,
                "ts": now_ts - 90,
            },
            {
                "text": "Remember I prefer concise responses.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.95,
                "ts": now_ts - 60,
            },
            {
                "text": "Remember Plex requests should use Overseerr first.",
                "source": "telegram_user_note",
                "tier": "session",
                "confidence": 0.95,
                "ts": now_ts - 30,
            },
            {
                "text": "Remember restart guidance should include /ops health before action.",
                "source": "telegram_user_note",
                "tier": "session",
                "confidence": 0.95,
                "ts": now_ts - 15,
            },
        ]
        bridge.save_memory_state(bridge.MEMORY_STATE)

        _enabled, style_summary, _style_prov = bridge.get_memory_context(user_id, intent_scope="style")
        style_text = str(style_summary).lower()
        if "concise responses" not in style_text:
            return False, "memory_intent_style_missing"
        if "plex" in style_text or "restart guidance" in style_text:
            return False, "memory_intent_style_leak"

        _enabled, media_summary, _media_prov = bridge.get_memory_context(user_id, intent_scope="media")
        media_text = str(media_summary).lower()
        if "plex requests" not in media_text:
            return False, "memory_intent_media_missing"
        if "legal name" in media_text or "concise responses" in media_text:
            return False, "memory_intent_media_leak"

        _enabled, identity_summary, _identity_prov = bridge.get_memory_context(user_id, intent_scope="identity")
        identity_text = str(identity_summary).lower()
        if "legal name" not in identity_text:
            return False, "memory_intent_identity_missing"
        if "restart guidance" in identity_text:
            return False, "memory_intent_identity_leak"

        inferred_scope = bridge.infer_memory_intent_scope("Can you use a concise tone?", mode="rag")
        if str(inferred_scope) != "style":
            return False, f"memory_intent_infer_style_mismatch:{inferred_scope}"
        inferred_scope = bridge.infer_memory_intent_scope("Please check ops restart health", mode="rag")
        if str(inferred_scope) != "ops":
            return False, f"memory_intent_infer_ops_mismatch:{inferred_scope}"

    return True, "ok"


def check_memory_telemetry_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-telemetry-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "100"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory_telemetry", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9013
        bridge.set_memory_enabled(user_id, True)

        saved, _count, reason = bridge.add_memory_note(
            user_id,
            "Remember this but confidence is too low.",
            source="telegram_user_note",
            confidence=0.1,
            provenance={"command": "memory_add"},
            tier="preference",
        )
        if saved or str(reason) != "low_confidence":
            return False, "memory_telemetry_gate_expected_reject_missing"

        saved, _count, reason = bridge.add_memory_note(
            user_id,
            "Remember I prefer dark mode.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"command": "memory_add"},
            tier="preference",
        )
        if not saved or str(reason) != "pass":
            return False, "memory_telemetry_seed_add_failed"

        saved, _count, reason = bridge.add_memory_note(
            user_id,
            "Remember I prefer light mode.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"command": "memory_add"},
            tier="preference",
        )
        if not saved or str(reason) != "pass":
            return False, "memory_telemetry_conflict_add_failed"

        _enabled, _summary, _prov = bridge.get_memory_context(user_id, intent_scope="style")
        conflicts = bridge.list_memory_conflicts(user_id)
        if not conflicts:
            return False, "memory_telemetry_conflict_missing"

        target_index = int(conflicts[0].get("index", 0) or 0)
        if target_index < 1:
            return False, "memory_telemetry_conflict_index_invalid"

        resolved, _detail = bridge.resolve_memory_conflict(user_id, target_index, "keep")
        if not resolved:
            return False, "memory_telemetry_conflict_resolve_failed"

        bridge.append_memory_telemetry(
            "scope_infer",
            user_id=user_id,
            fields={"mode": "rag", "scope": "style", "has_text": True, "text_len": 28},
        )

        telemetry_path = tmp_path / "memory_telemetry.jsonl"
        if not telemetry_path.exists():
            return False, "memory_telemetry_file_missing"

        rows: list[dict] = []
        for raw_line in telemetry_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = str(raw_line or "").strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)

        if not rows:
            return False, "memory_telemetry_rows_missing"

        events = {str(row.get("event", "")) for row in rows}
        required_events = {"scope_infer", "write_gate", "write_commit", "conflict_detected", "context", "conflict_resolve"}
        if not required_events.issubset(events):
            missing = sorted(required_events.difference(events))
            return False, f"memory_telemetry_event_missing:{','.join(missing)}"

        context_rows = [row for row in rows if str(row.get("event", "")) == "context"]
        if not context_rows:
            return False, "memory_telemetry_context_event_missing"
        latest_context = context_rows[-1]
        fields_raw = latest_context.get("fields")
        fields = fields_raw if isinstance(fields_raw, dict) else {}
        if "latency_ms" not in fields:
            return False, "memory_telemetry_context_latency_missing"

    return True, "ok"


def check_memory_canary_controls_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-canary-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_SYNTHESIS_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CONFLICT_PROMPT_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_CONFLICT_REQUIRE_CONFIRMATION"] = "1"
        os.environ["TELEGRAM_MEMORY_INTENT_SCOPE_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = "9015"
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory_canary", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        non_canary_user_id = 9014
        canary_user_id = 9015
        bridge.set_memory_enabled(non_canary_user_id, True)
        bridge.set_memory_enabled(canary_user_id, True)

        non_scope = bridge.infer_memory_intent_scope("Please use a concise tone.", mode="rag", user_id=non_canary_user_id)
        if non_scope is not None:
            return False, f"memory_canary_non_scope_expected_none:{non_scope}"
        canary_scope = bridge.infer_memory_intent_scope("Please use a concise tone.", mode="rag", user_id=canary_user_id)
        if str(canary_scope) != "style":
            return False, f"memory_canary_scope_expected_style:{canary_scope}"

        now_ts = int(time.time())
        non_entry = bridge.get_memory_entry(non_canary_user_id)
        non_entry["enabled"] = True
        non_entry["notes"] = [
            {
                "text": "Remember I prefer concise responses.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.95,
                "ts": now_ts - 60,
            },
            {
                "text": "Remember Plex requests should use Overseerr first.",
                "source": "telegram_user_note",
                "tier": "session",
                "confidence": 0.95,
                "ts": now_ts - 30,
            },
        ]

        canary_entry = bridge.get_memory_entry(canary_user_id)
        canary_entry["enabled"] = True
        canary_entry["notes"] = [
            {
                "text": "Remember I prefer concise responses.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.95,
                "ts": now_ts - 60,
            },
            {
                "text": "Remember Plex requests should use Overseerr first.",
                "source": "telegram_user_note",
                "tier": "session",
                "confidence": 0.95,
                "ts": now_ts - 30,
            },
        ]
        bridge.save_memory_state(bridge.MEMORY_STATE)

        _en, non_summary, _pr = bridge.get_memory_context(non_canary_user_id, intent_scope="style")
        non_text = str(non_summary).lower()
        if "plex requests" not in non_text:
            return False, "memory_canary_non_scope_filter_unexpected"

        _en, canary_summary, _pr = bridge.get_memory_context(canary_user_id, intent_scope="style")
        canary_text = str(canary_summary).lower()
        if "concise responses" not in canary_text:
            return False, "memory_canary_scope_filter_missing_style"
        if "plex requests" in canary_text:
            return False, "memory_canary_scope_filter_leak"

        saved, _count, reason = bridge.add_memory_note(
            non_canary_user_id,
            "Remember I prefer oat milk.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved or str(reason) != "pass":
            return False, "memory_canary_non_conflict_seed_failed"
        saved, _count, reason = bridge.add_memory_note(
            non_canary_user_id,
            "Remember I prefer almond milk.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved or str(reason) != "pass":
            return False, "memory_canary_non_conflict_pair_failed"
        _en, non_conflict_summary, _pr = bridge.get_memory_context(non_canary_user_id)
        non_conflict_text = str(non_conflict_summary).lower()
        if "need confirmation" in non_conflict_text:
            return False, "memory_canary_non_conflict_gate_unexpected"

        saved, _count, reason = bridge.add_memory_note(
            canary_user_id,
            "Remember I prefer oat milk.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved or str(reason) != "pass":
            return False, "memory_canary_conflict_seed_failed"
        saved, _count, reason = bridge.add_memory_note(
            canary_user_id,
            "Remember I prefer almond milk.",
            source="telegram_user_note",
            confidence=0.95,
            provenance={"channel": "telegram", "command": "memory_add"},
            tier="preference",
        )
        if not saved or str(reason) != "pass":
            return False, "memory_canary_conflict_pair_failed"
        _en, canary_conflict_summary, _pr = bridge.get_memory_context(canary_user_id)
        canary_conflict_text = str(canary_conflict_summary).lower()
        if "need confirmation" not in canary_conflict_text:
            return False, "memory_canary_conflict_gate_missing"

    return True, "ok"


def check_memory_conflict_workflow_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-conflict-ops-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "100"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CONFLICT_REMINDER_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_CONFLICT_REMINDER_SECONDS"] = "300"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory_conflict_ops", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9016
        now_ts = int(time.time())
        detected_ts = now_ts - 720

        entry = bridge.get_memory_entry(user_id)
        entry["enabled"] = True
        entry["notes"] = [
            {
                "text": "Remember I prefer oat milk.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.95,
                "ts": now_ts - 1800,
                "conflict_candidate": True,
                "conflict_group": "memory_conflict_telegram_user_note_preference_1_2",
                "conflict_detected_ts": detected_ts,
                "conflict_hint": {"prior_ts": now_ts - 1800, "prior_source": "telegram_user_note", "prior_tier": "preference"},
            },
            {
                "text": "Remember I prefer almond milk.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.95,
                "ts": now_ts - 600,
                "conflict_candidate": True,
                "conflict_group": "memory_conflict_telegram_user_note_preference_1_2",
                "conflict_detected_ts": detected_ts,
                "conflict_hint": {"prior_ts": now_ts - 600, "prior_source": "telegram_user_note", "prior_tier": "preference"},
            },
        ]
        bridge.save_memory_state(bridge.MEMORY_STATE)

        conflicts = bridge.list_memory_conflicts(user_id)
        if len(conflicts) != 2:
            return False, f"memory_conflict_workflow_count_mismatch:{len(conflicts)}"
        if not all(bool(item.get("needs_reminder", False)) for item in conflicts if isinstance(item, dict)):
            return False, "memory_conflict_workflow_reminder_flag_missing"
        if not all(int(item.get("age_seconds", 0) or 0) >= 300 for item in conflicts if isinstance(item, dict)):
            return False, "memory_conflict_workflow_age_missing"

        sent_messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, txt: sent_messages.append(str(txt)))
        if not bridge.handle_memory_command(710, user_id, "/memory conflicts"):
            return False, "memory_conflict_workflow_command_not_handled"
        if not sent_messages:
            return False, "memory_conflict_workflow_command_reply_missing"
        latest = sent_messages[-1].lower()
        if "stale" not in latest or "exceeded reminder threshold" not in latest:
            return False, "memory_conflict_workflow_stale_hint_missing"

        snapshot = bridge.build_status_snapshot()
        if int(snapshot.get("memory_conflicts_total", 0) or 0) < 2:
            return False, "memory_conflict_workflow_status_total_missing"
        if int(snapshot.get("memory_conflicts_stale", 0) or 0) < 2:
            return False, "memory_conflict_workflow_status_stale_missing"

    return True, "ok"


def check_memory_feedback_ranking_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-memory-feedback-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_MEMORY_CANARY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_CANARY_PERCENT"] = "100"
        os.environ["TELEGRAM_MEMORY_CANARY_INCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_CANARY_EXCLUDE_USER_IDS"] = ""
        os.environ["TELEGRAM_MEMORY_FEEDBACK_RANKING_ENABLED"] = "1"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_ENABLED"] = "0"
        os.environ["TELEGRAM_MEMORY_TELEMETRY_PATH"] = str(tmp_path / "memory_telemetry.jsonl")

        spec = importlib.util.spec_from_file_location("telegram_bridge_memory_feedback", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9017
        now_ts = int(time.time())
        entry = bridge.get_memory_entry(user_id)
        entry["enabled"] = True
        entry["notes"] = [
            {
                "text": "Remember I prefer concise responses.",
                "source": "telegram_user_note",
                "tier": "preference",
                "confidence": 0.95,
                "ts": now_ts - 120,
            },
            {
                "text": "Remember session topic is retries.",
                "source": "textbook_request",
                "tier": "session",
                "confidence": 0.95,
                "ts": now_ts - 90,
            },
        ]
        bridge.save_memory_state(bridge.MEMORY_STATE)

        model = bridge.get_memory_feedback_model(entry)
        if float(model.get("global_weight", 0.0) or 0.0) != 1.0:
            return False, "memory_feedback_initial_global_weight_mismatch"

        pref_item = entry["notes"][0]
        pref_mult_before = bridge.memory_feedback_rank_multiplier(entry, pref_item)
        if abs(pref_mult_before - 1.0) > 0.0001:
            return False, f"memory_feedback_initial_multiplier_mismatch:{pref_mult_before}"

        bridge.record_memory_feedback_signal(user_id=user_id, signal="feedback_too_vague")
        entry = bridge.get_memory_entry(user_id)
        model = bridge.get_memory_feedback_model(entry)
        tier_weights = model.get("tier_weights") if isinstance(model.get("tier_weights"), dict) else {}
        if float(tier_weights.get("preference", 1.0) or 1.0) <= 1.0:
            return False, "memory_feedback_preference_boost_missing"

        pref_mult_after = bridge.memory_feedback_rank_multiplier(entry, pref_item)
        if pref_mult_after <= pref_mult_before:
            return False, f"memory_feedback_multiplier_not_increased:{pref_mult_after}"

        bridge.record_memory_feedback_signal(
            user_id=user_id,
            signal="conflict_drop",
            note_source="telegram_user_note",
            note_tier="preference",
        )
        entry = bridge.get_memory_entry(user_id)
        model = bridge.get_memory_feedback_model(entry)
        source_weights = model.get("source_weights") if isinstance(model.get("source_weights"), dict) else {}
        src_weight = float(source_weights.get("telegram_user_note", 1.0) or 1.0)
        if src_weight >= 1.0:
            return False, f"memory_feedback_source_penalty_missing:{src_weight}"

        _enabled, _summary, provenance = bridge.get_memory_context(user_id)
        if not isinstance(provenance, list) or not provenance:
            return False, "memory_feedback_context_provenance_missing"
        if "feedback_multiplier" not in provenance[0]:
            return False, "memory_feedback_provenance_multiplier_missing"

        why_text = bridge.build_memory_why_text(user_id, limit=2)
        if "feedback_ranking:" not in why_text:
            return False, "memory_feedback_why_line_missing"

    return True, "ok"


def check_status_json_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-status-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_status", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9002
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        payload = bridge.build_status_json_report()
        try:
            data = json.loads(payload)
        except Exception:
            return False, "status_json_parse_failed"

        required = [
            "notifications_policy_enabled",
            "notify_critical_only",
            "notify_min_priority",
            "users_active",
            "admins_active",
            "notify_stats_updated_at",
            "incident_state_updated_at",
            "digest_queue_users",
            "digest_queue_items",
            "delivery_outcomes_24h",
        ]
        missing = [key for key in required if key not in data]
        if missing:
            return False, f"status_json_missing:{','.join(missing)}"

        outcomes = data.get("delivery_outcomes_24h")
        if not isinstance(outcomes, dict):
            return False, "status_json_outcomes_invalid"
        for key in ["sent", "sent_partial", "failed", "rate_limited", "deferred", "skipped"]:
            if key not in outcomes:
                return False, f"status_json_outcome_missing:{key}"

    return True, "ok"


def check_textbook_fulfillment_contract() -> tuple[bool, str]:
    valid_payload = {
        "textbook_request": "Linear Algebra and Its Applications by Gilbert Strang for MATH 241",
        "delivery_email": "student@example.edu",
        "lawful_sources_only": True,
        "validation_summary": "matched ISBN 9780030105678 from legal catalogs",
        "selected_candidate": {
            "title": "Linear Algebra and Its Applications",
            "author": "Gilbert Strang",
            "isbn": "9780030105678",
            "source": "google_books",
            "source_url": "https://books.google.com/books?id=abc",
        },
        "file_url": "https://example.edu/files/linear-algebra-sample.pdf",
        "file_mime": "application/pdf",
        "user_id": "9001",
    }
    deny_payload = {
        "textbook_request": "Any book",
        "delivery_email": "student@example.edu",
        "lawful_sources_only": False,
        "validation_summary": "none",
        "selected_candidate": {},
        "user_id": "9001",
    }
    missing_payload = {
        "textbook_request": "",
        "delivery_email": "student@example.edu",
        "lawful_sources_only": True,
        "user_id": "9001",
    }

    try:
        valid_data = post_json(TEXTBOOK_WEBHOOK_URL, valid_payload)
        deny_data = post_json(TEXTBOOK_WEBHOOK_URL, deny_payload)
        missing_data = post_json(TEXTBOOK_WEBHOOK_URL, missing_payload)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)

    valid_reply = str(valid_data.get("reply", "")).lower()
    if not bool(valid_data.get("file_ready_for_email")):
        return False, "valid_not_ready"
    if str(valid_data.get("fulfillment_id", "")).strip() == "":
        return False, "valid_missing_fulfillment_id"
    if str(valid_data.get("delivery_status", "")).strip() != "dispatch_ready":
        return False, "valid_delivery_status_mismatch"
    timeline = valid_data.get("status_timeline")
    if not isinstance(timeline, list) or not timeline:
        return False, "valid_missing_status_timeline"
    if str(valid_data.get("file_url", "")).strip() == "":
        return False, "valid_missing_file_url"
    if str(valid_data.get("file_mime", "")).strip() == "":
        return False, "valid_missing_file_mime"
    if str(valid_data.get("ingest_text", "")).strip() == "":
        return False, "valid_missing_ingest_text"
    if "queued" not in valid_reply:
        return False, "valid_missing_queue_reply"

    deny_reply = str(deny_data.get("reply", "")).lower()
    if bool(deny_data.get("file_ready_for_email")):
        return False, "deny_ready_unexpected"
    if str(deny_data.get("delivery_status", "")).strip() != "denied_lawful_only":
        return False, "deny_delivery_status_mismatch"
    if "lawful_sources_only" not in deny_reply:
        return False, "deny_message_mismatch"

    missing_reply = str(missing_data.get("reply", "")).lower()
    if bool(missing_data.get("file_ready_for_email")):
        return False, "missing_ready_unexpected"
    if str(missing_data.get("delivery_status", "")).strip() != "denied_missing_request":
        return False, "missing_delivery_status_mismatch"
    if "provide textbook details" not in missing_reply:
        return False, "missing_message_mismatch"

    return True, "ok"


def check_textbook_untrusted_source_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-textbook-allowlist-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_TEXTBOOK_STATE"] = str(tmp_path / "textbook_state.json")
        os.environ["TEXTBOOK_ENFORCE_FILE_DOMAIN_ALLOWLIST"] = "true"
        os.environ["TEXTBOOK_ALLOWED_FILE_DOMAINS"] = "example.edu"

        spec = importlib.util.spec_from_file_location("telegram_bridge_textbook_allowlist", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9012
        chat_id = 712
        user_record = {
            "role": "admin",
            "status": "active",
            "preferred_delivery_email": "student@example.edu",
            "updated_at": bridge.utc_now(),
        }
        bridge.USER_REGISTRY.setdefault("users", {})[str(user_id)] = user_record
        bridge.save_user_registry(bridge.USER_REGISTRY)

        bridge.TEXTBOOK_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "details": "title: Example Textbook, author: Example Author",
            "parsed_fields": {"title": "Example Textbook", "author": "Example Author"},
            "candidate_summary": "candidate ok",
            "delivery_email": "student@example.edu",
            "options": [{"title": "Example Textbook", "authors": "Example Author"}],
            "selected_candidate": {"title": "Example Textbook", "authors": "Example Author"},
            "selected_index": 1,
        }
        bridge.save_textbook_state(bridge.TEXTBOOK_STATE)

        send_calls = {"count": 0}

        def fake_send_email(**_kwargs):
            send_calls["count"] += 1
            return True, "email_dispatched"

        def fake_call_n8n(webhook: str, _payload: dict) -> dict:
            if webhook == bridge.TEXTBOOK_WEBHOOK:
                return {
                    "reply": "ok",
                    "file_ready_for_email": True,
                    "file_url": "https://evil.example.net/book.pdf",
                    "file_mime": "application/pdf",
                    "fulfillment_id": "fulfillment-allowlist-test-1",
                    "delivery_status": "dispatch_ready",
                    "delivery_mode": "ops_queue",
                    "status_timeline": ["2026-01-01T00:00:00Z:dispatch_ready"],
                }
            return {"reply": "ok"}

        sent_messages: list[str] = []
        setattr(bridge, "send_message", lambda _chat_id, text: sent_messages.append(str(text)))
        setattr(bridge, "send_textbook_delivery_email", fake_send_email)
        setattr(bridge, "call_n8n", fake_call_n8n)

        handled = bridge.handle_textbook_command(chat_id, user_id, "/textbook confirm", user_record, "admin")
        if not handled:
            return False, "textbook_confirm_not_handled"

        if send_calls["count"] != 0:
            return False, f"allowlist_expected_0_send_calls_got_{send_calls['count']}"

        last_fulfillment = bridge.get_textbook_last_fulfillment(user_id) or {}
        if str(last_fulfillment.get("delivery_status", "")).strip() != "dispatch_failed_untrusted_source":
            return False, "allowlist_delivery_status_mismatch"

        if int(last_fulfillment.get("dispatch_attempt_count", 0) or 0) != 1:
            return False, "allowlist_dispatch_attempt_count_mismatch"

        last_error = str(last_fulfillment.get("last_error", "")).strip()
        if "untrusted_source" not in last_error:
            return False, "allowlist_last_error_missing"

        if not any("blocked_untrusted_source" in msg for msg in sent_messages):
            return False, "allowlist_user_message_missing"

    return True, "ok"


def check_textbook_pick_alias_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-textbook-pick-alias-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_TEXTBOOK_STATE"] = str(tmp_path / "textbook_state.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_textbook_pick_alias", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9040
        chat_id = 740
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "user", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        bridge.TEXTBOOK_STATE.setdefault("pending", {})[str(user_id)] = {
            "chat_id": chat_id,
            "created_at": int(time.time()),
            "details": "title: Example Book, author: Example Author",
            "parsed_fields": {"title": "Example Book", "author": "Example Author"},
            "candidate_summary": "",
            "delivery_email": "",
            "options": [
                {
                    "provider": "openlibrary",
                    "title": "Example Book",
                    "authors": "Example Author",
                    "year": "2020",
                    "isbn": "",
                    "source_url": "https://openlibrary.org",
                    "cover_url": "",
                }
            ],
            "selected_candidate": {},
            "selected_index": 0,
        }
        bridge.save_textbook_state(bridge.TEXTBOOK_STATE)

        out_messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: out_messages.append(str(text)) or True)

        user_record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        handled = bridge.handle_textbook_command(
            chat_id=chat_id,
            user_id=user_id,
            text="/textbook 1",
            user_record=user_record,
            role="user",
        )
        if not handled:
            return False, "textbook_pick_alias_not_handled"

        updated = bridge.get_textbook_request(user_id)
        if not updated:
            return False, "textbook_pick_alias_missing_pending"
        if int(updated.get("selected_index", 0) or 0) != 1:
            return False, "textbook_pick_alias_selected_index_mismatch"
        if not out_messages or "Candidate selected" not in out_messages[-1]:
            return False, "textbook_pick_alias_message_missing"

    return True, "ok"


def check_textbook_delivery_ack_retry_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-textbook-ack-retry-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_TEXTBOOK_STATE"] = str(tmp_path / "textbook_state.json")
        os.environ["TEXTBOOK_ENFORCE_FILE_DOMAIN_ALLOWLIST"] = "true"
        os.environ["TEXTBOOK_ALLOWED_FILE_DOMAINS"] = "example.edu"

        spec = importlib.util.spec_from_file_location("telegram_bridge_textbook_ack_retry", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9013
        chat_id = 713
        user_record = {
            "role": "admin",
            "status": "active",
            "preferred_delivery_email": "student@example.edu",
            "updated_at": bridge.utc_now(),
        }
        bridge.USER_REGISTRY.setdefault("users", {})[str(user_id)] = user_record
        bridge.save_user_registry(bridge.USER_REGISTRY)

        bridge.set_textbook_last_fulfillment(
            user_id,
            {
                "created_at": int(time.time()),
                "fulfillment_id": "fulfillment-ack-retry-test-1",
                "delivery_email": "student@example.edu",
                "delivery_status": "email_dispatched",
                "delivery_mode": "smtp_bridge",
                "status_timeline": ["2026-01-01T00:00:00Z:email_dispatched"],
                "dispatch_attempt_count": 0,
                "last_dispatch_at": "",
                "last_error": "",
                "file_url": "https://example.edu/files/testbook.pdf",
                "request_details": "title: Example Textbook, author: Example Author",
                "selected_candidate": {"title": "Example Textbook", "authors": "Example Author"},
            },
        )

        send_calls = {"count": 0}

        def fake_send_email(**_kwargs):
            send_calls["count"] += 1
            return True, "email_dispatched"

        sent_messages: list[str] = []
        setattr(bridge, "send_message", lambda _chat_id, text: sent_messages.append(str(text)) or True)
        setattr(bridge, "send_textbook_delivery_email", fake_send_email)

        if not bridge.handle_textbook_command(chat_id, user_id, "/textbook resend", user_record, "admin"):
            return False, "textbook_resend_not_handled"
        if send_calls["count"] != 1:
            return False, "textbook_resend_send_count_mismatch"

        after_resend = bridge.get_textbook_last_fulfillment(user_id) or {}
        if str(after_resend.get("delivery_status", "")).strip() != "email_redispatched":
            return False, "textbook_resend_status_mismatch"
        if int(after_resend.get("dispatch_attempt_count", 0) or 0) < 1:
            return False, "textbook_resend_attempt_count_mismatch"

        if not bridge.handle_textbook_command(chat_id, user_id, "/textbook delivered", user_record, "admin"):
            return False, "textbook_delivered_not_handled"
        after_delivered = bridge.get_textbook_last_fulfillment(user_id) or {}
        if str(after_delivered.get("delivery_status", "")).strip() != "delivery_confirmed_by_user":
            return False, "textbook_delivered_status_mismatch"

        if not bridge.handle_textbook_command(chat_id, user_id, "/textbook failed mailbox bounce", user_record, "admin"):
            return False, "textbook_failed_not_handled"
        after_failed = bridge.get_textbook_last_fulfillment(user_id) or {}
        if str(after_failed.get("delivery_status", "")).strip() != "delivery_reported_failed_by_user":
            return False, "textbook_failed_status_mismatch"
        if "user_reported:mailbox bounce" not in str(after_failed.get("last_error", "")):
            return False, "textbook_failed_reason_missing"

    return True, "ok"


def check_workspace_ttl_cleanup_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-workspace-ttl-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_WORKSPACE_STATE"] = str(tmp_path / "workspace_state.json")
        os.environ["TELEGRAM_WORKSPACE_TTL_SECONDS"] = "86400"
        os.environ["TELEGRAM_WORKSPACE_MAX_DOCS"] = "8"

        spec = importlib.util.spec_from_file_location("telegram_bridge_workspace_ttl", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9021
        chat_id = 721
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        ingest_calls: list[dict] = []
        deleted_docs: list[str] = []

        setattr(bridge, "send_message", lambda _chat_id, _text: True)

        def fake_call_n8n(webhook: str, payload: dict) -> dict:
            if webhook == bridge.RAG_INGEST_WEBHOOK:
                ingest_calls.append(dict(payload))
                return {"reply": "queued"}
            return {"reply": "ok"}

        def fake_delete_doc(tenant_id: str, doc_id: str) -> tuple[bool, str]:
            if tenant_id != f"u_{user_id}":
                return False, "tenant_mismatch"
            deleted_docs.append(doc_id)
            return True, "ok"

        setattr(bridge, "call_n8n", fake_call_n8n)
        setattr(bridge, "delete_workspace_doc_from_qdrant", fake_delete_doc)

        if not bridge.handle_workspace_command(chat_id, user_id, "/workspace create vehicle-manuals", "admin"):
            return False, "workspace_create_not_handled"

        if not bridge.handle_workspace_command(chat_id, user_id, "/workspace add wheel torque spec 140 Nm", "admin"):
            return False, "workspace_add_not_handled"

        if not ingest_calls:
            return False, "workspace_ingest_not_called"
        last_ingest = ingest_calls[-1]
        if str(last_ingest.get("source_type", "")).strip() != "workspace_temp":
            return False, "workspace_ingest_source_type_mismatch"

        entry = bridge.get_workspace(user_id)
        if not isinstance(entry, dict):
            return False, "workspace_missing_after_add"

        docs_raw = entry.get("docs")
        docs = docs_raw if isinstance(docs_raw, list) else []
        if len(docs) != 1:
            return False, "workspace_doc_count_mismatch"
        doc_id = str(docs[0].get("doc_id", "")).strip()
        if not doc_id:
            return False, "workspace_doc_id_missing"

        entry["expires_at"] = int(time.time()) - 1
        bridge.set_workspace(user_id, entry)

        cleaned, removed_docs, failed_docs = bridge.cleanup_expired_workspaces(now_ts=int(time.time()))
        if cleaned != 1:
            return False, "workspace_cleanup_count_mismatch"
        if removed_docs != 1 or failed_docs != 0:
            return False, "workspace_cleanup_doc_result_mismatch"
        if bridge.get_workspace(user_id) is not None:
            return False, "workspace_not_cleared"
        if doc_id not in deleted_docs:
            return False, "workspace_doc_not_deleted"

    return True, "ok"


def check_workspace_mode_payload_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-workspace-mode-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_WORKSPACE_STATE"] = str(tmp_path / "workspace_state.json")
        os.environ["TELEGRAM_WORKSPACE_TTL_SECONDS"] = "86400"

        spec = importlib.util.spec_from_file_location("telegram_bridge_workspace_mode", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9022
        chat_id = 722
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "admin", status="active")
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        record["registration_state"] = "active"
        record["full_name"] = "Smoke Admin"
        record["telegram_username"] = "smokeuser"
        record["updated_at"] = bridge.utc_now()
        bridge.USER_REGISTRY.setdefault("users", {})[str(user_id)] = record
        bridge.save_user_registry(bridge.USER_REGISTRY)
        bridge.set_memory_enabled(user_id, True)
        bridge.add_memory_note(user_id, "memory-note-smoke")

        payloads: list[dict] = []
        setattr(bridge, "send_message", lambda _chat_id, _text: True)

        def fake_call_n8n(webhook: str, payload: dict) -> dict:
            if webhook == bridge.RAG_INGEST_WEBHOOK:
                return {"reply": "queued"}
            if webhook in {bridge.RAG_WEBHOOK, bridge.OPS_WEBHOOK}:
                payloads.append(dict(payload))
                return {"reply": "ok"}
            return {"reply": "ok"}

        setattr(bridge, "call_n8n", fake_call_n8n)

        bridge.handle_workspace_command(chat_id, user_id, "/workspace create mode-smoke", "admin")
        bridge.handle_workspace_command(chat_id, user_id, "/workspace add workspace note for smoke", "admin")
        bridge.handle_workspace_command(chat_id, user_id, "/workspace mode workspace", "admin")

        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": user_id, "username": "smokeuser", "first_name": "Smoke"},
                "text": "/ops show workspace mode payload",
            },
        }
        bridge.process_update(update)

        if not payloads:
            return False, "workspace_mode_payload_missing"
        payload = payloads[-1]

        if str(payload.get("workspace_mode", "")).strip() != "workspace":
            return False, "workspace_mode_flag_mismatch"
        if not bool(payload.get("workspace_context_only", False)):
            return False, "workspace_context_only_missing"
        if bool(payload.get("memory_enabled_effective", True)):
            return False, "workspace_mode_memory_not_disabled"
        if str(payload.get("memory_summary_effective", "")).strip() != "":
            return False, "workspace_mode_memory_summary_not_cleared"
        if not bool(payload.get("workspace_active", False)):
            return False, "workspace_active_missing"
        if not isinstance(payload.get("workspace_doc_ids"), list) or not payload.get("workspace_doc_ids"):
            return False, "workspace_doc_ids_missing"

    return True, "ok"


def check_notify_quiet_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-quiet-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_quiet", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        chat_id = 700
        user_id = 9003
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)
        setattr(bridge, "send_message", lambda _cid, _txt: None)

        if not bridge.handle_notify_command(chat_id, user_id, "/notify quiet 22-07"):
            return False, "notify_quiet_set_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if not bool(record.get("quiet_hours_enabled", False)):
            return False, "notify_quiet_not_enabled"
        if int(record.get("quiet_hours_start_hour", -1)) != 22 or int(record.get("quiet_hours_end_hour", -1)) != 7:
            return False, "notify_quiet_window_mismatch"

        if not bridge.handle_notify_command(chat_id, user_id, "/notify quiet off"):
            return False, "notify_quiet_off_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        if bool(record.get("quiet_hours_enabled", False)):
            return False, "notify_quiet_off_failed"

    return True, "ok"


def check_notify_quiet_topic_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-quiet-topic-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_quiet_topic", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        chat_id = 701
        user_id = 9004
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        captured: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: captured.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id, user_id, "/notify quiet media 22-07"):
            return False, "notify_quiet_topic_set_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        topic_map = record.get("quiet_hours_topics") if isinstance(record.get("quiet_hours_topics"), dict) else {}
        media_cfg = topic_map.get("media") if isinstance(topic_map, dict) else None
        if not isinstance(media_cfg, dict):
            return False, "notify_quiet_topic_missing"
        if int(media_cfg.get("start_hour", -1)) != 22 or int(media_cfg.get("end_hour", -1)) != 7:
            return False, "notify_quiet_topic_window_mismatch"

        if not bridge.handle_notify_command(chat_id, user_id, "/notify quiet media off"):
            return False, "notify_quiet_topic_off_not_handled"
        record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        topic_map_raw = record.get("quiet_hours_topics") if isinstance(record, dict) else {}
        topic_map = topic_map_raw if isinstance(topic_map_raw, dict) else {}
        if "media" in topic_map:
            return False, "notify_quiet_topic_off_failed"

    return True, "ok"


def check_notify_delivery_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-delivery-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DELIVERY_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_delivery", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9008
        chat_id = 708
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)
        bridge.save_delivery_state(
            {
                "users": {
                    "9111": {
                        "notify_delivery_fail_streak": 3,
                        "notify_delivery_last_reason": "telegram_http_400",
                        "notify_delivery_last_failed_at": int(time.time()) - 45,
                        "notify_quarantine_until": int(time.time()) + 180,
                    }
                },
                "updated_at": "",
            }
        )

        out_messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: out_messages.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify delivery list 5"):
            return False, "notify_delivery_not_handled"
        if not out_messages:
            return False, "notify_delivery_no_output"
        text = out_messages[-1]
        if "Delivery inbox:" not in text:
            return False, "notify_delivery_missing_header"
        if "user=9111" not in text or "reason=telegram_http_400" not in text:
            return False, "notify_delivery_missing_entry"

    return True, "ok"


def check_notify_health_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-notify-health-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DELIVERY_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")
        os.environ["TELEGRAM_DELIVERY_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")

        now_ts = int(time.time())
        (tmp_path / "notify_stats.json").write_text(
            json.dumps(
                {
                    "events": [
                        {"ts": now_ts - 60, "topic": "media-alerts", "result": "sent", "reason": "", "recipients": 2},
                        {"ts": now_ts - 50, "topic": "ops-alerts", "result": "sent_partial", "reason": "telegram_http_400", "recipients": 1},
                        {"ts": now_ts - 40, "topic": "ops-alerts", "result": "failed", "reason": "send_error", "recipients": 0},
                    ],
                    "updated_at": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (tmp_path / "delivery_state.json").write_text(
            json.dumps(
                {
                    "users": {
                        "9001": {
                            "notify_delivery_last_reason": "send_error",
                            "notify_delivery_fail_streak": 1,
                            "notify_delivery_last_failed_at": now_ts - 30,
                        },
                        "9002": {
                            "notify_delivery_last_reason": "telegram_http_400",
                            "notify_delivery_fail_streak": 2,
                            "notify_delivery_last_failed_at": now_ts - 20,
                            "notify_quarantine_until": now_ts + 300,
                        },
                    },
                    "media_quarantine_bypass_once": {
                        "enabled": True,
                        "armed_at": now_ts - 10,
                        "expires_at": now_ts + 120,
                    },
                    "updated_at": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        spec = importlib.util.spec_from_file_location("telegram_bridge_notify_health", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9034
        chat_id = 734
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        out_messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: out_messages.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify health"):
            return False, "notify_health_not_handled"
        if not out_messages:
            return False, "notify_health_no_output"

        output = out_messages[-1]
        if "Notification health (last 24h):" not in output:
            return False, "notify_health_missing_header"
        if "- total_events: 3" not in output:
            return False, "notify_health_missing_total"
        if "- delivery_inbox_entries: 2" not in output:
            return False, "notify_health_missing_delivery_inbox"
        if "- quarantined_active: 1" not in output:
            return False, "notify_health_missing_quarantine_count"

    return True, "ok"


def check_notify_delivery_retry_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-delivery-retry-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DELIVERY_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")

        now_ts = int(time.time())
        (tmp_path / "delivery_state.json").write_text(
            json.dumps(
                {
                    "users": {
                        "9111": {
                            "notify_delivery_last_reason": "send_error",
                            "notify_delivery_fail_streak": 2,
                            "notify_delivery_last_failed_at": now_ts - 90,
                        },
                        "9222": {
                            "notify_delivery_last_reason": "telegram_http_400",
                            "notify_delivery_fail_streak": 3,
                            "notify_delivery_last_failed_at": now_ts - 60,
                            "notify_quarantine_until": now_ts + 600,
                        },
                    },
                    "updated_at": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        spec = importlib.util.spec_from_file_location("telegram_bridge_delivery_retry", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9035
        chat_id = 735
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        out_messages: list[str] = []

        def fake_send_message(target_chat_id: int, text: str) -> bool:
            if int(target_chat_id) == chat_id:
                out_messages.append(str(text))
                return True
            return int(target_chat_id) == 9111

        setattr(bridge, "send_message", fake_send_message)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify delivery retry all 10"):
            return False, "notify_delivery_retry_not_handled"
        if not out_messages:
            return False, "notify_delivery_retry_no_output"
        output = out_messages[-1]
        if "Delivery retry result:" not in output:
            return False, "notify_delivery_retry_missing_header"
        if "- attempted: 1" not in output:
            return False, "notify_delivery_retry_attempted_mismatch"
        if "- sent_ok: 1" not in output:
            return False, "notify_delivery_retry_sent_mismatch"
        if "- skipped_nonretryable: 1" not in output:
            return False, "notify_delivery_retry_nonretryable_mismatch"

        state = bridge.load_delivery_state()
        users = state.get("users") if isinstance(state, dict) else {}
        user_9111 = users.get("9111") if isinstance(users, dict) else None
        user_9222 = users.get("9222") if isinstance(users, dict) else None
        if not isinstance(user_9111, dict) or not isinstance(user_9222, dict):
            return False, "notify_delivery_retry_state_missing"
        try:
            fail_streak_9111 = int(user_9111.get("notify_delivery_fail_streak", 99))
        except (TypeError, ValueError):
            fail_streak_9111 = 99
        if fail_streak_9111 != 0:
            return False, "notify_delivery_retry_9111_not_cleared"
        if str(user_9111.get("notify_delivery_last_reason", "x")).strip() != "":
            return False, "notify_delivery_retry_9111_reason_not_cleared"
        try:
            failed_at_9111 = int(user_9111.get("notify_delivery_last_failed_at", -1))
        except (TypeError, ValueError):
            failed_at_9111 = -1
        if failed_at_9111 != 0:
            return False, "notify_delivery_retry_9111_failed_at_not_cleared"
        if str(user_9222.get("notify_delivery_last_reason", "")).strip() != "telegram_http_400":
            return False, "notify_delivery_retry_9222_reason_changed"

    return True, "ok"


def check_notify_quarantine_media_bypass_once_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-quarantine-bypass-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_MEDIA_QUARANTINE_BYPASS_TTL_SECONDS"] = "300"

        spec = importlib.util.spec_from_file_location("telegram_bridge_quarantine_bypass", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9032
        chat_id = 732
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        out_messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: out_messages.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify quarantine media-bypass-once"):
            return False, "notify_quarantine_media_bypass_usage_not_handled"
        if not out_messages or "Usage: /notify quarantine media-bypass-once CONFIRM" not in out_messages[-1]:
            return False, "notify_quarantine_media_bypass_usage_missing"

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify quarantine media-bypass-once CONFIRM"):
            return False, "notify_quarantine_media_bypass_confirm_not_handled"

        state = bridge.load_delivery_state()
        marker = state.get("media_quarantine_bypass_once") if isinstance(state, dict) else None
        if not isinstance(marker, dict):
            return False, "notify_quarantine_media_bypass_marker_missing"
        if not bool(marker.get("enabled", False)):
            return False, "notify_quarantine_media_bypass_not_enabled"
        if int(marker.get("armed_by", 0) or 0) != admin_id:
            return False, "notify_quarantine_media_bypass_armed_by_mismatch"
        if int(marker.get("expires_at", 0) or 0) <= int(marker.get("armed_at", 0) or 0):
            return False, "notify_quarantine_media_bypass_expiry_invalid"

    return True, "ok"


def check_notify_quarantine_media_bypass_status_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-quarantine-bypass-status-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")

        now_ts = int(time.time())
        (tmp_path / "delivery_state.json").write_text(
            json.dumps(
                {
                    "users": {},
                    "media_quarantine_bypass_once": {
                        "enabled": False,
                        "armed_at": now_ts - 120,
                        "armed_by": 9001,
                        "expires_at": now_ts + 600,
                        "consumed_at": now_ts - 30,
                        "consume_reason": "used",
                    },
                    "updated_at": "",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        spec = importlib.util.spec_from_file_location("telegram_bridge_quarantine_bypass_status", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9033
        chat_id = 733
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        out_messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: out_messages.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify quarantine media-bypass-status"):
            return False, "notify_quarantine_media_bypass_status_not_handled"
        if not out_messages:
            return False, "notify_quarantine_media_bypass_status_no_output"

        output = out_messages[-1]
        if "Media quarantine bypass status (one-time):" not in output:
            return False, "notify_quarantine_media_bypass_status_missing_header"
        if "- enabled: no" not in output:
            return False, "notify_quarantine_media_bypass_status_missing_enabled"
        if "- armed_by: 9001" not in output:
            return False, "notify_quarantine_media_bypass_status_missing_armed_by"
        if "- consume_reason: used" not in output:
            return False, "notify_quarantine_media_bypass_status_missing_reason"

    return True, "ok"


def check_notify_media_first_seen_stats_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-media-first-seen-stats-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_STATE"] = str(tmp_path / "media_first_seen.json")
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")

        now_ts = int(time.time())
        (tmp_path / "media_first_seen.json").write_text(
            json.dumps(
                {
                    "items": {
                        "media-alerts|movie|dune2021|2021": {
                            "first_seen": now_ts - 3600,
                            "last_seen": now_ts - 120,
                            "event_count": 3,
                        },
                        "media-alerts|movie|arrival2016|2016": {
                            "first_seen": now_ts - 7200,
                            "last_seen": now_ts - 300,
                            "event_count": 2,
                        },
                    },
                    "updated_at": "2026-02-27T00:00:00+00:00",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        spec = importlib.util.spec_from_file_location("telegram_bridge_media_first_seen_stats", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9016
        chat_id = 716
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: messages.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify media-first-seen stats 1"):
            return False, "notify_media_first_seen_not_handled"
        if not messages:
            return False, "notify_media_first_seen_no_output"

        output = messages[-1]
        if "Media first-seen cache:" not in output:
            return False, "notify_media_first_seen_missing_header"
        if "entries: 2" not in output:
            return False, "notify_media_first_seen_missing_count"
        if "key=media-alerts|movie|dune2021|2021" not in output:
            return False, "notify_media_first_seen_missing_top_entry"
        if "...and 1 more" not in output:
            return False, "notify_media_first_seen_missing_truncation"

    return True, "ok"


def check_notify_media_first_seen_clear_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-media-first-seen-clear-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_STATE"] = str(tmp_path / "media_first_seen.json")
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")

        now_ts = int(time.time())
        (tmp_path / "media_first_seen.json").write_text(
            json.dumps(
                {
                    "items": {
                        "media-alerts|movie|dune2021|2021": {
                            "first_seen": now_ts - 3600,
                            "last_seen": now_ts - 120,
                            "event_count": 3,
                        },
                        "media-alerts|movie|arrival2016|2016": {
                            "first_seen": now_ts - 7200,
                            "last_seen": now_ts - 300,
                            "event_count": 2,
                        },
                    },
                    "updated_at": "2026-02-27T00:00:00+00:00",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        spec = importlib.util.spec_from_file_location("telegram_bridge_media_first_seen_clear", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9017
        chat_id = 717
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        messages: list[str] = []
        setattr(bridge, "send_message", lambda _cid, text: messages.append(str(text)) or True)

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify media-first-seen clear dune 2021"):
            return False, "notify_media_first_seen_clear_not_handled"
        if not messages:
            return False, "notify_media_first_seen_clear_no_output"
        if "Cleared 1 media first-seen entry" not in messages[-1]:
            return False, "notify_media_first_seen_clear_missing_ack"

        after_clear = bridge.load_media_first_seen_state()
        items_after_clear = after_clear.get("items") if isinstance(after_clear, dict) else {}
        if not isinstance(items_after_clear, dict):
            return False, "notify_media_first_seen_clear_state_invalid"
        if any("dune2021" in key for key in items_after_clear.keys()):
            return False, "notify_media_first_seen_clear_target_still_present"

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify media-first-seen clear all CONFIRM"):
            return False, "notify_media_first_seen_clear_all_not_handled"
        if "Remaining: 0" not in messages[-1]:
            return False, "notify_media_first_seen_clear_all_missing_ack"

        final_state = bridge.load_media_first_seen_state()
        final_items = final_state.get("items") if isinstance(final_state, dict) else {}
        if not isinstance(final_items, dict) or final_items:
            return False, "notify_media_first_seen_clear_all_state_not_empty"

    return True, "ok"


def check_notify_validate_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-notify-validate-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_notify_validate", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9013
        chat_id = 713
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        messages: list[str] = []
        setattr(bridge, "send_message", lambda _chat_id, text: messages.append(str(text)) or True)
        setattr(
            bridge,
            "run_notify_validate_probe",
            lambda request_user_id: {
                "ok": True,
                "stage": "fanout",
                "topic": "ops-alerts",
                "probe_id": f"nv-local-{request_user_id}",
                "detail": "sent",
                "reason": "(none)",
                "recipients": 1,
                "latency_seconds": 0.3,
            },
        )

        if not bridge.handle_notify_command(chat_id=chat_id, user_id=admin_id, text="/notify validate"):
            return False, "notify_validate_not_handled"
        if not messages:
            return False, "notify_validate_no_output"

        text = messages[-1]
        if "Notify validate: PASS" not in text:
            return False, "notify_validate_missing_pass"
        if "probe_id: nv-local-9013" not in text:
            return False, "notify_validate_missing_probe_id"
        if "detail: sent" not in text:
            return False, "notify_validate_missing_detail"

    return True, "ok"


def check_digest_now_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-digest-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_digest", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9005
        target_id = 9010
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.set_user_record(bridge.USER_REGISTRY, target_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        bridge.save_digest_queue_state(
            {
                "users": {
                    str(target_id): {
                        "items": [
                            {
                                "ts": 123,
                                "topic": "ops-alerts",
                                "title": "Synthetic queued",
                                "message": "digest command verification",
                                "priority": 4,
                                "incident_id": "INC-TEST123",
                            }
                        ],
                        "updated_at": "",
                    }
                },
                "updated_at": "",
            }
        )

        sent_to: list[int] = []

        def fake_send(chat_id: int, text: str) -> bool:
            sent_to.append(int(chat_id))
            return True

        setattr(bridge, "send_message", fake_send)
        if not bridge.handle_digest_command(chat_id=admin_id, user_id=admin_id, text="/digest now"):
            return False, "digest_now_not_handled"

        after_state = bridge.load_digest_queue_state()
        queued_users, queued_items = bridge.digest_queue_counts(after_state)
        if queued_items != 0 or queued_users != 0:
            return False, "digest_queue_not_cleared"

        if target_id not in sent_to:
            return False, "digest_target_not_sent"

    return True, "ok"


def check_digest_stats_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-digest-stats-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")

        spec = importlib.util.spec_from_file_location("telegram_bridge_digest_stats", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9006
        target_id = 9011
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.set_user_record(bridge.USER_REGISTRY, target_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        bridge.save_digest_queue_state(
            {
                "users": {
                    str(target_id): {
                        "items": [
                            {
                                "ts": 123,
                                "topic": "ops-alerts",
                                "title": "Synthetic queued",
                                "message": "digest stats verification",
                                "priority": 4,
                                "incident_id": "INC-TEST124",
                            }
                        ],
                        "updated_at": "",
                    }
                },
                "updated_at": "",
                "last_flush": {"at": "2026-01-01T00:00:00+00:00", "attempted": 1, "sent": 1, "failed": 0},
            }
        )

        out_messages: list[str] = []
        setattr(bridge, "send_message", lambda _chat_id, text: out_messages.append(str(text)) or True)

        if not bridge.handle_digest_command(chat_id=admin_id, user_id=admin_id, text="/digest stats"):
            return False, "digest_stats_not_handled"
        if not out_messages:
            return False, "digest_stats_no_output"

        text = out_messages[-1].lower()
        expected_fragments = ["digest queue stats", "queued_users", "queued_items", "last_flush_attempted", "last_flush_sent"]
        for fragment in expected_fragments:
            if fragment not in text:
                return False, f"digest_stats_missing_{fragment}"

    return True, "ok"


def check_low_signal_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-low-signal-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_LOW_SIGNAL_FILTER_ENABLED"] = "true"
        os.environ["TELEGRAM_LOW_SIGNAL_TOKEN_MAX_CHARS"] = "2"

        spec = importlib.util.spec_from_file_location("telegram_bridge_low_signal", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9010
        chat_id = 710
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "user", status="active")
        seeded_record = bridge.get_user_record(bridge.USER_REGISTRY, user_id) or {}
        seeded_record["full_name"] = "Smoke User"
        seeded_record["telegram_username"] = "smokeuser"
        seeded_record["age"] = 30
        seeded_record["account_class"] = "adult"
        seeded_record["registration_state"] = "active"
        seeded_record["child_guardrails_enabled"] = False
        bridge.USER_REGISTRY.setdefault("users", {})[str(user_id)] = seeded_record
        bridge.save_user_registry(bridge.USER_REGISTRY)

        sent_messages: list[str] = []
        setattr(bridge, "send_message", lambda _chat_id, text: sent_messages.append(str(text)))

        def unexpected_n8n(*_args, **_kwargs):
            raise RuntimeError("n8n_called_for_low_signal")

        setattr(bridge, "call_n8n", unexpected_n8n)

        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": user_id, "username": "smokeuser", "first_name": "Smoke"},
                "text": "ds",
            },
        }

        try:
            bridge.process_update(update)
        except RuntimeError as exc:
            if "n8n_called_for_low_signal" in str(exc):
                return False, "low_signal_routed_to_n8n"
            raise

        if not sent_messages:
            return False, "low_signal_no_reply"

        if "add more detail" not in sent_messages[-1].lower():
            return False, "low_signal_reply_mismatch"

    return True, "ok"


def check_rate_limit_debounce_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-rate-limit-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_RATE_LIMIT_MAX_REQUESTS"] = "2"
        os.environ["TELEGRAM_RATE_LIMIT_WINDOW_SECONDS"] = "30"
        os.environ["TELEGRAM_RATE_LIMIT_NOTICE_DEBOUNCE_ENABLED"] = "true"

        spec = importlib.util.spec_from_file_location("telegram_bridge_rate_limit", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        user_id = 9011
        bridge.set_user_record(bridge.USER_REGISTRY, user_id, "user", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        allowed1, _, notify1 = bridge.check_and_record_rate_limit(user_id)
        allowed2, _, notify2 = bridge.check_and_record_rate_limit(user_id)
        allowed3, _, notify3 = bridge.check_and_record_rate_limit(user_id)
        allowed4, _, notify4 = bridge.check_and_record_rate_limit(user_id)

        if not (allowed1 and allowed2 and (not allowed3) and (not allowed4)):
            return False, "rate_limit_sequence_mismatch"
        if notify1 or notify2:
            return False, "rate_limit_unexpected_notify_while_allowed"
        if not notify3:
            return False, "rate_limit_missing_first_notify"
        if notify4:
            return False, "rate_limit_debounce_failed"

        report = bridge.build_rate_limit_report()
        if "notice_debounce:" not in report:
            return False, "rate_limit_report_missing_debounce"

    return True, "ok"


def check_admin_command_cooldown_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-admin-cooldown-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
        os.environ["TELEGRAM_BOOTSTRAP_ADMINS"] = ""
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_APPROVALS_STATE"] = str(tmp_path / "approvals.json")
        os.environ["TELEGRAM_MEDIA_SELECTION_STATE"] = str(tmp_path / "media_selection.json")
        os.environ["TELEGRAM_RATE_LIMIT_STATE"] = str(tmp_path / "rate_limit.json")
        os.environ["TELEGRAM_MEMORY_STATE"] = str(tmp_path / "memory.json")
        os.environ["TELEGRAM_BRIDGE_STATE"] = str(tmp_path / "bridge_state.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_STATE"] = str(tmp_path / "admin_command_cooldowns.json")
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_SECONDS"] = "60"
        os.environ["TELEGRAM_ADMIN_COMMAND_COOLDOWN_COMMANDS"] = "/digest stats"

        spec = importlib.util.spec_from_file_location("telegram_bridge_admin_cooldown", BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "bridge_import_spec"

        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)

        admin_id = 9015
        chat_id = 715
        bridge.set_user_record(bridge.USER_REGISTRY, admin_id, "admin", status="active")
        bridge.save_user_registry(bridge.USER_REGISTRY)

        messages: list[str] = []
        setattr(bridge, "send_message", lambda _chat_id, text: messages.append(str(text)) or True)

        if not bridge.handle_digest_command(chat_id=chat_id, user_id=admin_id, text="/digest stats"):
            return False, "admin_cooldown_first_not_handled"
        first_count = len(messages)
        if first_count < 1:
            return False, "admin_cooldown_first_no_output"

        if not bridge.handle_digest_command(chat_id=chat_id, user_id=admin_id, text="/digest stats"):
            return False, "admin_cooldown_second_not_handled"
        second_count = len(messages)
        if second_count != first_count + 1:
            return False, "admin_cooldown_warning_missing"

        if "command cooldown active" not in messages[-1].lower():
            return False, "admin_cooldown_warning_text_missing"

        if not bridge.handle_digest_command(chat_id=chat_id, user_id=admin_id, text="/digest stats"):
            return False, "admin_cooldown_third_not_handled"
        third_count = len(messages)
        if third_count != second_count:
            return False, "admin_cooldown_repeat_warning_not_suppressed"

    return True, "ok"


def check_media_first_seen_only_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-media-first-seen-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_STATE_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")
        os.environ["TELEGRAM_NOTIFY_STATS_SQLITE_PATH"] = str(tmp_path / "notify_state.db")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DEDUPE_STATE"] = str(tmp_path / "dedupe.json")
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_STATE"] = str(tmp_path / "media_first_seen.json")
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_SQLITE_PATH"] = str(tmp_path / "media_first_seen.db")
        os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "true"
        os.environ["TELEGRAM_NOTIFY_CRITICAL_ONLY"] = "false"
        os.environ["TELEGRAM_MEDIA_READY_GATE_ENABLED"] = "false"
        os.environ["TELEGRAM_MEDIA_NOISE_FILTER_ENABLED"] = "false"
        os.environ["TELEGRAM_MEDIA_FIRST_SEEN_ONLY_ENABLED"] = "true"
        os.environ["TELEGRAM_INCIDENT_COLLAPSE_ENABLED"] = "false"

        spec = importlib.util.spec_from_file_location("ntfy_bridge_media_first_seen", NTFY_BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "ntfy_bridge_import_spec"

        ntfy_bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ntfy_bridge)

        registry = {
            "users": {
                "8676528265": {
                    "status": "active",
                    "role": "admin",
                    "notify_topics": ["all"],
                    "quiet_hours_enabled": False,
                }
            }
        }
        (tmp_path / "users.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        (tmp_path / "dedupe.json").write_text(json.dumps({"items": {}}, ensure_ascii=False), encoding="utf-8")

        send_calls: list[tuple[int, str]] = []

        def fake_send_or_edit(chat_id: int, text: str, edit_message_id: int | None = None):
            send_calls.append((int(chat_id), str(text)))
            return True, "sent", 901, bool(edit_message_id)

        setattr(ntfy_bridge, "send_or_edit_telegram_message", fake_send_or_edit)

        title = "Dune (2021) is now available in Plex"
        message = "Dune (2021) is now available in Plex"
        ntfy_bridge.fanout_to_telegram(topic="media-alerts", title=title, message=message, priority=3)
        ntfy_bridge.fanout_to_telegram(topic="media-alerts", title=title, message=message, priority=3)

        if len(send_calls) != 1:
            return False, f"media_first_seen_expected_one_send_got_{len(send_calls)}"

        stats_state = ntfy_bridge.load_notify_stats_state()
        events = stats_state.get("events") if isinstance(stats_state, dict) else []
        media_events = [event for event in events if isinstance(event, dict) and event.get("topic") == "media-alerts"]
        if len(media_events) < 2:
            return False, "media_first_seen_missing_events"

        last_event = media_events[-1]
        if str(last_event.get("result", "")) != "skipped":
            return False, "media_first_seen_last_result_mismatch"
        if str(last_event.get("reason", "")) != "media_first_seen_repeat":
            return False, "media_first_seen_last_reason_mismatch"

        first_seen_state = ntfy_bridge.load_media_first_seen_state()
        items = first_seen_state.get("items") if isinstance(first_seen_state, dict) else {}
        if not isinstance(items, dict) or len(items) != 1:
            return False, "media_first_seen_state_items_mismatch"

    return True, "ok"


def check_deferred_digest_cleanup_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-digest-cleanup-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DEDUPE_STATE"] = str(tmp_path / "dedupe.json")
        os.environ["TELEGRAM_STATE_SQLITE_PATH"] = str(tmp_path / "telegram_state.db")
        os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "true"
        os.environ["TELEGRAM_NOTIFY_CRITICAL_ONLY"] = "false"
        os.environ["TELEGRAM_MEDIA_READY_GATE_ENABLED"] = "false"
        os.environ["TELEGRAM_MEDIA_NOISE_FILTER_ENABLED"] = "true"

        spec = importlib.util.spec_from_file_location("ntfy_bridge_digest_cleanup", NTFY_BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "ntfy_bridge_import_spec"

        ntfy_bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ntfy_bridge)

        registry = {
            "users": {
                "8676528265": {
                    "status": "active",
                    "role": "admin",
                    "notify_topics": ["all"],
                    "quiet_hours_enabled": False,
                }
            }
        }
        (tmp_path / "users.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

        queue_state = {
            "users": {
                "8676528265": {
                    "items": [
                        {
                            "ts": int(time.time()) - 100,
                            "topic": "media-alerts",
                            "category": "media",
                            "title": "Media Ready Verification Sintel",
                            "message": "Sintel is now available in Plex. verification_run=media-verify-111",
                            "priority": 3,
                            "incident_id": "INC-A",
                        },
                        {
                            "ts": int(time.time()) - 90,
                            "topic": "media-alerts",
                            "category": "media",
                            "title": "Media Ready Verification Sintel",
                            "message": "Sintel is now available in Plex. verification_run=media-verify-222",
                            "priority": 3,
                            "incident_id": "INC-B",
                        },
                        {
                            "ts": int(time.time()) - 80,
                            "topic": "media-alerts",
                            "category": "media",
                            "title": "Quiet Topic Drill Media",
                            "message": "Sintel is now available in Plex. quiet_topic_drill=1",
                            "priority": 3,
                            "incident_id": "INC-C",
                        },
                        {
                            "ts": int(time.time()) - 70,
                            "topic": "media-alerts",
                            "category": "media",
                            "title": "Interstellar (2014) is now available in Plex",
                            "message": "Interstellar (2014) is now available in Plex",
                            "priority": 3,
                            "incident_id": "INC-D",
                        },
                        {
                            "ts": int(time.time()) - 60,
                            "topic": "media-alerts",
                            "category": "media",
                            "title": "Interstellar (2014) is now available in Plex",
                            "message": "Interstellar (2014) is now available in Plex",
                            "priority": 3,
                            "incident_id": "INC-E",
                        },
                    ],
                    "updated_at": "",
                }
            },
            "updated_at": "",
        }
        ntfy_bridge.save_digest_queue_state(queue_state)

        sent_texts: list[str] = []
        setattr(ntfy_bridge, "send_telegram_message", lambda _chat_id, text: sent_texts.append(str(text)) or (True, "sent"))

        ntfy_bridge.flush_deferred_digests(registry)

        if len(sent_texts) != 1:
            return False, f"digest_cleanup_expected_one_message_got_{len(sent_texts)}"

        digest_text = sent_texts[0]
        if "Deferred alert digest (1 item)" not in digest_text:
            return False, "digest_cleanup_count_mismatch"
        if "Interstellar (2014) is now available in Plex" not in digest_text:
            return False, "digest_cleanup_missing_interstellar"
        if "verification_run=" in digest_text:
            return False, "digest_cleanup_verification_not_filtered"
        if "quiet_topic_drill=" in digest_text:
            return False, "digest_cleanup_quiet_drill_not_filtered"
        if "Media Ready Verification" in digest_text:
            return False, "digest_cleanup_verification_title_not_filtered"
        if "hidden low-signal updates: 3" not in digest_text:
            return False, "digest_cleanup_noise_counter_missing"
        if "condensed duplicates: 1" not in digest_text:
            return False, "digest_cleanup_dedupe_counter_missing"

    return True, "ok"


def check_topic_quiet_defer_vs_critical_bypass_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-topic-quiet-flow-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DEDUPE_STATE"] = str(tmp_path / "dedupe.json")
        os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "true"
        os.environ["TELEGRAM_NOTIFY_CRITICAL_ONLY"] = "false"
        os.environ["TELEGRAM_MEDIA_READY_GATE_ENABLED"] = "false"
        os.environ["TELEGRAM_MEDIA_NOISE_FILTER_ENABLED"] = "false"

        spec = importlib.util.spec_from_file_location("ntfy_bridge_topic_quiet", NTFY_BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "ntfy_bridge_import_spec"

        ntfy_bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ntfy_bridge)

        now_hour = int(ntfy_bridge.current_local_hour())
        start_hour = (now_hour - 1) % 24
        end_hour = (now_hour + 1) % 24

        registry = {
            "users": {
                "8676528265": {
                    "status": "active",
                    "role": "admin",
                    "notify_topics": ["all"],
                    "quiet_hours_enabled": False,
                    "quiet_hours_topics": {
                        "media": {
                            "enabled": True,
                            "start_hour": start_hour,
                            "end_hour": end_hour,
                        }
                    },
                }
            }
        }
        (tmp_path / "users.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

        sent_calls: list[tuple[int, str]] = []

        def fake_send_or_edit(chat_id: int, text: str, edit_message_id: int | None = None):
            sent_calls.append((int(chat_id), str(text)))
            return True, "sent", 123, bool(edit_message_id)

        setattr(ntfy_bridge, "send_or_edit_telegram_message", fake_send_or_edit)

        ntfy_bridge.fanout_to_telegram(
            topic="media-alerts",
            title="Topic Quiet Smoke Media",
            message="non-critical media event",
            priority=3,
        )
        ntfy_bridge.fanout_to_telegram(
            topic="ops-alerts",
            title="Topic Quiet Smoke Ops",
            message="CRITICAL: bypass quiet-hours verification",
            priority=5,
        )

        if len(sent_calls) != 1:
            return False, f"topic_quiet_expected_one_send_got_{len(sent_calls)}"

        sent_chat_id, sent_text = sent_calls[0]
        if sent_chat_id != 8676528265:
            return False, "topic_quiet_sent_wrong_chat"
        if "Incident ID:" not in sent_text:
            return False, "topic_quiet_missing_incident_text"

        digest_state = ntfy_bridge.load_digest_queue_state()
        digest_users = digest_state.get("users") if isinstance(digest_state, dict) else {}
        if not isinstance(digest_users, dict):
            return False, "topic_quiet_digest_missing_users"
        digest_entry = digest_users.get("8676528265") if isinstance(digest_users.get("8676528265"), dict) else {}
        digest_items = digest_entry.get("items") if isinstance(digest_entry, dict) and isinstance(digest_entry.get("items"), list) else []
        media_items = [item for item in digest_items if isinstance(item, dict) and str(item.get("topic", "")) == "media-alerts"]
        if len(media_items) < 1:
            return False, "topic_quiet_media_not_deferred"

        stats_state = ntfy_bridge.load_notify_stats_state()
        events = stats_state.get("events") if isinstance(stats_state, dict) else []
        if not isinstance(events, list):
            return False, "topic_quiet_stats_missing"
        media_last = None
        ops_last = None
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("topic") == "media-alerts":
                media_last = event
            if event.get("topic") == "ops-alerts":
                ops_last = event

        if not isinstance(media_last, dict) or media_last.get("result") != "deferred":
            return False, "topic_quiet_media_result_mismatch"
        if str(media_last.get("reason", "")) != "quiet_hours":
            return False, "topic_quiet_media_reason_mismatch"
        if not isinstance(ops_last, dict) or ops_last.get("result") not in {"sent", "sent_partial"}:
            return False, "topic_quiet_ops_result_mismatch"

    return True, "ok"


def check_incident_collapse_edit_path_local() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="tg-smoke-incident-collapse-") as tmp:
        tmp_path = Path(tmp)

        os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "dummy") or "dummy"
        os.environ["TELEGRAM_USER_REGISTRY"] = str(tmp_path / "users.json")
        os.environ["TELEGRAM_NOTIFY_STATS_STATE"] = str(tmp_path / "notify_stats.json")
        os.environ["TELEGRAM_DIGEST_QUEUE_STATE"] = str(tmp_path / "digest_queue.json")
        os.environ["TELEGRAM_INCIDENT_STATE"] = str(tmp_path / "incidents.json")
        os.environ["TELEGRAM_DELIVERY_STATE"] = str(tmp_path / "delivery_state.json")
        os.environ["TELEGRAM_DEDUPE_STATE"] = str(tmp_path / "dedupe.json")
        os.environ["TELEGRAM_NOTIFICATIONS_ENABLED"] = "true"
        os.environ["TELEGRAM_NOTIFY_CRITICAL_ONLY"] = "false"
        os.environ["TELEGRAM_MEDIA_READY_GATE_ENABLED"] = "false"
        os.environ["TELEGRAM_MEDIA_NOISE_FILTER_ENABLED"] = "false"
        os.environ["TELEGRAM_INCIDENT_COLLAPSE_ENABLED"] = "true"
        os.environ["TELEGRAM_INCIDENT_COLLAPSE_WINDOW_SECONDS"] = "900"

        spec = importlib.util.spec_from_file_location("ntfy_bridge_incident_collapse", NTFY_BRIDGE_PATH)
        if spec is None or spec.loader is None:
            return False, "ntfy_bridge_import_spec"

        ntfy_bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ntfy_bridge)

        registry = {
            "users": {
                "8676528265": {
                    "status": "active",
                    "role": "admin",
                    "notify_topics": ["all"],
                    "quiet_hours_enabled": False,
                }
            }
        }
        (tmp_path / "users.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

        send_calls: list[tuple[int, int | None, str]] = []

        def fake_send_or_edit(chat_id: int, text: str, edit_message_id: int | None = None):
            send_calls.append((int(chat_id), edit_message_id, str(text)))
            if edit_message_id and int(edit_message_id) > 0:
                return True, "sent", int(edit_message_id), True
            return True, "sent", 777, False

        setattr(ntfy_bridge, "send_or_edit_telegram_message", fake_send_or_edit)

        incident_args = {
            "topic": "ops-alerts",
            "title": "Incident Collapse Smoke",
            "message": "CRITICAL: collapse path verification",
            "priority": 5,
        }

        ntfy_bridge.save_dedupe_state({"items": {}})
        ntfy_bridge.fanout_to_telegram(**incident_args)
        ntfy_bridge.save_dedupe_state({"items": {}})
        ntfy_bridge.fanout_to_telegram(**incident_args)

        if len(send_calls) != 2:
            return False, f"incident_collapse_expected_2_calls_got_{len(send_calls)}"

        first_call = send_calls[0]
        second_call = send_calls[1]
        if first_call[1] not in {None, 0}:
            return False, "incident_collapse_first_call_unexpected_edit_id"
        if second_call[1] != 777:
            return False, "incident_collapse_second_call_missing_edit_id"

        incident_state = ntfy_bridge.load_incident_state()
        incidents = incident_state.get("incidents") if isinstance(incident_state, dict) else {}
        if not isinstance(incidents, dict):
            return False, "incident_collapse_missing_incidents"

        incident_id = ntfy_bridge.build_incident_id(
            topic="ops-alerts",
            category="ops",
            title="Incident Collapse Smoke",
            message="CRITICAL: collapse path verification",
        )
        incident = incidents.get(incident_id)
        if not isinstance(incident, dict):
            return False, "incident_collapse_missing_incident_record"

        if int(incident.get("event_count", 0) or 0) < 2:
            return False, "incident_collapse_event_count_mismatch"

        targets = incident.get("message_targets") if isinstance(incident.get("message_targets"), dict) else {}
        target = targets.get("8676528265") if isinstance(targets.get("8676528265"), dict) else {}
        if int(target.get("message_id", 0) or 0) != 777:
            return False, "incident_collapse_message_target_mismatch"

    return True, "ok"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Telegram/chat smoke checks.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available check names and exit.",
    )
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        metavar="NAME",
        help="Run only the named check (repeatable).",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "live", "local"],
        default="all",
        help="Select check class: all (default), live webhook checks, or local/offline checks.",
    )
    return parser.parse_args()


def main() -> int:
    checks = [
        ("webhook_basic", "live", check_webhook_basic),
        ("workspace_mode_live_webhook", "live", check_workspace_mode_live_webhook),
        ("profile_seed_fallback_route", "live", check_profile_seed_fallback_route),
        ("personality_correction_ack_live", "live", check_personality_correction_ack_live),
        ("personality_uncertainty_no_hallucination_live", "live", check_personality_uncertainty_no_hallucination_live),
        ("personality_low_confidence_tier_live", "live", check_personality_low_confidence_tier_live),
        ("personality_recovery_mode_live", "live", check_personality_recovery_mode_live),
        ("personality_smalltalk_budget_marker_live", "live", check_personality_smalltalk_budget_marker_live),
        ("personality_rag_budget_marker_live", "live", check_personality_rag_budget_marker_live),
        ("personality_ops_budget_marker_live", "live", check_personality_ops_budget_marker_live),
        ("tenant_isolation", "live", check_tenant_isolation),
        ("textbook_fulfillment_contract", "live", check_textbook_fulfillment_contract),
        ("textbook_untrusted_source_local", "local", check_textbook_untrusted_source_local),
        ("textbook_pick_alias_local", "local", check_textbook_pick_alias_local),
        ("textbook_delivery_ack_retry_local", "local", check_textbook_delivery_ack_retry_local),
        ("workspace_ttl_cleanup_local", "local", check_workspace_ttl_cleanup_local),
        ("workspace_mode_payload_local", "local", check_workspace_mode_payload_local),
        ("profile_commands_local", "local", check_profile_commands_local),
        ("memory_regression_local", "local", check_memory_regression_local),
        ("memory_tier_decay_order_local", "local", check_memory_tier_decay_order_local),
        ("memory_intent_scope_local", "local", check_memory_intent_scope_local),
        ("memory_telemetry_local", "local", check_memory_telemetry_local),
        ("memory_canary_controls_local", "local", check_memory_canary_controls_local),
        ("memory_conflict_workflow_local", "local", check_memory_conflict_workflow_local),
        ("memory_feedback_ranking_local", "local", check_memory_feedback_ranking_local),
        ("child_account_guardrails_local", "local", check_child_account_guardrails_local),
        ("status_json_local", "local", check_status_json_local),
        ("notify_quiet_local", "local", check_notify_quiet_local),
        ("notify_quiet_topic_local", "local", check_notify_quiet_topic_local),
        ("notify_delivery_local", "local", check_notify_delivery_local),
        ("notify_health_local", "local", check_notify_health_local),
        ("notify_delivery_retry_local", "local", check_notify_delivery_retry_local),
        ("notify_quarantine_media_bypass_once_local", "local", check_notify_quarantine_media_bypass_once_local),
        ("notify_quarantine_media_bypass_status_local", "local", check_notify_quarantine_media_bypass_status_local),
        ("notify_media_first_seen_stats_local", "local", check_notify_media_first_seen_stats_local),
        ("notify_media_first_seen_clear_local", "local", check_notify_media_first_seen_clear_local),
        ("notify_validate_local", "local", check_notify_validate_local),
        ("digest_now_local", "local", check_digest_now_local),
        ("digest_stats_local", "local", check_digest_stats_local),
        ("low_signal_local", "local", check_low_signal_local),
        ("rate_limit_debounce_local", "local", check_rate_limit_debounce_local),
        ("admin_command_cooldown_local", "local", check_admin_command_cooldown_local),
        ("media_first_seen_only_local", "local", check_media_first_seen_only_local),
        ("deferred_digest_cleanup_local", "local", check_deferred_digest_cleanup_local),
        ("topic_quiet_defer_vs_critical_bypass_local", "local", check_topic_quiet_defer_vs_critical_bypass_local),
        ("incident_collapse_edit_path_local", "local", check_incident_collapse_edit_path_local),
    ]

    args = parse_args()
    if args.mode in {"all", "local"}:
        ensure_writable_memory_telemetry_path()

    all_check_map = {name: (kind, fn) for name, kind, fn in checks}
    if args.mode != "all":
        checks = [item for item in checks if item[1] == args.mode]
    check_map = {name: fn for name, _kind, fn in checks}

    if args.list:
        for name, kind, _ in checks:
            print(f"{name}\t[{kind}]")
        return 0

    selected_names = [str(name).strip() for name in args.check if str(name).strip()]
    if selected_names:
        unknown = [name for name in selected_names if name not in all_check_map]
        mode_mismatch = [name for name in selected_names if name in all_check_map and name not in check_map]
        if unknown:
            print(f"[FAIL] Unknown check name(s): {', '.join(unknown)}")
            print("Use --list to see valid check names.")
            return 2
        if mode_mismatch:
            print(
                f"[FAIL] Check name(s) not in mode={args.mode}: {', '.join(mode_mismatch)}"
            )
            print("Use --list --mode <all|live|local> to discover checks by mode.")
            return 2
        checks = [(name, all_check_map[name][0], all_check_map[name][1]) for name in selected_names]

    failures = 0
    print(f"Running {len(checks)} Telegram/chat smoke checks (mode={args.mode})")
    for name, _kind, fn in checks:
        ok, detail = fn()
        if ok:
            print(f"[PASS] {name}: {detail}")
        else:
            failures += 1
            print(f"[FAIL] {name}: {detail}")

    if failures:
        print(f"\nResult: {failures} failing check(s)")
        return 1

    print("\nResult: all Telegram/chat smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
