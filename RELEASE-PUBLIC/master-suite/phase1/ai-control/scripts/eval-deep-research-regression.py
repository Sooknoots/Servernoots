#!/usr/bin/env python3
import argparse
import json
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deep-research start/status/report regression checks against n8n webhook"
    )
    parser.add_argument("--n8n-base", default="http://127.0.0.1:5678")
    parser.add_argument("--webhook", default="/webhook/deep-research")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--summary-file", default="checkpoints/deep-research-regression-latest.json")
    parser.add_argument("--tmp-summary-file", default="/tmp/deep-research-regression-latest.json")
    parser.add_argument("--archive-prefix", default="deep-research-regression")
    parser.add_argument("--chat-id", default="700")
    parser.add_argument("--user-id", default="9001")
    parser.add_argument("--tenant-id", default="u_9001")
    parser.add_argument("--role", default="user")
    return parser.parse_args()


def read_env_var(key: str) -> str | None:
    for env_file in (ROOT / ".env.secrets", ROOT / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            if k.strip() != key:
                continue
            value = v.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            return value
    return None


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any] | None, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
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


def short_raw(raw: str) -> str:
    lines = raw.splitlines()
    return "\n".join(lines[-10:])


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> None:
    args = parse_args()
    webhook_url = f"{args.n8n_base.rstrip('/')}/{args.webhook.lstrip('/')}"

    now_ts = int(time.time())
    run_id = f"rr-regression-{now_ts}"

    nextcloud_base = read_env_var("RESEARCH_NEXTCLOUD_BASE_URL") or "http://nextcloud"
    nextcloud_user = read_env_var("RESEARCH_NEXTCLOUD_USER") or read_env_var("NEXTCLOUD_ADMIN_USER")
    nextcloud_password = read_env_var("RESEARCH_NEXTCLOUD_PASSWORD") or read_env_var("NEXTCLOUD_ADMIN_PASSWORD")
    nextcloud_folder = read_env_var("RESEARCH_NEXTCLOUD_FOLDER") or "research-reports"

    start_payload: dict[str, Any] = {
        "source": "telegram",
        "action": "start",
        "run_id": run_id,
        "chat_id": args.chat_id,
        "user_id": args.user_id,
        "role": args.role,
        "tenant_id": args.tenant_id,
        "query": "Regression probe: summarize current AI control reliability posture.",
        "delivery": {
            "channel": "telegram",
            "mode": "nextcloud_link",
            "link_ttl_seconds": 86400,
        },
        "timestamp": now_ts,
    }

    if nextcloud_base:
        start_payload["nextcloud_base_url"] = nextcloud_base
    if nextcloud_user:
        start_payload["nextcloud_user"] = nextcloud_user
    if nextcloud_password:
        start_payload["nextcloud_password"] = nextcloud_password
    if nextcloud_folder:
        start_payload["nextcloud_folder"] = nextcloud_folder

    checks: list[dict[str, Any]] = []

    start_status, start_body, start_raw = post_json(webhook_url, start_payload, timeout=args.timeout)
    start_body = start_body if isinstance(start_body, dict) else {}

    add_check(checks, "start_http_ok", start_status == 200, f"status={start_status}")
    add_check(
        checks,
        "start_registered",
        "requested webhook \"POST deep-research\" is not registered" not in start_raw,
        "webhook_registered",
    )

    start_run_id = str(start_body.get("run_id") or "")
    start_status_value = str(start_body.get("status") or "")
    start_report_url = str(start_body.get("report_url") or "")

    add_check(checks, "start_has_run_id", bool(start_run_id), f"run_id={start_run_id}")
    add_check(checks, "start_status_ready", start_status_value == "ready", f"status={start_status_value}")
    add_check(checks, "start_has_report_url", bool(start_report_url), f"url_len={len(start_report_url)}")

    status_payload = {
        "source": "telegram",
        "action": "status",
        "run_id": start_run_id or run_id,
        "chat_id": args.chat_id,
        "user_id": args.user_id,
        "role": args.role,
        "tenant_id": args.tenant_id,
        "report_url_hint": start_report_url,
        "report_title_hint": str(start_body.get("report_title") or ""),
        "link_expires_at_hint": int(start_body.get("link_expires_at") or 0),
        "timestamp": now_ts + 1,
    }

    status_http, status_body, status_raw = post_json(webhook_url, status_payload, timeout=args.timeout)
    status_body = status_body if isinstance(status_body, dict) else {}

    status_status_value = str(status_body.get("status") or "")
    status_report_url = str(status_body.get("report_url") or "")

    add_check(checks, "status_http_ok", status_http == 200, f"status={status_http}")
    add_check(checks, "status_ready", status_status_value == "ready", f"status={status_status_value}")
    add_check(checks, "status_has_report_url", bool(status_report_url), f"url_len={len(status_report_url)}")
    add_check(
        checks,
        "status_report_url_match",
        bool(start_report_url) and bool(status_report_url) and start_report_url == status_report_url,
        "start_vs_status_url_match",
    )

    report_payload = {
        "source": "telegram",
        "action": "report",
        "run_id": start_run_id or run_id,
        "chat_id": args.chat_id,
        "user_id": args.user_id,
        "role": args.role,
        "tenant_id": args.tenant_id,
        "report_url_hint": status_report_url or start_report_url,
        "report_title_hint": str(status_body.get("report_title") or start_body.get("report_title") or ""),
        "link_expires_at_hint": int(status_body.get("link_expires_at") or start_body.get("link_expires_at") or 0),
        "timestamp": now_ts + 2,
    }

    report_http, report_body, report_raw = post_json(webhook_url, report_payload, timeout=args.timeout)
    report_body = report_body if isinstance(report_body, dict) else {}

    report_status_value = str(report_body.get("status") or "")
    report_report_url = str(report_body.get("report_url") or "")

    add_check(checks, "report_http_ok", report_http == 200, f"status={report_http}")
    add_check(checks, "report_ready", report_status_value == "ready", f"status={report_status_value}")
    add_check(checks, "report_has_report_url", bool(report_report_url), f"url_len={len(report_report_url)}")
    add_check(
        checks,
        "report_report_url_match",
        bool(status_report_url) and bool(report_report_url) and status_report_url == report_report_url,
        "status_vs_report_url_match",
    )

    add_check(
        checks,
        "report_url_http_like",
        report_report_url.startswith("http://") or report_report_url.startswith("https://"),
        f"report_url={report_report_url[:120]}",
    )

    overall_passed = bool(checks) and all(bool(item.get("ok")) for item in checks)

    summary: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target": {
            "webhook_url": webhook_url,
            "chat_id": args.chat_id,
            "user_id": args.user_id,
            "tenant_id": args.tenant_id,
            "role": args.role,
        },
        "run_id_requested": run_id,
        "run_id_observed": start_run_id,
        "overall_passed": overall_passed,
        "checks": checks,
        "responses": {
            "start": {
                "http_status": start_status,
                "status": start_status_value,
                "run_id": start_run_id,
                "report_url": start_report_url,
                "error": str(start_body.get("error") or ""),
                "raw_tail": short_raw(start_raw),
            },
            "status": {
                "http_status": status_http,
                "status": status_status_value,
                "run_id": str(status_body.get("run_id") or ""),
                "report_url": status_report_url,
                "error": str(status_body.get("error") or ""),
                "raw_tail": short_raw(status_raw),
            },
            "report": {
                "http_status": report_http,
                "status": report_status_value,
                "run_id": str(report_body.get("run_id") or ""),
                "report_url": report_report_url,
                "error": str(report_body.get("error") or ""),
                "raw_tail": short_raw(report_raw),
            },
        },
    }

    summary_path = (ROOT / args.summary_file).resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_name = f"{args.archive_prefix}-{timestamp_token}.json"
    archive_path = summary_path.parent / archive_name

    archive_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(archive_path, summary_path)

    tmp_path = Path(args.tmp_summary_file)
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"DEEP_RESEARCH_REGRESSION={'PASS' if overall_passed else 'FAIL'}")
    print(f"SUMMARY_FILE={summary_path}")
    print(f"ARCHIVE_FILE={archive_path}")
    print(f"TMP_SUMMARY_FILE={tmp_path}")
    for item in checks:
        print(f"- {item.get('name')}: {'PASS' if item.get('ok') else 'FAIL'}")

    if not overall_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
