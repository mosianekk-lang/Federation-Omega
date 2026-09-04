from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path

from .engine import SovereignEngine
from .ledger import JsonlLedger
from .models import Budget, MissionIR
from .policy import PolicyEngine
from .providers import MockProvider, OpenRouterProvider
from .router import ProviderRouter


def build_engine(data_dir: str | Path = "data") -> SovereignEngine:
    providers = [MockProvider("local-mock")]
    if os.getenv("SEB_ENABLE_OPENROUTER") == "1":
        providers.insert(0, OpenRouterProvider())
    return SovereignEngine(JsonlLedger(Path(data_dir) / "events.jsonl"),
                           PolicyEngine(max_authority="A2", allow_external_effects=False),
                           ProviderRouter(providers))


class Handler(BaseHTTPRequestHandler):
    engine = build_engine()

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok", "ledger_valid": self.engine.ledger.verify(),
                             "external_effects": False,
                             "service": os.getenv("K_SERVICE", "local"),
                             "revision": os.getenv("K_REVISION", "local")})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/v1/missions/execute":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("invalid content length")
            body = json.loads(self.rfile.read(length))
            mission = MissionIR(
                mission_id=body["mission_id"], objective=body["objective"],
                requirements=tuple(body.get("requirements", [])),
                acceptance_tests=tuple(body.get("acceptance_tests", [])),
                authority_class=body.get("authority_class", "A0"),
                data_class=body.get("data_class", "private"),
                allowed_tools=tuple(body.get("allowed_tools", [])),
                budget=Budget(max_tokens=int(body.get("max_tokens", 4000))))
            result = self.engine.execute(mission, body["prompt"],
                                         {"type": "object"},
                                         lambda output: isinstance(output, dict) and output.get("accepted") is True)
            self._json(200, asdict(result))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": "invalid_request", "detail": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        print(json.dumps({"event": "http_access", "message": format % args}))


def main() -> None:
    host = os.getenv("SEB_HOST", "127.0.0.1")
    port = int(os.getenv("SEB_PORT", "8080"))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
