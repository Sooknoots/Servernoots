#!/usr/bin/env python3
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

AUDIT_LOG = os.getenv("AUDIT_LOG", "/opt/guardrails/audit.log")
HOST = os.getenv("AUDIT_HOST", "0.0.0.0")
PORT = int(os.getenv("AUDIT_PORT", "18081"))
MAX_LINES = int(os.getenv("AUDIT_MAX_LINES", "50"))
DEFAULT_LINES = int(os.getenv("AUDIT_DEFAULT_LINES", "10"))


def tail_lines(path: str, lines: int) -> str:
    if not os.path.exists(path):
        return "audit.log not found"

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.readlines()

    if not data:
        return "audit.log is empty"

    selected = data[-lines:]
    return "".join(selected).strip() or "audit.log is empty"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/last", "/last/"):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"not found")
            return

        params = parse_qs(parsed.query)
        requested = params.get("lines", [str(DEFAULT_LINES)])[0]
        try:
            lines = int(requested)
        except ValueError:
            lines = DEFAULT_LINES

        if lines < 1:
            lines = 1
        if lines > MAX_LINES:
            lines = MAX_LINES

        output = tail_lines(AUDIT_LOG, lines)
        encoded = output.encode("utf-8", errors="ignore")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
