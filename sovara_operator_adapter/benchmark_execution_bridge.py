from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


_ALLOWED_COSTS = {"ZERO", "INCLUDED", "UNKNOWN", "PAID"}
_ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}
_ALLOWED_DISPOSITIONS = {
    "ADOPT",
    "ADAPT",
    "ALREADY_PRESENT",
    "NOT_APPLICABLE",
    "HELD_WITH_EXACT_GATE",
    "REJECTED_WITH_EVIDENCE",
}
_AUTONOMOUS_COSTS = {"ZERO", "INCLUDED"}


@dataclass(frozen=True)
class CapabilityGene:
    gene_id: str
    practice_id: str
    origin: str
    capability: str
    priority: str
    target_selector: str
    applicability_tags: tuple[str, ...] = ()
    non_reuse_conditions: tuple[str, ...] = ()
    effect_class: str = "A1_INTERNAL"
    cost_class: str = "INCLUDED"
    reversible: bool = True
    proof_gate: str = "INDEPENDENT_SEMANTIC_READBACK"
    source_current: bool = True

    def validate(self) -> None:
        for name, value in (
            ("gene_id", self.gene_id),
            ("practice_id", self.practice_id),
            ("origin", self.origin),
            ("capability", self.capability),
            ("target_selector", self.target_selector),
            ("proof_gate", self.proof_gate),
        ):
            if not value:
                raise ValueError(f"{name} is required")
        if self.priority not in _ALLOWED_PRIORITIES:
            raise ValueError("priority must be P0, P1, P2, or P3")
        if self.cost_class not in _ALLOWED_COSTS:
            raise ValueError("cost_class must be ZERO, INCLUDED, UNKNOWN, or PAID")


@dataclass(frozen=True)
class ReceiverState:
    receiver_id: str
    receiver_class: str
    capability_tags: tuple[str, ...]
    source_current: bool
    authority_ceiling: str
    existing_authority: bool
    independent_readback_available: bool
    rollback_available: bool
    already_present_gene_ids: tuple[str, ...] = ()
    privacy_or_matter_hold: bool = False
    consequential_effect_required: bool = False
    iam_or_secret_change_required: bool = False
    external_effect_required: bool = False
    paid_or_unknown_incremental_cost: bool = False
    explicit_non_applicability: bool = False
    evidence_rejection_reason: str = ""

    def validate(self) -> None:
        if not self.receiver_id:
            raise ValueError("receiver_id is required")
        if not self.receiver_class:
            raise ValueError("receiver_class is required")
        if not self.authority_ceiling:
            raise ValueError("authority_ceiling is required")


@dataclass(frozen=True)
class AdoptionWorkPacket:
    gene_id: str
    receiver_id: str
    disposition: str
    aaa_state: str
    kuag_state: str
    mission_id: str
    status: str
    reason: str
    autonomous_execution_admissible: bool
    owner_trigger_required: bool
    continue_unaffected_receivers: bool
    proof_gate: str
    rollback: str
    authority_ceiling: str
    authorizes_authority_inheritance: bool = False
    self_certifies_value: bool = False


@dataclass(frozen=True)
class DiffusionCycleState:
    gene_id: str
    receiver_id: str
    priority: str
    successful_eligible_cycles_without_disposition: int
    exact_gate_recorded: bool = False
    fallback_and_resume_trigger_recorded: bool = False

    def validate(self) -> None:
        if self.priority not in _ALLOWED_PRIORITIES:
            raise ValueError("priority must be P0, P1, P2, or P3")
        if self.successful_eligible_cycles_without_disposition < 0:
            raise ValueError("cycle count cannot be negative")


