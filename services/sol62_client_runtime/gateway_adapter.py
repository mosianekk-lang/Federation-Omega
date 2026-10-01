from __future__ import annotations

from federation.mobile_gateway.fuse_mobile_v1 import EffectClass, MobileRequest, Mode
from services.fuse_mobile_gateway.runtime import (
    GatewayRuntime,
    RuntimeBindingError,
    VerifiedIdentity,
)
from sol_61_runtime.sol_62_complete_client_runtime import (
    ExecutionRequest,
    ExecutionResponse,
)


_CLEAR_PRE_DISPATCH = frozenset(
    {
        "FEDERATION_EXECUTOR_UNBOUND",
        "OWNER_EFFECT_APPROVAL_REQUIRED",
        "RUNTIME_CONFIGURATION_INCOMPLETE",
        "IDENTITY_VERIFIER_UNBOUND",
        "SESSION_SIGNER_UNBOUND",
        "CAPABILITY_UNAVAILABLE",
        "MODEL_UNAVAILABLE",
        "TOOL_UNAVAILABLE",
    }
)


class GatewayChatAdapter:
    """Execute SOL client read-only/internal work through the existing FUSE gateway."""

    def __init__(self, gateway: GatewayRuntime, identity: VerifiedIdentity) -> None:
        self.gateway = gateway
        self.identity = identity

    async def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        selected_route_id = str(request.route.route_id or "").strip()
        bound_route_id = self.gateway.execution_route_id
        bound_provider = self.gateway.execution_provider
        if not bound_route_id:
            return ExecutionResponse(
                False,
                dispatch_started=False,
                constraint_code="FEDERATION_EXECUTOR_UNBOUND",
                message="FUSE gateway has no bound execution route.",
                proof_issuer="FUSE_GATEWAY",
            )
        if selected_route_id not in {"", "FUSE-AUTO", bound_route_id}:
            return ExecutionResponse(
                False,
                dispatch_started=False,
                constraint_code="EXECUTOR_ROUTE_MISMATCH",
                message=(
                    f"SOL selected route {selected_route_id!r}, but the gateway is bound "
                    f"to {bound_route_id!r}."
                ),
                proof_issuer="FUSE_GATEWAY",
            )

        try:
            mode = Mode(request.binding.mode)
        except ValueError:
            mode = Mode.AUTO
        try:
            effect = EffectClass(request.binding.effect_class)
        except ValueError:
            effect = EffectClass.READ_ONLY

        intent = str(request.binding.payload.get("intent") or request.objective).strip()
        mobile = MobileRequest(
            intent=intent,
            mode=mode,
            requested_sources=tuple(request.binding.requested_sources),
            requested_models=tuple(request.binding.requested_models),
            requested_agents=tuple(request.binding.requested_agents),
            effect_class=effect,
            verification="HIGH",
        )
        try:
            result = await self.gateway.execute(self.identity, mobile)
        except RuntimeBindingError as error:
            return ExecutionResponse(
                False,
                dispatch_started=error.code not in _CLEAR_PRE_DISPATCH,
                constraint_code=error.code,
                message=str(error),
                proof_issuer="FUSE_GATEWAY",
            )

        if (
            selected_route_id not in {"", "FUSE-AUTO"}
            and bound_provider
            and result.provider
            and str(result.provider) != bound_provider
        ):
            return ExecutionResponse(
                False,
                dispatch_started=True,
                provider_ref=result.trace_id,
                readback={"status": result.status, "provider": result.provider},
                constraint_code="EXECUTOR_PROVIDER_READBACK_MISMATCH",
                message=(
                    f"Gateway executor declared provider {bound_provider!r}, "
                    f"but provider readback returned {result.provider!r}."
                ),
                proof_issuer="FUSE_GATEWAY",
            )

        evidence = {
            "status": result.status,
            "trace_id": result.trace_id,
            "provider": result.provider,
            "model": result.model,
            "source_refs": list(result.source_refs),
            "selected_route_id": selected_route_id or "FUSE-AUTO",
            "bound_executor_route_id": bound_route_id,
            "bound_executor_provider": bound_provider,
            "route_fidelity_verified": True,
            "text_sha256_source": "GATEWAY_RESULT_TEXT",
        }
        return ExecutionResponse(
            True,
            dispatch_started=True,
            provider_ref=result.trace_id,
            readback={"status": result.status},
            proof_evidence=evidence,
            evidence_class="GATEWAY_READBACK",
            proof_issuer="FUSE_GATEWAY",
            scope="FUSE_GATEWAY",
        )
