from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

from evidenceops.capability_heartbeat.foundation.contracts import digest
from evidenceops.heartbeat_api.runtime import HeartbeatApiRuntime, build_runtime_from_env
from evidenceops.heartbeat_api.schemas import IngestRequest


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runtime() -> HeartbeatApiRuntime:
    return build_runtime_from_env(
        {
            "HEARTBEAT_MODE": "development",
            "HEARTBEAT_INTERNAL_AUTH_VALUE": "T" * 32,
            "HEARTBEAT_ROOT_NODE_ID": "NODE-ROOT",
            "HEARTBEAT_ACCEPT_NODE_ID": "NODE-EVIDENCEOPS",
            "HEARTBEAT_OWNER_CODE": "OWNER-A1B2C3D4",
            "HEARTBEAT_MATTER_CODE": "MATTER-B1C2D3E4",
            "HEARTBEAT_ROOT_SIGNER_B64": base64.b64encode(b"R" * 32).decode("ascii"),
            "HEARTBEAT_ACCEPT_SIGNER_B64": base64.b64encode(b"A" * 32).decode("ascii"),
        }
    )


def ingest_request(*, idempotency_code: str = "ONE", sequence: int = 1) -> IngestRequest:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return IngestRequest(
        idempotency_hash=digest({"idempotency": idempotency_code}),
        trace_id=digest({"trace": idempotency_code}),
        root_transaction_id=digest({"transaction": idempotency_code}),
        mission_code="MISSION-C1D2E3F4",
        emitter_node_id="NODE-ROOT",
        authority_ceiling="A0",
        state="NEEDS_CAPABILITY",
        observed_at=timestamp(now),
        expires_at=timestamp(now + timedelta(minutes=5)),
        sequence=sequence,
        observations=(
            {
                "source_code": "LOCAL_REPO",
                "node_id": "NODE-ROOT",
                "capability_code": "CAP-INDEX",
                "status": "AVAILABLE",
                "confidence_bp": 9000,
                "freshness_seconds": 1,
                "evidence_count": 3,
                "blocker_code": "NONE",
                "capability_hash": digest({"capability": "INDEX"}),
                "observed_at": timestamp(now),
                "semantic_receipt": digest({"receipt": "INDEX"}),
            },
        ),
    )
