from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .orchestrator import Jarvis
from .principles import catalogue

APP = Jarvis(os.getenv("JARVIS_STATE_DIR", "state"))
MAX_BODY_BYTES = 1_000_000


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        expected = os.getenv("JARVIS_API_TOKEN", "")
        return not expected or self.headers.get("authorization") == f"Bearer {expected}"

    def _body(self) -> dict[str, Any]:
        raw_length = int(self.headers.get("content-length", "0"))
        if raw_length < 0 or raw_length > MAX_BODY_BYTES:
            raise ValueError("INVALID_CONTENT_LENGTH")
        value = json.loads(self.rfile.read(raw_length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("JSON_OBJECT_REQUIRED")
        return value

    def do_GET(self) -> None:
        if self.path == "/health":
            return self._json(200, APP.health())
        if not self._authorized():
            return self._json(403, {"ok": False, "error": "FORBIDDEN"})
        if self.path == "/v1/capabilities":
            return self._json(200, APP.capabilities())
        if self.path == "/v1/principles":
            return self._json(200, {"principles": catalogue()})
        if self.path == "/v1/execution-policy":
            return self._json(200, APP.execution_policy())
        if self.path == "/":
            page = Path(__file__).parent.parent / "web" / "index.html"
            data = page.read_bytes()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return None
        return self._json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:
        if not self._authorized():
            return self._json(403, {"ok": False, "error": "FORBIDDEN"})
        try:
            body = self._body()
            if self.path == "/v1/chat":
                return self._json(200, APP.chat(str(body.get("message", ""))))
            if self.path == "/v1/plan":
                return self._json(200, APP.plan(str(body.get("objective", ""))))
            if self.path == "/v1/authorize":
                return self._json(200, APP.authorize(str(body.get("missionId", "")), str(body.get("action", "")), str(body.get("capability", "")), body.get("permit")))
            if self.path == "/v1/cycle-review":
                elapsed = body.get("elapsedSeconds")
                retries = body.get("retries", 0)
                gates = body.get("qualityGates")
                if isinstance(elapsed, bool) or not isinstance(elapsed, int):
                    raise ValueError("ELAPSED_SECONDS_INTEGER_REQUIRED")
                if isinstance(retries, bool) or not isinstance(retries, int):
                    raise ValueError("RETRIES_INTEGER_REQUIRED")
                if not isinstance(gates, dict) or not all(isinstance(k, str) and isinstance(v, bool) for k, v in gates.items()):
                    raise ValueError("BOOLEAN_QUALITY_GATES_REQUIRED")
                return self._json(200, APP.review_cycle(elapsed, gates, retries))
            return self._json(404, {"ok": False, "error": "NOT_FOUND"})
        except Exception as exc:
            return self._json(400, {"ok": False, "error": str(exc) or type(exc).__name__})

    def log_message(self, *_: Any) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("message", nargs="?")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    args = parser.parse_args()
    if args.serve or os.getenv("PORT"):
        host = "0.0.0.0" if os.getenv("JARVIS_API_TOKEN") else "127.0.0.1"
        ThreadingHTTPServer((host, args.port), Handler).serve_forever()
    else:
        print(json.dumps(APP.chat(args.message or "Report readiness."), indent=2))


if __name__ == "__main__":
    main()
