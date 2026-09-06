"""FUSE Live Capability / Worker Attestation v1.

Separates worker definitions and registrations from currently usable runtime capacity.
A worker counts as live only when a fresh attestation belongs to the current capability
epoch and carries the proof required by its runtime state.

Provider-neutral and effect-free: this module consumes supplied receipts; it does not
spawn workers, call providers, grant authority, or manufacture liveness.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from hashlib import sha256
import json
from typing import Iterable

from federation.capability_truth_v1 import (
    CapabilityTruthRecord,
    ClaimKind,
    EvidenceRef,
    Maturity,
)

SCHEMA = "FUSE-LIVE-WORKER-ATTESTATION-V1"
VERSION = "1.0.0"


def _instant(value: str) -> datetime:
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("ATTESTATION_TIMESTAMP_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class WorkerState(IntEnum):
    REGISTERED = 10
    RUNTIME_AVAILABLE = 20
    TOOL_BOUND = 30
    MISSION_ASSIGNED = 40
    HEARTBEAT_VERIFIED = 50
    RESULT_VERIFIED = 60
    RETIRED = 90


@dataclass(frozen=True, slots=True)
class CapabilityEpoch:
    epoch_id: str
    subject: str
    observed_at: str
    expires_at: str
    source_ref: str
    valid: bool = True

    def validate(self) -> "CapabilityEpoch":
        if not self.epoch_id.strip() or not self.subject.strip() or not self.source_ref.strip():
            raise ValueError("CAPABILITY_EPOCH_IDENTITY_REQUIRED")
        observed = _instant(self.observed_at)
        expires = _instant(self.expires_at)
        if expires <= observed:
            raise ValueError("CAPABILITY_EPOCH_EXPIRY_INVALID")
        return self

    def current_at(self, now: str) -> bool:
        self.validate()
        point = _instant(now)
        return bool(self.valid and _instant(self.observed_at) <= point < _instant(self.expires_at))


@dataclass(frozen=True, slots=True)
class WorkerAttestation:
    attestation_id: str
    worker_id: str
    capability_id: str
    epoch_id: str
    state: WorkerState
    observed_at: str
    expires_at: str
    source_ref: str
    runtime_id: str = ""
    mission_id: str = ""
    tool_refs: tuple[str, ...] = ()
    heartbeat_ref: str = ""
    result_ref: str = ""
    independently_verified: bool = False

    def validate(self) -> "WorkerAttestation":
        if not all((self.attestation_id.strip(), self.worker_id.strip(), self.capability_id.strip(), self.epoch_id.strip(), self.source_ref.strip())):
            raise ValueError("WORKER_ATTESTATION_IDENTITY_REQUIRED")
        observed = _instant(self.observed_at)
        expires = _instant(self.expires_at)
        if expires <= observed:
            raise ValueError("WORKER_ATTESTATION_EXPIRY_INVALID")
        if self.state >= WorkerState.RUNTIME_AVAILABLE and not self.runtime_id.strip():
            raise ValueError("RUNTIME_STATE_REQUIRES_RUNTIME_ID")
        if self.state >= WorkerState.TOOL_BOUND and not self.tool_refs:
            raise ValueError("TOOL_BOUND_STATE_REQUIRES_TOOL_REF")
        if self.state >= WorkerState.MISSION_ASSIGNED and not self.mission_id.strip():
            raise ValueError("MISSION_ASSIGNED_STATE_REQUIRES_MISSION_ID")
        if self.state >= WorkerState.HEARTBEAT_VERIFIED and not self.heartbeat_ref.strip():
            raise ValueError("HEARTBEAT_STATE_REQUIRES_RECEIPT")
        if self.state >= WorkerState.RESULT_VERIFIED and not self.result_ref.strip():
            raise ValueError("RESULT_STATE_REQUIRES_RESULT_REF")
        return self


_STATE_TRUTH = {
    WorkerState.REGISTERED: (ClaimKind.ROLE_REGISTRATION, Maturity.DESIGNED),
    WorkerState.RUNTIME_AVAILABLE: (ClaimKind.HOST_RECEIPT, Maturity.HOSTED),
    WorkerState.TOOL_BOUND: (ClaimKind.HOST_RECEIPT, Maturity.HOSTED),
    WorkerState.MISSION_ASSIGNED: (ClaimKind.HOST_RECEIPT, Maturity.HOSTED),
    WorkerState.HEARTBEAT_VERIFIED: (ClaimKind.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING),
    WorkerState.RESULT_VERIFIED: (ClaimKind.BEHAVIOURAL_EVIDENCE, Maturity.BEHAVIOUR_VERIFIED),
}


@dataclass(frozen=True, slots=True)
class WorkerLivenessDecision:
    worker_id: str
    capability_id: str
    state: str
    worker_state: WorkerState
    epoch_id: str
    reasons: tuple[str, ...] = ()

    @property
    def live(self) -> bool:
        return self.state == "LIVE_WORKER"


class WorkerAttestationCourt:
    """Compile current-epoch worker receipts into Capability Truth evidence."""

    def decide(self, attestation: WorkerAttestation, epoch: CapabilityEpoch, *, now: str) -> WorkerLivenessDecision:
        attestation.validate(); epoch.validate()
        reasons: list[str] = []
        if attestation.state is WorkerState.RETIRED:
            reasons.append("WORKER_RETIRED")
        if attestation.epoch_id != epoch.epoch_id:
            reasons.append("ATTESTATION_EPOCH_MISMATCH")
        if epoch.subject != attestation.capability_id:
            reasons.append("EPOCH_CAPABILITY_SUBJECT_MISMATCH")
        if not epoch.current_at(now):
            reasons.append("CAPABILITY_EPOCH_NOT_CURRENT")
        point = _instant(now)
        if not (_instant(attestation.observed_at) <= point < _instant(attestation.expires_at)):
            reasons.append("WORKER_ATTESTATION_NOT_CURRENT")
        if attestation.state < WorkerState.HEARTBEAT_VERIFIED:
            reasons.append("HEARTBEAT_NOT_VERIFIED")
        return WorkerLivenessDecision(
            worker_id=attestation.worker_id,
            capability_id=attestation.capability_id,
            state="LIVE_WORKER" if not reasons else "NOT_LIVE",
            worker_state=attestation.state,
            epoch_id=epoch.epoch_id,
            reasons=tuple(reasons),
        )

    def to_evidence(self, attestation: WorkerAttestation, epoch: CapabilityEpoch, *, now: str) -> EvidenceRef:
        attestation.validate(); epoch.validate()
        if attestation.state is WorkerState.RETIRED:
            raise ValueError("RETIRED_WORKER_CANNOT_PRODUCE_CAPABILITY_EVIDENCE")
        kind, maturity = _STATE_TRUTH[attestation.state]
        current = bool(
            attestation.epoch_id == epoch.epoch_id
            and epoch.subject == attestation.capability_id
            and epoch.current_at(now)
            and _instant(attestation.observed_at) <= _instant(now) < _instant(attestation.expires_at)
        )
        proof_ref = attestation.source_ref
        if attestation.state >= WorkerState.HEARTBEAT_VERIFIED:
            proof_ref = attestation.heartbeat_ref
        if attestation.state >= WorkerState.RESULT_VERIFIED:
            proof_ref = attestation.result_ref
        return EvidenceRef(
            evidence_id=attestation.attestation_id,
            capability_id=attestation.capability_id,
            claim_kind=kind,
            source_ref=proof_ref,
            declared_maturity=maturity,
            fresh=current,
            independently_verified=attestation.independently_verified,
            metadata=(
                ("worker_id", attestation.worker_id),
                ("runtime_id", attestation.runtime_id),
                ("epoch_id", attestation.epoch_id),
                ("worker_state", attestation.state.name),
                ("attestation_source", attestation.source_ref),
            ),
        ).validate()

    def record_for_capability(
        self,
        capability_id: str,
        attestations: Iterable[WorkerAttestation],
        epoch: CapabilityEpoch,
        *,
        now: str,
    ) -> CapabilityTruthRecord:
        if epoch.subject != capability_id:
            raise ValueError("CAPABILITY_EPOCH_RECORD_SUBJECT_MISMATCH")
        evidence = tuple(
            self.to_evidence(item, epoch, now=now)
            for item in attestations
            if item.capability_id == capability_id and item.state is not WorkerState.RETIRED
        )
        return CapabilityTruthRecord(capability_id, evidence).validate()

    def live_workers(
        self,
        attestations: Iterable[WorkerAttestation],
        epoch: CapabilityEpoch,
        *,
        now: str,
    ) -> tuple[str, ...]:
        live = {
            item.worker_id
            for item in attestations
            if self.decide(item, epoch, now=now).live
        }
        return tuple(sorted(live))


__all__ = [
    "SCHEMA", "VERSION", "CapabilityEpoch", "WorkerAttestation", "WorkerAttestationCourt",
    "WorkerLivenessDecision", "WorkerState", "digest",
]
