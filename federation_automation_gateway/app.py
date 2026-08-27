from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import socket
import uuid

from flask import Flask, jsonify

from .contracts import RECEIPT_SCHEMA
from .google_executor import GoogleExecutor
from .policy import evaluate
from .sheets_bus import SheetsBus

app = Flask(__name__)

SHEET_ID = os.environ.get("FED_AUTOMATION_SHEET_ID", "")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", ""))
BOOTSTRAP_SA = os.environ.get("FED_BOOTSTRAP_SA", "")
EXECUTOR_ID = os.environ.get("K_REVISION", socket.gethostname())
LOGICAL_TZ = timezone(timedelta(hours=2))


def now_sast() -> str:
    return datetime.now(LOGICAL_TZ).isoformat(timespec="seconds")


def canonical_hash(value) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def get_bus() -> SheetsBus:
    if not SHEET_ID:
        raise RuntimeError("FED_AUTOMATION_SHEET_ID is not configured")
    return SheetsBus(SHEET_ID)


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "federation-automation-gateway",
            "schema": "FED-AUTOMATION-GATEWAY-V1",
            "project": PROJECT_ID,
            "sheet_bound": bool(SHEET_ID),
            "elevated_identity_bound": bool(BOOTSTRAP_SA),
            "executor": EXECUTOR_ID,
            "supported_adapters": sorted(GoogleExecutor.SUPPORTED_ADAPTERS),
            "apps_script_route": "OWNER_OAUTH_BROKER",
            "production_effect": False,
            "checked_at_sast": now_sast(),
        }
    )


def write_receipt(
    bus: SheetsBus,
    *,
    receipt_id: str,
    command,
    state: str,
    started: str,
    provider_status: str,
    semantic_readback: str,
    proof: dict,
    production_effect: bool,
    truth_boundary: str,
) -> None:
    bus.append_receipt(
        [
            receipt_id,
            command.command_id,
            state,
            EXECUTOR_ID,
            PROJECT_ID,
            command.target_alias,
            command.action,
            command.effect_class.value,
            started,
            now_sast(),
            provider_status,
            semantic_readback,
            "",
            "",
            "",
            json.dumps(proof, sort_keys=True),
            canonical_hash(proof),
            "",
            production_effect,
            truth_boundary,
        ]
    )


