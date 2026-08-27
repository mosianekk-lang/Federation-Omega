"""Minimal provider-neutral Frontier Convergence control service.

The service has no provider credentials and performs no external provider
effects. It is suitable behind SOVARA/Cloud Run IAM/IAP or another authenticated
ingress. Consequential actions remain outside this process.
"""
from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .core import (
    ActionMode,
    AIControlTower,
    EffectContract,
    FrontierConvergenceEngine,
    FrontierSignal,
    ScenarioBranch,
    SQLiteConvergenceStore,
    utc_now,
)

VERSION = "1.0.0"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


class App:
    def __init__(self, db_path: str) -> None:
        self.store = SQLiteConvergenceStore(db_path)
        self.engine = FrontierConvergenceEngine(self.store)
        self.tower = AIControlTower(self.store)

    def health(self) -> dict[str, Any]:
        return {
            "service": "SUPERIOR_LOGIC_GEMINI_FRONTIER_CONVERGENCE",
            "version": VERSION,
            "state": "READY_INTERNAL_CONTROL_RUNTIME",
            "provider_effects": False,
            "event_chain_valid": self.store.verify_event_chain(),
            "observed_at": utc_now(),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "FrontierConvergence/1.0"
    app: App

    def _reply(self, code: int, value: Any) -> None:
        payload = _json_bytes(value)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("INVALID_CONTENT_LENGTH")
        if length < 1 or length > 1_000_000:
            raise ValueError("BODY_SIZE_INVALID")
        raw = self.rfile.read(length)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("JSON_OBJECT_REQUIRED")
        return value

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._reply(200, self.app.health())
            return
        if path == "/v1/status":
            self._reply(200, self.app.health())
            return
        if path == "/v1/control-tower/assets":
            self._reply(200, {"assets": self.app.tower.inventory()})
            return
        if path == "/":
            ui = Path(__file__).with_name("web").joinpath("index.html")
            payload = ui.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)
            return
        self._reply(404, {"error": "NOT_FOUND"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/v1/frontier/signals":
                signal = FrontierSignal.create(
                    source_organization=str(body["source_organization"]),
                    capability_class=str(body["capability_class"]),
                    mechanism=str(body["mechanism"]),
                    evidence_refs=body.get("evidence_refs", ()),
                    observed_at=body.get("observed_at"),
                    source_freshness_days=int(body.get("source_freshness_days", 0)),
                )
                receipt = self.app.engine.observe(signal)
                self._reply(201, {"signal": asdict(signal), "receipt": receipt})
                return
            if path == "/v1/effects/compile":
                contract = EffectContract.create(
                    mission_id=str(body["mission_id"]),
                    target=str(body["target"]),
                    action=str(body["action"]),
                    parameters=dict(body.get("parameters", {})),
                    mode=ActionMode(str(body.get("mode", "READ"))),
                    authority_class=str(body["authority_class"]),
                    expected_semantic_result=str(body["expected_semantic_result"]),
                    readback_plan=body.get("readback_plan", ()),
                    rollback_plan=body.get("rollback_plan", ()),
                    privacy_envelope_id=body.get("privacy_envelope_id"),
                )
                self._reply(201, {"effect_contract": asdict(contract), "executed": False})
                return
            if path == "/v1/scenarios/materialize":
                scenario = ScenarioBranch.create(
                    mission_id=str(body["mission_id"]),
                    base_state=dict(body.get("base_state", {})),
                    delta=dict(body.get("delta", {})),
                )
                self._reply(201, {
                    "scenario": asdict(scenario),
                    "materialized": scenario.materialized(),
                    "diff": scenario.diff(),
                    "canonical_mutation": False,
                })
                return
            self._reply(404, {"error": "NOT_FOUND"})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._reply(400, {"error": type(exc).__name__, "detail": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def run() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    db_path = os.getenv("FC_DB_PATH", "/tmp/frontier-convergence.db")
    Handler.app = App(db_path)
    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    run()
