"""OF50 adapter for the canonical Alpha→Omega Turnkey Build Engine."""
from __future__ import annotations

from dataclasses import dataclass

from federation.of50_ace_v1 import ALPHA_OMEGA_LIFECYCLE, AlphaOmegaPacket, FormationDecision
from .engine import AlphaOmegaEngine
from .models import BuildPlan


@dataclass(frozen=True)
class OF50AlphaOmegaResult:
    plan: BuildPlan
    packet: AlphaOmegaPacket


def compile_of50_alpha_omega_packet(
    engine: AlphaOmegaEngine,
    *,
    mission_id: str,
    objective: str,
    formation_decision: FormationDecision,
    constraints: list[str] | None = None,
    preferred_surfaces: list[str] | None = None,
    rollback_ref: str,
    runtime_target: str,
    terminal_criteria: tuple[str, ...],
) -> OF50AlphaOmegaResult | None:
    if not formation_decision.implementation_required:
        return None
    errors = formation_decision.validate()
    if errors:
        raise ValueError("invalid Formation decision: " + ";".join(errors))
    plan = engine.build_plan({
        "title": f"OF50 {mission_id}",
        "description": objective,
        "outcomes": list(terminal_criteria),
        "constraints": list(constraints or []),
        "preferred_surfaces": list(preferred_surfaces or []),
    })
    # Alpha→Omega build_plan is planning only; source/planning must never become
    # provider-runtime proof without independent provider readback.
    plan.truth_boundary["of50_mission_id"] = mission_id
    plan.truth_boundary["formation_cycle_ref"] = formation_decision.foundry_cycle_ref
    plan.truth_boundary["provider_readback"] = False
    packet = AlphaOmegaPacket(
        mission_id=mission_id,
        packet_ref=f"OF50-AO-{plan.architecture['system_name']}",
        build_plan_ref=plan.architecture["system_name"],
        lifecycle=ALPHA_OMEGA_LIFECYCLE,
        proof_gates=("TEST", "ROLLBACK", "SEMANTIC_READBACK"),
        rollback_ref=rollback_ref,
        runtime_target=runtime_target,
        terminal_criteria=terminal_criteria,
        authority_ceiling=formation_decision.authority_ceiling,
        truth_boundary=dict(plan.truth_boundary),
    )
    packet_errors = packet.validate()
    if packet_errors:
        raise ValueError("invalid Alpha→Omega packet: " + ";".join(packet_errors))
    return OF50AlphaOmegaResult(plan=plan, packet=packet)


__all__ = ["OF50AlphaOmegaResult", "compile_of50_alpha_omega_packet"]
