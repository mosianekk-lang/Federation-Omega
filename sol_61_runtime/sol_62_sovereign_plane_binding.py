from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "SOL62_FUSE_SOVEREIGN_PLANE_BINDING_V1"
VERSION = "1.0.0"
PLANE_ID = "FUSE_SOVEREIGN_PLANE_R59"

RouteOrderResolver = Callable[[Mapping[str, Any]], Sequence[str]]


@dataclass(frozen=True, slots=True)
class SovereignPlaneContract:
    plane_id: str = PLANE_ID
    startup_authority: str = "START:FUSE_ONE_FRESH_CANON"
    estate_resolution_service: str = "estate.resolve"
    strategic_service: str = "strategy.intelligence"
    route_portfolio_policy: str = "MISSION_ROUTE_PORTFOLIO_V2"
    more_policy: str = "MORE_V2"
    truth_root: str = "SOL_6_2"
    resident_executor: str = "FUSE_GENESIS_RESIDENT_EXECUTOR_V2"
    source_arbiter: str = "FDOF"
    state_integrity: str = "SICF"
    proof_plane: str = "PROOFOS_REALITY_JUDGE"
    authority_expansion: bool = False
    provider_effect_authorized: bool = False


class Sol62SovereignPlaneBinding:
    """Thin attachment from SOL 6.2 to the existing FUSE Sovereign Plane.

    SOL remains mission/effect truth. The binding may only order routes that SOL
    has already classified as current, callable, authorized and privacy-safe.
    It cannot mint a route, authority, provider effect, proof or completion.
    """

    def __init__(
        self,
        *,
        resolver: RouteOrderResolver | None = None,
        contract: SovereignPlaneContract | None = None,
    ) -> None:
        self.resolver = resolver
        self.contract = contract or SovereignPlaneContract()

    def status(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            **asdict(self.contract),
            "attachment_state": "BOUND",
            "route_resolver_state": "EXTERNAL_RESOLVER_BOUND" if self.resolver else "LOCAL_DETERMINISTIC_FALLBACK",
            "truth_boundary": "ORCHESTRATION_BINDING_NE_AUTHORITY_NE_EXECUTION_NE_COMPLETION",
        }

    def mission_envelope(
        self,
        *,
        mission_id: str,
        objective: str,
        owner_subject: str,
        session_id: str = "",
    ) -> dict[str, Any]:
        objective_sha256 = hashlib.sha256(objective.encode("utf-8")).hexdigest()
        return {
            "schema": "SOL62_SOVEREIGN_MISSION_ENVELOPE_V1",
            "plane_id": self.contract.plane_id,
            "startup_authority": self.contract.startup_authority,
            "mission_id": mission_id,
            "mission_identity_preserved": True,
            "objective_sha256": objective_sha256,
            "owner_subject": owner_subject,
            "session_id": session_id,
            "estate_resolution_service": self.contract.estate_resolution_service,
            "route_portfolio_policy": self.contract.route_portfolio_policy,
            "truth_root": self.contract.truth_root,
            "resident_executor": self.contract.resident_executor,
            "source_arbiter": self.contract.source_arbiter,
            "state_integrity": self.contract.state_integrity,
            "proof_plane": self.contract.proof_plane,
            "authority_expansion": False,
            "provider_effect_authorized": False,
        }

    @staticmethod
    def _fallback_order(routes: Sequence[Any]) -> list[Any]:
        return sorted(
            routes,
            key=lambda route: (
                -int(getattr(route, "priority", 50)),
                str(getattr(route, "cost_class", "UNKNOWN")),
                str(getattr(route, "route_id", "")),
            ),
        )

    def order_routes(
        self,
        routes: Sequence[Any],
        *,
        mission_id: str,
        transition_id: str,
        operation: str,
    ) -> tuple[list[Any], dict[str, Any]]:
        fallback = self._fallback_order(routes)
        eligible = {str(route.route_id): route for route in fallback}
        mode = "LOCAL_DETERMINISTIC_FALLBACK"
        requested: list[str] = []
        resolver_error_class = ""

        if self.resolver is not None and fallback:
            payload = {
                "schema": "FUSE_SOVEREIGN_ROUTE_ELECTION_INPUT_V1",
                "plane_id": self.contract.plane_id,
                "mission_id": mission_id,
                "transition_id": transition_id,
                "operation": operation,
                "hard_gates_preapplied": True,
                "authority_expansion_allowed": False,
                "routes": [
                    {
                        "route_id": route.route_id,
                        "provider": route.provider,
                        "capabilities": list(route.capabilities),
                        "operations": list(route.operations),
                        "priority": route.priority,
                        "cost_class": route.cost_class,
                        "failure_domain": route.failure_domain,
                    }
                    for route in fallback
                ],
            }
            try:
                requested = [str(value) for value in self.resolver(payload)]
                if len(requested) != len(set(requested)):
                    raise ValueError("SOVEREIGN_ROUTE_ORDER_DUPLICATE")
                unknown = [route_id for route_id in requested if route_id not in eligible]
                if unknown:
                    raise ValueError("SOVEREIGN_ROUTE_OUTSIDE_SOL_ELIGIBLE_SET")
                mode = "EXTERNAL_SOVEREIGN_RESOLVER"
            except Exception as exc:  # route-local resolver degradation; SOL stays live
                requested = []
                resolver_error_class = type(exc).__name__
                mode = "SOVEREIGN_RESOLVER_DEGRADED_LOCAL_FALLBACK"

        selected = [eligible[route_id] for route_id in requested]
        selected_ids = set(requested)
        selected.extend(route for route in fallback if route.route_id not in selected_ids)
        receipt = {
            "schema": "SOL62_SOVEREIGN_ROUTE_ELECTION_RECEIPT_V1",
            "plane_id": self.contract.plane_id,
            "mission_id": mission_id,
            "transition_id": transition_id,
            "operation": operation,
            "mode": mode,
            "eligible_route_ids": [route.route_id for route in fallback],
            "ordered_route_ids": [route.route_id for route in selected],
            "failure_domains": [route.failure_domain for route in selected],
            "resolver_error_class": resolver_error_class,
            "authority_expansion": False,
            "provider_effect_authorized": False,
            "truth_boundary": "ORDERED_ALREADY_ELIGIBLE_ROUTES_ONLY",
        }
        return selected, receipt
