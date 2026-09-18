from __future__ import annotations

"""FUSE Runtime Convergence Binding v4.

V4 preserves V1-V3 and promotes Alpha→Omega only to a verified local BUILD
stage when the existing AlphaOmegaEngine has actually emitted its local package
and the current artifacts read back to the content hashes in the receipt.

V4 does not promote TEST, provider DEPLOY, provider VERIFY, OPERATE, provider
semantic readback, or F130 terminal completion.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from evidenceops.innovation_engine.foundry_model import FoundryCycleResult
from federation.aarek_v1 import MissionSnapshot
from federation.alpha_omega_lifecycle_binding_v1 import (
    AlphaOmegaLocalBuildBinder,
    AlphaOmegaLocalBuildReceipt,
)
from federation.oh50_producer_adapter_v1 import OH50ProducerReceipt
from federation.of50_ace_v1 import OF50CycleRequest
from federation.runtime_convergence_binding_v3 import (
    RuntimeConvergenceBinderV3,
    RuntimeConvergenceResultV3,
)

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V4"
VERSION = "4.0.0"
CAPABILITY_ID = "FUSE-FRCB-004"


class StageStateV4(str, Enum):
    PRODUCER_INVOCATION_VERIFIED = "PRODUCER_INVOCATION_VERIFIED"
    FOUNDRY_CYCLE_RECEIPT_VERIFIED = "FOUNDRY_CYCLE_RECEIPT_VERIFIED"
    LOCAL_BUILD_RECEIPT_VERIFIED = "LOCAL_BUILD_RECEIPT_VERIFIED"
    STRUCTURALLY_BOUND = "STRUCTURALLY_BOUND"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class StageBindingV4:
    stage: str
    state: StageStateV4
    producer: str
    mission_id: str
    artifact_ref: str
    artifact_digest: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceiptV4:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    stages: tuple[StageBindingV4, ...]
    v3_receipt_digest: str
    alpha_omega_local_build_verified: bool
    alpha_omega_build_receipt_digest: str
    alpha_omega_packet_digest: str
    of50_receipt_digest: str
    of50_completion_verified: bool
    f130_terminal_completion_verified: bool
    provider_execution_verified: bool
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
            "v3_receipt_digest": self.v3_receipt_digest,
            "alpha_omega_local_build_verified": self.alpha_omega_local_build_verified,
            "alpha_omega_build_receipt_digest": self.alpha_omega_build_receipt_digest,
            "alpha_omega_packet_digest": self.alpha_omega_packet_digest,
            "of50_receipt_digest": self.of50_receipt_digest,
            "of50_completion_verified": self.of50_completion_verified,
            "f130_terminal_completion_verified": self.f130_terminal_completion_verified,
            "provider_execution_verified": self.provider_execution_verified,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        build_fields_valid = (
            bool(self.alpha_omega_build_receipt_digest and self.alpha_omega_packet_digest)
            if self.alpha_omega_local_build_verified
            else not self.alpha_omega_build_receipt_digest and not self.alpha_omega_packet_digest
        )
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.capability_id == CAPABILITY_ID
            and build_fields_valid
            and boundary.get("alpha_omega_local_build_verified")
                is self.alpha_omega_local_build_verified
            and boundary.get("alpha_omega_test_stage_verified") is False
            and boundary.get("alpha_omega_provider_deployment_verified") is False
            and boundary.get("provider_execution_verified") is False
            and boundary.get("provider_semantic_readback_verified") is False
            and boundary.get("f130_terminal_completion_verified") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceResultV4:
    v3_result: RuntimeConvergenceResultV3
    alpha_omega_build_receipt: AlphaOmegaLocalBuildReceipt | None
    convergence_receipt: RuntimeConvergenceReceiptV4


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


class RuntimeConvergenceBinderV4:
    """Bind current Alpha→Omega local BUILD artifacts into the V3 chain."""

    def __init__(
        self,
        *,
        v3: RuntimeConvergenceBinderV3 | None = None,
        alpha_binder: AlphaOmegaLocalBuildBinder | None = None,
    ) -> None:
        self.v3 = v3 or RuntimeConvergenceBinderV3()
        self.alpha_binder = alpha_binder or AlphaOmegaLocalBuildBinder()

    def evaluate(
        self,
        *,
        aarek_snapshot: MissionSnapshot,
        of50_request: OF50CycleRequest,
        oh50_producer_receipt: OH50ProducerReceipt,
        foundry_result: FoundryCycleResult,
        alpha_omega_build_receipt: AlphaOmegaLocalBuildReceipt | None = None,
    ) -> RuntimeConvergenceResultV4:
        formation = of50_request.formation_decision
        if formation is None:
            raise ValueError("FORMATION_DECISION_REQUIRED")

        packet = of50_request.alpha_omega_packet
        build_verified = False
        verified_build: AlphaOmegaLocalBuildReceipt | None = None
        if formation.implementation_required:
            if packet is None:
                raise ValueError("ALPHA_OMEGA_PACKET_REQUIRED")
            if alpha_omega_build_receipt is None:
                raise ValueError("ALPHA_OMEGA_LOCAL_BUILD_RECEIPT_REQUIRED")
            verified_build = self.alpha_binder.bind(
                mission_id=of50_request.mission_id,
                packet=packet,
                receipt=alpha_omega_build_receipt,
            )
            build_verified = True
        elif alpha_omega_build_receipt is not None:
            raise ValueError("ALPHA_OMEGA_BUILD_RECEIPT_PRESENT_WHEN_NOT_REQUIRED")

        v3_result = self.v3.evaluate(
            aarek_snapshot=aarek_snapshot,
            of50_request=of50_request,
            oh50_producer_receipt=oh50_producer_receipt,
            foundry_result=foundry_result,
        )

        stages: list[StageBindingV4] = []
        for stage in v3_result.convergence_receipt.stages:
            if stage.stage == "ALPHA_OMEGA_IF_REQUIRED" and build_verified:
                assert verified_build is not None
                stages.append(StageBindingV4(
                    stage=stage.stage,
                    state=StageStateV4.LOCAL_BUILD_RECEIPT_VERIFIED,
                    producer=verified_build.producer_id,
                    mission_id=stage.mission_id,
                    artifact_ref=verified_build.receipt_digest,
                    artifact_digest=verified_build.packet_digest,
                    limitations=(
                        "Current local BUILD artifacts and packet binding are verified.",
                        "TEST, provider DEPLOY, provider VERIFY, OPERATE and semantic readback remain unverified.",
                    ),
                ))
                continue

            if stage.state.value == "NOT_REQUIRED":
                mapped = StageStateV4.NOT_REQUIRED
            elif stage.state.value == "FOUNDRY_CYCLE_RECEIPT_VERIFIED":
                mapped = StageStateV4.FOUNDRY_CYCLE_RECEIPT_VERIFIED
            elif stage.state.value == "PRODUCER_INVOCATION_VERIFIED":
                mapped = StageStateV4.PRODUCER_INVOCATION_VERIFIED
            else:
                mapped = StageStateV4.STRUCTURALLY_BOUND
            stages.append(StageBindingV4(
                stage=stage.stage,
                state=mapped,
                producer=stage.producer,
                mission_id=stage.mission_id,
                artifact_ref=stage.artifact_ref,
                artifact_digest=stage.artifact_digest,
                limitations=stage.limitations,
            ))

        build_receipt_digest = verified_build.receipt_digest if verified_build else ""
        build_packet_digest = verified_build.packet_digest if verified_build else ""
        truth_boundary = MappingProxyType({
            **dict(v3_result.convergence_receipt.truth_boundary),
            "alpha_omega_local_build_verified": build_verified,
            "alpha_omega_test_stage_verified": False,
            "alpha_omega_provider_deployment_verified": False,
            "provider_execution_verified": False,
            "provider_semantic_readback_verified": False,
            "operational_runtime_verified": False,
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
            "v3_receipt_digest": v3_result.convergence_receipt.receipt_digest,
            "alpha_omega_local_build_verified": build_verified,
            "alpha_omega_build_receipt_digest": build_receipt_digest,
            "alpha_omega_packet_digest": build_packet_digest,
            "of50_receipt_digest": v3_result.v2_result.v1_result.of50_receipt.receipt_digest,
            "of50_completion_verified": bool(
                v3_result.v2_result.v1_result.of50_receipt.completion_verified
            ),
            "f130_terminal_completion_verified": False,
            "provider_execution_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = RuntimeConvergenceReceiptV4(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=of50_request.mission_id,
            objective=of50_request.objective,
            authority_ceiling=of50_request.authority_ceiling,
            stages=tuple(stages),
            v3_receipt_digest=v3_result.convergence_receipt.receipt_digest,
            alpha_omega_local_build_verified=build_verified,
            alpha_omega_build_receipt_digest=build_receipt_digest,
            alpha_omega_packet_digest=build_packet_digest,
            of50_receipt_digest=v3_result.v2_result.v1_result.of50_receipt.receipt_digest,
            of50_completion_verified=bool(
                v3_result.v2_result.v1_result.of50_receipt.completion_verified
            ),
            f130_terminal_completion_verified=False,
            provider_execution_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FRCB_V4_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResultV4(
            v3_result=v3_result,
            alpha_omega_build_receipt=verified_build,
            convergence_receipt=receipt,
        )


__all__ = [
    "CAPABILITY_ID",
    "RuntimeConvergenceBinderV4",
    "RuntimeConvergenceReceiptV4",
    "RuntimeConvergenceResultV4",
    "SCHEMA",
    "StageBindingV4",
    "StageStateV4",
    "VERSION",
]
