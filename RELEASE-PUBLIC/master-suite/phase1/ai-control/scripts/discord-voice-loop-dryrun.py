#!/usr/bin/env python3
import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import request, error, parse


def normalize_id(value: Any) -> str:
    return str(value or "").strip()


VOICE_CONTROL_COMMANDS = {"join", "leave", "listen_on", "listen_off", "voice_status", "voice_stop"}


def post_json(url: str, payload: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except Exception:
        return {"raw": body}


def post_openwhisper_source_url(stt_base: str, audio_url: str, model: str, timeout_sec: int) -> dict[str, Any]:
    query = parse.urlencode({"source_url": audio_url, "model": model})
    url = stt_base.rstrip("/") + "/v1/audio/transcriptions" + "?" + query
    req = request.Request(url, data=b"", method="POST")
    with request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except Exception:
        return {"raw": body}


def extract_reply_text(payload: dict[str, Any]) -> str:
    for key in ("reply", "message", "text", "raw"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def read_event_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.event_file:
        return json.loads(Path(args.event_file).read_text(encoding="utf-8"))
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return json.loads(data)
    raise SystemExit("Provide --event-file or pipe event JSON via stdin")


def run_voice_loop(event: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    user_id = normalize_id(event.get("user_id") or event.get("discord_user_id"))
    if not user_id:
        raise ValueError("event.user_id is required")

    control_command = str(event.get("command") or "").strip().lower()
    if control_command in VOICE_CONTROL_COMMANDS:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "route": "discord-voice-loop-dryrun",
            "dry_run": True,
            "timing_ms": elapsed_ms,
            "control": {
                "status": "accepted",
                "command": control_command,
                "voice_session_id": str(event.get("voice_session_id") or ""),
            },
            "stt": {
                "status": "skipped_control",
                "provider_url": args.stt_base.rstrip("/") + args.stt_path,
                "model": args.stt_model,
            },
            "rag": {
                "status": "skipped_control",
                "webhook": args.n8n_base.rstrip("/") + args.rag_webhook,
            },
            "tts": {
                "status": "skipped_control",
                "voice": args.tts_voice,
                "format": "text",
            },
        }

    transcript = str(event.get("transcript") or event.get("message") or "").strip()
    stt_status = "skipped"
    stt_payload: dict[str, Any] = {}

    if not transcript:
        audio_url = str(event.get("audio_url") or "").strip()
        if not audio_url:
            raise ValueError("voice loop requires transcript/message or audio_url")
        stt_req = {
            "audio_url": audio_url,
            "model": args.stt_model,
            "source": "discord",
        }
        stt_url = args.stt_base.rstrip("/") + args.stt_path
        try:
            stt_payload = post_json(stt_url, stt_req, timeout_sec=args.timeout)
        except error.HTTPError as exc:
            if int(getattr(exc, "code", 0)) != 404:
                raise
            stt_payload = post_openwhisper_source_url(
                stt_base=args.stt_base,
                audio_url=audio_url,
                model=args.stt_model,
                timeout_sec=args.timeout,
            )
        transcript = str(stt_payload.get("text") or stt_payload.get("transcript") or "").strip()
        stt_status = "ok" if transcript else "empty"

    rag_payload = {
        "source": "discord",
        "chat_id": str(event.get("chat_id") or event.get("channel_id") or event.get("voice_channel_id") or "discord"),
        "user_id": user_id,
        "role": str(event.get("role") or "user"),
        "tenant_id": str(event.get("tenant_id") or f"u_{user_id}"),
        "full_name": str(event.get("full_name") or event.get("display_name") or event.get("username") or "").strip(),
        "telegram_username": str(event.get("username") or "").strip().lower(),
        "message": transcript,
        "has_audio": bool(event.get("audio_url") or event.get("has_audio")),
        "audio_url": event.get("audio_url"),
        "voice_session_id": str(event.get("voice_session_id") or ""),
        "voice_mode": True,
        "voice_command": str(event.get("command") or "voice_loop"),
    }

    rag_url = args.n8n_base.rstrip("/") + args.rag_webhook
    rag_result = post_json(rag_url, rag_payload, timeout_sec=args.timeout)
    reply_text = extract_reply_text(rag_result)

    elapsed_ms = int((time.time() - started) * 1000)
    return {
        "route": "discord-voice-loop-dryrun",
        "dry_run": True,
        "timing_ms": elapsed_ms,
        "stt": {
            "status": stt_status,
            "used_transcript": transcript,
            "provider_url": args.stt_base.rstrip("/") + args.stt_path,
            "model": args.stt_model,
            "raw": stt_payload if stt_payload else None,
        },
        "rag": {
            "status": "ok" if reply_text else "no_reply_text",
            "webhook": rag_url,
            "raw": rag_result,
        },
        "tts": {
            "status": "ready" if reply_text else "empty",
            "voice": args.tts_voice,
            "format": "text",
            "text": reply_text,
            "text_preview": reply_text[:240],
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DiscordVoiceLoopDryRun/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path not in {"/discord-voice-command", "/voice-loop"}:
            self._json(404, {"error": "not_found"})
            return

        try:
            raw_len = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raw_len = 0

        raw = self.rfile.read(max(0, raw_len))
        try:
            event = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            self._json(400, {"error": "invalid_json"})
            return

        try:
            result = run_voice_loop(event, self.server.args)
            self._json(200, result)
        except Exception as exc:
            self._json(500, {"error": "voice_loop_failed", "detail": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        if self.server.args.quiet:
            return
        super().log_message(format, *args)


class VoiceLoopServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, args: argparse.Namespace):
        super().__init__(server_address, RequestHandlerClass)
        self.args = args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discord voice loop dry-run helper (STT -> RAG -> TTS text contract)")
    parser.add_argument("--event-file", default="", help="Input event JSON file path")
    parser.add_argument("--serve", action="store_true", help="Run HTTP server mode")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for --serve mode")
    parser.add_argument("--port", type=int, default=8101, help="Bind port for --serve mode")
    parser.add_argument("--n8n-base", default="http://127.0.0.1:5678", help="n8n base URL")
    parser.add_argument("--rag-webhook", default="/webhook/rag-query", help="RAG webhook path")
    parser.add_argument("--stt-base", default="http://127.0.0.1:9001", help="STT base URL")
    parser.add_argument("--stt-path", default="/v1/audio/transcriptions/by-url", help="STT path for by-url transcription")
    parser.add_argument("--stt-model", default="whisper-1", help="STT model identifier")
    parser.add_argument("--tts-voice", default="allison", help="Dry-run TTS voice label")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout seconds")
    parser.add_argument("--quiet", action="store_true", help="Suppress HTTP server request logs")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.serve:
        server = VoiceLoopServer((args.host, args.port), Handler, args)
        print(f"discord-voice-loop-dryrun listening on http://{args.host}:{args.port}")
        server.serve_forever()
        return

    event = read_event_from_args(args)
    result = run_voice_loop(event, args)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
