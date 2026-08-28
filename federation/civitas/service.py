from __future__ import annotations

"""Loopback HTTP surface for the CIVITAS internal shadow runtime."""

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any, Mapping
from urllib.parse import urlparse

from .contracts import MaturityEvidence, MaturityStage, ProofLevel, ProofRef
from .suite import FederationCivitasSuite


class FederationCivitasService:
    def __init__(self, suite: FederationCivitasSuite | None = None) -> None:
        self.suite = suite or FederationCivitasSuite()

    def health(self) -> Mapping[str, Any]:
        return {
            "status": "PASS",
            "suite_id": self.suite.SUITE_ID,
            "mode": "INTERNAL_SHADOW",
            "service_count": len(self.suite.catalog.services),
            "product_count": len(self.suite.catalog.products),
            "provider_runtime_proven": False,
            "production_traffic": False,
            "external_effects": 0,
        }

    def catalog(self) -> Mapping[str, Any]:
        return self.suite.catalog.as_mapping()

    def manifest(self) -> Mapping[str, Any]:
        return self.suite.manifest()

    def query(self, question: str) -> Mapping[str, Any]:
        return self.suite.query(question)

    def shadow_deploy(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        observed_at = str(payload.get("observed_at", "2026-08-28T00:00:00+00:00"))
        proof = ProofRef(
            source_ref=str(payload.get("source_ref", "local-runtime")),
            proof_ref=str(payload.get("proof_ref", "local-runtime-readback")),
            observed_at=observed_at,
            level=ProofLevel(str(payload.get("proof_level", ProofLevel.RUNTIME_READBACK.value))),
            confidence=float(payload.get("confidence", 0.9)),
            ttl_seconds=int(payload.get("ttl_seconds", 3600)),
            independent_source=str(payload.get("independent_source", "LOCAL_RUNTIME")),
        )
        evidence = MaturityEvidence(
            service_id=self.suite.SUITE_ID,
            claimed_stage=MaturityStage(str(payload.get("claimed_stage", MaturityStage.RUNTIME_READBACK.value))),
            proof_refs=(proof,),
            tests_passed=bool(payload.get("tests_passed", True)),
            shadow_passed=bool(payload.get("shadow_passed", True)),
            runtime_readback=bool(payload.get("runtime_readback", True)),
            provider_readback=bool(payload.get("provider_readback", False)),
            rollback_passed=bool(payload.get("rollback_passed", False)),
            resilience_passed=bool(payload.get("resilience_passed", False)),
            independent_assurance=bool(payload.get("independent_assurance", True)),
            sustained_soak=bool(payload.get("sustained_soak", False)),
        )
        return asdict(self.suite.shadow_deploy(evidence))


class _Handler(BaseHTTPRequestHandler):
    service = FederationCivitasService()

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> Mapping[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid Content-Length")
        if length < 0 or length > 1_000_000:
            raise ValueError("request body outside bounded size")
        if length == 0:
            return {}
        decoded = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("JSON object required")
        return decoded

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        routes = {
            "/health": self.service.health,
            "/catalog": self.service.catalog,
            "/manifest": self.service.manifest,
        }
        handler = routes.get(path)
        if handler is None:
            self._json(404, {"error": "NOT_FOUND", "external_effects": 0})
            return
        try:
            self._json(200, handler())
        except Exception as exc:  # pragma: no cover - HTTP boundary
            self._json(500, {"error": type(exc).__name__, "message": str(exc), "external_effects": 0})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._body()
            if path == "/query":
                result = self.service.query(str(payload.get("question", "")))
            elif path == "/shadow-deploy":
                result = self.service.shadow_deploy(payload)
            else:
                self._json(404, {"error": "NOT_FOUND", "external_effects": 0})
                return
            self._json(200, result)
        except Exception as exc:  # pragma: no cover - HTTP boundary
            self._json(400, {"error": type(exc).__name__, "message": str(exc), "external_effects": 0})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def serve(*, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("default CIVITAS service is loopback-only")
    if not 1 <= int(port) <= 65535:
        raise ValueError("invalid port")
    server = ThreadingHTTPServer((host, int(port)), _Handler)
    server.serve_forever()
    return server


__all__ = ["FederationCivitasService", "serve"]
