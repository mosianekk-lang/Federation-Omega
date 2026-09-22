from __future__ import annotations

"""Proof-bounded convergence from CapabilityTwin truth into Living State.

This module does not invent capability truth and does not probe providers.  It
classifies already-admitted CapabilityTwin observations, carries diagnostics
without promoting them into runtime proof, and uses the existing
LivingWorldModel.ingest_capability_twin adapter as the sole Living State write
path.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from evidenceops.caseforge.federation_capability_twin import CapabilityTwin, TwinState
from evidenceops.caseforge.federation_evolution_program import SYSTEM_PROFILES

from .model import LivingWorldModel


class EstateStatus(str, Enum):
    GREEN = "GREEN"
    UNBOUND = "UNBOUND"
    DORMANT = "DORMANT"
    STALE = "STALE"
    UNMEASURED = "UNMEASURED"


@dataclass(frozen=True, slots=True)
class UsageObservation:
    system_id: str
    invocation_count: int
    proof_ref: str

    def validate(self) -> "UsageObservation":
        if self.system_id not in SYSTEM_PROFILES:
            raise ValueError(f"unregistered Federation system: {self.system_id}")
        if self.invocation_count < 0:
            raise ValueError("invocation_count must be non-negative")
        if not self.proof_ref.strip():
            raise ValueError("usage observation requires proof_ref")
        return self


@dataclass(frozen=True, slots=True)
class ProbeObservation:
    """Diagnostic route evidence. Failed probes never become runtime state."""

    system_id: str
    probe_state: str
    proof_ref: str
    verified: bool

    def validate(self) -> "ProbeObservation":
        if self.system_id not in SYSTEM_PROFILES:
            raise ValueError(f"unregistered Federation system: {self.system_id}")
        if not self.probe_state.strip() or not self.proof_ref.strip():
            raise ValueError("probe_state and proof_ref are required")
        return self


@dataclass(frozen=True, slots=True)
class EstateRow:
    system_id: str
    status: EstateStatus
    twin_state: str
    runtime_state: str
    invocation_count: int | None
    proof_refs: tuple[str, ...]
    diagnostics: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EstateConvergenceReport:
    rows: tuple[EstateRow, ...]
    counts: Mapping[str, int]
    living_state_event_count: int
    living_state_event_head: str
    report_sha256: str
    authority_ceiling: str = "A1_INTERNAL"
    external_effects: int = 0


def classify_twin(twin: CapabilityTwin, usage: UsageObservation | None = None) -> tuple[EstateStatus, tuple[str, ...]]:
    twin.validate()
    state = twin.twin_state
    if usage is not None:
        usage.validate()
        if usage.system_id != twin.system_id:
            raise ValueError("usage observation system does not match twin")

    if state is TwinState.STALE:
        return EstateStatus.STALE, ("CAPABILITY_TWIN_STALE",)
    if state in {TwinState.RUNTIME_VERIFIED, TwinState.PROVIDER_VERIFIED}:
        if usage is not None and usage.invocation_count == 0:
            return EstateStatus.DORMANT, ("RUNTIME_BOUND_EXPLICIT_ZERO_INVOCATIONS",)
        return EstateStatus.GREEN, (
            "RUNTIME_SEMANTIC_READBACK_VERIFIED",
            "INVOCATION_UNMEASURED" if usage is None else "INVOCATION_OBSERVED",
        )
    if state in {
        TwinState.SOURCE_VERIFIED_RUNTIME_UNVERIFIED,
        TwinState.CANONICAL_VERIFIED_ADAPTER_REQUIRED,
        TwinState.SOURCE_AND_TESTS_VERIFIED_RUNTIME_UNBOUND,
        TwinState.RUNTIME_PARTIAL,
    }:
        return EstateStatus.UNBOUND, (f"TWIN_STATE:{state.value}",)
    return EstateStatus.UNMEASURED, (f"TWIN_STATE:{state.value}",)


def converge_estate(
    twins: Sequence[CapabilityTwin] = (),
    *,
    usage: Sequence[UsageObservation] = (),
    probes: Sequence[ProbeObservation] = (),
) -> tuple[LivingWorldModel, EstateConvergenceReport]:
    twin_map: dict[str, CapabilityTwin] = {}
    for twin in twins:
        twin.validate()
        if twin.system_id not in SYSTEM_PROFILES:
            raise ValueError(f"unregistered Federation system: {twin.system_id}")
        if twin.system_id in twin_map:
            raise ValueError(f"duplicate twin: {twin.system_id}")
        twin_map[twin.system_id] = twin

    usage_map: dict[str, UsageObservation] = {}
    for item in usage:
        item.validate()
        if item.system_id in usage_map:
            raise ValueError(f"duplicate usage observation: {item.system_id}")
        usage_map[item.system_id] = item

    probe_map: dict[str, list[ProbeObservation]] = {}
    for probe in probes:
        probe.validate()
        probe_map.setdefault(probe.system_id, []).append(probe)

    model = LivingWorldModel()
    rows: list[EstateRow] = []
    for system_id in sorted(SYSTEM_PROFILES):
        twin = twin_map.get(system_id)
        diagnostics = tuple(
            sorted(f"PROBE:{p.probe_state}:{'VERIFIED' if p.verified else 'NOT_VERIFIED'}:{p.proof_ref}" for p in probe_map.get(system_id, ()))
        )
        if twin is None:
            reasons = ["NO_ADMITTED_CAPABILITY_TWIN"]
            if diagnostics:
                reasons.append("DIAGNOSTIC_PROBE_DOES_NOT_PROMOTE_RUNTIME_STATE")
            rows.append(EstateRow(
                system_id=system_id,
                status=EstateStatus.UNMEASURED,
                twin_state="NO_TWIN",
                runtime_state="UNKNOWN",
                invocation_count=None,
                proof_refs=tuple(sorted(p.proof_ref for p in probe_map.get(system_id, ()))),
                diagnostics=diagnostics,
                reason_codes=tuple(reasons),
            ))
            continue

        model.ingest_capability_twin(twin)
        item_usage = usage_map.get(system_id)
        status, reasons = classify_twin(twin, item_usage)
        proof_refs = {twin.proof_ref}
        if twin.provider_readback_ref:
            proof_refs.add(twin.provider_readback_ref)
        if item_usage is not None:
            proof_refs.add(item_usage.proof_ref)
        proof_refs.update(p.proof_ref for p in probe_map.get(system_id, ()))
        rows.append(EstateRow(
            system_id=system_id,
            status=status,
            twin_state=twin.twin_state.value,
            runtime_state=twin.runtime_state.value,
            invocation_count=None if item_usage is None else item_usage.invocation_count,
            proof_refs=tuple(sorted(ref for ref in proof_refs if ref)),
            diagnostics=diagnostics,
            reason_codes=reasons,
        ))

    counts = {status.value: sum(row.status is status for row in rows) for status in EstateStatus}
    payload = {
        "rows": [asdict(row) for row in rows],
        "counts": counts,
        "living_state_event_count": model.event_count,
        "living_state_event_head": model.event_head_digest,
        "authority_ceiling": model.authority_ceiling,
        "external_effects": model.external_effects,
    }
    report_sha = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    report = EstateConvergenceReport(
        rows=tuple(rows),
        counts=counts,
        living_state_event_count=model.event_count,
        living_state_event_head=model.event_head_digest,
        report_sha256=report_sha,
        authority_ceiling=model.authority_ceiling,
        external_effects=model.external_effects,
    )
    return model, report


__all__ = [
    "EstateConvergenceReport",
    "EstateRow",
    "EstateStatus",
    "ProbeObservation",
    "UsageObservation",
    "classify_twin",
    "converge_estate",
]
