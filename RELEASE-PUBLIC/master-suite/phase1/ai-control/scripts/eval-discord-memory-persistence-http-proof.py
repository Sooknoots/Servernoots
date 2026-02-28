#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib import request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M8 HTTP /proxy parity persistence proof")
    parser.add_argument("--proxy-port", type=int, default=18099)
    parser.add_argument("--mock-port", type=int, default=18102)
    parser.add_argument("--state-file", default="/tmp/discord-m8-state-http.json")
    parser.add_argument("--audit-file", default="/tmp/discord-m8-audit-http.jsonl")
    parser.add_argument("--proof-file", default="/tmp/discord-m8-persistence-http-proof.txt")
    parser.add_argument("--proxy-log", default="/tmp/discord-m8-proxy-http.log")
    parser.add_argument("--mock-log", default="/tmp/discord-m8-mock-http.log")
    parser.add_argument("--guild-id", default="g1")
    parser.add_argument("--channel-id", default="c1")
    parser.add_argument("--user-id", default="111")
    parser.add_argument("--tenant-id", default="u_111")
    return parser.parse_args()


def post_proxy(port: int, event_obj: dict) -> dict:
    data = json.dumps(event_obj).encode("utf-8")
    req = request.Request(f"http://127.0.0.1:{port}/proxy", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def main() -> None:
    args = parse_args()
    state_file = Path(args.state_file)
    audit_file = Path(args.audit_file)
    proof_file = Path(args.proof_file)
    proxy_log = Path(args.proxy_log)
    mock_log = Path(args.mock_log)

    for path in (state_file, audit_file, proof_file, proxy_log, mock_log):
        if path.exists():
            path.unlink()

    mock_code = (
        "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
        "import json\n"
        "class H(BaseHTTPRequestHandler):\n"
        "  def do_POST(self):\n"
        "    n=int(self.headers.get('Content-Length','0') or 0); self.rfile.read(n)\n"
        "    b=json.dumps({'reply':'ok','memory_summary':'allowed_should_persist'}).encode('utf-8')\n"
        "    self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)\n"
        "  def log_message(self, fmt, *args):\n"
        "    return\n"
        f"HTTPServer(('127.0.0.1',{args.mock_port}),H).serve_forever()\n"
    )

    mock = subprocess.Popen(
        ["/usr/bin/python3", "-c", mock_code],
        stdout=mock_log.open("w"),
        stderr=subprocess.STDOUT,
    )

    proxy = subprocess.Popen(
        [
            "/usr/bin/python3",
            "scripts/discord-rag-proxy-server.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.proxy_port),
            "--n8n-base",
            f"http://127.0.0.1:{args.mock_port}",
            "--rag-webhook",
            "/webhook/rag-query",
            "--ops-webhook",
            "/webhook/ops-commands-ingest",
            "--allow-guild-ids",
            args.guild_id,
            "--allow-channel-ids",
            args.channel_id,
            "--memory-state-file",
            str(state_file),
            "--audit-log",
            str(audit_file),
            "--voice-cooldown-seconds",
            "0",
            "--quiet",
        ],
        stdout=proxy_log.open("w"),
        stderr=subprocess.STDOUT,
    )

    lines: list[str] = []
    try:
        ready = False
        for _ in range(80):
            try:
                post_proxy(
                    args.proxy_port,
                    {
                        "user_id": "ready",
                        "guild_id": args.guild_id,
                        "channel_id": args.channel_id,
                        "message": "/memory show",
                    },
                )
                ready = True
                break
            except Exception:
                time.sleep(0.2)
        if not ready:
            raise RuntimeError("proxy not ready")

        lines.append("== HTTP STEP 1: opt-in ==")
        lines.append(
            json.dumps(
                post_proxy(
                    args.proxy_port,
                    {
                        "user_id": args.user_id,
                        "guild_id": args.guild_id,
                        "channel_id": args.channel_id,
                        "role": "user",
                        "tenant_id": args.tenant_id,
                        "message": "/memory opt-in",
                    },
                ),
                separators=(",", ":"),
            )
        )
        lines.append("state_after_opt_in:")
        lines.append(json.dumps(json.loads(state_file.read_text())["users"][args.user_id], separators=(",", ":")))

        lines.append("== HTTP STEP 2: blocked low-confidence ask ==")
        lines.append(
            json.dumps(
                post_proxy(
                    args.proxy_port,
                    {
                        "user_id": args.user_id,
                        "guild_id": args.guild_id,
                        "channel_id": args.channel_id,
                        "role": "user",
                        "tenant_id": args.tenant_id,
                        "message": "/ask hello",
                        "has_audio": True,
                        "speaker_confidence": 0.42,
                    },
                ),
                separators=(",", ":"),
            )
        )
        lines.append("state_after_blocked_attempt:")
        lines.append(json.dumps(json.loads(state_file.read_text())["users"][args.user_id], separators=(",", ":")))

        lines.append("== HTTP STEP 3: allowed high-confidence ask ==")
        lines.append(
            json.dumps(
                post_proxy(
                    args.proxy_port,
                    {
                        "user_id": args.user_id,
                        "guild_id": args.guild_id,
                        "channel_id": args.channel_id,
                        "role": "user",
                        "tenant_id": args.tenant_id,
                        "message": "/ask hello again",
                        "has_audio": True,
                        "speaker_confidence": 0.95,
                    },
                ),
                separators=(",", ":"),
            )
        )
        lines.append("state_after_allowed_attempt:")
        lines.append(json.dumps(json.loads(state_file.read_text())["users"][args.user_id], separators=(",", ":")))

        lines.append("== HTTP AUDIT TAIL ==")
        if audit_file.exists():
            lines.extend(audit_file.read_text().strip().splitlines()[-10:])
    finally:
        proxy.terminate()
        mock.terminate()
        try:
            proxy.wait(timeout=5)
        except Exception:
            proxy.kill()
        try:
            mock.wait(timeout=5)
        except Exception:
            mock.kill()

    proof_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"HTTP_PROOF_FILE={proof_file}")


if __name__ == "__main__":
    main()
