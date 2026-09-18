from __future__ import annotations

"""Private Cloud Run HTTP carrier for the admitted FUSE Work Plane GCS runtime.

Cloud Run IAM remains the ingress authority. This module exposes only typed Work Plane
state-machine operations and never exposes shell, arbitrary Python, source mutation,
IAM mutation, secret reads, billing or traffic controls.
"""

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from typing import Any

from respawn.work_plane_gcs_runtime import DurableBundleRuntime

SCHEMA = "FUSE-WORK-PLANE-CLOUD-SERVICE-V1"
VERSION = "1.0.0"
MAX_BODY_BYTES = 65536
ALLOWED_ACTIONS = frozenset({
    "PUBLISH", "CLAIM", "HEARTBEAT", "RUNNING", "CHECKPOINT",
    "EFFECT_UNKNOWN", "RESULT_READY", "RECOVER_ORPHAN",
    "CONFIRM_EFFECT_READBACK", "IMPORT_EXTERNAL_RESULT", "PROJECTION",
})


def contract() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": SCHEMA,
        "version": VERSION,
        "actions": sorted(ALLOWED_ACTIONS),
        "private_cloud_run_iam_required": True,
        "arbitrary_shell": False,
        "inline_python": False,
        "source_mutation": False,
        "iam_mutation": False,
        "secret_payload_read": False,
        "public_ingress_authorized": False,
        "traffic_promotion_authorized": False,
        "truth_root": False,
        "backend": "GCS_SINGLE_OBJECT_GENERATION_CAS",
    }


def execute_payload(body: dict[str, Any], runtime: DurableBundleRuntime | None = None) -> dict[str, Any]:
    action = str(body.get("action") or "").upper()
    if action not in ALLOWED_ACTIONS:
        raise ValueError("ACTION_NOT_ALLOWED")
    mission_id = str(body.get("mission_id") or "").strip()
    if not mission_id:
        raise ValueError("MISSION_ID_REQUIRED")
    runtime = runtime or DurableBundleRuntime.from_environment()
    receipt = runtime.execute(
        operation=action,
        mission_id=mission_id,
        actor=str(body.get("actor") or "FUSE_WORK_PLANE"),
        fence=None if body.get("fence") is None else int(body["fence"]),
        payload=body.get("payload"),
        effect_id=None if body.get("effect_id") is None else str(body["effect_id"]),
        readback=None if body.get("readback") is None else str(body["readback"]),
        proof_ref=None if body.get("proof_ref") is None else str(body["proof_ref"]),
        verifier=None if body.get("verifier") is None else str(body["verifier"]),
        ttl_seconds=int(body.get("ttl_seconds", 120)),
    )
    return {
        "ok": True,
        "schema": SCHEMA,
        "adapter_version": receipt.adapter_version,
        "operation": receipt.operation,
        "mission_id": receipt.mission_id,
        "prior_generation": receipt.prior_generation,
        "committed_generation": receipt.committed_generation,
        "bundle_sha256": receipt.bundle_sha256,
        "result": receipt.result,
        "provider_effect_authorized": receipt.provider_effect_authorized,
        "receipt_sha256": receipt.receipt_sha256,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "FUSEWorkPlaneCloud/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        size = int(self.headers.get("content-length", "0") or 0)
        if size < 0 or size > MAX_BODY_BYTES:
            raise ValueError("BODY_TOO_LARGE")
        body = json.loads(self.rfile.read(size) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("BODY_OBJECT_REQUIRED")
        return body

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path == "/health":
            return self._json(200, {"ok": True, "schema": SCHEMA, "version": VERSION, "backend": "GCS_SINGLE_OBJECT_GENERATION_CAS"})
        if self.path == "/contract":
            return self._json(200, contract())
        return self._json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.path != "/v1/execute":
            return self._json(404, {"ok": False, "error": "NOT_FOUND"})
        try:
            return self._json(200, execute_payload(self._body()))
        except KeyError as exc:
            return self._json(404, {"ok": False, "error": str(exc)})
        except (RuntimeError, ValueError) as exc:
            return self._json(409, {"ok": False, "error": str(exc)})
        except Exception as exc:  # fail closed; never echo provider/secret detail
            return self._json(500, {"ok": False, "error": type(exc).__name__})

    def log_message(self, _fmt: str, *_args: Any) -> None:
        return None


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
