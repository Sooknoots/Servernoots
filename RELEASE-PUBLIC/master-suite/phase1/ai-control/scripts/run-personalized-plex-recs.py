#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class UserProfile:
    telegram_user_id: int
    plex_username: str
    display_name: str
    preferred_genres: list[str]


def now_ts() -> int:
    return int(time.time())


def parse_iso_to_ts(value: Any) -> int:
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


def normalize_genre(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.title()


def normalize_title_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()


def request_json(url: str, headers: dict[str, str], timeout: int = 25, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, headers=headers, method=method.upper(), data=payload)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="ignore")
    return json.loads(raw) if raw.strip() else {}


def resolve_overseerr_base(base: str, api_key: str, timeout: int = 15) -> str:
    candidates: list[str] = []
    configured = str(base or "").strip().rstrip("/")
    if configured:
        candidates.append(configured)
    for fallback in ("http://127.0.0.1:5055", "http://host.docker.internal:5055"):
        if fallback not in candidates:
            candidates.append(fallback)

    headers = {"Accept": "application/json", "X-Api-Key": api_key}
    for candidate in candidates:
        try:
            request_json(f"{candidate}/api/v1/status", headers=headers, timeout=timeout)
            return candidate
        except Exception:
            continue
    return configured


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"notified": {}, "requested": {}, "updated_at": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"notified": {}, "requested": {}, "updated_at": ""}
    notified = payload.get("notified") if isinstance(payload, dict) else {}
    requested = payload.get("requested") if isinstance(payload, dict) else {}
    if not isinstance(notified, dict):
        notified = {}
    if not isinstance(requested, dict):
        requested = {}
    return {"notified": notified, "requested": requested, "updated_at": str(payload.get("updated_at", ""))}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def prune_state(state: dict[str, Any], retention_seconds: int, ts_now: int) -> None:
    keep_after = ts_now - max(1, retention_seconds)
    for key in ("notified", "requested"):
        bucket = state.get(key)
        if not isinstance(bucket, dict):
            state[key] = {}
            continue
        cleaned: dict[str, int] = {}
        for marker, value in bucket.items():
            try:
                item_ts = int(value)
            except Exception:
                continue
            if item_ts >= keep_after:
                cleaned[str(marker)] = item_ts
        state[key] = cleaned


def tautulli_call(base: str, api_key: str, cmd: str, params: dict[str, Any] | None = None, timeout: int = 25) -> Any:
    query = {"apikey": api_key, "cmd": cmd}
    if params:
        for key, value in params.items():
            if value is None:
                continue
            query[str(key)] = value
    encoded = urllib.parse.urlencode(query)
    url = f"{base.rstrip('/')}/api/v2?{encoded}"
    payload = request_json(url, headers={"Accept": "application/json"}, timeout=timeout)
    response = payload.get("response") if isinstance(payload, dict) else {}
    if not isinstance(response, dict):
        return None
    if str(response.get("result", "")).lower() != "success":
        return None
    return response.get("data")


