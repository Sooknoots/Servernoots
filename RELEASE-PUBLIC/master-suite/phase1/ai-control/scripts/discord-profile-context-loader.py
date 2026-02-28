#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any


def normalize_id(value: Any) -> str:
    return str(value or "").strip()


def load_profiles(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    profiles = obj.get("profiles") if isinstance(obj, dict) else None
    if not isinstance(profiles, dict):
        raise ValueError("profiles JSON missing top-level 'profiles' object")
    return profiles


def parse_ids(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gated Discord profile context payload")
    parser.add_argument("--profiles", default="work/discord-seed/discord_user_profiles.json", help="Path to discord_user_profiles.json")
    parser.add_argument("--user-id", required=True, help="Target Discord user id for this request")
    parser.add_argument("--interaction-user-id", default="", help="Discord user id actively sending/speaking in this interaction")
    parser.add_argument("--active-user-ids", default="", help="Comma-separated active IDs currently in channel/session")
    parser.add_argument("--allow-force", action="store_true", help="Force profile context allowed (admin/backfill only)")
    parser.add_argument("--out", default="", help="Optional output file path (writes JSON payload). Prints to stdout always")
    args = parser.parse_args()

    profiles = load_profiles(Path(args.profiles))

    user_id = normalize_id(args.user_id)
    interaction_user_id = normalize_id(args.interaction_user_id)
    active_ids = parse_ids(args.active_user_ids)

    profile = profiles.get(user_id) or {}
    profile_seed = str(profile.get("user_profile_seed") or "").strip()
    profile_image = str(profile.get("avatar_path") or "").strip()

    allowed = bool(args.allow_force or (interaction_user_id and interaction_user_id == user_id) or (user_id in active_ids))

    payload = {
        "user_id": user_id,
        "interaction_user_id": interaction_user_id,
        "active_user_ids": active_ids,
        "profile_context_allowed": allowed,
        "user_profile_seed": profile_seed if allowed else "",
        "user_profile_image_url": profile_image if allowed else "",
        "profile_present": bool(profile),
    }

    text = json.dumps(payload, ensure_ascii=False)
    print(text)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
