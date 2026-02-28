#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live Telegram role allowlist smoke checks against telegram-n8n-bridge")
    parser.add_argument("--container", default="telegram-n8n-bridge")
    parser.add_argument("--summary-file", default="/tmp/telegram-role-allowlist-smoke.json")
    return parser.parse_args()


def build_probe_script() -> str:
    return r'''
import json
import pathlib
import importlib.util

path = "/app/bridge/telegram_to_n8n.py"
if not pathlib.Path(path).exists():
    path = "/app/telegram_to_n8n.py"

spec = importlib.util.spec_from_file_location("bridge_mod", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

users = mod.USER_REGISTRY.get("users", {}) if isinstance(mod.USER_REGISTRY, dict) else {}
admin = None
user = None
for uid, rec in users.items():
    if not isinstance(rec, dict) or rec.get("status") != "active":
        continue
    if rec.get("role") == "admin" and admin is None:
        admin = (uid, rec)
    if rec.get("role") == "user" and user is None:
        user = (uid, rec)

if not admin or not user:
    print(json.dumps({"ok": False, "error": "missing_active_admin_or_user", "has_admin": bool(admin), "has_user": bool(user)}))
    raise SystemExit(2)

orig = mod.telegram_request
captured = []

def fake_tr(method, payload=None):
    if method == "sendMessage":
        captured.append(payload or {})
        return {"ok": True, "result": {"message_id": len(captured)}}
    return {"ok": True, "result": []}

mod.telegram_request = fake_tr

def run_case(uid, rec, text):
    before = len(captured)
    uid_int = int(uid) if str(uid).isdigit() else uid
    update = {
        "update_id": 2000000 + before,
        "message": {
            "message_id": 900 + before,
            "date": 1772262000,
            "chat": {"id": uid_int, "type": "private", "username": rec.get("telegram_username", "")},
            "from": {
                "id": uid_int,
                "is_bot": False,
                "first_name": (rec.get("full_name") or "Test").split(" ")[0] if isinstance(rec.get("full_name"), str) else "Test",
                "username": rec.get("telegram_username", ""),
            },
            "text": text,
        },
    }
    mod.process_update(update)
    if len(captured) == before:
        return {"text": text, "sent": False, "reply": ""}
    out = str(captured[-1].get("text", ""))
    return {"text": text, "sent": True, "reply": out}

uid_user, rec_user = user
uid_admin, rec_admin = admin

cases = []
cases.append({"actor": "user", "uid": str(uid_user), **run_case(uid_user, rec_user, "/notify me json")})
cases.append({"actor": "user", "uid": str(uid_user), **run_case(uid_user, rec_user, "/status")})
cases.append({"actor": "user", "uid": str(uid_user), **run_case(uid_user, rec_user, "/ops docker ps")})
cases.append({"actor": "admin", "uid": str(uid_admin), **run_case(uid_admin, rec_admin, "/status")})

mod.telegram_request = orig

print(json.dumps({
    "ok": True,
    "role_allowlist_present": bool((mod.POLICY_TELEGRAM_SETTINGS.get("role_command_allowlist") or {})),
    "cases": cases,
}, ensure_ascii=False))
'''


def parse_json_payload(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    raise ValueError("No JSON payload found in docker exec output")


def main() -> None:
    args = parse_args()
    probe_script = build_probe_script()

    command = [
        "docker",
        "exec",
        args.container,
        "python",
        "-c",
        probe_script,
    ]
    proc = subprocess.run(command, text=True, capture_output=True)

    summary: dict = {
        "container": args.container,
        "command_rc": proc.returncode,
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
        "overall_passed": False,
        "checks": [],
        "probe": None,
    }

    if proc.returncode != 0:
        summary["checks"].append({"name": "docker_exec_success", "ok": False, "detail": f"rc={proc.returncode}"})
    else:
        summary["checks"].append({"name": "docker_exec_success", "ok": True, "detail": "ok"})

    probe: dict | None = None
    if proc.returncode == 0:
        try:
            probe = parse_json_payload(proc.stdout or "")
            summary["probe"] = probe
        except Exception as exc:
            summary["checks"].append({"name": "probe_json_parse", "ok": False, "detail": str(exc)})

    if isinstance(probe, dict):
        cases = probe.get("cases") if isinstance(probe.get("cases"), list) else []

        def get_case(actor: str, text: str) -> dict:
            for item in cases:
                if isinstance(item, dict) and item.get("actor") == actor and item.get("text") == text:
                    return item
            return {}

        user_notify = get_case("user", "/notify me json")
        user_status = get_case("user", "/status")
        user_ops = get_case("user", "/ops docker ps")
        admin_status = get_case("admin", "/status")

        summary["checks"].append({
            "name": "role_allowlist_present",
            "ok": bool(probe.get("role_allowlist_present")),
            "detail": str(probe.get("role_allowlist_present")),
        })
        summary["checks"].append({
            "name": "user_notify_me_allowed",
            "ok": bool(user_notify.get("sent")) and bool(str(user_notify.get("reply", "")).strip()),
            "detail": str(user_notify.get("reply", ""))[:160],
        })
        summary["checks"].append({
            "name": "user_status_blocked",
            "ok": "not allowed for your role" in str(user_status.get("reply", "")).lower(),
            "detail": str(user_status.get("reply", ""))[:160],
        })
        summary["checks"].append({
            "name": "user_ops_blocked",
            "ok": "admin-only" in str(user_ops.get("reply", "")).lower(),
            "detail": str(user_ops.get("reply", ""))[:160],
        })
        summary["checks"].append({
            "name": "admin_status_allowed",
            "ok": bool(admin_status.get("sent")) and "bridge status" in str(admin_status.get("reply", "")).lower(),
            "detail": str(admin_status.get("reply", ""))[:160],
        })

    checks = summary.get("checks", []) if isinstance(summary.get("checks"), list) else []
    summary["overall_passed"] = bool(checks) and all(bool(item.get("ok")) for item in checks)

    output_path = Path(args.summary_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"TELEGRAM_ROLE_ALLOWLIST_SMOKE={'PASS' if summary['overall_passed'] else 'FAIL'}")
    print(f"SUMMARY_FILE={output_path}")
    for item in checks:
        print(f"- {item.get('name')}: {'PASS' if item.get('ok') else 'FAIL'}")

    if not summary["overall_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
