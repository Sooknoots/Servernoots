#!/usr/bin/env python3
import argparse
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M8 CLI proxy persistence proof (blocked vs allowed)")
    parser.add_argument("--mock-port", type=int, default=18101)
    parser.add_argument("--state-file", default="/tmp/discord-m8-state-cli.json")
    parser.add_argument("--audit-file", default="/tmp/discord-m8-audit-cli.jsonl")
    parser.add_argument("--proof-file", default="/tmp/discord-m8-persistence-cli-proof.txt")
    parser.add_argument("--guild-id", default="g1")
    parser.add_argument("--channel-id", default="c1")
    parser.add_argument("--user-id", default="111")
    parser.add_argument("--tenant-id", default="u_111")
    return parser.parse_args()


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        _ = self.rfile.read(length)
        body = json.dumps({"reply": "ok", "memory_summary": "allowed_should_persist"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args):
        return


def run_event(args: argparse.Namespace, state_file: Path, audit_file: Path, event_obj: dict) -> str:
    cmd = [
        "/usr/bin/python3",
        "scripts/discord-rag-proxy.py",
        "--n8n-base",
        f"http://127.0.0.1:{args.mock_port}",
        "--rag-webhook",
        "/webhook/rag-query",
        "--allow-guild-ids",
        args.guild_id,
        "--allow-channel-ids",
        args.channel_id,
        "--memory-state-file",
        str(state_file),
        "--audit-log",
        str(audit_file),
    ]
    proc = subprocess.run(
        cmd,
        input=(json.dumps(event_obj) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout.decode("utf-8", errors="replace").strip()


def main() -> None:
    args = parse_args()
    state_file = Path(args.state_file)
    audit_file = Path(args.audit_file)
    proof_file = Path(args.proof_file)

    for path in (state_file, audit_file, proof_file):
        if path.exists():
            path.unlink()

    server = HTTPServer(("127.0.0.1", args.mock_port), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    lines: list[str] = []
    try:
        lines.append("== CLI STEP 1: opt-in ==")
        lines.append(
            run_event(
                args,
                state_file,
                audit_file,
                {
                    "user_id": args.user_id,
                    "guild_id": args.guild_id,
                    "channel_id": args.channel_id,
                    "role": "user",
                    "tenant_id": args.tenant_id,
                    "message": "/memory opt-in",
                },
            )
        )
        lines.append("state_after_opt_in:")
        lines.append(json.dumps(json.loads(state_file.read_text())["users"][args.user_id], separators=(",", ":")))

        lines.append("== CLI STEP 2: blocked low-confidence ask ==")
        lines.append(
            run_event(
                args,
                state_file,
                audit_file,
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
            )
        )
        lines.append("state_after_blocked_attempt:")
        lines.append(json.dumps(json.loads(state_file.read_text())["users"][args.user_id], separators=(",", ":")))

        lines.append("== CLI STEP 3: allowed high-confidence ask ==")
        lines.append(
            run_event(
                args,
                state_file,
                audit_file,
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
            )
        )
        lines.append("state_after_allowed_attempt:")
        lines.append(json.dumps(json.loads(state_file.read_text())["users"][args.user_id], separators=(",", ":")))

        lines.append("== CLI AUDIT TAIL ==")
        if audit_file.exists():
            lines.extend(audit_file.read_text().strip().splitlines()[-10:])
    finally:
        server.shutdown()
        server.server_close()

    proof_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"CLI_PROOF_FILE={proof_file}")


if __name__ == "__main__":
    main()