def parse_tautulli_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("data", "recently_added", "items", "results"):
        raw = data.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def extract_genres_from_metadata(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("genres") if isinstance(metadata, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            tag = normalize_genre(item.get("tag") or item.get("name"))
            if tag:
                out.append(tag)
        else:
            tag = normalize_genre(item)
            if tag:
                out.append(tag)
    deduped: list[str] = []
    seen: set[str] = set()
    for genre in out:
        marker = genre.lower()
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(genre)
    return deduped


def load_user_profiles(path: Path) -> list[UserProfile]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    raw_users = payload.get("users") if isinstance(payload, dict) else []
    if not isinstance(raw_users, list):
        return []

    users: list[UserProfile] = []
    for raw in raw_users:
        if not isinstance(raw, dict):
            continue
        try:
            telegram_user_id = int(raw.get("telegram_user_id") or raw.get("telegram_id") or 0)
        except Exception:
            continue
        plex_username = str(raw.get("plex_username") or raw.get("tautulli_username") or "").strip()
        if telegram_user_id <= 0 or not plex_username:
            continue
        display_name = str(raw.get("display_name") or raw.get("name") or plex_username).strip() or plex_username
        preferred_genres_raw = raw.get("preferred_genres")
        preferred_genres: list[str] = []
        if isinstance(preferred_genres_raw, list):
            preferred_genres = [normalize_genre(item) for item in preferred_genres_raw if normalize_genre(item)]
        users.append(
            UserProfile(
                telegram_user_id=telegram_user_id,
                plex_username=plex_username,
                display_name=display_name,
                preferred_genres=preferred_genres,
            )
        )
    return users


def load_do_not_request_titles(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = str(raw_line or "").strip()
            if not line or line.startswith("#"):
                continue
            key = normalize_title_key(line)
            if key:
                out.add(key)
    except Exception:
        return set()
    return out


def count_recent_requests_for_user(requested_state: dict[str, Any], user_id: int, since_ts: int) -> int:
    total = 0
    prefix = f"{int(user_id)}|"
    for marker, ts_value in requested_state.items():
        marker_text = str(marker)
        if not marker_text.startswith(prefix):
            continue
        try:
            item_ts = int(ts_value)
        except Exception:
            continue
        if item_ts >= since_ts:
            total += 1
    return total


def build_user_genre_scores(
    history: list[dict[str, Any]],
    users: list[UserProfile],
    metadata_cache: dict[str, list[str]],
    tautulli_base: str,
    tautulli_api_key: str,
    timeout: int,
) -> dict[int, dict[str, int]]:
    user_map = {user.plex_username.lower(): user for user in users}
    scores: dict[int, dict[str, int]] = {user.telegram_user_id: {} for user in users}

    for item in history:
        username = str(item.get("user") or item.get("user_name") or item.get("friendly_name") or "").strip().lower()
        if not username:
            continue
        profile = user_map.get(username)
        if profile is None:
            continue

        media_type = str(item.get("media_type") or "").strip().lower()
        if media_type and media_type != "movie":
            continue

        rating_key = str(item.get("rating_key") or item.get("grandparent_rating_key") or "").strip()
        if not rating_key:
            continue

        genres = metadata_cache.get(rating_key)
        if genres is None:
            data = tautulli_call(
                base=tautulli_base,
                api_key=tautulli_api_key,
                cmd="get_metadata",
                params={"rating_key": rating_key},
                timeout=timeout,
            )
            metadata = data if isinstance(data, dict) else {}
            genres = extract_genres_from_metadata(metadata)
            metadata_cache[rating_key] = genres

        for genre in genres:
            bucket = scores.setdefault(profile.telegram_user_id, {})
            bucket[genre] = int(bucket.get(genre, 0)) + 1

    for user in users:
        bucket = scores.setdefault(user.telegram_user_id, {})
        for genre in user.preferred_genres:
            bucket[genre] = int(bucket.get(genre, 0)) + 3

    return scores


def top_genres_for_user(scores: dict[str, int], limit: int = 3) -> list[str]:
    if not scores:
        return []
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ordered[: max(1, limit)]]


def fetch_recently_added_movies(tautulli_base: str, tautulli_api_key: str, timeout: int = 25) -> list[dict[str, Any]]:
    data = tautulli_call(base=tautulli_base, api_key=tautulli_api_key, cmd="get_recently_added", params={"count": 200}, timeout=timeout)
    items = parse_tautulli_items(data)
    return [item for item in items if isinstance(item, dict)]


def item_added_ts(item: dict[str, Any]) -> int:
    for key in ("added_at", "addedAt", "added"):
        if key in item:
            try:
                return int(item.get(key) or 0)
            except Exception:
                pass
    for key in ("added_at", "addedAt", "added"):
        ts = parse_iso_to_ts(item.get(key))
        if ts > 0:
            return ts
    return 0


def post_ntfy(ntfy_base: str, topic: str, title: str, message: str, priority: str = "default") -> tuple[bool, str]:
    url = f"{ntfy_base.rstrip('/')}/{topic.lstrip('/')}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8", errors="ignore"),
        method="POST",
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": "movie_camera,information_source",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            return True, "sent"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def overseerr_search_movies(base: str, api_key: str, query: str, timeout: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query": query, "page": 1, "language": "en"})
    url = f"{base.rstrip('/')}/api/v1/search?{params}"
    payload = request_json(url, headers={"Accept": "application/json", "X-Api-Key": api_key}, timeout=timeout)
    raw = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if str(item.get("mediaType") or "").strip().lower() != "movie":
            continue
        out.append(item)
    return out


def should_skip_overseerr_movie(item: dict[str, Any]) -> bool:
    media_info = item.get("mediaInfo") if isinstance(item.get("mediaInfo"), dict) else {}
    try:
        status = int(media_info.get("status", 0) or 0)
    except Exception:
        status = 0
    return status >= 2


