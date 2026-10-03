"""FRCB lifecycle adapter for the existing Alpha→Omega Turnkey Engine."""
from __future__ import annotations

from federation.alpha_omega_lifecycle_binding_v1 import (
    AlphaOmegaLocalBuildReceipt,
    build_local_receipt,
)

from .engine import AlphaOmegaEngine
from .of50_adapter import OF50AlphaOmegaResult


def execute_local_build_for_frcb(
    engine: AlphaOmegaEngine,
    result: OF50AlphaOmegaResult,
) -> AlphaOmegaLocalBuildReceipt:
    """Execute the existing local BUILD stage and bind artifact readback.

    This does not execute TEST, provider DEPLOY, provider VERIFY, OPERATE or
    semantic readback. Those stages remain explicitly unverified.
    """
    plan = result.plan
    packet = result.packet
    system_name = str(plan.architecture.get("system_name") or "")
    if not system_name or system_name != packet.build_plan_ref:
        raise ValueError("ALPHA_OMEGA_PLAN_PACKET_IDENTITY_MISMATCH")

    raw = engine.execute_local_build(plan)
    build_dir = str(raw.get("build_dir") or "")
    state = str(raw.get("state") or "")
    boundary = raw.get("truth_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_TRUTH_BOUNDARY_REQUIRED")

    return build_local_receipt(
        packet=packet,
        build_dir=build_dir,
        local_build_state=state,
        truth_boundary=boundary,
    )


__all__ = ["execute_local_build_for_frcb"]
