from __future__ import annotations

"""Execute and verify one provider operation through the existing FDOF bridge.

This adapter is deliberately thin. V5 has already selected the executor and
acquired the transition fence. V6 consumes that exact activation, dispatches
once through FederationProviderBridge, performs provider-native semantic
readback, and emits an FRCB-bound provider execution receipt.

No new provider runtime, authority plane, scheduler, credential store, or effect
mechanism is introduced.
"""

from dataclasses import asdict

from federation.fdof_capability_activation_binding_v1 import (
    FDOFCapabilityActivationReceipt,
)
from federation.fdof_provider_execution_binding_v1 import (
    FDOFProviderExecutionReceipt,
    build_fdof_provider_execution_receipt,
)

try:
    from .fdof_provider_bridge_v1 import (
        DispatchReceipt,
        FederationProviderBridge,
        ProviderExecutionRequest,
    )
    from .sol_62_frontier_primitives import digest
except ImportError:
    from fdof_provider_bridge_v1 import (
        DispatchReceipt,
        FederationProviderBridge,
        ProviderExecutionRequest,
    )
    from sol_62_frontier_primitives import digest


def execute_and_verify_for_frcb(
    bridge: FederationProviderBridge,
    activation: FDOFCapabilityActivationReceipt,
    request: ProviderExecutionRequest,
    *,
    now_epoch: int,
) -> FDOFProviderExecutionReceipt:
    """Run the exact V5 route/fence into provider-native semantic readback."""

    if not activation.verify(now_epoch=int(now_epoch)):
        raise ValueError("FDOF_PROVIDER_EXECUTION_ACTIVATION_INVALID_OR_STALE")

    expected = {
        "mission_id": activation.mission_id,
        "route_id": activation.route_id,
        "transition_id": activation.transition_id,
        "executor_id": activation.executor_id,
        "provider": activation.executor_provider,
        "operation": activation.operation,
        "target": activation.target,
    }
    for field, value in expected.items():
        if getattr(request, field) != value:
            raise ValueError(
                f"FDOF_PROVIDER_REQUEST_{field.upper()}_MISMATCH:"
                f"{getattr(request, field)}!={value}"
            )
    if not request.execution_id.strip():
        raise ValueError("FDOF_PROVIDER_EXECUTION_ID_REQUIRED")
    if not request.idempotency_key.strip():
        raise ValueError("FDOF_PROVIDER_IDEMPOTENCY_KEY_REQUIRED")

    dispatched = bridge.execute(
        request,
        lease_epoch=activation.lease_epoch,
        fencing_token=activation.fencing_token,
        now_epoch=int(now_epoch),
    )
    if dispatched.get("state") == "DISPATCH_REJECTED":
        raise ValueError("FDOF_PROVIDER_DISPATCH_REJECTED")

    if dispatched.get("state") == "VERIFIED":
        status = bridge.fdof.status(now_epoch=int(now_epoch))
        return build_fdof_provider_execution_receipt(
            activation=activation,
            execution_state=dispatched,
            fdof_status=status,
            verified_at_epoch=int(dispatched.get("updated_at_epoch") or now_epoch),
        )

    if dispatched.get("dispatch_accepted") is not True:
        raise ValueError("FDOF_PROVIDER_DISPATCH_NOT_ACCEPTED")
    provider_request_id = str(dispatched.get("provider_request_id") or "").strip()
    if not provider_request_id:
        raise ValueError("FDOF_PROVIDER_REQUEST_ID_REQUIRED")

    durable_request_sha = str(dispatched.get("request_sha256") or "")
    expected_request_sha = digest(asdict(request))
    if durable_request_sha != expected_request_sha:
        raise ValueError("FDOF_PROVIDER_REQUEST_DIGEST_MISMATCH")

    dispatch_receipt = DispatchReceipt(
        execution_id=request.execution_id,
        provider=request.provider,
        provider_request_id=provider_request_id,
        accepted=True,
        effect_uncertain=dispatched.get("state") == "EFFECT_UNKNOWN",
        summary=dict(dispatched.get("dispatch_summary") or {}),
    )
    verified = bridge.verify(
        request,
        dispatch_receipt=dispatch_receipt,
        now_epoch=int(now_epoch),
    )
    if verified.get("state") != "VERIFIED":
        raise ValueError("FDOF_PROVIDER_SEMANTIC_READBACK_NOT_VERIFIED")

    status = bridge.fdof.status(now_epoch=int(now_epoch))
    return build_fdof_provider_execution_receipt(
        activation=activation,
        execution_state=verified,
        fdof_status=status,
        verified_at_epoch=int(now_epoch),
    )


__all__ = ["execute_and_verify_for_frcb"]
