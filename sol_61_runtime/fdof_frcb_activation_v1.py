from __future__ import annotations

"""FDOF route/fence activation adapter for FRCB v5.

This adapter composes the existing FederationDistributedOperatingFabric and
SOL 6.2 transition fence. It does not dispatch a provider action and it does
not create provider authority.
"""

from dataclasses import asdict

from federation.fdof_capability_activation_binding_v1 import (
    FDOFCapabilityActivationReceipt,
    build_fdof_activation_receipt,
)

try:
    from .fdof_v1 import FederationDistributedOperatingFabric, RouteRequest
    from .sol_62_frontier_primitives import digest
except ImportError:  # direct-module compatibility used by existing SOL tests/tools
    from fdof_v1 import FederationDistributedOperatingFabric, RouteRequest
    from sol_62_frontier_primitives import digest


def activate_for_frcb(
    fdof: FederationDistributedOperatingFabric,
    request: RouteRequest,
    *,
    now_epoch: int,
    lease_ttl_seconds: int = 120,
) -> FDOFCapabilityActivationReceipt:
    """Select one fresh verified route and acquire its live transition fence."""

    request_body = asdict(request)
    route = fdof.route(request, now_epoch=now_epoch)
    expected_request_sha = digest(request_body)
    if route.get("request_sha256") != expected_request_sha:
        raise ValueError("FDOF_FRCB_ROUTE_REQUEST_DIGEST_MISMATCH")

    executor_row = fdof.control.get_state("fdof.executor", str(route["executor_id"]))
    health_row = fdof.control.get_state("fdof.executor_health", str(route["executor_id"]))
    if executor_row is None:
        raise ValueError("FDOF_FRCB_EXECUTOR_STATE_MISSING")
    if health_row is None:
        raise ValueError("FDOF_FRCB_HEALTH_STATE_MISSING")

    health_state = fdof.health_state(str(route["executor_id"]), now_epoch=now_epoch)
    if health_state.get("state") != "HEALTHY":
        raise ValueError("FDOF_FRCB_EXECUTOR_NOT_HEALTHY")

    lease = fdof.acquire_transition_lease(
        request.transition_id,
        str(route["executor_id"]),
        ttl_seconds=lease_ttl_seconds,
        now_epoch=now_epoch,
    )
    status = fdof.status(now_epoch=now_epoch)

    return build_fdof_activation_receipt(
        request=request_body,
        route_decision=route,
        executor=executor_row["value"],
        health_observation=health_row["value"],
        lease=lease,
        fdof_status=status,
        issued_at_epoch=now_epoch,
    )


__all__ = ["activate_for_frcb"]
