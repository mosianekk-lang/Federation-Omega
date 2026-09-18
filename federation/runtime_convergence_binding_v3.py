from __future__ import annotations

"""FUSE Runtime Convergence Binding v3.

V3 preserves the admitted V1/V2 boundaries and promotes Formation Innovation
only when the exact EvidenceOps FoundryCycleResult receipt is verified and
bound to the FormationDecision consumed by OF50.

No Alpha-Omega runtime execution, provider execution, F130 terminal commit, or
whole-mission COMPLETE_VERIFIED is inherited.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from evidenceops.innovation_engine.foundry_model import FoundryCycleResult
from federation.aarek_v1 import MissionSnapshot
from federation.formation_foundry_binding_v1 import (
    FormationFoundryBinder,
    FormationFoundryBindingReceipt,
)
from federation.oh50_producer_adapter_v1 import OH50ProducerReceipt
from federation.of50_ace_v1 import OF50CycleRequest
from federation.runtime_convergence_binding_v2 import (
    RuntimeConvergenceBinderV2,
    RuntimeConvergenceResultV2,
)

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V3"
VERSION = "3.0.0"
CAPABILITY_ID = "FUSE-FRCB-003"


class StageStateV3(str, Enum):
    PRODUCER_INVOCATION_VERIFIED = "PRODUCER_INVOCATION_VERIFIED"
    FOUNDRY_CYCLE_RECEIPT_VERIFIED = "FOUNDRY_CYCLE_RECEIPT_VERIFIED"
    STRUCTURALLY_BOUND = "STRUCTURALLY_BOUND"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class StageBindingV3:
    stage: str
    state: StageStateV3
    producer: str
    mission_id: str
    artifact_ref: str
    artifact_digest: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceiptV3:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    stages: tuple[StageBindingV3, ...]
    v2_receipt_digest: str
    formation_binding_receipt_digest: str
    formation_foundry_receipt_sha256: str
    formation_proof_sha256: str
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
            "v2_receipt_digest": self.v2_receipt_digest,
            "formation_binding_receipt_digest": self.formation_binding_receipt_digest,
            "formation_foundry_receipt_sha256": self.formation_foundry_receipt_sha256,
            "formation_proof_sha256": self.formation_proof_sha256,
            "of50_receipt_digest": self.of50_receipt_digest,
            "of50_completion_verified": self.of50_completion_verified,
            "f130_terminal_completion_verified": self.f130_terminal_completion_verified,
            "provider_execution_verified": self.provider_execution_verified,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.capability_id == CAPABILITY_ID
            and len(self.formation_foundry_receipt_sha256) == 64
            and len(self.formation_proof_sha256) == 64
            and boundary.get("formation_foundry_cycle_verified") is True
            and boundary.get("formation_chain_proof_verified") is True
            and boundary.get("alpha_omega_runtime_execution_verified") is False
            and boundary.get("provider_execution_verified") is False
            and boundary.get("f130_terminal_completion_verified") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceResultV3:
    v2_result: RuntimeConvergenceResultV2
    formation_binding_receipt: FormationFoundryBindingReceipt
    convergence_receipt: RuntimeConvergenceReceiptV3


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


class RuntimeConvergenceBinderV3:
    """Bind a verified Formation foundry cycle into the V2 convergence chain."""

    def __init__(
        self,
        *,
        v2: RuntimeConvergenceBinderV2 | None = None,
        formation_binder: FormationFoundryBinder | None = None,
    ) -> None:
        self.v2 = v2 or RuntimeConvergenceBinderV2()
        self.formation_binder = formation_binder or FormationFoundryBinder()

    def evaluate(
        self,
        *,
        aarek_snapshot: MissionSnapshot,
        of50_request: OF50CycleRequest,
        oh50_producer_receipt: OH50ProducerReceipt,
        foundry_result: FoundryCycleResult,
    ) -> RuntimeConvergenceResultV3:
        formation = of50_request.formation_decision
        if formation is None:
            raise ValueError("FORMATION_DECISION_REQUIRED")

        formation_binding = self.formation_binder.bind(
            mission_id=of50_request.mission_id,
            foundry_result=foundry_result,
            formation_decision=formation,
        )
        v2_result = self.v2.evaluate(
            aarek_snapshot=aarek_snapshot,
            of50_request=of50_request,
            oh50_producer_receipt=oh50_producer_receipt,
        )

        stages: list[StageBindingV3] = []
        for stage in v2_result.convergence_receipt.stages:
            if stage.stage == "FORMATION_INNOVATION":
                stages.append(StageBindingV3(
                    stage=stage.stage,
                    state=StageStateV3.FOUNDRY_CYCLE_RECEIPT_VERIFIED,
                    producer=formation_binding.producer_id,
                    mission_id=stage.mission_id,
                    artifact_ref=formation_binding.receipt_digest,
                    artifact_digest=formation_binding.foundry_receipt_sha256,
                    limitations=(
                        "EvidenceOps deterministic foundry-cycle receipt and chain proof are verified.",
                        "FoundryCycleResult has no native mission_id; mission attachment is verified through FormationDecision.",
                        "Independent external attestation and provider execution remain unverified.",
                    ),
                ))
                continue

            if stage.state.value == "NOT_REQUIRED":
                mapped = StageStateV3.NOT_REQUIRED
            elif stage.state.value == "PRODUCER_INVOCATION_VERIFIED":
                mapped = StageStateV3.PRODUCER_INVOCATION_VERIFIED
            else:
                mapped = StageStateV3.STRUCTURALLY_BOUND
            stages.append(StageBindingV3(
                stage=stage.stage,
                state=mapped,
                producer=stage.producer,
                mission_id=stage.mission_id,
                artifact_ref=stage.artifact_ref,
                artifact_digest=stage.artifact_digest,
                limitations=stage.limitations,
            ))

        truth_boundary = MappingProxyType({
            **dict(v2_result.convergence_receipt.truth_boundary),
            "formation_foundry_cycle_verified": True,
            "formation_chain_proof_verified": True,
            "formation_mission_identity_native_to_foundry_receipt": False,
            "formation_independent_attestation_verified": False,
            "alpha_omega_runtime_execution_verified": False,
            "provider_execution_verified": False,
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
            "v2_receipt_digest": v2_result.convergence_receipt.receipt_digest,
            "formation_binding_receipt_digest": formation_binding.receipt_digest,
            "formation_foundry_receipt_sha256": formation_binding.foundry_receipt_sha256,
            "formation_proof_sha256": formation_binding.proof_sha256,
            "of50_receipt_digest": v2_result.v1_result.of50_receipt.receipt_digest,
            "of50_completion_verified": bool(v2_result.v1_result.of50_receipt.completion_verified),
            "f130_terminal_completion_verified": False,
            "provider_execution_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = RuntimeConvergenceReceiptV3(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=of50_request.mission_id,
            objective=of50_request.objective,
            authority_ceiling=of50_request.authority_ceiling,
            stages=tuple(stages),
            v2_receipt_digest=v2_result.convergence_receipt.receipt_digest,
            formation_binding_receipt_digest=formation_binding.receipt_digest,
            formation_foundry_receipt_sha256=formation_binding.foundry_receipt_sha256,
            formation_proof_sha256=formation_binding.proof_sha256,
            of50_receipt_digest=v2_result.v1_result.of50_receipt.receipt_digest,
            of50_completion_verified=bool(v2_result.v1_result.of50_receipt.completion_verified),
            f130_terminal_completion_verified=False,
            provider_execution_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FRCB_V3_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResultV3(
            v2_result=v2_result,
            formation_binding_receipt=formation_binding,
            convergence_receipt=receipt,
        )


__all__ = [
    "CAPABILITY_ID",
    "RuntimeConvergenceBinderV3",
    "RuntimeConvergenceReceiptV3",
    "RuntimeConvergenceResultV3",
    "SCHEMA",
    "StageBindingV3",
    "StageStateV3",
    "VERSION",
]
