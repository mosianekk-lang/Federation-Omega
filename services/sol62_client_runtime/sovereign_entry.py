from __future__ import annotations

from typing import Any

from services.sol62_client_runtime.app import app
from services.sol62_client_runtime.capability_registry import compile_registry


SERVICE_ID = "runtime.transactional"
CAPABILITY_ID = "CAP-SOL62-TRANSACTIONAL-RUNTIME-V1"
ECP_ID = "ECP-SOL62-SOVEREIGN-PLANE-START438-001"
SOL_ROLE = "transactional_execution_state_spine"
KERNEL_ROLE = "TRANSACTIONAL_MISSION_TRUTH_AND_VERIFIED_TRANSITION_KERNEL"


@app.get("/api/status")
async def sovereign_runtime_status() -> dict[str, Any]:
    """Redacted control-plane status for the existing SOL 6.2 runtime.

    This endpoint exposes contracts and readiness only. It cannot schedule,
    elect an unqualified route, mint authority, authorize provider effects,
    certify finality, or mutate runtime state.
    """
    ctx = app.state.sol62_context
    sovereign = ctx.sovereign_plane.status()
    registry = compile_registry(gateway_execution_ready=ctx.gateway.execution_ready)
    return {
        "ok": True,
        "schema": "SOL62_SOVEREIGN_ATTACHMENT_STATUS_V1",
        "service_id": SERVICE_ID,
        "capability_id": CAPABILITY_ID,
        "ecp_id": ECP_ID,
        "sol_role": SOL_ROLE,
        "kernel_role": KERNEL_ROLE,
        "source_frontier": ctx.source_frontier,
        "control_attachment": sovereign["attachment_state"],
        "orchestration_plane": sovereign["plane_id"],
        "startup_authority": sovereign["startup_authority"],
        "truth_root": sovereign["truth_root"],
        "resident_executor": sovereign["resident_executor"],
        "source_arbiter": sovereign["source_arbiter"],
        "state_integrity": sovereign["state_integrity"],
        "proof_plane": sovereign["proof_plane"],
        "route_resolver_state": sovereign["route_resolver_state"],
        "authority_expansion": False,
        "provider_effect_authorized": False,
        "scheduler_ownership": False,
        "independent_finality": False,
        "capability_registry": {
            "schema": registry["schema"],
            "counts": registry["counts"],
            "truth_boundary": registry["truth_boundary"],
        },
        "truth_boundary": (
            "CONTROL_ATTACHMENT_NE_SOURCE_ADMITTED_NE_DEPLOYED_RUNTIME_NE_PROVIDER_BOUND_NE_"
            "VERIFIED_REALITY_NE_DURABLE_WAKE_EXECUTED_NE_BEHAVIOUR_VERIFIED_NE_COMPLETE_VERIFIED"
        ),
    }
