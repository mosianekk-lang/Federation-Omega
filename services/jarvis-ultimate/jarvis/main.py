from __future__ import annotations

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any

from .execution import ExecutionEvidenceError
from .graph import GraphInputError
from .math_engine import MathExpressionError
from .orchestrator import Jarvis
from .principles import catalogue, doctrine_summary

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
        provided = self.headers.get("authorization", "")
        return not expected or hmac.compare_digest(provided, f"Bearer {expected}")

    def _body(self) -> dict[str, Any]:
        content_type = self.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ExecutionEvidenceError("APPLICATION_JSON_REQUIRED")
        raw_length = int(self.headers.get("content-length", "0"))
        if raw_length < 0 or raw_length > MAX_BODY_BYTES:
            raise ExecutionEvidenceError("INVALID_CONTENT_LENGTH")
        value = json.loads(self.rfile.read(raw_length) or b"{}")
        if not isinstance(value, dict):
            raise ExecutionEvidenceError("JSON_OBJECT_REQUIRED")
        return value

    def do_GET(self) -> None:
        if self.path == "/health":
            return self._json(200, APP.health())
        if self.path == "/":
            data = files("jarvis.resources").joinpath("index.html").read_bytes()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return None
        if not self._authorized():
            return self._json(403, {"ok": False, "error": "FORBIDDEN"})
        if self.path == "/v1/capabilities":
            return self._json(200, APP.capabilities())
        if self.path == "/v1/principles":
            return self._json(200, {"summary": doctrine_summary(), "principles": catalogue()})
        if self.path == "/v1/execution-policy":
            return self._json(200, APP.execution_policy())
        return self._json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:
        if not self._authorized():
            return self._json(403, {"ok": False, "error": "FORBIDDEN"})
        try:
            body = self._body()
            if self.path == "/v1/chat":
                return self._json(200, APP.chat(str(body.get("message", ""))))
            if self.path == "/v1/plan":
                return self._json(
                    200,
                    APP.plan(
                        str(body.get("objective", "")),
                        body.get("deliverableForm"),
                        body.get("expectedStateDelta"),
                    ),
                )
            if self.path == "/v1/math":
                return self._json(200, APP.math(str(body.get("expression", ""))))
            if self.path == "/v1/authorize":
                mission_version = body.get("missionVersion", 0)
                if isinstance(mission_version, bool) or not isinstance(mission_version, int):
                    raise ExecutionEvidenceError("MISSION_VERSION_INTEGER_REQUIRED")
                arguments = body.get("arguments")
                if arguments is not None and not isinstance(arguments, dict):
                    raise ExecutionEvidenceError("ACTION_ARGUMENTS_OBJECT_REQUIRED")
                return self._json(
                    200,
                    APP.authorize(
                        str(body.get("missionId", "")),
                        mission_version,
                        str(body.get("actionId", "")),
                        str(body.get("capability", "")),
                        body.get("resource"),
                        arguments,
                        body.get("permit"),
                    ),
                )
            if self.path == "/v1/cycle-review":
                elapsed = body.get("elapsedSeconds")
                retries = body.get("retries", 0)
                evidence = body.get("qualityEvidence")
                routes = body.get("routeResults")
                next_pathway = body.get("nextBestAutomatedPathway", "")
                if isinstance(elapsed, bool) or not isinstance(elapsed, int):
                    raise ExecutionEvidenceError("ELAPSED_SECONDS_INTEGER_REQUIRED")
                if isinstance(retries, bool) or not isinstance(retries, int):
                    raise ExecutionEvidenceError("RETRIES_INTEGER_REQUIRED")
                if not isinstance(evidence, dict):
                    raise ExecutionEvidenceError("QUALITY_EVIDENCE_OBJECT_REQUIRED")
                if not isinstance(routes, list):
                    raise ExecutionEvidenceError("ROUTE_RESULTS_ARRAY_REQUIRED")
                return self._json(
                    200,
                    APP.review_cycle(
                        elapsed,
                        evidence,
                        routes,
                        str(next_pathway),
                        retries,
                    ),
                )
            return self._json(404, {"ok": False, "error": "NOT_FOUND"})
        except (ExecutionEvidenceError, GraphInputError, MathExpressionError, ValueError, json.JSONDecodeError) as exc:
            return self._json(400, {"ok": False, "error": str(exc) or type(exc).__name__})
        except Exception as exc:
            return self._json(400, {"ok": False, "error": type(exc).__name__})

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
