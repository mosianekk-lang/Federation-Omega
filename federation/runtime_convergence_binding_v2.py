from __future__ import annotations

"""FUSE Runtime Convergence Binding v2.

V2 preserves the admitted v1 authority boundary and adds one promotion only:
OH50 changes from a caller-supplied structural object to a producer-invocation
receipt bound to the exact SwarmManifest consumed by OF50.

No provider execution, external effect, independent cryptographic attestation,
Formation execution, Alpha-Omega runtime execution, F130 terminal commit, or
whole-mission COMPLETE_VERIFIED is inherited.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from federation.oh50_producer_adapter_v1 import (
    OH50ProducerReceipt,
    manifest_digest,
)
from federation.of50_ace_v1 import OF50CycleRequest
from federation.runtime_convergence_binding_v1 import (
    RuntimeConvergenceBinder as RuntimeConvergenceBinderV1,
    RuntimeConvergenceResult as RuntimeConvergenceResultV1,
)
from federation.aarek_v1 import MissionSnapshot

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V2"
VERSION = "2.0.0"
CAPABILITY_ID = "FUSE-FRCB-002"


class StageState(str, Enum):
    PRODUCER_INVOCATION_VERIFIED = "PRODUCER_INVOCATION_VERIFIED"
    STRUCTURALLY_BOUND = "STRUCTURALLY_BOUND"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class StageBindingV2:
    stage: str
    state: StageState
    producer: str
    mission_id: str
    artifact_ref: str
    artifact_digest: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceiptV2:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    stages: tuple[StageBindingV2, ...]
    v1_receipt_digest: str
    oh50_producer_receipt_digest: str
    oh50_manifest_digest: str
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
            "v1_receipt_digest": self.v1_receipt_digest,
            "oh50_producer_receipt_digest": self.oh50_producer_receipt_digest,
            "oh50_manifest_digest": self.oh50_manifest_digest,
            "of50_receipt_digest": self.of50_receipt_digest,
            "of50_completion_verified": self.of50_completion_verified,
            "f130_terminal_completion_verified": self.f130_terminal_completion_verified,
            "provider_execution_verified": self.provider_execution_verified,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.capability_id == CAPABILITY_ID
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceResultV2:
    v1_result: RuntimeConvergenceResultV1
    oh50_producer_receipt: OH50ProducerReceipt
    convergence_receipt: RuntimeConvergenceReceiptV2


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


def _equal(label: str, expected: str, actual: str) -> None:
    if expected != actual:
        raise ValueError(f"{label}_MISMATCH:{expected}!={actual}")


class RuntimeConvergenceBinderV2:
    """Bind an OH50 producer receipt to the exact v1/OF50 manifest."""

    def __init__(self, *, v1: RuntimeConvergenceBinderV1 | None = None) -> None:
        self.v1 = v1 or RuntimeConvergenceBinderV1()

    def evaluate(
        self,
        *,
        aarek_snapshot: MissionSnapshot,
        of50_request: OF50CycleRequest,
        oh50_producer_receipt: OH50ProducerReceipt,
    ) -> RuntimeConvergenceResultV2:
        if not oh50_producer_receipt.verify():
            raise ValueError("OH50_PRODUCER_RECEIPT_INVALID")
        manifest = of50_request.swarm_manifest
        if manifest is None:
            raise ValueError("OH50_MANIFEST_REQUIRED")

        _equal("OH50_RECEIPT_MISSION", of50_request.mission_id, oh50_producer_receipt.mission_id)
        _equal("OH50_RECEIPT_OBJECTIVE", of50_request.objective, oh50_producer_receipt.objective)
        _equal("OH50_RECEIPT_AUTHORITY", of50_request.authority_ceiling, oh50_producer_receipt.authority_ceiling)
        _equal("OH50_RECEIPT_HOST_ALGORITHM", manifest.host_algorithm_id, oh50_producer_receipt.host_algorithm_id)

        observed_manifest_digest = manifest_digest(manifest)
        _equal("OH50_RECEIPT_MANIFEST", observed_manifest_digest, oh50_producer_receipt.manifest_digest)

        v1_result = self.v1.evaluate(
            aarek_snapshot=aarek_snapshot,
            of50_request=of50_request,
        )
        stages: list[StageBindingV2] = []
        for stage in v1_result.convergence_receipt.stages:
            if stage.stage == "OH50":
                stages.append(StageBindingV2(
                    stage=stage.stage,
                    state=StageState.PRODUCER_INVOCATION_VERIFIED,
                    producer=oh50_producer_receipt.producer_id,
                    mission_id=stage.mission_id,
                    artifact_ref=oh50_producer_receipt.receipt_digest,
                    artifact_digest=oh50_producer_receipt.manifest_digest,
                    limitations=(
                        "OH50 in-process producer invocation and exact manifest binding are verified.",
                        "Independent signature/attestation and provider execution remain unverified.",
                    ),
                ))
            else:
                mapped = (
                    StageState.NOT_REQUIRED
                    if stage.state.value == "NOT_REQUIRED"
                    else (
                        StageState.PRODUCER_INVOCATION_VERIFIED
                        if stage.state.value == "EXECUTION_RECEIPT_VERIFIED"
                        else StageState.STRUCTURALLY_BOUND
                    )
                )
                stages.append(StageBindingV2(
                    stage=stage.stage,
                    state=mapped,
                    producer=stage.producer,
                    mission_id=stage.mission_id,
                    artifact_ref=stage.artifact_ref,
                    artifact_digest=stage.artifact_digest,
                    limitations=stage.limitations,
                ))

        truth_boundary = MappingProxyType({
            **dict(v1_result.convergence_receipt.truth_boundary),
            "oh50_producer_invocation_verified": True,
            "oh50_independent_attestation_verified": False,
            "formation_foundry_execution_verified": False,
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
            "v1_receipt_digest": v1_result.convergence_receipt.receipt_digest,
            "oh50_producer_receipt_digest": oh50_producer_receipt.receipt_digest,
            "oh50_manifest_digest": observed_manifest_digest,
            "of50_receipt_digest": v1_result.of50_receipt.receipt_digest,
            "of50_completion_verified": bool(v1_result.of50_receipt.completion_verified),
            "f130_terminal_completion_verified": False,
            "provider_execution_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = RuntimeConvergenceReceiptV2(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=of50_request.mission_id,
            objective=of50_request.objective,
            authority_ceiling=of50_request.authority_ceiling,
            stages=tuple(stages),
            v1_receipt_digest=v1_result.convergence_receipt.receipt_digest,
            oh50_producer_receipt_digest=oh50_producer_receipt.receipt_digest,
            oh50_manifest_digest=observed_manifest_digest,
            of50_receipt_digest=v1_result.of50_receipt.receipt_digest,
            of50_completion_verified=bool(v1_result.of50_receipt.completion_verified),
            f130_terminal_completion_verified=False,
            provider_execution_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FRCB_V2_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResultV2(
            v1_result=v1_result,
            oh50_producer_receipt=oh50_producer_receipt,
            convergence_receipt=receipt,
        )


__all__ = [
    "CAPABILITY_ID",
    "RuntimeConvergenceBinderV2",
    "RuntimeConvergenceReceiptV2",
    "RuntimeConvergenceResultV2",
    "SCHEMA",
    "StageBindingV2",
    "StageState",
    "VERSION",
]