@dataclass(frozen=True)
class ValueMeasurementEnvelope:
    work_id: str
    receiver_id: str
    before_state: str
    change_executed: str
    execution_ref: str
    independent_verifier: str
    readback_state: str
    quality_delta: str = "UNMEASURED"
    reliability_delta: str = "UNMEASURED"
    latency_delta: str = "UNMEASURED"
    cost_delta: str = "UNMEASURED"
    owner_burden_delta: str = "UNMEASURED"
    capability_delta: str = "UNMEASURED"
    regression_state: str = "UNMEASURED"
    truth_boundary: str = "RECEIVER_SPECIFIC_ONLY"

    def validate(self) -> None:
        for name, value in (
            ("work_id", self.work_id),
            ("receiver_id", self.receiver_id),
            ("before_state", self.before_state),
            ("change_executed", self.change_executed),
            ("execution_ref", self.execution_ref),
            ("independent_verifier", self.independent_verifier),
            ("readback_state", self.readback_state),
            ("truth_boundary", self.truth_boundary),
        ):
            if not value:
                raise ValueError(f"{name} is required")


def compile_adoption_work_packet(gene: CapabilityGene, receiver: ReceiverState) -> AdoptionWorkPacket:
    """Compile one receiver-specific CFBE capability gene without executing effects.

    The compiler preserves the receiver's authority and truth boundary. It emits
    an explicit disposition/work packet for SOVARA/Federation execution; it is
    not itself an external-effect executor and cannot certify realized value.
    """
    gene.validate()
    receiver.validate()
    mission_id = f"SOV-CFBE-{gene.gene_id}-{receiver.receiver_id}"

    if gene.gene_id in receiver.already_present_gene_ids:
        return _packet(gene, receiver, mission_id, "ALREADY_PRESENT", "AAA_ALREADY_PRESENT", "K4_ADOPTED_OR_LOCAL_EQUIVALENT", "NO_EXECUTION_REQUIRED", "receiver already contains an equivalent capability", False, False)

    if receiver.explicit_non_applicability:
        return _packet(gene, receiver, mission_id, "NOT_APPLICABLE", "AAA_NOT_APPLICABLE", "K2_HYPOTHESIS", "NO_EXECUTION_REQUIRED", "receiver explicitly excludes this capability", False, False)

    if receiver.evidence_rejection_reason:
        return _packet(gene, receiver, mission_id, "REJECTED_WITH_EVIDENCE", "AAA_REJECTED", "K2_HYPOTHESIS", "REJECTED", receiver.evidence_rejection_reason, False, False)

    if not gene.source_current:
        return _hold(gene, receiver, mission_id, "source benchmark evidence is stale")
    if not receiver.source_current:
        return _hold(gene, receiver, mission_id, "receiver state is stale and requires targeted reprobe")
    if receiver.privacy_or_matter_hold:
        return _hold(gene, receiver, mission_id, "receiver privacy or matter boundary blocks adaptation")

    required_tags = set(gene.applicability_tags)
    receiver_tags = set(receiver.capability_tags)
    if required_tags and not required_tags.intersection(receiver_tags):
        return _packet(gene, receiver, mission_id, "NOT_APPLICABLE", "AAA_NOT_APPLICABLE", "K2_HYPOTHESIS", "NO_EXECUTION_REQUIRED", "receiver has no matching applicability tag", False, False)

    if gene.cost_class not in _AUTONOMOUS_COSTS or receiver.paid_or_unknown_incremental_cost:
        return _owner_gate(gene, receiver, mission_id, "incremental cost is paid or unknown")
    if not receiver.existing_authority:
        return _owner_gate(gene, receiver, mission_id, "receiver lacks existing authority for the proposed adaptation")
    if receiver.consequential_effect_required or receiver.iam_or_secret_change_required or receiver.external_effect_required:
        return _owner_gate(gene, receiver, mission_id, "adaptation requires consequential, IAM/secret, or external effect authority")
    if not gene.reversible or not receiver.rollback_available:
        return _owner_gate(gene, receiver, mission_id, "receiver-specific activation is not reversibly bounded")
    if not receiver.independent_readback_available:
        return _hold(gene, receiver, mission_id, "independent semantic readback is unavailable")

    disposition = "ADAPT" if receiver.receiver_class not in {"NEW_BUILD", "EMPTY_RECEIVER"} else "ADOPT"
    return _packet(
        gene,
        receiver,
        mission_id,
        disposition,
        "AAA_ADAPT_READY",
        "K2_HYPOTHESIS",
        "READY_FOR_SOVARA_EXECUTION",
        "receiver relevance, freshness, authority, cost, rollback and proof gates passed",
        True,
        False,
    )


