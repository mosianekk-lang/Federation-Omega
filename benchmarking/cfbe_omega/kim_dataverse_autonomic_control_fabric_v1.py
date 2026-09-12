from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import (
    EventClass,
    MaintenanceEvent,
    OwnerBoundary,
    owner_interruption_firewall,
)


class LaneState(str, Enum):
    READY = "READY"
    HELD = "HELD"
    OWNER_REQUIRED = "OWNER_REQUIRED"
    DELEGATED = "DELEGATED"


@dataclass(frozen=True)
class AutonomicEvent:
    event_id: str
    event_class: EventClass
    lane_id: str
    self_resolvable: bool
    reversible: bool
    external_effect: bool = False
    owner_boundary: OwnerBoundary = OwnerBoundary.NONE
    failure_fingerprint: str | None = None
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaneDecision:
    event_id: str
    lane_id: str
    state: LaneState
    route: str
    owner_interrupt: bool
    continue_other_lanes: bool


@dataclass(frozen=True)
class AutonomicWave:
    decisions: tuple[LaneDecision, ...]
    owner_interruptions: tuple[str, ...]
    independent_lanes_continue: bool
    external_effect_authorized: bool = False

    def receipt(self) -> str:
        payload = {
            "decisions": [d.__dict__ | {"state": d.state.value} for d in self.decisions],
            "owner_interruptions": list(self.owner_interruptions),
            "independent_lanes_continue": self.independent_lanes_continue,
            "external_effect_authorized": self.external_effect_authorized,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()


ROUTES = {
    EventClass.MISSION: "BCO_PRIME_POLICY_MARKET_TO_SOL",
    EventClass.MAINTENANCE: "AUTOFIX_BUBBLES_ENGINEERING_TO_PROOFOS",
    EventClass.RECOVERY: "FAILURE_WIN_SOVARA_OR_LOCAL_RECOVERY",
    EventClass.EVOLUTION: "CFBE_CHALLENGER_TO_SHADOW_COURT",
}


def classify_and_route(event: AutonomicEvent) -> LaneDecision:
    gate = owner_interruption_firewall(
        MaintenanceEvent(
            event_id=event.event_id,
            event_class=event.event_class,
            self_resolvable=event.self_resolvable,
            reversible=event.reversible,
            external_effect=event.external_effect,
            owner_boundary=event.owner_boundary,
            affected_lanes=(event.lane_id,),
        )
    )
    if gate.interrupt_owner:
        return LaneDecision(
            event.event_id,
            event.lane_id,
            LaneState.OWNER_REQUIRED,
            "OWNER_AUTHORITY_FIREWALL",
            True,
            gate.continue_independent_lanes,
        )
    if event.event_class == EventClass.MAINTENANCE and event.self_resolvable and event.reversible:
        state = LaneState.DELEGATED
    elif event.event_class in {EventClass.RECOVERY, EventClass.EVOLUTION, EventClass.MISSION}:
        state = LaneState.DELEGATED
    else:
        state = LaneState.HELD
    return LaneDecision(
        event.event_id,
        event.lane_id,
        state,
        ROUTES[event.event_class],
        False,
        True,
    )


def compile_autonomic_wave(events: Sequence[AutonomicEvent]) -> AutonomicWave:
    ids = [event.event_id for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate event_id")
    decisions = tuple(classify_and_route(event) for event in events)
    owner_interruptions = tuple(d.event_id for d in decisions if d.owner_interrupt)
    return AutonomicWave(
        decisions=decisions,
        owner_interruptions=owner_interruptions,
        independent_lanes_continue=all(d.continue_other_lanes for d in decisions),
        external_effect_authorized=False,
    )


def maintenance_incident_from_ci(
    *,
    run_id: str,
    lane_id: str,
    failure_fingerprint: str,
    reversible: bool = True,
) -> AutonomicEvent:
    if not run_id or not failure_fingerprint:
        raise ValueError("run_id and failure_fingerprint are required")
    return AutonomicEvent(
        event_id=f"ci:{run_id}:{failure_fingerprint[:16]}",
        event_class=EventClass.MAINTENANCE,
        lane_id=lane_id,
        self_resolvable=True,
        reversible=reversible,
        external_effect=False,
        owner_boundary=OwnerBoundary.NONE,
        failure_fingerprint=failure_fingerprint,
    )


def provider_authority_event(*, event_id: str, lane_id: str) -> AutonomicEvent:
    return AutonomicEvent(
        event_id=event_id,
        event_class=EventClass.RECOVERY,
        lane_id=lane_id,
        self_resolvable=False,
        reversible=True,
        external_effect=False,
        owner_boundary=OwnerBoundary.AUTHORITY,
    )


def summarize_wave(wave: AutonomicWave) -> Mapping[str, object]:
    return {
        "event_count": len(wave.decisions),
        "delegated": sum(d.state == LaneState.DELEGATED for d in wave.decisions),
        "owner_required": sum(d.state == LaneState.OWNER_REQUIRED for d in wave.decisions),
        "held": sum(d.state == LaneState.HELD for d in wave.decisions),
        "independent_lanes_continue": wave.independent_lanes_continue,
        "external_effect_authorized": wave.external_effect_authorized,
        "receipt": wave.receipt(),
    }
