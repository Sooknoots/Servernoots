#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M9 channel parity probes and emit PASS/FAIL summary artifacts")
    parser.add_argument("--n8n-base", default="http://127.0.0.1:5678")
    parser.add_argument("--rag-webhook", default="/webhook/rag-query")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--user-id", default="111")
    parser.add_argument("--tenant-id", default="u_111")
    parser.add_argument("--summary-file", default="checkpoints/m9-parity-summary.json")
    parser.add_argument("--contract-file", default="checkpoints/m9-contract-parity.json")
    parser.add_argument("--tmp-summary-file", default="/tmp/discord-m9-parity-summary.json")
    parser.add_argument("--tmp-contract-file", default="/tmp/discord-m9-contract-parity.json")
    return parser.parse_args()


def post_json(url: str, payload: dict, timeout: float) -> tuple[int, dict | None, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            return resp.getcode(), parsed, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        return exc.code, parsed, raw
    except Exception as exc:
        return 0, None, str(exc)


def source_payload(source: str, args: argparse.Namespace, *, memory_write_allowed: bool) -> dict:
    base = {
        "source": source,
        "user_id": args.user_id,
        "role": "user",
        "tenant_id": args.tenant_id,
        "message": f"m9 parity probe {source} ({'allow' if memory_write_allowed else 'deny'})",
        "memory_enabled": True,
        "voice_memory_opt_in": True,
        "memory_summary": "m9_seed",
        "speaker_confidence": 0.95 if memory_write_allowed else 0.42,
        "memory_min_speaker_confidence": 0.8,
        "memory_write_allowed": memory_write_allowed,
        "has_audio": False,
    }
    if source == "discord":
        base.update({"chat_id": "m9-c1", "guild_id": "g1", "channel_id": "c1"})
    elif source == "telegram":
        base.update({"chat_id": 700, "telegram_username": "m9probe", "full_name": "M9 Probe"})
    else:
        base.update({"chat_id": "m9-ntfy"})
    return base


def evaluate_case(source: str, gate: str, status: int, body: dict | None, raw: str) -> dict:
    reply = ""
    memory_summary = None
    if isinstance(body, dict):
        reply = str(body.get("reply") or "")
        memory_summary = body.get("memory_summary")

    reply_present = bool(reply.strip())
    memory_summary_present = bool(str(memory_summary or "").strip())
    checks = [
        {"name": "http_status_ok", "ok": status == 200, "value": status},
        {"name": "reply_present", "ok": reply_present},
    ]
    passed = all(bool(item.get("ok")) for item in checks)
    return {
        "source": source,
        "gate": gate,
        "passed": passed,
        "checks": checks,
        "reply_present": reply_present,
        "memory_summary_present": memory_summary_present,
        "raw_tail": "\n".join(raw.splitlines()[-6:]),
    }


def main() -> None:
    args = parse_args()
    url = f"{args.n8n_base.rstrip('/')}/{args.rag_webhook.lstrip('/')}"

    results: list[dict] = []
    for source in ("discord", "telegram", "ntfy"):
        for gate, allowed in (("high", True), ("low", False)):
            payload = source_payload(source, args, memory_write_allowed=allowed)
            status, body, raw = post_json(url, payload, timeout=args.timeout)
            results.append(evaluate_case(source, gate, status, body, raw))

    policy_parity_checks = []
    for source in ("discord", "telegram", "ntfy"):
        source_cases = [r for r in results if r["source"] == source]
        source_passed = all(bool(case.get("passed")) for case in source_cases)
        policy_parity_checks.append({"source": source, "ok": source_passed})

    gate_memory_presence_checks = []
    for gate in ("high", "low"):
        gate_cases = [r for r in results if r["gate"] == gate]
        values = [bool(r.get("memory_summary_present")) for r in gate_cases]
        consistent = len(set(values)) == 1
        gate_memory_presence_checks.append(
            {
                "gate": gate,
                "ok": consistent,
                "values": values,
            }
        )

    contract_parity_checks = [
        {
            "case": f"{case['source']}_{case['gate']}",
            "ok": bool(case.get("passed")),
        }
        for case in results
    ]

    overall_passed = (
        all(item["ok"] for item in policy_parity_checks)
        and all(item["ok"] for item in contract_parity_checks)
        and all(item["ok"] for item in gate_memory_presence_checks)
    )

    summary = {
        "overall_passed": overall_passed,
        "target_url": url,
        "policy_parity_checks": policy_parity_checks,
        "contract_parity_checks": contract_parity_checks,
        "gate_memory_presence_checks": gate_memory_presence_checks,
        "results": results,
    }
    contract = {
        "discord": [r for r in results if r["source"] == "discord"],
        "telegram": [r for r in results if r["source"] == "telegram"],
        "ntfy": [r for r in results if r["source"] == "ntfy"],
    }

    summary_path = Path(args.summary_file)
    contract_path = Path(args.contract_file)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tmp_summary_path = Path(args.tmp_summary_file)
    tmp_contract_path = Path(args.tmp_contract_file)
    tmp_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"M9_PARITY_PACK={'PASS' if overall_passed else 'FAIL'}")
    print(f"SUMMARY_FILE={summary_path}")
    print(f"CONTRACT_FILE={contract_path}")
    print(f"TMP_SUMMARY_FILE={tmp_summary_path}")
    print(f"TMP_CONTRACT_FILE={tmp_contract_path}")

    if not overall_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
