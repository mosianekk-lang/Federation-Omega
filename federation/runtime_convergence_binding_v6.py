from __future__ import annotations

"""FUSE Runtime Convergence Binding v6.

V6 preserves V1-V5 and promotes provider execution only when one exact V5
route/fence activation is followed by provider dispatch and provider-native
semantic readback through the existing FDOF provider bridge.

V6 does not prove whole-mission terminal closure or F130 COMPLETE_VERIFIED.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from evidenceops.innovation_engine.foundry_model import FoundryCycleResult
from federation.aarek_v1 import MissionSnapshot
from federation.alpha_omega_lifecycle_binding_v1 import AlphaOmegaLocalBuildReceipt
from federation.fdof_capability_activation_binding_v1 import (
    FDOFCapabilityActivationReceipt,
)
from federation.fdof_provider_execution_binding_v1 import (
    FDOFProviderExecutionBinder,
    FDOFProviderExecutionReceipt,
)
from federation.oh50_producer_adapter_v1 import OH50ProducerReceipt
from federation.of50_ace_v1 import OF50CycleRequest
from federation.runtime_convergence_binding_v5 import (
    RuntimeConvergenceBinderV5,
    RuntimeConvergenceResultV5,
)

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V6"
VERSION = "6.0.0"
CAPABILITY_ID = "FUSE-FRCB-006"


class StageStateV6(str, Enum):
    PRODUCER_INVOCATION_VERIFIED = "PRODUCER_INVOCATION_VERIFIED"
    FOUNDRY_CYCLE_RECEIPT_VERIFIED = "FOUNDRY_CYCLE_RECEIPT_VERIFIED"
    LOCAL_BUILD_RECEIPT_VERIFIED = "LOCAL_BUILD_RECEIPT_VERIFIED"
    CAPABILITY_ROUTE_FENCE_VERIFIED = "CAPABILITY_ROUTE_FENCE_VERIFIED"
    PROVIDER_EXECUTION_READBACK_VERIFIED = "PROVIDER_EXECUTION_READBACK_VERIFIED"
    STRUCTURALLY_BOUND = "STRUCTURALLY_BOUND"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class StageBindingV6:
    stage: str
    state: StageStateV6
    producer: str
    mission_id: str
    artifact_ref: str
    artifact_digest: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceiptV6:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    stages: tuple[StageBindingV6, ...]
    v5_receipt_digest: str
    fdof_activation_receipt_digest: str
    provider_execution_receipt_digest: str
    provider_execution_id: str
    provider: str
    provider_target: str
    provider_semantic_state: str
    provider_correlation_id: str
    provider_verified_at_epoch: int
    of50_receipt_digest: str
    of50_completion_verified: bool
    provider_execution_verified: bool
    provider_semantic_readback_verified: bool
    f130_terminal_completion_verified: bool
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    @property
    def completion_verified(self) -> bool:
        return self.f130_terminal_completion_verified

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "capability_id": self.capability_id,
            "mission_id": self.mission_id,
            "objective": self.objective,
            "authority_ceiling": self.authority_ceiling,
            "stages": [asdict(item) for item in self.stages],
            "v5_receipt_digest": self.v5_receipt_digest,
            "fdof_activation_receipt_digest": self.fdof_activation_receipt_digest,
            "provider_execution_receipt_digest": self.provider_execution_receipt_digest,
            "provider_execution_id": self.provider_execution_id,
            "provider": self.provider,
            "provider_target": self.provider_target,
            "provider_semantic_state": self.provider_semantic_state,
            "provider_correlation_id": self.provider_correlation_id,
            "provider_verified_at_epoch": self.provider_verified_at_epoch,
            "of50_receipt_digest": self.of50_receipt_digest,
            "of50_completion_verified": self.of50_completion_verified,
            "provider_execution_verified": self.provider_execution_verified,
            "provider_semantic_readback_verified": self.provider_semantic_readback_verified,
            "f130_terminal_completion_verified": self.f130_terminal_completion_verified,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.capability_id == CAPABILITY_ID
            and self.mission_id.strip()
            and self.v5_receipt_digest.startswith("sha256:")
            and self.fdof_activation_receipt_digest.startswith("sha256:")
            and self.provider_execution_receipt_digest.startswith("sha256:")
            and self.provider_execution_id.strip()
            and self.provider.strip()
            and self.provider_target.strip()
            and self.provider_semantic_state.strip()
            and self.provider_correlation_id.strip()
            and self.provider_verified_at_epoch >= 0
            and self.provider_execution_verified is True
            and self.provider_semantic_readback_verified is True
            and self.f130_terminal_completion_verified is False
            and boundary.get("provider_dispatch_verified") is True
            and boundary.get("provider_execution_verified") is True
            and boundary.get("provider_native_readback_verified") is True
            and boundary.get("provider_semantic_readback_verified") is True
            and boundary.get("expected_semantic_state_verified") is True
            and boundary.get("fdof_event_chain_verified") is True
            and boundary.get("provider_authority_created") is False
            and boundary.get("f130_terminal_completion_verified") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceResultV6:
    v5_result: RuntimeConvergenceResultV5
    provider_execution_receipt: FDOFProviderExecutionReceipt
    convergence_receipt: RuntimeConvergenceReceiptV6


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class RuntimeConvergenceBinderV6:
    """Bind provider-native execution/readback into the V5 convergence chain."""

    def __init__(
        self,
        *,
        v5: RuntimeConvergenceBinderV5 | None = None,
        provider_binder: FDOFProviderExecutionBinder | None = None,
    ) -> None:
        self.v5 = v5 or RuntimeConvergenceBinderV5()
        self.provider_binder = provider_binder or FDOFProviderExecutionBinder()

    def evaluate(
        self,
        *,
        aarek_snapshot: MissionSnapshot,
        of50_request: OF50CycleRequest,
        oh50_producer_receipt: OH50ProducerReceipt,
        foundry_result: FoundryCycleResult,
        fdof_activation_receipt: FDOFCapabilityActivationReceipt,
        provider_execution_receipt: FDOFProviderExecutionReceipt,
        now_epoch: int,
        alpha_omega_build_receipt: AlphaOmegaLocalBuildReceipt | None = None,
    ) -> RuntimeConvergenceResultV6:
        provider = self.provider_binder.bind(
            mission_id=of50_request.mission_id,
            activation=fdof_activation_receipt,
            receipt=provider_execution_receipt,
        )
        if int(now_epoch) < provider.verified_at_epoch:
            raise ValueError("FDOF_PROVIDER_EXECUTION_VERIFICATION_FROM_FUTURE")

        v5_result = self.v5.evaluate(
            aarek_snapshot=aarek_snapshot,
            of50_request=of50_request,
            oh50_producer_receipt=oh50_producer_receipt,
            foundry_result=foundry_result,
            fdof_activation_receipt=fdof_activation_receipt,
            now_epoch=provider.verified_at_epoch,
            alpha_omega_build_receipt=alpha_omega_build_receipt,
        )

        if (
            provider.activation_receipt_digest
            != v5_result.fdof_activation_receipt.receipt_digest
        ):
            raise ValueError("FRCB_V6_PROVIDER_ACTIVATION_CHAIN_MISMATCH")

        stages: list[StageBindingV6] = []
        for stage in v5_result.convergence_receipt.stages:
            if stage.state.value == "NOT_REQUIRED":
                mapped = StageStateV6.NOT_REQUIRED
            elif stage.state.value == "CAPABILITY_ROUTE_FENCE_VERIFIED":
                mapped = StageStateV6.CAPABILITY_ROUTE_FENCE_VERIFIED
            elif stage.state.value == "LOCAL_BUILD_RECEIPT_VERIFIED":
                mapped = StageStateV6.LOCAL_BUILD_RECEIPT_VERIFIED
            elif stage.state.value == "FOUNDRY_CYCLE_RECEIPT_VERIFIED":
                mapped = StageStateV6.FOUNDRY_CYCLE_RECEIPT_VERIFIED
            elif stage.state.value == "PRODUCER_INVOCATION_VERIFIED":
                mapped = StageStateV6.PRODUCER_INVOCATION_VERIFIED
            else:
                mapped = StageStateV6.STRUCTURALLY_BOUND
            stages.append(StageBindingV6(
                stage=stage.stage,
                state=mapped,
                producer=stage.producer,
                mission_id=stage.mission_id,
                artifact_ref=stage.artifact_ref,
                artifact_digest=stage.artifact_digest,
                limitations=stage.limitations,
            ))

        stages.append(StageBindingV6(
            stage="PROVIDER_EXECUTION_READBACK",
            state=StageStateV6.PROVIDER_EXECUTION_READBACK_VERIFIED,
            producer=provider.producer_id,
            mission_id=provider.mission_id,
            artifact_ref=provider.receipt_digest,
            artifact_digest=provider.request_sha256,
            limitations=(
                "One exact FDOF execution request was accepted and provider-native semantic readback matched the expected state.",
                "This proves the bound provider operation, not whole-mission terminal completion.",
                "F130 remains the only terminal commit authority.",
            ),
        ))

        base_of50 = v5_result.v4_result.v3_result.v2_result.v1_result.of50_receipt
        truth_boundary = MappingProxyType({
            **dict(v5_result.convergence_receipt.truth_boundary),
            "provider_dispatch_verified": True,
            "provider_execution_verified": True,
            "provider_native_readback_verified": True,
            "provider_semantic_readback_verified": True,
            "expected_semantic_state_verified": True,
            "fdof_event_chain_verified": True,
            "provider_authority_created": False,
            "f130_terminal_completion_verified": False,
            "authority_widened": False,
        })
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "capability_id": CAPABILITY_ID,
            "mission_id": of50_request.mission_id,
            "objective": of50_request.objective,
            "authority_ceiling": of50_request.authority_ceiling,
            "stages": [asdict(item) for item in stages],
            "v5_receipt_digest": v5_result.convergence_receipt.receipt_digest,
            "fdof_activation_receipt_digest": fdof_activation_receipt.receipt_digest,
            "provider_execution_receipt_digest": provider.receipt_digest,
            "provider_execution_id": provider.execution_id,
            "provider": provider.provider,
            "provider_target": provider.target,
            "provider_semantic_state": provider.semantic_state,
            "provider_correlation_id": provider.provider_correlation_id,
            "provider_verified_at_epoch": provider.verified_at_epoch,
            "of50_receipt_digest": base_of50.receipt_digest,
            "of50_completion_verified": bool(base_of50.completion_verified),
            "provider_execution_verified": True,
            "provider_semantic_readback_verified": True,
            "f130_terminal_completion_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = RuntimeConvergenceReceiptV6(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=of50_request.mission_id,
            objective=of50_request.objective,
            authority_ceiling=of50_request.authority_ceiling,
            stages=tuple(stages),
            v5_receipt_digest=v5_result.convergence_receipt.receipt_digest,
            fdof_activation_receipt_digest=fdof_activation_receipt.receipt_digest,
            provider_execution_receipt_digest=provider.receipt_digest,
            provider_execution_id=provider.execution_id,
            provider=provider.provider,
            provider_target=provider.target,
            provider_semantic_state=provider.semantic_state,
            provider_correlation_id=provider.provider_correlation_id,
            provider_verified_at_epoch=provider.verified_at_epoch,
            of50_receipt_digest=base_of50.receipt_digest,
            of50_completion_verified=bool(base_of50.completion_verified),
            provider_execution_verified=True,
            provider_semantic_readback_verified=True,
            f130_terminal_completion_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FRCB_V6_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResultV6(
            v5_result=v5_result,
            provider_execution_receipt=provider,
            convergence_receipt=receipt,
        )


__all__ = [
    "CAPABILITY_ID",
    "RuntimeConvergenceBinderV6",
    "RuntimeConvergenceReceiptV6",
    "RuntimeConvergenceResultV6",
    "SCHEMA",
    "StageBindingV6",
    "StageStateV6",
    "VERSION",
]
