"""Federation Knowledge Propagation Fabric v1.

This module extends the existing Federation consolidation fabric.  It does not
create a new sovereign truth, memory, scheduler, or authority plane.

The contract is deliberately proof-bounded:

    DISCOVER -> SEAL -> PUBLISH -> MATCH -> COMPATIBILITY -> DISPOSITION
    -> APPLY/ADAPT -> READBACK -> ACK -> MEASURE -> SUPERSEDE/RETAIN

A Bible/chat/source entry is not propagation proof.  Receiver-specific explicit
state plus readback is required, and runtime/provider/value evidence remains a
separate proof class.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


class Disposition(str, Enum):
    UNSEEN = "UNSEEN"
    RECEIVED = "RECEIVED"
    COMPATIBILITY_CHECKED = "COMPATIBILITY_CHECKED"
    ADOPT = "ADOPT"
    ADAPT = "ADAPT"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    HELD = "HELD"
    REJECTED_WITH_REASON = "REJECTED_WITH_REASON"
    APPLIED = "APPLIED"
    VERIFIED = "VERIFIED"
    VALUE_OBSERVED = "VALUE_OBSERVED"
    SUPERSEDED = "SUPERSEDED"


class Currentness(str, Enum):
    ACTIVE_CURRENT = "ACTIVE_CURRENT"
    ACTIVE_CURRENT_WITH_HOLDS = "ACTIVE_CURRENT_WITH_HOLDS"
    ACTIVE_STALE = "ACTIVE_STALE"


class CompletionState(str, Enum):
    WORK_COMPLETE_PROPAGATION_PENDING = "WORK_COMPLETE_PROPAGATION_PENDING"
    WORK_COMPLETE_PROPAGATION_VERIFIED = "WORK_COMPLETE_PROPAGATION_VERIFIED"


EXPLICIT_DISPOSITIONS = frozenset(
    {
        Disposition.ADOPT,
        Disposition.ADAPT,
        Disposition.ALREADY_PRESENT,
        Disposition.NOT_APPLICABLE,
        Disposition.HELD,
        Disposition.REJECTED_WITH_REASON,
        Disposition.APPLIED,
        Disposition.VERIFIED,
        Disposition.VALUE_OBSERVED,
    }
)

VERIFIED_DISPOSITIONS = frozenset(
    {Disposition.VERIFIED, Disposition.VALUE_OBSERVED, Disposition.ALREADY_PRESENT}
)


@dataclass(frozen=True)
class KnowledgeDelta:
    delta_id: str
    sequence: int
    source_epoch: str
    content_sha256: str
    proof_class: str
    priority: str
    receiver_classes: frozenset[str]
    authority_ceiling: str
    effect_ceiling: str
    supersedes_delta_id: str | None = None

    def validate(self) -> None:
        if not self.delta_id:
            raise ValueError("delta_id is required")
        if self.sequence < 1:
            raise ValueError("sequence must be positive")
        if len(self.content_sha256) != 64:
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        if self.priority not in {"P0", "P1", "P2"}:
            raise ValueError("priority must be P0, P1 or P2")
        if not self.receiver_classes:
            raise ValueError("at least one receiver class is required")


@dataclass(frozen=True)
class Receiver:
    receiver_class: str
    receiver_id: str
    source_state: str


@dataclass(frozen=True)
class ReceiverAck:
    delta_id: str
    delta_sequence: int
    receiver_id: str
    disposition: Disposition
    proof_ref: str = ""
    reason: str = ""

    @property
    def is_explicit(self) -> bool:
        return self.disposition in EXPLICIT_DISPOSITIONS

    @property
    def is_verified(self) -> bool:
        return self.disposition in VERIFIED_DISPOSITIONS or bool(self.proof_ref)


@dataclass(frozen=True)
class Watermark:
    receiver_id: str
    last_consumed_sequence: int
    canonical_head_sequence: int
    open_holds: int
    open_unseen: int
    currentness: Currentness


@dataclass(frozen=True)
class PropagationReport:
    required_receivers: int
    dispositioned_receivers: int
    verified_receivers: int
    held_receivers: int
    unseen_receivers: int
    coverage_rate: float
    verified_rate: float

    @property
    def fully_dispositioned(self) -> bool:
        return self.required_receivers == self.dispositioned_receivers

    @property
    def fully_verified(self) -> bool:
        return self.required_receivers == self.verified_receivers


@dataclass(frozen=True)
class StrandedLearning:
    delta_id: str
    receiver_id: str
    priority: str
    reason: str


def receiver_is_applicable(delta: KnowledgeDelta, receiver: Receiver) -> bool:
    """Return applicability without transferring authority/maturity semantics."""
    return (
        "ALL" in delta.receiver_classes
        or receiver.receiver_class in delta.receiver_classes
        or receiver.receiver_id in delta.receiver_classes
    )


def explicit_ack_map(acks: Iterable[ReceiverAck]) -> dict[tuple[str, str], ReceiverAck]:
    result: dict[tuple[str, str], ReceiverAck] = {}
    for ack in acks:
        key = (ack.receiver_id, ack.delta_id)
        if key in result:
            raise ValueError(f"duplicate receiver/delta ACK: {key}")
        if not ack.is_explicit:
            raise ValueError(f"non-terminal ACK cannot advance watermark: {key}")
        result[key] = ack
    return result


def compute_watermark(
    receiver: Receiver,
    deltas: Sequence[KnowledgeDelta],
    acks: Iterable[ReceiverAck],
    canonical_head_sequence: int,
) -> Watermark:
    ack_by_key = explicit_ack_map(acks)
    applicable = [d for d in deltas if receiver_is_applicable(d, receiver)]
    consumed = 0
    holds = 0
    unseen = 0
    for delta in applicable:
        ack = ack_by_key.get((receiver.receiver_id, delta.delta_id))
        if ack is None:
            unseen += 1
            continue
        consumed = max(consumed, delta.sequence)
        if ack.disposition is Disposition.HELD:
            holds += 1

    if unseen:
        state = Currentness.ACTIVE_STALE
    elif holds:
        state = Currentness.ACTIVE_CURRENT_WITH_HOLDS
    elif consumed >= canonical_head_sequence or not applicable:
        state = Currentness.ACTIVE_CURRENT
    else:
        state = Currentness.ACTIVE_STALE

    return Watermark(
        receiver_id=receiver.receiver_id,
        last_consumed_sequence=consumed,
        canonical_head_sequence=canonical_head_sequence,
        open_holds=holds,
        open_unseen=unseen,
        currentness=state,
    )


def node_may_claim_current(watermark: Watermark) -> bool:
    """Fail closed if applicable propagation is unseen.

    Explicit HELD state is allowed but must remain visible as
    ACTIVE_CURRENT_WITH_HOLDS rather than being silently painted green.
    """
    return watermark.currentness is not Currentness.ACTIVE_STALE


def propagation_report(
    delta: KnowledgeDelta,
    receivers: Sequence[Receiver],
    acks: Iterable[ReceiverAck],
) -> PropagationReport:
    ack_by_key = explicit_ack_map(acks)
    required = [r for r in receivers if receiver_is_applicable(delta, r)]
    dispositioned = verified = held = 0
    for receiver in required:
        ack = ack_by_key.get((receiver.receiver_id, delta.delta_id))
        if ack is None:
            continue
        dispositioned += 1
        if ack.is_verified:
            verified += 1
        if ack.disposition is Disposition.HELD:
            held += 1
    total = len(required)
    unseen = total - dispositioned
    return PropagationReport(
        required_receivers=total,
        dispositioned_receivers=dispositioned,
        verified_receivers=verified,
        held_receivers=held,
        unseen_receivers=unseen,
        coverage_rate=(dispositioned / total if total else 1.0),
        verified_rate=(verified / total if total else 1.0),
    )


def completion_state(
    delta_ids: Iterable[str],
    reports: Mapping[str, PropagationReport],
) -> CompletionState:
    for delta_id in delta_ids:
        report = reports.get(delta_id)
        if report is None or not report.fully_dispositioned:
            return CompletionState.WORK_COMPLETE_PROPAGATION_PENDING
    return CompletionState.WORK_COMPLETE_PROPAGATION_VERIFIED


def stranded_learning(
    *,
    deltas: Sequence[KnowledgeDelta],
    receivers: Sequence[Receiver],
    acks: Iterable[ReceiverAck],
    propagation_cycle: int,
    age_days_by_delta: Mapping[str, int] | None = None,
) -> tuple[StrandedLearning, ...]:
    ack_by_key = explicit_ack_map(acks)
    age_days_by_delta = age_days_by_delta or {}
    out: list[StrandedLearning] = []
    for delta in deltas:
        for receiver in receivers:
            if not receiver_is_applicable(delta, receiver):
                continue
            if (receiver.receiver_id, delta.delta_id) in ack_by_key:
                continue
            stranded = False
            if delta.priority == "P0":
                stranded = propagation_cycle >= 1
            elif delta.priority == "P1":
                stranded = propagation_cycle >= 2
            else:
                stranded = age_days_by_delta.get(delta.delta_id, 0) >= 7
            if stranded:
                out.append(
                    StrandedLearning(
                        delta_id=delta.delta_id,
                        receiver_id=receiver.receiver_id,
                        priority=delta.priority,
                        reason="NO_EXPLICIT_DISPOSITION_WITHIN_THRESHOLD",
                    )
                )
    return tuple(out)


def superseded_receiver_state(
    *,
    old_delta_id: str,
    new_delta_id: str,
    existing_acks: Iterable[ReceiverAck],
) -> dict[str, str]:
    """Invalidate only dependent currentness; never transfer stale proof."""
    affected: dict[str, str] = {}
    for ack in existing_acks:
        if ack.delta_id == old_delta_id:
            affected[ack.receiver_id] = f"STALE_PENDING_REVALIDATION:{new_delta_id}"
    return affected
