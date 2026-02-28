#!/usr/bin/env python3
# Note: set EVAL_ALLOW_TEST_PROBES=1 to intentionally run test-only probe-token cases without warning.
import json
import argparse
import re
import sys
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "scripts" / "routing-eval-cases.json"
WEBHOOK_URL = "http://127.0.0.1:5678/webhook/rag-query"
ROUTE_RE = re.compile(r"\[route:([^\] ]+)")
PC_RE = re.compile(r"\bpc:([^\] ]+)")
TONE_TARGET_RE = re.compile(r"\btone_target:([^\] ]+)")
BREVITY_RE = re.compile(r"\bbrevity:([^\] ]+)")
SAFETY_RE = re.compile(r"\bsafety:([^\] ]+)")
STYLE_GATE_RE = re.compile(r"\bsg:(pass|fail)")
STYLE_GATE_REASON_RE = re.compile(r"\bsgr:([^\] ]+)")
VALID_TONE_TARGETS = {"warm", "neutral", "concise"}
VALID_BREVITY_TARGETS = {"short", "balanced", "detailed"}
VALID_SAFETY_MODES = {"strict", "default"}
VALID_STYLE_GATE_STATES = {"pass", "fail"}


def call_webhook(message: str, payload_overrides: dict | None = None) -> str:
    payload = {
        "source": "telegram",
        "chat_id": 999999,
        "user_id": 999999,
        "message": message,
    }
    if payload_overrides:
        payload.update(payload_overrides)
    req = urllib.request.Request(
        WEBHOOK_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    return str(data.get("reply", ""))


def extract_route(reply: str) -> str:
    match = ROUTE_RE.search(reply)
    return match.group(1).strip() if match else "<missing>"


def extract_marker(pattern: re.Pattern[str], reply: str) -> str:
    match = pattern.search(reply)
    return match.group(1).strip() if match else "<missing>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate routing behavior for rag-query webhook.",
        epilog="Tip: set EVAL_ALLOW_TEST_PROBES=1 to suppress warnings for intentional test-only probe-token cases.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--require-contract",
        action="store_true",
        dest="require_contract",
        help="Require persona contract markers (default).",
    )
    group.add_argument(
        "--no-require-contract",
        action="store_false",
        dest="require_contract",
        help="Disable persona contract marker checks for this run.",
    )
    parser.set_defaults(require_contract=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not CASES_FILE.exists():
        print(f"[FAIL] Missing cases file: {CASES_FILE}")
        return 2

    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    failed = 0

    print(f"Running {len(cases)} routing checks against {WEBHOOK_URL}")
    for case in cases:
        name = case["name"]
        message = case["message"]
        if "__stylegate_force_fail__" in str(message):
            allow_probe = str(os.getenv("EVAL_ALLOW_TEST_PROBES", "")).strip().lower() in {"1", "true", "yes", "on"}
            in_ci = str(os.getenv("CI", "")).strip().lower() in {"1", "true", "yes", "on"}
            if not (allow_probe or in_ci):
                print(
                    f"[WARN] {name}: test-only token '__stylegate_force_fail__' is present; "
                    "set EVAL_ALLOW_TEST_PROBES=1 for intentional local probe runs"
                )
        expected_raw = case["expected_route_prefix"]
        expected = [item.strip() for item in expected_raw.split("|") if item.strip()]
        payload_overrides = case.get("payload") or {}
        contains_raw = str(case.get("expected_contains", "")).strip()
        expected_contains = [item.strip() for item in contains_raw.split("|") if item.strip()]
        case_require_contract = bool(case.get("require_contract", True))
        require_contract = bool(args.require_contract) and case_require_contract
        expected_contract_version = str(case.get("expected_contract_version", "v1")).strip() or "v1"
        require_style_gate = bool(case.get("require_style_gate", True))
        expected_style_gate_pass = bool(case.get("expected_style_gate_pass", True))
        expected_style_gate_reason = str(case.get("expected_style_gate_reason", "")).strip()

        try:
            reply = call_webhook(message, payload_overrides)
            route = extract_route(reply)
        except urllib.error.HTTPError as exc:
            failed += 1
            print(f"[FAIL] {name}: HTTP {exc.code} reason=http")
            continue
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc} reason=error")
            continue

        route_ok = any(route.startswith(prefix) for prefix in expected)
        contains_ok = all(token.lower() in reply.lower() for token in expected_contains)
        contract_version = extract_marker(PC_RE, reply)
        tone_target = extract_marker(TONE_TARGET_RE, reply)
        brevity_target = extract_marker(BREVITY_RE, reply)
        safety_mode = extract_marker(SAFETY_RE, reply)
        style_gate_state = extract_marker(STYLE_GATE_RE, reply)
        style_gate_reason = extract_marker(STYLE_GATE_REASON_RE, reply)
        contract_ok = True
        if require_contract:
            contract_ok = (
                contract_version == expected_contract_version
                and tone_target in VALID_TONE_TARGETS
                and brevity_target in VALID_BREVITY_TARGETS
                and safety_mode in VALID_SAFETY_MODES
            )

        style_gate_ok = True
        if require_style_gate:
            style_gate_ok = (
                style_gate_state in VALID_STYLE_GATE_STATES
                and style_gate_reason != "<missing>"
                and ((style_gate_state == "pass") == expected_style_gate_pass)
            )
            if style_gate_ok and expected_style_gate_reason:
                style_gate_ok = style_gate_reason == expected_style_gate_reason

        ok = route_ok and contains_ok and contract_ok and style_gate_ok
        reasons = []
        if not route_ok:
            reasons.append("route")
        if not contains_ok:
            reasons.append("contains")
        if not contract_ok:
            reasons.append("contract")
        if not style_gate_ok:
            reasons.append("style_gate")
        reason_text = f" reason={'+'.join(reasons)}" if reasons else ""
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        contract_dbg = (
            f" contract={{pc:{contract_version}, tone_target:{tone_target}, brevity:{brevity_target}, safety:{safety_mode}}}"
            if require_contract
            else ""
        )
        style_gate_dbg = (
            f" style_gate={{sg:{style_gate_state}, sgr:{style_gate_reason}}}"
            if require_style_gate
            else ""
        )
        if expected_contains:
            print(
                f"[{status}] {name}: route={route} expected={expected_raw} contains={expected_contains}{contract_dbg}{style_gate_dbg}{reason_text}"
            )
        else:
            print(f"[{status}] {name}: route={route} expected={expected_raw}{contract_dbg}{style_gate_dbg}{reason_text}")

    if failed:
        print(f"\nResult: {failed} failing case(s)")
        return 1

    print("\nResult: all routing checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
