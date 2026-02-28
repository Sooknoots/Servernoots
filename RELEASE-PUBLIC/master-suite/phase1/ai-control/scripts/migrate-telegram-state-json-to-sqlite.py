#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json_or_default(path: str, default: dict[str, Any]) -> dict[str, Any]:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return default
    except Exception:
        return default


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state_kv (
            key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def upsert_state(conn: sqlite3.Connection, key: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO state_kv(key, payload, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
        """,
        (key, json.dumps(payload, ensure_ascii=False), utc_now()),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate Telegram bridge runtime JSON state files into a SQLite state_kv store.",
    )
    parser.add_argument("--sqlite", required=True, help="Target SQLite DB path")
    parser.add_argument("--delivery", default="/state/telegram_delivery_state.json")
    parser.add_argument("--dedupe", default="/state/telegram_dedupe_state.json")
    parser.add_argument("--notify-stats", default="/state/telegram_notify_stats.json")
    parser.add_argument("--digest-queue", default="/state/telegram_digest_queue.json")
    parser.add_argument("--incidents", default="/state/telegram_incidents.json")
    args = parser.parse_args()

    mapping: list[tuple[str, str, dict[str, Any]]] = [
        ("delivery", args.delivery, {"users": {}, "updated_at": utc_now()}),
        ("dedupe", args.dedupe, {"items": {}}),
        ("notify_stats", args.notify_stats, {"events": [], "updated_at": utc_now()}),
        ("digest_queue", args.digest_queue, {"users": {}, "updated_at": utc_now()}),
        ("incidents", args.incidents, {"incidents": {}, "updated_at": utc_now()}),
    ]

    sqlite_dir = os.path.dirname(args.sqlite)
    if sqlite_dir:
        os.makedirs(sqlite_dir, exist_ok=True)

    conn = sqlite3.connect(args.sqlite)
    try:
        ensure_table(conn)
        for key, src_path, default in mapping:
            payload = load_json_or_default(src_path, default)
            upsert_state(conn, key, payload)
            print(f"migrated key={key} source={src_path}")
        conn.commit()
    finally:
        conn.close()

    print(f"sqlite migration complete path={args.sqlite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
