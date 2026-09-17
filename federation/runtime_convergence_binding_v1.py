from __future__ import annotations

"""FUSE Runtime Convergence Binding v1.

Thin, effect-free binding layer between already-existing AAREK and OF50 contracts.
It creates no scheduler, authority plane, provider runtime, memory root, proof plane,
foundry, or execution surface.

Primary purpose:
    prevent a caller-supplied reference string from masquerading as execution of
    a mandatory upstream stage.

v1 performs one real upstream invocation (AAREK), validates the already-typed
OH50 / Formation / Alpha→Omega objects supplied to OF50, binds all identities to
one mission/objective/authority envelope, and then evaluates OF50.

It deliberately does NOT claim that validating OH50/Formation/Alpha→Omega objects
proves those producers executed. Those stages remain STRUCTURALLY_BOUND until
their own producer-attested receipts are supplied by later bindings.

FRCB is not a terminal-completion authority. OF50 stage completion is exposed
explicitly as ``of50_completion_verified`` while ``completion_verified`` remains a
terminal-safe alias that cannot become true in v1 without an F130 terminal commit.
"""

from dataclasses import asdict, dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from federation.aarek_v1 import (
    AarekKernel,
    AarekReceipt,
    AarekState,
    Decision as AarekDecision,
    MissionSnapshot,
)
from federation.of50_ace_v1 import (
    AlphaOmegaPacket,
    FormationDecision,
    OF50ACEKernel,
    OF50CycleReceipt,
    OF50CycleRequest,
    SwarmManifest,
)

SCHEMA = "FUSE-RUNTIME-CONVERGENCE-BINDING-V1"
VERSION = "1.0.0"
CAPABILITY_ID = "FUSE-FRCB-001"


class BindingState(str, Enum):
    EXECUTION_RECEIPT_VERIFIED = "EXECUTION_RECEIPT_VERIFIED"
    STRUCTURALLY_BOUND = "STRUCTURALLY_BOUND"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True, slots=True)
class StageBinding:
    stage: str
    state: BindingState
    producer: str
    mission_id: str
    artifact_ref: str
    artifact_digest: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConvergenceReceipt:
    schema: str
    version: str
    capability_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    stages: tuple[StageBinding, ...]
    bound_request_digest: str
    of50_receipt_digest: str
    of50_completion_verified: bool
    f130_terminal_completion_verified: bool
    provider_execution_verified: bool
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    @property
    def completion_verified(self) -> bool:
        """Terminal-safe compatibility alias.

        FRCB v1 cannot independently authorize whole-mission completion, so this
        alias follows only F130 terminal completion and therefore remains false in
        v1 even if the embedded OF50 court reports its own completion as verified.
        """
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
            "bound_request_digest": self.bound_request_digest,
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
class RuntimeConvergenceResult:
    aarek_receipt: AarekReceipt
    bound_request: OF50CycleRequest
    of50_receipt: OF50CycleReceipt
    convergence_receipt: RuntimeConvergenceReceipt


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=_default)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _object_digest(value: Any) -> str:
    try:
        body = asdict(value)
    except TypeError:
        body = value
    return _digest(body)


def _require_equal(label: str, expected: str, actual: str) -> None:
    if expected != actual:
        raise ValueError(f"{label}_MISMATCH:{expected}!={actual}")