@app.post("/tick")
def tick():
    # Cloud Run IAM + Scheduler OIDC is the transport authorization boundary.
    # This worker intentionally leaves Apps Script rows QUEUED for the separate
    # owner-OAuth broker; a service-account worker must never steal those rows.
    bus = get_bus()
    executor = GoogleExecutor(project_id=PROJECT_ID, elevated_sa=BOOTSTRAP_SA)
    processed: list[dict[str, str]] = []
    completed_keys = bus.completed_idempotency_keys()

    for row_number, command in bus.queued(limit=50):
        if command.adapter_id not in executor.SUPPORTED_ADAPTERS:
            continue

        receipt_id = "RCP-" + uuid.uuid4().hex[:20]
        started = now_sast()

        if command.idempotency_key and command.idempotency_key in completed_keys:
            proof = {
                "schema": RECEIPT_SCHEMA,
                "command_sha256": command.digest(),
                "idempotency_key": command.idempotency_key,
                "classification": "DUPLICATE_ALREADY_COMPLETED",
            }
            write_receipt(
                bus,
                receipt_id=receipt_id,
                command=command,
                state="REJECTED",
                started=started,
                provider_status="NOT_EXECUTED",
                semantic_readback="IDEMPOTENCY_REPLAY_BLOCKED",
                proof=proof,
                production_effect=False,
                truth_boundary="Duplicate idempotency key was rejected before provider execution.",
            )
            bus.finish(
                row_number,
                state="REJECTED",
                completed_at_sast=now_sast(),
                receipt_id=receipt_id,
                error_code="IDEMPOTENCY_REPLAY",
            )
            processed.append({"command_id": command.command_id, "state": "REJECTED"})
            continue

        lease = bus.lease(command.lease_id)
        decision = evaluate(command, lease, now=datetime.now(LOGICAL_TZ))

        if decision.state != "ALLOW":
            proof = {
                "schema": RECEIPT_SCHEMA,
                "decision": decision.__dict__,
                "command_sha256": command.digest(),
            }
            write_receipt(
                bus,
                receipt_id=receipt_id,
                command=command,
                state="REJECTED",
                started=started,
                provider_status="NOT_EXECUTED",
                semantic_readback=decision.reason,
                proof=proof,
                production_effect=False,
                truth_boundary="Policy rejected the command before provider execution.",
            )
            bus.finish(
                row_number,
                state="REJECTED",
                completed_at_sast=now_sast(),
                receipt_id=receipt_id,
                error_code="POLICY_REJECTED",
            )
            processed.append({"command_id": command.command_id, "state": "REJECTED"})
            continue

        claim_until = (datetime.now(LOGICAL_TZ) + timedelta(minutes=5)).isoformat(
            timespec="seconds"
        )
        bus.claim(
            row_number,
            owner=EXECUTOR_ID,
            until_sast=claim_until,
            started_at_sast=started,
        )

        # Mission authority is consumed before the provider call. Failed/retried
        # provider work therefore cannot silently reuse the same command budget.
        if command.lease_id and decision.authority_mode == "MISSION_LEASE":
            bus.consume_lease_command(command.lease_id)

        try:
            result = executor.execute(command, elevated=decision.use_elevated_identity)
            proof = {
                "schema": RECEIPT_SCHEMA,
                "command_sha256": command.digest(),
                "idempotency_key": command.idempotency_key,
                "authority_mode": decision.authority_mode,
                "elevated_identity_used": decision.use_elevated_identity,
                "rollback_required": decision.rollback_required,
                "readback_required": decision.readback_required,
                "provider": result.proof,
            }
            write_receipt(
                bus,
                receipt_id=receipt_id,
                command=command,
                state=result.provider_status,
                started=started,
                provider_status=result.provider_status,
                semantic_readback=result.semantic_readback,
                proof=proof,
                production_effect=result.production_effect,
                truth_boundary=(
                    "Provider status is admitted only to the extent supported by nested semantic readback."
                ),
            )
            bus.finish(
                row_number,
                state=result.provider_status,
                completed_at_sast=now_sast(),
                receipt_id=receipt_id,
            )
            if command.idempotency_key and result.provider_status in {"DONE", "PARTIAL"}:
                completed_keys.add(command.idempotency_key)
            processed.append(
                {"command_id": command.command_id, "state": result.provider_status}
            )
        except Exception as exc:
            error = {
                "schema": RECEIPT_SCHEMA,
                "type": type(exc).__name__,
                "message": str(exc)[:1500],
                "command_sha256": command.digest(),
                "idempotency_key": command.idempotency_key,
            }
            write_receipt(
                bus,
                receipt_id=receipt_id,
                command=command,
                state="FAILED",
                started=started,
                provider_status="FAILED",
                semantic_readback="EXECUTION_EXCEPTION",
                proof=error,
                production_effect=False,
                truth_boundary="Provider execution failed; no success or mutation is inferred.",
            )
            bus.finish(
                row_number,
                state="FAILED",
                completed_at_sast=now_sast(),
                receipt_id=receipt_id,
                error_code=type(exc).__name__,
            )
            processed.append({"command_id": command.command_id, "state": "FAILED"})

    bus.append_heartbeat(
        [
            "HB-" + uuid.uuid4().hex[:16],
            now_sast(),
            "federation-automation-gateway",
            EXECUTOR_ID,
            EXECUTOR_ID,
            PROJECT_ID,
            len(processed),
            "",
            "",
            processed[-1]["command_id"] if processed else "",
            "HEALTHY",
            json.dumps({"processed": processed}, sort_keys=True),
        ]
    )
    return jsonify({"ok": True, "processed": processed, "checked_at_sast": now_sast()})
