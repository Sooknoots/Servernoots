#!/usr/bin/env python3
import argparse
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STOPWORDS = {
    "the", "and", "for", "you", "that", "with", "this", "are", "was", "have", "just", "from",
    "your", "but", "not", "all", "can", "its", "it's", "they", "them", "our", "about", "what",
    "when", "where", "will", "would", "there", "their", "has", "had", "out", "get", "got", "did",
    "one", "two", "too", "lol", "lmao", "bro", "yeah", "yes", "nah", "im", "i'm", "ive", "i've",
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'_\-]{2,}")
CHANNEL_RE = re.compile(r"^(?P<name>.+?)_[A-Za-z0-9\-]{6,}/")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_") or "unknown"


def tokenize(text: str) -> list[str]:
    terms = []
    for token in TOKEN_RE.findall(text.lower()):
        if token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        terms.append(token)
    return terms


@dataclass
class UserAgg:
    user_id: str
    usernames: Counter = field(default_factory=Counter)
    global_names: Counter = field(default_factory=Counter)
    avatar_hashes: Counter = field(default_factory=Counter)
    message_count: int = 0
    channel_counts: Counter = field(default_factory=Counter)
    token_counts: Counter = field(default_factory=Counter)
    recent_messages: list[dict[str, str]] = field(default_factory=list)

    def add_message(self, msg: dict[str, Any], channel_name: str) -> None:
        author = msg.get("author") or {}
        username = str(author.get("username") or "").strip()
        global_name = str(author.get("global_name") or "").strip()
        avatar_hash = str(author.get("avatar") or "").strip()
        content = str(msg.get("content") or "").strip()
        timestamp = str(msg.get("timestamp") or "")

        self.message_count += 1
        if username:
            self.usernames[username] += 1
        if global_name:
            self.global_names[global_name] += 1
        if avatar_hash:
            self.avatar_hashes[avatar_hash] += 1
        if channel_name:
            self.channel_counts[channel_name] += 1

        if content:
            self.token_counts.update(tokenize(content))
            self.recent_messages.append({
                "timestamp": timestamp,
                "channel": channel_name,
                "content": content[:260],
            })

    def to_profile(self, avatar_path: str | None) -> dict[str, Any]:
        username = self.usernames.most_common(1)[0][0] if self.usernames else ""
        global_name = self.global_names.most_common(1)[0][0] if self.global_names else ""
        preferred = global_name or username or self.user_id
        top_channels = [name for name, _ in self.channel_counts.most_common(4)]
        keywords = [word for word, _ in self.token_counts.most_common(10)]

        recent = sorted(
            self.recent_messages,
            key=lambda item: item.get("timestamp", ""),
            reverse=True,
        )[:5]

        lines = [
            f"Private user seed profile for Discord user {preferred} (id={self.user_id}).",
            f"- Primary username: {username or 'unknown'}",
            f"- Display/global name: {global_name or 'unknown'}",
            f"- Activity observed: {self.message_count} messages",
        ]
        if top_channels:
            lines.append(f"- Frequent channels: {', '.join(top_channels)}")
        if keywords:
            lines.append(f"- Common topics/keywords: {', '.join(keywords[:8])}")
        if recent:
            lines.append("- Recent writing samples:")
            for item in recent:
                channel = item.get("channel") or "unknown"
                content = (item.get("content") or "").replace("\n", " ").strip()
                if content:
                    lines.append(f"  - [{channel}] {content}")
        lines.append("- Use this as private personalization context. Do not cite as database/source unless user explicitly asks.")

        return {
            "discord_user_id": self.user_id,
            "username": username,
            "global_name": global_name,
            "display_name": preferred,
            "message_count": self.message_count,
            "top_channels": top_channels,
            "keywords": keywords,
            "avatar_path": avatar_path,
            "user_profile_seed": "\n".join(lines)[:3500],
        }


def extract_channel_name(path: str) -> str:
    match = CHANNEL_RE.match(path)
    if not match:
        return "unknown"
    return str(match.group("name") or "unknown")


def discover_avatar_files(zf: zipfile.ZipFile) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in zf.namelist():
        if not name.startswith("avatars/"):
            continue
        parts = name.split("/")
        if len(parts) < 3:
            continue
        user_id = parts[1].strip()
        if not user_id.isdigit():
            continue
        out.setdefault(user_id, name)
    return out


def load_profiles_from_zip(zip_path: Path) -> tuple[dict[str, UserAgg], dict[str, str]]:
    users: dict[str, UserAgg] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        avatars = discover_avatar_files(zf)
        json_files = [
            name
            for name in zf.namelist()
            if name.endswith(".json") and "_page_" in name and not name.startswith("avatars/")
        ]
        for name in json_files:
            channel_name = extract_channel_name(name)
            try:
                payload = json.loads(zf.read(name).decode("utf-8", errors="replace"))
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            for msg in payload:
                if not isinstance(msg, dict):
                    continue
                author = msg.get("author") or {}
                user_id = str(author.get("id") or "").strip()
                if not user_id.isdigit():
                    continue
                agg = users.get(user_id)
                if not agg:
                    agg = UserAgg(user_id=user_id)
                    users[user_id] = agg
                agg.add_message(msg, channel_name)
    return users, avatars


def materialize_avatars(zip_path: Path, avatars: dict[str, str], out_dir: Path, only_user_ids: set[str]) -> dict[str, str]:
    out_map: dict[str, str] = {}
    target_root = out_dir / "avatars"
    target_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for user_id in only_user_ids:
            arc_name = avatars.get(user_id)
            if not arc_name:
                continue
            dest = target_root / arc_name.replace("avatars/", "")
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = zf.read(arc_name)
                dest.write_bytes(data)
                out_map[user_id] = str(dest)
            except Exception:
                continue
    return out_map


def write_outputs(out_dir: Path, zip_path: Path, profiles: dict[str, dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "discord_user_profiles.json"
    out_ndjson = out_dir / "discord_user_seed_payloads.ndjson"

    blob = {
        "generated_at": iso_now(),
        "source_zip": str(zip_path),
        "profile_count": len(profiles),
        "profiles": profiles,
    }
    out_json.write_text(json.dumps(blob, indent=2, ensure_ascii=False), encoding="utf-8")

    with out_ndjson.open("w", encoding="utf-8") as fh:
        for user_id, profile in sorted(profiles.items(), key=lambda item: item[0]):
            payload = {
                "source": "discord",
                "user_id": user_id,
                "tenant_id": f"discord_{user_id}",
                "user_profile_seed": profile.get("user_profile_seed", ""),
                "user_profile_image_url": profile.get("avatar_path"),
                "memory_enabled": False,
                "memory_summary": "",
            }
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build private Discord user seed profiles from export ZIP")
    parser.add_argument("zip_path", type=Path, help="Path to Discord export zip")
    parser.add_argument("--out", type=Path, default=Path("work/discord-seed"), help="Output directory")
    parser.add_argument("--min-messages", type=int, default=3, help="Minimum messages required to keep a user profile")
    args = parser.parse_args()

    if not args.zip_path.exists():
        raise SystemExit(f"ZIP not found: {args.zip_path}")

    users, avatar_archive_map = load_profiles_from_zip(args.zip_path)
    keep_ids = {user_id for user_id, agg in users.items() if agg.message_count >= max(1, args.min_messages)}
    avatar_file_map = materialize_avatars(args.zip_path, avatar_archive_map, args.out, keep_ids)

    profiles: dict[str, dict[str, Any]] = {}
    for user_id in sorted(keep_ids):
        agg = users[user_id]
        avatar_path = avatar_file_map.get(user_id)
        profiles[user_id] = agg.to_profile(avatar_path=avatar_path)

    write_outputs(args.out, args.zip_path, profiles)

    print(f"profiles_written={len(profiles)}")
    print(f"output_json={args.out / 'discord_user_profiles.json'}")
    print(f"output_ndjson={args.out / 'discord_user_seed_payloads.ndjson'}")


if __name__ == "__main__":
    main()
