"""Local live-reload server for editing the rules page and rules JSON."""
from __future__ import annotations

import argparse
import json
import os
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
WATCH_PATHS = [
    ROOT / "rules.html",
    ROOT / "data" / "rules.json",
    ROOT / "assets" / "site.css",
    ROOT / "assets" / "site-shell.css",
    ROOT / "assets" / "site-shell.js",
]

LIVE_RELOAD_SNIPPET = """
<script>
(() => {
  const source = new EventSource('/__live-reload');
  source.onmessage = event => {
    if (event.data === 'reload') window.location.reload();
  };
})();
</script>
"""


def latest_mtime() -> float:
    times = []
    for path in WATCH_PATHS:
        try:
            times.append(path.stat().st_mtime)
        except FileNotFoundError:
            continue
    return max(times, default=0)


class LiveReloadHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, directory: str | None = None, **kwargs) -> None:
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/__live-reload":
            self.handle_live_reload()
            return
        if parsed.path in {"", "/"}:
            self.path = "/rules.html"
        if parsed.path == "/rules.html":
            self.handle_rules_page()
            return
        super().do_GET()

    def handle_rules_page(self) -> None:
        try:
            html = (ROOT / "rules.html").read_text(encoding="utf-8")
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "rules.html not found")
            return

        body = html.replace("</body>", LIVE_RELOAD_SNIPPET + "\n</body>")
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def handle_live_reload(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        last_seen = latest_mtime()
        while True:
            time.sleep(0.75)
            current = latest_mtime()
            if current > last_seen:
                last_seen = current
                self.wfile.write(b"data: reload\n\n")
                self.wfile.flush()
                return
            self.wfile.write(b": keepalive\n\n")
            self.wfile.flush()

    def log_message(self, format: str, *args) -> None:
        message = format % args
        print(f"[rules-dev] {self.address_string()} {message}")


def validate_rules_json() -> None:
    path = ROOT / "data" / "rules.json"
    json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve rules.html with live reload.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    os.chdir(ROOT)
    validate_rules_json()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), LiveReloadHandler)
    print(f"Rules dev server running at http://127.0.0.1:{args.port}/rules.html")
    print("Watching rules.html, data/rules.json, and shared shell assets.")
    server.serve_forever()


if __name__ == "__main__":
    main()
