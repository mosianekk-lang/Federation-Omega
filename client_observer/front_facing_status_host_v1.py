from __future__ import annotations

"""Local FUSE host for front-facing status telemetry.

Binds only to loopback. Browser/client observers can POST sanitized status
snapshots; the host normalizes them through FrontFacingStatusObserver → CFRE →
AAA → Hypercube.

This host does not inspect the browser by itself and does not create provider
authority. It is an ingestion point for telemetry supplied by an installed,
authorized FUSE-owned client observer.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
from typing import Any

from .front_facing_status_observer_v1 import (
    FrontFacingStatusObserver,
    snapshot_from_mapping,
)


HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class ObserverRegistry:
    def __init__(self, *, stall_seconds: float = 60.0) -> None:
        self.stall_seconds = float(stall_seconds)
        self._observers: dict[str, FrontFacingStatusObserver] = {}

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot = snapshot_from_mapping(payload)
        observer = self._observers.setdefault(
            snapshot.source_id,
            FrontFacingStatusObserver(stall_seconds=self.stall_seconds),
        )
        decision = observer.ingest(snapshot)
        recovery = decision.recovery
        return {
            "schema": "FUSE-FRONT-FACING-STATUS-HOST-RESPONSE-V1",
            "state": decision.state,
            "snapshot_digest": decision.snapshot_digest,
            "no_progress_seconds": decision.no_progress_seconds,
            "owner_visible_progress_required": decision.owner_visible_progress_required,
            "auto_continue_intent": decision.auto_continue_intent,
            "recovery": recovery,
            "truth_boundary": (
                "This result proves only that a bound client supplied front-facing "
                "telemetry to the local FUSE observer. It does not prove native "
                "ChatGPT UI control or hidden platform access."
            ),
        }


def _handler(registry: ObserverRegistry):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FUSEFrontStatus/1.0"

        def _send_json(self, status: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            origin = self.headers.get("Origin", "")
            if origin.startswith(("chrome-extension://", "edge-extension://", "moz-extension://")):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self) -> None:  # noqa: N802
            origin = self.headers.get("Origin", "")
            self.send_response(204)
            if origin.startswith(("chrome-extension://", "edge-extension://", "moz-extension://")):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "content-type")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
                self.send_header("Vary", "Origin")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self._send_json(
                    200,
                    {
                        "schema": "FUSE-FRONT-FACING-STATUS-HOST-HEALTH-V1",
                        "state": "READY",
                        "loopback_only": True,
                    },
                )
                return
            self._send_json(404, {"error": "NOT_FOUND"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/front-facing-status":
                self._send_json(404, {"error": "NOT_FOUND"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 64 * 1024:
                    raise ValueError("INVALID_CONTENT_LENGTH")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON_OBJECT_REQUIRED")
                result = registry.ingest(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, result)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def serve(*, port: int = DEFAULT_PORT, stall_seconds: float = 60.0) -> None:
    registry = ObserverRegistry(stall_seconds=stall_seconds)
    server = ThreadingHTTPServer((HOST, int(port)), _handler(registry))
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--stall-seconds", type=float, default=60.0)
    args = parser.parse_args(argv)
    serve(port=args.port, stall_seconds=args.stall_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
