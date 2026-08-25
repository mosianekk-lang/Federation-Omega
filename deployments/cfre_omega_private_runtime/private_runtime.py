#!/usr/bin/env python3
"""Private Cloud Run execution surface for the hash-pinned CFRE-OMEGA repair."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from evidenceops.build_system.runtime_controls import (
    CancellationToken,
    DeliveryJournal,
    DistinctRouteCircuit,
    HandoffStore,
    HeartbeatScheduler,
    Route,
    RuntimePolicy,
    SYSTEM_IDENTITY,
)


EXPECTED_REPAIR_SHA256 = "58c1e456f02642bcccdf13c8029a07dc4f497f6418c274afc6d8185365f7407b"
EXPECTED_MANIFEST_SHA256 = "c581e04c3a5f15e59451e1fc6201ad1b07032418f632994001bf2d449f6b93e7"
ARCHIVE = Path("/opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-20260825.tar.gz")
MANIFEST = Path("/opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-RESPAWN-MANIFEST-20260825.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integrity() -> dict[str, object]:
    archive_sha = sha256_file(ARCHIVE)
    manifest_sha = sha256_file(MANIFEST)
    return {
        "ok": archive_sha == EXPECTED_REPAIR_SHA256 and manifest_sha == EXPECTED_MANIFEST_SHA256,
        "archiveSha256": archive_sha,
        "manifestSha256": manifest_sha,
    }


def canary(transaction_id: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cfre-private-") as folder:
        root = Path(folder)
        beats = []
        scheduler = HeartbeatScheduler(0.01, lambda event: beats.append(event.sequence))
        scheduler.start()
        time.sleep(0.035)
        heartbeat_ok = scheduler.stop() and len(beats) >= 1

        cancellation = CancellationToken(root / "state.sqlite", transaction_id)
        cancellation.cancel("private canary")
        cancellation_ok = cancellation.state()["cancelled"] is True

        circuit = DistinctRouteCircuit(root / "state.sqlite", [Route("primary", 10), Route("alternate", 5)])
        circuit.open("primary", "synthetic-private-canary")
        route_ok = circuit.select_distinct("primary").route_id == "alternate"

        handoff = HandoffStore(root / "handoff.json")
        payload = {"identity": SYSTEM_IDENTITY, "transaction_id": transaction_id}
        handoff.write(transaction_id, payload)
        handoff_ok = handoff.read(transaction_id) == payload

        journal = DeliveryJournal(root / "delivery.sqlite")
        artifact_sha = hashlib.sha256(b"CFRE-OMEGA").hexdigest()
        journal.deliver(transaction_id, "canary", artifact_sha, acknowledgement="private-runtime-readback")
        delivery_ok = journal.readback(transaction_id)["state"] == "ACKNOWLEDGED"

        policy = RuntimePolicy(providers_enabled=False)
        try:
            policy.admit("PROVIDER_CANARY")
            negative_ok = False
        except Exception:
            negative_ok = True

        checks = {
            "heartbeat": heartbeat_ok,
            "cancellation": cancellation_ok,
            "distinctRoute": route_ok,
            "handoff": handoff_ok,
            "delivery": delivery_ok,
            "providerDisabled": negative_ok,
        }
        return {"ok": all(checks.values()), "status": "CFRE_PRIVATE_CANARY_PASS" if all(checks.values()) else "CFRE_PRIVATE_CANARY_FAIL", "identity": SYSTEM_IDENTITY, "transactionId": transaction_id, "checks": checks}


class Handler(BaseHTTPRequestHandler):
    server_version = "CFRE-OMEGA/private-runtime1"

    def send_json(self, code: int, body: dict[str, object]) -> None:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            proof = integrity()
            self.send_json(200 if proof["ok"] else 500, {**proof, "status": "CFRE_PRIVATE_RUNTIME_READY" if proof["ok"] else "CFRE_INTEGRITY_FAILURE", "identity": SYSTEM_IDENTITY})
            return
        if self.path == "/contract":
            self.send_json(200, {"ok": True, "identity": SYSTEM_IDENTITY, "providersEnabled": False, "actions": ["RUN_CONTINUITY_CANARY"]})
            return
        self.send_json(404, {"ok": False, "status": "NOT_FOUND"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/canary":
            self.send_json(404, {"ok": False, "status": "NOT_FOUND"})
            return
        transaction_id = self.headers.get("x-cfre-transaction-id", "").strip()
        if not transaction_id or len(transaction_id) > 180:
            self.send_json(400, {"ok": False, "status": "TRANSACTION_ID_REQUIRED"})
            return
        try:
            result = canary(transaction_id)
            self.send_json(200 if result["ok"] else 500, result)
        except Exception as exc:  # fail closed without traceback leakage
            self.send_json(500, {"ok": False, "status": "CFRE_PRIVATE_CANARY_ERROR", "errorType": type(exc).__name__})

    def log_message(self, format: str, *args: object) -> None:
        print(json.dumps({"event": "http", "message": format % args}, sort_keys=True), flush=True)


if __name__ == "__main__":
    proof = integrity()
    if not proof["ok"]:
        raise SystemExit("CFRE artifact integrity check failed")
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
