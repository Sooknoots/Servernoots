#!/usr/bin/env python3
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture retry-safe ntfy evidence for ops-alerts topic")
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--topic", default="ops-alerts")
    parser.add_argument("--since", default="6h")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retry-count", type=int, default=6)
    parser.add_argument("--retry-delay-seconds", type=float, default=1.0)
    parser.add_argument("--retain-events", type=int, default=20)
    parser.add_argument("--contains", action="append", default=[])
    parser.add_argument("--summary-file", default="checkpoints/ops-alerts-evidence-latest.json")
    parser.add_argument("--tmp-summary-file", default="/tmp/ops-alerts-evidence-latest.json")
    return parser.parse_args()


def fetch_url(url: str, timeout: float) -> tuple[int, str, str | None]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return int(response.getcode() or 0), response.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code or 0), body, f"http_error:{exc.code}"
    except Exception as exc:
        return 0, "", str(exc)


def parse_events(raw: str) -> tuple[list[dict[str, Any]], str | None]:
    text = (raw or "").strip()
    if not text:
        return [], None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)], None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("messages"), list):
                return [item for item in parsed["messages"] if isinstance(item, dict)], None
            return [parsed], None
    except Exception:
        pass

    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            parsed_line = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed_line, dict):
            events.append(parsed_line)

    if events:
        return events, None
    return [], "parse_error:no_json_events"


def normalize_terms(values: list[str]) -> list[str]:
    terms: list[str] = []
    for value in values:
        for token in str(value).split(","):
            term = token.strip().lower()
            if term:
                terms.append(term)
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped


def filter_events(events: list[dict[str, Any]], topic: str, contains_terms: list[str]) -> list[dict[str, Any]]:
    scoped = [event for event in events if str(event.get("topic") or "") == topic]
    if not contains_terms:
        return scoped

    filtered: list[dict[str, Any]] = []
    for event in scoped:
        haystack = f"{event.get('title', '')}\n{event.get('message', '')}".lower()
        if any(term in haystack for term in contains_terms):
            filtered.append(event)
    return filtered


def main() -> int:
    args = parse_args()
    contains_terms = normalize_terms(args.contains)

    base = args.base_url.rstrip("/")
    encoded_topic = urllib.parse.quote(args.topic, safe="")
    encoded_since = urllib.parse.quote(args.since, safe="")

    url_candidates = [
        f"{base}/v1/messages?topic={encoded_topic}&since={encoded_since}",
        f"{base}/{encoded_topic}/json?since={encoded_since}&poll=1",
        f"{base}/{encoded_topic}/json?since={encoded_since}",
    ]

    attempts: list[dict[str, Any]] = []
    selected_url = ""
    status_code = 0
    raw_error = ""
    all_events: list[dict[str, Any]] = []
    filtered_events: list[dict[str, Any]] = []

    for url in url_candidates:
        success_for_url = False
        for attempt in range(1, max(1, args.retry_count) + 1):
            status, raw_body, error = fetch_url(url, timeout=args.timeout)
            status_code = status
            raw_error = error or ""
            attempt_row: dict[str, Any] = {"attempt": attempt, "url": url, "status": status}
            if error:
                attempt_row["error"] = error

            if status == 200:
                parsed_events, parse_error = parse_events(raw_body)
                scoped_events = [event for event in parsed_events if isinstance(event, dict)]
                filtered = filter_events(scoped_events, args.topic, contains_terms)
                attempt_row["events"] = len(scoped_events)
                attempt_row["filtered"] = len(filtered)
                if parse_error:
                    attempt_row["error"] = parse_error
                attempts.append(attempt_row)

                if not parse_error:
                    selected_url = url
                    all_events = scoped_events
                    filtered_events = filtered
                    success_for_url = True
                    break
            else:
                attempts.append(attempt_row)

            if attempt < max(1, args.retry_count):
                time.sleep(max(0.0, args.retry_delay_seconds))

        if success_for_url:
            break

    retained = filtered_events[-max(1, args.retain_events) :] if filtered_events else []

    if contains_terms:
        overall_passed = bool(filtered_events)
    else:
        overall_passed = bool(all_events)

    captured_at = datetime.now(timezone.utc)
    timestamp = captured_at.strftime("%Y-%m-%dT%H-%M-%SZ")

    summary_path = Path(args.summary_file)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path = summary_path.with_name(f"{summary_path.stem}-{timestamp}{summary_path.suffix}")
    tmp_summary_path = Path(args.tmp_summary_file)
    tmp_summary_path.parent.mkdir(parents=True, exist_ok=True)

    last_event = filtered_events[-1] if filtered_events else {}
    summary: dict[str, Any] = {
        "topic": args.topic,
        "url": selected_url or (url_candidates[-1] if url_candidates else ""),
        "url_candidates": url_candidates,
        "captured_at_utc": captured_at.isoformat(),
        "status_code": status_code,
        "attempts": attempts,
        "retry_count": max(1, args.retry_count),
        "total_events": len(all_events),
        "filtered_events": len(filtered_events),
        "contains_filters": contains_terms,
        "retained_events": len(retained),
        "last_event_title": last_event.get("title"),
        "last_event_message": last_event.get("message"),
        "last_event_time": last_event.get("time"),
        "events": retained,
        "overall_passed": overall_passed,
        "error": raw_error,
        "summary_file": str(summary_path.resolve()),
        "archive_file": str(archive_path.resolve()),
        "tmp_summary_file": str(tmp_summary_path.resolve()),
    }

    encoded = json.dumps(summary, indent=2)
    summary_path.write_text(encoded + "\n", encoding="utf-8")
    archive_path.write_text(encoded + "\n", encoding="utf-8")
    tmp_summary_path.write_text(encoded + "\n", encoding="utf-8")

    print(f"OPS_ALERTS_EVIDENCE={'PASS' if overall_passed else 'FAIL'}")
    print(f"SUMMARY_FILE={summary_path}")
    print(f"ARCHIVE_FILE={archive_path}")
    print(f"TMP_SUMMARY_FILE={tmp_summary_path}")
    print(f"FILTERED_EVENTS={len(filtered_events)}")
    if selected_url:
        print(f"URL_USED={selected_url}")
    elif url_candidates:
        print(f"URL_USED={url_candidates[-1]}")

    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())