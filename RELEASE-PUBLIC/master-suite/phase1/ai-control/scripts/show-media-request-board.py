#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


def request_json(url: str, api_key: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def resolve_overseerr_base(base: str, api_key: str) -> str:
    candidates: list[str] = []
    normalized = (base or "").strip().rstrip("/")
    if normalized:
        candidates.append(normalized)
    if "http://127.0.0.1:5055" not in candidates:
        candidates.append("http://127.0.0.1:5055")

    for candidate in candidates:
        try:
            request_json(f"{candidate}/api/v1/status", api_key=api_key, timeout=15)
            return candidate
        except Exception:
            continue

    raise RuntimeError("Unable to reach Overseerr API with current OVERSEERR_URL/OVERSEERR_API_KEY")


def request_status_label(code: Any) -> str:
    mapping = {
        1: "PENDING",
        2: "APPROVED",
        3: "DECLINED",
        4: "PROCESSING",
        5: "COMPLETED",
    }
    try:
        return mapping.get(int(code), f"UNKNOWN({code})")
    except Exception:
        return f"UNKNOWN({code})"


def media_status_label(code: Any) -> str:
    mapping = {
        1: "UNKNOWN",
        2: "PENDING",
        3: "PROCESSING",
        4: "PARTIAL",
        5: "AVAILABLE",
    }
    try:
        return mapping.get(int(code), f"S{code}")
    except Exception:
        return f"S{code}"


def media_title(base: str, api_key: str, media_type: str, tmdb_id: Any, cache: dict[tuple[str, int], str]) -> str:
    try:
        numeric_tmdb = int(tmdb_id)
    except Exception:
        return "unknown"

    key = (media_type, numeric_tmdb)
    if key in cache:
        return cache[key]

    title = "unknown"
    try:
        if media_type == "movie":
            payload = request_json(f"{base}/api/v1/movie/{numeric_tmdb}", api_key=api_key)
            title = str(payload.get("title") or payload.get("originalTitle") or "unknown")
        elif media_type == "tv":
            payload = request_json(f"{base}/api/v1/tv/{numeric_tmdb}", api_key=api_key)
            title = str(payload.get("name") or payload.get("originalName") or "unknown")
    except Exception:
        title = "unknown"

    cache[key] = title
    return title


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


def load_telegram_media_notify_events(limit: int) -> list[dict[str, Any]]:
    cmd = [
        "docker",
        "exec",
        "ntfy-n8n-bridge",
        "python",
        "-c",
        (
            "import json,sqlite3; "
            "conn=sqlite3.connect('/state/telegram_state.db'); "
            "row=conn.execute(\"select payload from state_kv where key='notify_stats'\").fetchone(); "
            "conn.close(); "
            "d=json.loads(row[0]) if row and row[0] else {}; "
            "ev=d.get('events',[]) if isinstance(d,dict) else []; "
            "media=[e for e in ev if isinstance(e,dict) and e.get('topic')=='media-alerts']; "
            f"print(json.dumps(media[-{max(1, limit)}:], ensure_ascii=False))"
        ),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout.strip() or "[]")
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Show current Overseerr media request board")
    parser.add_argument("--take", type=int, default=25, help="Max number of requests to display (default: 25)")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument(
        "--with-telegram",
        action="store_true",
        help="Merge Telegram media-alert send heuristics (from ntfy bridge notify_stats)",
    )
    parser.add_argument(
        "--telegram-limit",
        type=int,
        default=400,
        help="How many recent media-alert events to inspect for Telegram merge (default: 400)",
    )
    args = parser.parse_args()

    api_key = os.getenv("OVERSEERR_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OVERSEERR_API_KEY is not set")
        return 1

    base = resolve_overseerr_base(os.getenv("OVERSEERR_URL", "http://127.0.0.1:5055"), api_key=api_key)
    query = urllib.parse.urlencode({"take": max(1, args.take), "skip": 0, "sort": "added"})
    payload = request_json(f"{base}/api/v1/request?{query}", api_key=api_key)
    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list):
        results = []

    telegram_events: list[dict[str, Any]] = []
    if args.with_telegram:
        telegram_events = load_telegram_media_notify_events(limit=max(50, args.telegram_limit))

    title_cache: dict[tuple[str, int], str] = {}
    rows: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        media = item.get("media") if isinstance(item.get("media"), dict) else {}
        media_type = str(item.get("type") or media.get("mediaType") or "unknown")
        title = media_title(
            base=base,
            api_key=api_key,
            media_type=media_type,
            tmdb_id=media.get("tmdbId"),
            cache=title_cache,
        )

        requested_by = item.get("requestedBy") if isinstance(item.get("requestedBy"), dict) else {}
        requester = (
            requested_by.get("displayName")
            or requested_by.get("username")
            or requested_by.get("email")
            or "unknown"
        )

        rows.append(
            {
                "request_id": item.get("id"),
                "title": title,
                "type": media_type,
                "request_status": request_status_label(item.get("status")),
                "media_status": media_status_label(media.get("status")),
                "requested_by": requester,
                "created_at": item.get("createdAt"),
                "updated_at": item.get("updatedAt"),
                "created_ts": parse_iso_ts_to_epoch(item.get("createdAt")),
            }
        )

    if args.with_telegram:
        for row in rows:
            created_ts = int(row.get("created_ts", 0) or 0)
            matches = [
                event
                for event in telegram_events
                if int(event.get("ts", 0) or 0) >= created_ts
                and str(event.get("result", "")) in {"sent", "sent_partial"}
            ]
            latest = matches[-1] if matches else {}
            row["telegram_notified"] = bool(matches)
            row["telegram_result"] = str(latest.get("result", "")) if matches else ""
            row["telegram_reason"] = str(latest.get("reason", "")) if matches else ""

    if args.json:
        print(
            json.dumps(
                {
                    "overseerr_base": base,
                    "count": len(rows),
                    "telegram_merge_enabled": bool(args.with_telegram),
                    "telegram_event_count": len(telegram_events),
                    "requests": rows,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"overseerr_base={base}")
    print(f"request_count={len(rows)}")
    if not rows:
        return 0

    if args.with_telegram:
        header = (
            f"{'id':<4} {'type':<6} {'request':<10} {'media':<10} {'tg':<3} "
            f"{'tg_result':<11} {'title':<24} {'requester':<20} {'created_at':<25}"
        )
    else:
        header = f"{'id':<4} {'type':<6} {'request':<10} {'media':<10} {'title':<30} {'requester':<20} {'created_at':<25}"
    print(header)
    print("-" * len(header))
    for row in rows:
        if args.with_telegram:
            print(
                f"{str(row['request_id']):<4} "
                f"{str(row['type']):<6} "
                f"{str(row['request_status']):<10} "
                f"{str(row['media_status']):<10} "
                f"{'Y' if row.get('telegram_notified') else 'N':<3} "
                f"{str(row.get('telegram_result', ''))[:11]:<11} "
                f"{str(row['title'])[:24]:<24} "
                f"{str(row['requested_by'])[:20]:<20} "
                f"{str(row['created_at'])[:25]:<25}"
            )
        else:
            print(
                f"{str(row['request_id']):<4} "
                f"{str(row['type']):<6} "
                f"{str(row['request_status']):<10} "
                f"{str(row['media_status']):<10} "
                f"{str(row['title'])[:30]:<30} "
                f"{str(row['requested_by'])[:20]:<20} "
                f"{str(row['created_at'])[:25]:<25}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
