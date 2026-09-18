from __future__ import annotations

"""FUSE Runtime Convergence Binding v5.

V5 preserves V1-V4 and binds one fresh FDOF route-selection plus SOL 6.2
transition fence as capability-activation evidence.

This proves that a qualifying execution route was callable and fenced at the
recorded evaluation epoch. It does not prove provider dispatch, provider
execution, provider semantic readback, or F130 terminal completion.
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
    FDOFCapabilityActivationBinder,
    FDOFCapabilityActivationReceipt,
)
from federation.oh50_producer_adapter_v1 import OH50ProducerReceipt
from federation.of50_ace_v1 import OF50CycleRequest
from federation.runtime_convergence_binding_v4 import (
    RuntimeConvergenceBinderV4,
    RuntimeConvergenceResultV4,
)

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V5"
VERSION = "5.0.0"
CAPABILITY_ID = "FUSE-FRCB-005"


class StageStateV5(str, Enum):
    PRODUCER_INVOCATION_VERIFIED = "PRODUCER_INVOCATION_VERIFIED"
    FOUNDRY_CYCLE_RECEIPT_VERIFIED = "FOUNDRY_CYCLE_RECEIPT_VERIFIED"
    LOCAL_BUILD_RECEIPT_VERIFIED = "LOCAL_BUILD_RECEIPT_VERIFIED"
    CAPABILITY_ROUTE_FENCE_VERIFIED = "CAPABILITY_ROUTE_FENCE_VERIFIED"
    STRUCTURALLY_BOUND = "STRUCTURALLY_BOUND"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class StageBindingV5:
    stage: str
    state: StageStateV5
    producer: str
    mission_id: str
    artifact_ref: str
    artifact_digest: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceiptV5:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    stages: tuple[StageBindingV5, ...]
    v4_receipt_digest: str
    fdof_activation_receipt_digest: str
    fdof_executor_id: str
    fdof_provider: str
    fdof_target: str
    fdof_transition_id: str
    fdof_fencing_token: int
    activation_verified_at_epoch: int
    activation_lease_expires_at_epoch: int
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
            "v4_receipt_digest": self.v4_receipt_digest,
            "fdof_activation_receipt_digest": self.fdof_activation_receipt_digest,
            "fdof_executor_id": self.fdof_executor_id,
            "fdof_provider": self.fdof_provider,
            "fdof_target": self.fdof_target,
            "fdof_transition_id": self.fdof_transition_id,
            "fdof_fencing_token": self.fdof_fencing_token,
            "activation_verified_at_epoch": self.activation_verified_at_epoch,
            "activation_lease_expires_at_epoch": self.activation_lease_expires_at_epoch,
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
            and self.fdof_activation_receipt_digest.startswith("sha256:")
            and self.fdof_executor_id.strip()
            and self.fdof_provider.strip()
            and self.fdof_target.strip()
            and self.fdof_transition_id.strip()
            and self.fdof_fencing_token >= 1
            and self.activation_verified_at_epoch
                < self.activation_lease_expires_at_epoch
            and boundary.get("fdof_capability_route_verified") is True
            and boundary.get("fdof_transition_fence_verified") is True
            and boundary.get("activation_is_historical_not_perpetual") is True
            and boundary.get("provider_dispatch_verified") is False
            and boundary.get("provider_execution_verified") is False
            and boundary.get("provider_semantic_readback_verified") is False
            and boundary.get("provider_authority_created") is False
            and boundary.get("f130_terminal_completion_verified") is False
            and self.provider_execution_verified is False
            and self.provider_semantic_readback_verified is False
            and self.f130_terminal_completion_verified is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceResultV5:
    v4_result: RuntimeConvergenceResultV4
    fdof_activation_receipt: FDOFCapabilityActivationReceipt
    convergence_receipt: RuntimeConvergenceReceiptV5


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


class RuntimeConvergenceBinderV5:
    """Bind fresh FDOF route/fence evidence into the V4 convergence chain."""

    def __init__(
        self,
        *,
        v4: RuntimeConvergenceBinderV4 | None = None,
        fdof_binder: FDOFCapabilityActivationBinder | None = None,
    ) -> None:
        self.v4 = v4 or RuntimeConvergenceBinderV4()
        self.fdof_binder = fdof_binder or FDOFCapabilityActivationBinder()

    def evaluate(
        self,
        *,
        aarek_snapshot: MissionSnapshot,
        of50_request: OF50CycleRequest,
        oh50_producer_receipt: OH50ProducerReceipt,
        foundry_result: FoundryCycleResult,
        fdof_activation_receipt: FDOFCapabilityActivationReceipt,
        now_epoch: int,
        alpha_omega_build_receipt: AlphaOmegaLocalBuildReceipt | None = None,
    ) -> RuntimeConvergenceResultV5:
        packet = of50_request.alpha_omega_packet
        expected_target = packet.runtime_target if packet is not None else ""
        activation = self.fdof_binder.bind(
            mission_id=of50_request.mission_id,
            receipt=fdof_activation_receipt,
            now_epoch=int(now_epoch),
            expected_target=expected_target,
        )

        v4_result = self.v4.evaluate(
            aarek_snapshot=aarek_snapshot,
            of50_request=of50_request,
            oh50_producer_receipt=oh50_producer_receipt,
            foundry_result=foundry_result,
            alpha_omega_build_receipt=alpha_omega_build_receipt,
        )

        stages: list[StageBindingV5] = []
        for stage in v4_result.convergence_receipt.stages:
            if stage.state.value == "NOT_REQUIRED":
                mapped = StageStateV5.NOT_REQUIRED
            elif stage.state.value == "LOCAL_BUILD_RECEIPT_VERIFIED":
                mapped = StageStateV5.LOCAL_BUILD_RECEIPT_VERIFIED
            elif stage.state.value == "FOUNDRY_CYCLE_RECEIPT_VERIFIED":
                mapped = StageStateV5.FOUNDRY_CYCLE_RECEIPT_VERIFIED
            elif stage.state.value == "PRODUCER_INVOCATION_VERIFIED":
                mapped = StageStateV5.PRODUCER_INVOCATION_VERIFIED
            else:
                mapped = StageStateV5.STRUCTURALLY_BOUND
            stages.append(StageBindingV5(
                stage=stage.stage,
                state=mapped,
                producer=stage.producer,
                mission_id=stage.mission_id,
                artifact_ref=stage.artifact_ref,
                artifact_digest=stage.artifact_digest,
                limitations=stage.limitations,
            ))

        stages.append(StageBindingV5(
            stage="CAPABILITY_ACTIVATION",
            state=StageStateV5.CAPABILITY_ROUTE_FENCE_VERIFIED,
            producer=activation.producer_id,
            mission_id=activation.mission_id,
            artifact_ref=activation.receipt_digest,
            artifact_digest=activation.request_sha256,
            limitations=(
                "Fresh FDOF route selection and SOL 6.2 transition fence were verified at the recorded epoch.",
                "The lease is time-bounded and must be revalidated before later execution.",
                "Provider dispatch, provider effect and semantic readback are not proven by capability activation.",
            ),
        ))

        base_of50 = v4_result.v3_result.v2_result.v1_result.of50_receipt
        truth_boundary = MappingProxyType({
            **dict(v4_result.convergence_receipt.truth_boundary),
            "fdof_capability_route_verified": True,
            "fdof_transition_fence_verified": True,
            "activation_is_historical_not_perpetual": True,
            "provider_dispatch_verified": False,
            "provider_execution_verified": False,
            "provider_semantic_readback_verified": False,
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
            "v4_receipt_digest": v4_result.convergence_receipt.receipt_digest,
            "fdof_activation_receipt_digest": activation.receipt_digest,
            "fdof_executor_id": activation.executor_id,
            "fdof_provider": activation.executor_provider,
            "fdof_target": activation.target,
            "fdof_transition_id": activation.transition_id,
            "fdof_fencing_token": activation.fencing_token,
            "activation_verified_at_epoch": int(now_epoch),
            "activation_lease_expires_at_epoch": activation.lease_expires_at_epoch,
            "of50_receipt_digest": base_of50.receipt_digest,
            "of50_completion_verified": bool(base_of50.completion_verified),
            "provider_execution_verified": False,
            "provider_semantic_readback_verified": False,
            "f130_terminal_completion_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = RuntimeConvergenceReceiptV5(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=of50_request.mission_id,
            objective=of50_request.objective,
            authority_ceiling=of50_request.authority_ceiling,
            stages=tuple(stages),
            v4_receipt_digest=v4_result.convergence_receipt.receipt_digest,
            fdof_activation_receipt_digest=activation.receipt_digest,
            fdof_executor_id=activation.executor_id,
            fdof_provider=activation.executor_provider,
            fdof_target=activation.target,
            fdof_transition_id=activation.transition_id,
            fdof_fencing_token=activation.fencing_token,
            activation_verified_at_epoch=int(now_epoch),
            activation_lease_expires_at_epoch=activation.lease_expires_at_epoch,
            of50_receipt_digest=base_of50.receipt_digest,
            of50_completion_verified=bool(base_of50.completion_verified),
            provider_execution_verified=False,
            provider_semantic_readback_verified=False,
            f130_terminal_completion_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FRCB_V5_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResultV5(
            v4_result=v4_result,
            fdof_activation_receipt=activation,
            convergence_receipt=receipt,
        )


__all__ = [
    "CAPABILITY_ID",
    "RuntimeConvergenceBinderV5",
    "RuntimeConvergenceReceiptV5",
    "RuntimeConvergenceResultV5",
    "SCHEMA",
    "StageBindingV5",
    "StageStateV5",
    "VERSION",
]
