"""OF50 adapter for the canonical EvidenceOps Formation Innovation Engine.

Consumes an already-executed foundry cycle and competing route hypotheses. This
module is an adapter only; it never creates another foundry or widens A1 authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from federation.of50_ace_v1 import Authority, FormationDecision, ReuseBuildDecision, RouteCandidate


def _as_mapping(foundry_result: Any) -> Mapping[str, Any]:
    if hasattr(foundry_result, "as_dict"):
        return foundry_result.as_dict()
    if isinstance(foundry_result, Mapping):
        return foundry_result
    raise TypeError("foundry_result must be FoundryCycleResult-like or a mapping")


def compile_of50_formation_decision(
    *,
    mission_id: str,
    foundry_result: Any,
    route_candidates: Sequence[Mapping[str, Any]],
    selected_route_id: str,
    reuse_vs_build: str,
    selected_capability_hypothesis: str,
    implementation_required: bool,
) -> FormationDecision:
    body = _as_mapping(foundry_result)
    if body.get("external_effect") not in (False, None):
        raise ValueError("Formation Innovation result must remain no-effect")
    authority = str(body.get("authority_ceiling") or Authority.A1_INTERNAL.value)
    if authority != Authority.A1_INTERNAL.value:
        raise ValueError("Formation Innovation adapter requires A1_INTERNAL ceiling")
    cycle_ref = str(body.get("cycle_id") or body.get("receipt_sha256") or "").strip()
    if not cycle_ref:
        raise ValueError("foundry cycle reference is required")
    routes = tuple(
        RouteCandidate(
            route_id=str(item["route_id"]),
            route_family=str(item["route_family"]),
            score=float(item.get("score", 0.0)),
            falsifier=str(item.get("falsifier", "")),
            capability_hypothesis=str(item.get("capability_hypothesis", "")),
        )
        for item in route_candidates
    )
    decision = FormationDecision(
        mission_id=mission_id,
        foundry_cycle_ref=cycle_ref,
        route_candidates=routes,
        selected_route_id=selected_route_id,
        reuse_vs_build=ReuseBuildDecision(reuse_vs_build),
        selected_capability_hypothesis=selected_capability_hypothesis,
        implementation_required=implementation_required,
        authority_ceiling=authority,
        external_effect=False,
    )
    errors = decision.validate()
    if errors:
        raise ValueError(";".join(errors))
    return decision


__all__ = ["compile_of50_formation_decision"]
