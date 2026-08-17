from __future__ import annotations

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from .orchestrator import Jarvis
from .principles import catalogue, doctrine_summary

APP = Jarvis(os.getenv("JARVIS_STATE_DIR", "state"))


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def _authorized(self) -> bool:
        expected = os.getenv("JARVIS_API_TOKEN", "")
        provided = self.headers.get("authorization", "")
        return not expected or hmac.compare_digest(provided, f"Bearer {expected}")

    def do_GET(self):
        if self.path == "/health": return self._json(200, APP.health())
        if not self._authorized(): return self._json(403, {"ok": False, "error": "FORBIDDEN"})
        if self.path == "/v1/capabilities": return self._json(200, APP.capabilities())
        if self.path == "/v1/principles": return self._json(200, {"summary": doctrine_summary(), "principles": catalogue()})
        if self.path == "/":
            data = files("jarvis.resources").joinpath("index.html").read_bytes(); self.send_response(200); self.send_header("content-type", "text/html; charset=utf-8"); self.send_header("content-length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        self._json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self):
        if not self._authorized(): return self._json(403, {"ok": False, "error": "FORBIDDEN"})
        try:
            length = min(int(self.headers.get("content-length", "0")), 1_000_000)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/v1/chat": return self._json(200, APP.chat(str(body.get("message", ""))))
            if self.path == "/v1/plan": return self._json(200, APP.plan(str(body.get("objective", ""))))
            if self.path == "/v1/math": return self._json(200, APP.math(str(body.get("expression", ""))))
            if self.path == "/v1/authorize": return self._json(200, APP.authorize(str(body.get("missionId", "")), str(body.get("actionId", "")), str(body.get("capability", "")), body.get("permit")))
            return self._json(404, {"ok": False, "error": "NOT_FOUND"})
        except Exception as exc:
            return self._json(400, {"ok": False, "error": type(exc).__name__})

    def log_message(self, *_): pass


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("message", nargs="?"); parser.add_argument("--serve", action="store_true"); parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080"))); args = parser.parse_args()
    if args.serve or os.getenv("PORT"):
        host = "0.0.0.0" if os.getenv("JARVIS_API_TOKEN") else "127.0.0.1"
        ThreadingHTTPServer((host, args.port), Handler).serve_forever()
    else:
        print(json.dumps(APP.chat(args.message or "Report readiness."), indent=2))


if __name__ == "__main__": main()