def request_overseerr_movie(base: str, api_key: str, media_id: int, timeout: int) -> tuple[bool, str]:
    url = f"{base.rstrip('/')}/api/v1/request"
    body = {"mediaType": "movie", "mediaId": int(media_id)}
    try:
        request_json(url, headers={"Accept": "application/json", "Content-Type": "application/json", "X-Api-Key": api_key}, timeout=timeout, method="POST", body=body)
        return True, "requested"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Personalized Plex recommendations + optional Overseerr auto-request")
    parser.add_argument("--profiles", default=os.getenv("MEDIA_USER_PROFILE_PATH", "work/media-user-profiles.json"))
    parser.add_argument("--state", default=os.getenv("MEDIA_PERSONALIZATION_STATE", "logs/media-personalization-state.json"))
    parser.add_argument("--history-length", type=int, default=int(os.getenv("MEDIA_HISTORY_LENGTH", "600")))
    parser.add_argument("--recent-hours", type=int, default=int(os.getenv("MEDIA_RECENT_HOURS", "48")))
    parser.add_argument("--state-retention-days", type=int, default=int(os.getenv("MEDIA_STATE_RETENTION_DAYS", "14")))
    parser.add_argument("--top-genres", type=int, default=int(os.getenv("MEDIA_TOP_GENRES", "3")))
    parser.add_argument("--max-recs-per-user", type=int, default=int(os.getenv("MEDIA_MAX_RECS_PER_USER", "3")))
    parser.add_argument("--auto-request-per-user", type=int, default=int(os.getenv("MEDIA_AUTO_REQUEST_PER_USER", "0")))
    parser.add_argument(
        "--auto-request-daily-cap-per-user",
        type=int,
        default=int(os.getenv("MEDIA_AUTO_REQUEST_DAILY_CAP_PER_USER", "1")),
    )
    parser.add_argument(
        "--do-not-request-file",
        default=os.getenv("MEDIA_DO_NOT_REQUEST_FILE", "work/media-do-not-request.txt"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profiles = load_user_profiles(Path(args.profiles))
    if not profiles:
        print("No user profiles found. Add users to work/media-user-profiles.json")
        return 1

    tautulli_url = os.getenv("TAUTULLI_URL", "").strip().rstrip("/")
    tautulli_api_key = os.getenv("TAUTULLI_API_KEY", "").strip()
    ntfy_base = os.getenv("NTFY_BASE", "http://127.0.0.1:8091").strip()
    ntfy_topic = os.getenv("MEDIA_PERSONALIZED_TOPIC", "media-recommendations").strip() or "media-recommendations"
    overseerr_url = os.getenv("OVERSEERR_URL", "http://127.0.0.1:5055").strip().rstrip("/")
    overseerr_api_key = os.getenv("OVERSEERR_API_KEY", "").strip()
    timeout = 25
    if overseerr_api_key:
        overseerr_url = resolve_overseerr_base(base=overseerr_url, api_key=overseerr_api_key, timeout=timeout)

    if not tautulli_url or not tautulli_api_key:
        print("TAUTULLI_URL and TAUTULLI_API_KEY are required")
        return 1

    state_path = Path(args.state)
    state = load_state(state_path)
    ts_now = now_ts()
    prune_state(state, retention_seconds=max(1, args.state_retention_days) * 86400, ts_now=ts_now)

    history_data = tautulli_call(
        base=tautulli_url,
        api_key=tautulli_api_key,
        cmd="get_history",
        params={"length": max(50, args.history_length)},
        timeout=timeout,
    )
    history_items = parse_tautulli_items(history_data)
    metadata_cache: dict[str, list[str]] = {}
    genre_scores = build_user_genre_scores(
        history=history_items,
        users=profiles,
        metadata_cache=metadata_cache,
        tautulli_base=tautulli_url,
        tautulli_api_key=tautulli_api_key,
        timeout=timeout,
    )

    recent_items = fetch_recently_added_movies(tautulli_base=tautulli_url, tautulli_api_key=tautulli_api_key, timeout=timeout)
    recent_cutoff = ts_now - max(1, args.recent_hours) * 3600

    notified = state.get("notified") if isinstance(state.get("notified"), dict) else {}
    requested = state.get("requested") if isinstance(state.get("requested"), dict) else {}
    do_not_request_titles = load_do_not_request_titles(Path(args.do_not_request_file))

    total_notifications = 0
    total_requests = 0

    for user in profiles:
        user_scores = genre_scores.get(user.telegram_user_id, {})
        top_genres = top_genres_for_user(user_scores, limit=max(1, args.top_genres))
        if not top_genres:
            continue

        rec_lines: list[str] = []
        matched_keys: list[str] = []
        for item in recent_items:
            media_type = str(item.get("media_type") or "movie").strip().lower()
            if media_type and media_type != "movie":
                continue
            added_ts = item_added_ts(item)
            if added_ts <= 0 or added_ts < recent_cutoff:
                continue

            rating_key = str(item.get("rating_key") or "").strip()
            if not rating_key:
                continue

            genres = metadata_cache.get(rating_key)
            if genres is None:
                metadata = tautulli_call(
                    base=tautulli_url,
                    api_key=tautulli_api_key,
                    cmd="get_metadata",
                    params={"rating_key": rating_key},
                    timeout=timeout,
                )
                genres = extract_genres_from_metadata(metadata if isinstance(metadata, dict) else {})
                metadata_cache[rating_key] = genres

            if not genres:
                continue
            overlap = [genre for genre in genres if genre in top_genres]
            if not overlap:
                continue

            marker = f"{user.telegram_user_id}|{rating_key}"
            if marker in notified:
                continue

            title = str(item.get("full_title") or item.get("title") or "Unknown title").strip()
            rec_lines.append(f"- {title} [{', '.join(overlap[:2])}]")
            matched_keys.append(marker)
            if len(rec_lines) >= max(1, args.max_recs_per_user):
                break

        request_lines: list[str] = []
        if args.auto_request_per_user > 0 and overseerr_api_key:
            daily_cap = max(0, int(args.auto_request_daily_cap_per_user))
            if daily_cap <= 0:
                continue
            day_window_start = ts_now - 86400
            recent_request_count = count_recent_requests_for_user(
                requested_state=requested,
                user_id=user.telegram_user_id,
                since_ts=day_window_start,
            )
            if recent_request_count >= daily_cap:
                print(f"auto_request_cap_reached user={user.telegram_user_id} daily_cap={daily_cap} recent={recent_request_count}")
                continue

            candidate_items: list[dict[str, Any]] = []
            for genre in top_genres:
                search_items = overseerr_search_movies(base=overseerr_url, api_key=overseerr_api_key, query=genre, timeout=timeout)
                candidate_items.extend(search_items)

            deduped: dict[int, dict[str, Any]] = {}
            for item in candidate_items:
                media_id = item.get("id")
                try:
                    media_id_int = int(media_id)
                except Exception:
                    continue
                if should_skip_overseerr_movie(item):
                    continue
                existing = deduped.get(media_id_int)
                if existing is None or float(item.get("popularity", 0) or 0) > float(existing.get("popularity", 0) or 0):
                    deduped[media_id_int] = item

            ordered = sorted(deduped.values(), key=lambda item: float(item.get("popularity", 0) or 0), reverse=True)
            for item in ordered:
                try:
                    media_id_int = int(item.get("id"))
                except Exception:
                    continue
                request_marker = f"{user.telegram_user_id}|{media_id_int}"
                if request_marker in requested:
                    continue

                title = str(item.get("title") or item.get("name") or "Unknown").strip()
                title_key = normalize_title_key(title)
                if title_key and title_key in do_not_request_titles:
                    continue
                if args.dry_run:
                    ok, reason = True, "dry_run"
                else:
                    ok, reason = request_overseerr_movie(base=overseerr_url, api_key=overseerr_api_key, media_id=media_id_int, timeout=timeout)
                if not ok:
                    continue
                requested[request_marker] = ts_now
                recent_request_count += 1
                request_lines.append(f"- {title}")
                total_requests += 1
                if recent_request_count >= daily_cap:
                    break
                if len(request_lines) >= max(1, args.auto_request_per_user):
                    break

        if not rec_lines and not request_lines:
            continue

        lines = [
            f"🎬 Personalized picks for {user.display_name}",
            f"Taste profile: {', '.join(top_genres)}",
        ]
        if rec_lines:
            lines.append("Recently added in Plex that match your taste:")
            lines.extend(rec_lines)
        if request_lines:
            lines.append("Queued for download/request:")
            lines.extend(request_lines)
        lines.append("reply with /media if you want additional requests")
        lines.append(f"notify_targets={user.telegram_user_id}")

        title = f"Personalized Plex updates: {user.display_name}"
        body = "\n".join(lines)
        if args.dry_run:
            ok, reason = True, "dry_run"
        else:
            ok, reason = post_ntfy(ntfy_base=ntfy_base, topic=ntfy_topic, title=title, message=body, priority="default")

        if ok:
            total_notifications += 1
            for marker in matched_keys:
                notified[marker] = ts_now
        else:
            print(f"notify_failed user={user.telegram_user_id} reason={reason}")

    state["notified"] = notified
    state["requested"] = requested
    save_state(state_path, state)

    print(f"users={len(profiles)} notified={total_notifications} auto_requested={total_requests} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