class RuntimeConvergenceBinder:
    """Bind real AAREK evaluation to OF50 without widening authority."""

    def __init__(self) -> None:
        self.aarek = AarekKernel()
        self.of50 = OF50ACEKernel()

    def evaluate(self, *, aarek_snapshot: MissionSnapshot, of50_request: OF50CycleRequest) -> RuntimeConvergenceResult:
        self._validate_identity(aarek_snapshot, of50_request)

        aarek_receipt = self.aarek.evaluate(aarek_snapshot)
        if not aarek_receipt.receipt_digest.startswith("sha256:"):
            raise ValueError("AAREK_RECEIPT_DIGEST_INVALID")
        _require_equal("AAREK_RECEIPT_MISSION", of50_request.mission_id, aarek_receipt.mission_id)

        aarek_completion_verified = bool(
            aarek_receipt.state is AarekState.COMPLETE_VERIFIED
            and aarek_receipt.decision is AarekDecision.ALLOW_COMPLETE_VERIFIED
            and not aarek_receipt.auto_continue_required
        )
        if of50_request.completion_requested and not aarek_completion_verified:
            raise ValueError("AAREK_COMPLETION_NOT_VERIFIED")

        supplied = of50_request.aarek_receipt_ref.strip()
        if supplied and supplied != aarek_receipt.receipt_digest:
            raise ValueError("AAREK_RECEIPT_REF_SUBSTITUTION")

        stages = [
            StageBinding(
                stage="AAREK",
                state=BindingState.EXECUTION_RECEIPT_VERIFIED,
                producer="FUSE-AAREK-V1.1",
                mission_id=of50_request.mission_id,
                artifact_ref=aarek_receipt.receipt_digest,
                artifact_digest=aarek_receipt.receipt_digest,
                limitations=(
                    "AAREK kernel invocation is receipt-bound.",
                    "AAREK is effect-free and does not prove provider execution.",
                ),
            )
        ]

        swarm = of50_request.swarm_manifest
        if swarm is None:
            raise ValueError("OH50_MANIFEST_REQUIRED")
        errors = swarm.validate()
        if errors:
            raise ValueError("OH50_MANIFEST_INVALID:" + ";".join(errors))
        _require_equal("OH50_MISSION", of50_request.mission_id, swarm.mission_id)
        _require_equal("OH50_OBJECTIVE", of50_request.objective, swarm.objective)
        _require_equal("OH50_AUTHORITY", of50_request.authority_ceiling, swarm.authority_ceiling)
        swarm_digest = _object_digest(swarm)
        stages.append(
            StageBinding(
                stage="OH50",
                state=BindingState.STRUCTURALLY_BOUND,
                producer=swarm.host_algorithm_id,
                mission_id=swarm.mission_id,
                artifact_ref=swarm_digest,
                artifact_digest=swarm_digest,
                limitations=("Typed manifest validation is not producer-attested OH50 execution.",),
            )
        )

        formation = of50_request.formation_decision
        if formation is None:
            raise ValueError("FORMATION_DECISION_REQUIRED")
        errors = formation.validate()
        if errors:
            raise ValueError("FORMATION_DECISION_INVALID:" + ";".join(errors))
        _require_equal("FORMATION_MISSION", of50_request.mission_id, formation.mission_id)
        _require_equal("FORMATION_AUTHORITY", of50_request.authority_ceiling, formation.authority_ceiling)
        formation_digest = _object_digest(formation)
        stages.append(
            StageBinding(
                stage="FORMATION_INNOVATION",
                state=BindingState.STRUCTURALLY_BOUND,
                producer="EVIDENCEOPS-FORMATION-INNOVATION",
                mission_id=formation.mission_id,
                artifact_ref=formation.foundry_cycle_ref,
                artifact_digest=formation_digest,
                limitations=("FormationDecision validation does not itself prove the foundry cycle executed.",),
            )
        )

        packet = of50_request.alpha_omega_packet
        if formation.implementation_required:
            if packet is None:
                raise ValueError("ALPHA_OMEGA_PACKET_REQUIRED")
            self._validate_alpha(packet, of50_request)
            packet_digest = _object_digest(packet)
            stages.append(
                StageBinding(
                    stage="ALPHA_OMEGA_IF_REQUIRED",
                    state=BindingState.STRUCTURALLY_BOUND,
                    producer="ALPHA-OMEGA-TURNKEY",
                    mission_id=packet.mission_id,
                    artifact_ref=packet.packet_ref,
                    artifact_digest=packet_digest,
                    limitations=("Validated AlphaOmegaPacket is a build/lifecycle contract, not provider deployment proof.",),
                )
            )
        elif packet is not None:
            self._validate_alpha(packet, of50_request)
            packet_digest = _object_digest(packet)
            stages.append(
                StageBinding(
                    stage="ALPHA_OMEGA_IF_REQUIRED",
                    state=BindingState.STRUCTURALLY_BOUND,
                    producer="ALPHA-OMEGA-TURNKEY",
                    mission_id=packet.mission_id,
                    artifact_ref=packet.packet_ref,
                    artifact_digest=packet_digest,
                    limitations=("Packet was present although implementation was not required.",),
                )
            )
        else:
            stages.append(
                StageBinding(
                    stage="ALPHA_OMEGA_IF_REQUIRED",
                    state=BindingState.NOT_REQUIRED,
                    producer="ALPHA-OMEGA-TURNKEY",
                    mission_id=of50_request.mission_id,
                    artifact_ref="",
                    artifact_digest="",
                    limitations=(),
                )
            )

        bound_request = replace(of50_request, aarek_receipt_ref=aarek_receipt.receipt_digest)
        of50_receipt = self.of50.evaluate(bound_request)

        request_digest = _object_digest(bound_request)
        truth_boundary = MappingProxyType({
            "aarek_execution_verified": True,
            "aarek_completion_verified": aarek_completion_verified,
            "oh50_producer_execution_verified": False,
            "formation_foundry_execution_verified": False,
            "alpha_omega_runtime_execution_verified": False,
            "provider_execution_verified": False,
            "provider_execution_inherited": False,
            "of50_stage_completion_verified": bool(of50_receipt.completion_verified),
            "f130_terminal_completion_verified": False,
            "authority_widened": False,
        })
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "capability_id": CAPABILITY_ID,
            "mission_id": bound_request.mission_id,
            "objective": bound_request.objective,
            "authority_ceiling": bound_request.authority_ceiling,
            "stages": [asdict(item) for item in stages],
            "bound_request_digest": request_digest,
            "of50_receipt_digest": of50_receipt.receipt_digest,
            "of50_completion_verified": bool(of50_receipt.completion_verified),
            "f130_terminal_completion_verified": False,
            "provider_execution_verified": False,
            "truth_boundary": dict(truth_boundary),
        }
        convergence = RuntimeConvergenceReceipt(
            schema=SCHEMA,
            version=VERSION,
            capability_id=CAPABILITY_ID,
            mission_id=bound_request.mission_id,
            objective=bound_request.objective,
            authority_ceiling=bound_request.authority_ceiling,
            stages=tuple(stages),
            bound_request_digest=request_digest,
            of50_receipt_digest=of50_receipt.receipt_digest,
            of50_completion_verified=bool(of50_receipt.completion_verified),
            f130_terminal_completion_verified=False,
            provider_execution_verified=False,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not convergence.verify():
            raise ValueError("FRCB_RECEIPT_SELF_VERIFICATION_FAILED")
        return RuntimeConvergenceResult(
            aarek_receipt=aarek_receipt,
            bound_request=bound_request,
            of50_receipt=of50_receipt,
            convergence_receipt=convergence,
        )

    @staticmethod
    def _validate_identity(aarek_snapshot: MissionSnapshot, request: OF50CycleRequest) -> None:
        _require_equal("MISSION", request.mission_id, aarek_snapshot.mission_id)
        _require_equal("OBJECTIVE", request.objective, aarek_snapshot.objective)
        _require_equal("AUTHORITY", request.authority_ceiling, aarek_snapshot.authority_ceiling)

    @staticmethod
    def _validate_alpha(packet: AlphaOmegaPacket, request: OF50CycleRequest) -> None:
        errors = packet.validate()
        if errors:
            raise ValueError("ALPHA_OMEGA_PACKET_INVALID:" + ";".join(errors))
        _require_equal("ALPHA_OMEGA_MISSION", request.mission_id, packet.mission_id)
        _require_equal("ALPHA_OMEGA_AUTHORITY", request.authority_ceiling, packet.authority_ceiling)


__all__ = [
    "BindingState",
    "CAPABILITY_ID",
    "RuntimeConvergenceBinder",
    "RuntimeConvergenceReceipt",
    "RuntimeConvergenceResult",
    "SCHEMA",
    "StageBinding",
    "VERSION",
]