def detect_stranded_learning(state: DiffusionCycleState) -> str:
    """Classify diffusion backlog without treating exact holds as stranded learning."""
    state.validate()
    if state.exact_gate_recorded and state.fallback_and_resume_trigger_recorded:
        return "EXACT_GATE_NOT_STRANDED"
    threshold = 2 if state.priority == "P0" else 3
    if state.successful_eligible_cycles_without_disposition >= threshold:
        return "STRANDED_LEARNING_REVIEW_REQUIRED"
    return "NOT_STRANDED_YET"


def rank_receiver_packets(gene: CapabilityGene, receivers: Iterable[ReceiverState]) -> list[AdoptionWorkPacket]:
    """Return deterministic executable receiver packets; held/rejected state stays durable elsewhere."""
    packets = [compile_adoption_work_packet(gene, receiver) for receiver in receivers]
    executable = [packet for packet in packets if packet.status == "READY_FOR_SOVARA_EXECUTION"]
    return sorted(executable, key=lambda packet: (packet.receiver_id, packet.mission_id))


def validate_value_measurement(envelope: ValueMeasurementEnvelope) -> str:
    """Require independent receiver readback before realized value can be registered."""
    envelope.validate()
    if envelope.readback_state not in {"VERIFIED", "SEMANTIC_PASS", "WRITE_AND_READBACK_VERIFIED"}:
        return "VALUE_UNVERIFIED_READBACK_REQUIRED"
    if envelope.independent_verifier == envelope.execution_ref:
        return "VALUE_UNVERIFIED_EXECUTOR_SELF_CERTIFICATION"
    if all(
        value == "UNMEASURED"
        for value in (
            envelope.quality_delta,
            envelope.reliability_delta,
            envelope.latency_delta,
            envelope.cost_delta,
            envelope.owner_burden_delta,
            envelope.capability_delta,
            envelope.regression_state,
        )
    ):
        return "VALUE_UNMEASURED"
    return "VALUE_MEASUREMENT_ADMISSIBLE_RECEIVER_SPECIFIC"


def _packet(
    gene: CapabilityGene,
    receiver: ReceiverState,
    mission_id: str,
    disposition: str,
    aaa_state: str,
    kuag_state: str,
    status: str,
    reason: str,
    autonomous: bool,
    owner_trigger: bool,
) -> AdoptionWorkPacket:
    if disposition not in _ALLOWED_DISPOSITIONS:
        raise ValueError(f"invalid disposition: {disposition}")
    return AdoptionWorkPacket(
        gene_id=gene.gene_id,
        receiver_id=receiver.receiver_id,
        disposition=disposition,
        aaa_state=aaa_state,
        kuag_state=kuag_state,
        mission_id=mission_id,
        status=status,
        reason=reason,
        autonomous_execution_admissible=autonomous,
        owner_trigger_required=owner_trigger,
        continue_unaffected_receivers=True,
        proof_gate=gene.proof_gate,
        rollback="RECEIVER_LOCAL_ROLLBACK_REQUIRED" if status == "READY_FOR_SOVARA_EXECUTION" else "NO_EFFECT_OR_HOLD",
        authority_ceiling=receiver.authority_ceiling,
    )


def _hold(gene: CapabilityGene, receiver: ReceiverState, mission_id: str, reason: str) -> AdoptionWorkPacket:
    return _packet(gene, receiver, mission_id, "HELD_WITH_EXACT_GATE", "AAA_HELD", "K2_HYPOTHESIS", "HELD_WITH_EXACT_GATE", reason, False, False)


def _owner_gate(gene: CapabilityGene, receiver: ReceiverState, mission_id: str, reason: str) -> AdoptionWorkPacket:
    packet = _packet(gene, receiver, mission_id, "HELD_WITH_EXACT_GATE", "AAA_HELD", "K2_HYPOTHESIS", "OWNER_TRIGGER_REQUIRED", reason, False, True)
    return packet
