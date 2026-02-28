#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_FILE = ROOT / "policy" / "policy.v1.yaml"
DEFAULT_WORKFLOWS = [
    ROOT / "workflows" / "rag-query-webhook.json",
    ROOT / "workflows" / "rag-ingest-webhook.json",
    ROOT / "workflows" / "ops-commands-webhook.json",
    ROOT / "workflows" / "ops-audit-review-webhook.json",
    ROOT / "workflows" / "ai-chat-webhook.json",
    ROOT / "workflows" / "textbook-fulfillment-webhook.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M3 policy release gate: topic contract + memory contract + channel parity")
    parser.add_argument("--policy-file", default=str(DEFAULT_POLICY_FILE))
    parser.add_argument("--n8n-base", default="http://127.0.0.1:5678")
    parser.add_argument("--rag-webhook", default="/webhook/rag-query")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--user-id", default="111")
    parser.add_argument("--tenant-id", default="u_111")
    parser.add_argument("--summary-file", default="checkpoints/m3-policy-release-gate-summary.json")
    parser.add_argument("--tmp-summary-file", default="/tmp/m3-policy-release-gate-summary.json")
    return parser.parse_args()


def load_policy_helpers() -> tuple[Any, Any]:
    policy_loader_path = ROOT / "bridge" / "policy_loader.py"
    spec = importlib.util.spec_from_file_location("m3_policy_loader", str(policy_loader_path))
    if not spec or not spec.loader:
        raise RuntimeError("policy_loader_import_spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    load_alerts = getattr(module, "load_policy_alert_settings", None)
    load_telegram = getattr(module, "load_policy_telegram_settings", None)
    if not callable(load_alerts) or not callable(load_telegram):
        raise RuntimeError("policy_loader_missing_functions")
    return load_alerts, load_telegram


def extract_topics_from_workflow(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    topics: list[str] = []

    for match in re.findall(r"NTFY_[A-Z_]+_TOPIC\s*\|\|\s*'([^']+)'", text):
        value = str(match).strip()
        if value:
            topics.append(value)

    for match in re.findall(r"http://ntfy/([a-z0-9\-]+)", text):
        value = str(match).strip()
        if value:
            topics.append(value)

    deduped: list[str] = []
    for topic in topics:
        if topic not in deduped:
            deduped.append(topic)
    return deduped


def check_topic_contract(policy_file: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    load_alerts, _ = load_policy_helpers()
    required_topics, topic_categories = load_alerts(policy_file)

    checks: list[dict[str, Any]] = []
    observed: dict[str, list[str]] = {}

    for workflow_path in DEFAULT_WORKFLOWS:
        if not workflow_path.exists():
            checks.append(
                {
                    "name": f"workflow_exists:{workflow_path.name}",
                    "ok": False,
                    "detail": "missing",
                }
            )
            continue

        topics = extract_topics_from_workflow(workflow_path)
        observed[workflow_path.name] = topics
        checks.append(
            {
                "name": f"workflow_topics_present:{workflow_path.name}",
                "ok": len(topics) > 0,
                "detail": ",".join(topics) if topics else "none",
            }
        )

        for topic in topics:
            in_required = topic in required_topics
            in_categories = topic in topic_categories
            checks.append(
                {
                    "name": f"topic_in_policy:{workflow_path.name}:{topic}",
                    "ok": in_required or in_categories,
                    "detail": f"required={in_required} category={in_categories}",
                }
            )

    metadata = {
        "required_topics": sorted(required_topics),
        "topic_categories": dict(sorted(topic_categories.items())),
        "observed_workflow_topics": observed,
    }
    return checks, metadata


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any] | None, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = None
            try:
                candidate = json.loads(raw)
                parsed = candidate if isinstance(candidate, dict) else None
            except Exception:
                parsed = None
            return response.getcode(), parsed, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = None
        try:
            candidate = json.loads(raw)
            parsed = candidate if isinstance(candidate, dict) else None
        except Exception:
            parsed = None
        return exc.code, parsed, raw
    except Exception as exc:
        return 0, None, str(exc)


def check_memory_contract(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = f"{args.n8n_base.rstrip('/')}/{args.rag_webhook.lstrip('/')}"
    probe_payload = {
        "message": "m3 memory contract probe",
        "user_id": args.user_id,
        "tenant_id": args.tenant_id,
        "role": "user",
        "memory_enabled": True,
        "voice_memory_opt_in": True,
        "memory_summary": "m3_memory_probe_seed",
        "memory_write_mode": "summary_only",
        "memory_min_speaker_confidence": 0.91,
        "memory_write_allowed": False,
        "memory_low_confidence_policy": "deny",
        "raw_audio_persist": True,
    }

    checks: list[dict[str, Any]] = []
    responses: dict[str, Any] = {}

    for source in ("discord", "telegram", "ntfy"):
        payload = dict(probe_payload)
        payload["source"] = source
        payload["chat_id"] = 700 if source == "telegram" else f"m3-{source}"
        payload["stt_debug_response_enabled"] = source == "telegram"

        status, body, raw = post_json(url, payload, timeout=args.timeout)
        body = body if isinstance(body, dict) else {}
        responses[source] = {
            "status": status,
            "reply_present": bool(str(body.get("reply") or "").strip()),
            "memory_summary_present": "memory_summary" in body,
            "raw_tail": "\n".join(raw.splitlines()[-6:]),
        }

        checks.append({"name": f"memory_http_ok:{source}", "ok": status == 200, "detail": f"status={status}"})
        checks.append(
            {
                "name": f"memory_reply_present:{source}",
                "ok": bool(str(body.get("reply") or "").strip()),
                "detail": "reply_non_empty",
            }
        )
        checks.append(
            {
                "name": f"memory_summary_key_present:{source}",
                "ok": "memory_summary" in body,
                "detail": "has_memory_summary_key",
            }
        )

        if source == "telegram":
            debug_memory = (((body.get("debug") or {}).get("memory")) if isinstance(body, dict) else {}) or {}
            checks.append(
                {
                    "name": "memory_debug_write_mode_passthrough",
                    "ok": str(debug_memory.get("memory_write_mode") or "") == "summary_only",
                    "detail": f"value={debug_memory.get('memory_write_mode')}",
                }
            )
            checks.append(
                {
                    "name": "memory_debug_write_allowed_passthrough",
                    "ok": debug_memory.get("memory_write_allowed") is False,
                    "detail": f"value={debug_memory.get('memory_write_allowed')}",
                }
            )
            min_value = debug_memory.get("memory_min_speaker_confidence")
            try:
                min_float = float(min_value)
                min_ok = abs(min_float - 0.91) < 1e-9
            except Exception:
                min_ok = False
            checks.append(
                {
                    "name": "memory_debug_min_conf_passthrough",
                    "ok": min_ok,
                    "detail": f"value={min_value}",
                }
            )
            checks.append(
                {
                    "name": "memory_debug_raw_audio_persist_passthrough",
                    "ok": debug_memory.get("raw_audio_persist") is True,
                    "detail": f"value={debug_memory.get('raw_audio_persist')}",
                }
            )

    return checks, {"target_url": url, "responses": responses}


def check_parity(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    script_path = ROOT / "scripts" / "eval-discord-channel-parity-pack.py"
    tmp_summary = Path("/tmp/m3-policy-gate-parity-summary.json")
    tmp_contract = Path("/tmp/m3-policy-gate-parity-contract.json")
    cmd = [
        "/usr/bin/python3",
        str(script_path),
        "--n8n-base",
        str(args.n8n_base),
        "--rag-webhook",
        str(args.rag_webhook),
        "--summary-file",
        str(tmp_summary),
        "--contract-file",
        str(tmp_contract),
        "--tmp-summary-file",
        str(tmp_summary),
        "--tmp-contract-file",
        str(tmp_contract),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)

    checks: list[dict[str, Any]] = [
        {
            "name": "parity_exec",
            "ok": proc.returncode == 0,
            "detail": f"rc={proc.returncode}",
        }
    ]

    parity_overall = False
    parity_obj: dict[str, Any] = {}
    if tmp_summary.exists():
        try:
            parsed = json.loads(tmp_summary.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                parity_obj = parsed
                parity_overall = bool(parsed.get("overall_passed"))
        except Exception:
            parity_obj = {}
    checks.append({"name": "parity_overall_passed", "ok": parity_overall, "detail": f"value={parity_overall}"})

    meta = {
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-12:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-12:]),
        "parity_summary_file": str(tmp_summary),
        "parity_contract_file": str(tmp_contract),
        "parity_summary": parity_obj,
    }
    return checks, meta


def main() -> None:
    args = parse_args()

    summary: dict[str, Any] = {
        "overall_passed": False,
        "checks": [],
        "sections": {},
    }

    topic_checks, topic_meta = check_topic_contract(args.policy_file)
    memory_checks, memory_meta = check_memory_contract(args)
    parity_checks, parity_meta = check_parity(args)

    summary["checks"] = topic_checks + memory_checks + parity_checks
    summary["sections"] = {
        "topic_contract": topic_meta,
        "memory_contract": memory_meta,
        "channel_parity": parity_meta,
    }

    checks = summary.get("checks", [])
    summary["overall_passed"] = bool(checks) and all(bool(item.get("ok")) for item in checks)

    summary_path = Path(args.summary_file)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tmp_summary_path = Path(args.tmp_summary_file)
    tmp_summary_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"M3_POLICY_GATE={'PASS' if summary['overall_passed'] else 'FAIL'}")
    print(f"SUMMARY_FILE={summary_path}")
    print(f"TMP_SUMMARY_FILE={tmp_summary_path}")

    for item in checks:
        print(f"- {item.get('name')}: {'PASS' if item.get('ok') else 'FAIL'} ({item.get('detail')})")

    if not summary["overall_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
