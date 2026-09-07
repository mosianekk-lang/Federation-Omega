"""FUSE Owner Protection Guard v1.

A non-sovereign, provider-neutral continuation and anti-dilution court that protects
owner time and mission completion. It composes existing FUSE/ChatGov/Failure-to-Win
semantics; it does not create a scheduler, authority plane, proof store, memory root,
or provider runtime.

The guard exists to make several failure-prevention rules machine-checkable:

* a blocker may stop only its lane and dependency descendants;
* safe independent work must continue automatically;
* immediate work may not be deferred to a timer merely because another lane is held;
* an unchanged failed route may not be retried without a changed failure predicate;
* a frozen source candidate may not be mutated while its admission court is active;
* machine-resolvable work may not be handed back to the owner;
* an owner rescue of a machine-detectable failure requires a prevention binding;
* stale mission pointers must be reconciled before continuation;
* completion may be claimed only after required outcomes and required lanes are proven.

This module is effect-free. It only evaluates supplied state and emits a deterministic
receipt. Host enforcement is a separate proof dimension.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


SCHEMA = "FUSE-OWNER-PROTECTION-GUARD-V1"
VERSION = "1.0.0"


class LaneState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    OWNER_HELD = "OWNER_HELD"
    PROVIDER_HELD = "PROVIDER_HELD"
    DONE = "DONE"


class GuardDecision(str, Enum):
    CONTINUE_AUTOMATICALLY = "CONTINUE_AUTOMATICALLY"
    CONTINUE_RECOVERY = "CONTINUE_RECOVERY"
    CHANGED_ROUTE_REQUIRED = "CHANGED_ROUTE_REQUIRED"
    HOLD_BUILD_EPOCH = "HOLD_BUILD_EPOCH"
    RECONCILE_MISSION_POINTER = "RECONCILE_MISSION_POINTER"
    PREVENTION_BINDING_REQUIRED = "PREVENTION_BINDING_REQUIRED"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
    BLOCKED_IRREDUCIBLY = "BLOCKED_IRREDUCIBLY"
    ALLOW_VERIFIED_COMPLETE = "ALLOW_VERIFIED_COMPLETE"


@dataclass(frozen=True, slots=True)
class MissionLane:
    lane_id: str
    state: LaneState
    required: bool = True
    dependencies: tuple[str, ...] = ()
    safe: bool = True
    authorized: bool = True
    available: bool = True
    owner_only: bool = False
    blocker_id: str = ""
    recovery_exhausted: bool = False
    failure_fingerprint: str = ""
    prior_failure_fingerprint: str = ""
    failure_predicate_changed: bool = False
    retry_requested: bool = False
    proof_refs: tuple[str, ...] = ()

    @property
    def terminal(self) -> bool:
        return self.state is LaneState.DONE


@dataclass(frozen=True, slots=True)
class BuildEpochState:
    epoch_id: str = ""
    admission_in_progress: bool = False
    frozen_candidate_head: str = ""
    observed_candidate_head: str = ""
    scope_change_proposed: bool = False


@dataclass(frozen=True, slots=True)
class OwnerProtectionSnapshot:
    mission_id: str
    current_mission_id: str
    objective: str
    lanes: tuple[MissionLane, ...] = ()
    required_outcomes: tuple[str, ...] = ()
    proven_outcomes: tuple[str, ...] = ()
    objective_satisfied: bool = False
    completion_claim_requested: bool = False
    final_response_requested: bool = False
    scheduled_deferral_proposed: bool = False
    user_requested_schedule: bool = False
    global_halt_asserted: bool = False
    machine_resolvable_owner_tasks: tuple[str, ...] = ()
    genuine_owner_decisions: tuple[str, ...] = ()
    owner_rescue_incident: bool = False
    prevention_evidence_ref: str = ""
    irreducible_blocker: str = ""
    exhaustion_evidence_ref: str = ""
    build_epoch: BuildEpochState = field(default_factory=BuildEpochState)


@dataclass(frozen=True, slots=True)
class OwnerProtectionReceipt:
    schema: str
    version: str
    mission_id: str
    decision: GuardDecision
    violations: tuple[str, ...]
    executable_lanes: tuple[str, ...]
    blocked_lanes: tuple[str, ...]
    owner_decisions: tuple[str, ...]
    owner_tasks_rejected: tuple[str, ...]
    completion_verified: bool
    final_response_allowed: bool
    auto_continue_required: bool
    receipt_digest: str


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class OwnerProtectionGuard:
    """Fail-closed owner-burden and mission-continuation guard."""

    def evaluate(self, snapshot: OwnerProtectionSnapshot) -> OwnerProtectionReceipt:
        self._validate(snapshot)
        lanes = {lane.lane_id: lane for lane in snapshot.lanes}
        violations: list[str] = []

        stale_mission = bool(
            snapshot.current_mission_id
            and snapshot.current_mission_id != snapshot.mission_id
        )
        if stale_mission:
            violations.append(
                f"STALE_MISSION_POINTER:{snapshot.current_mission_id}->{snapshot.mission_id}"
            )

        ready = self._dependency_ready_lanes(snapshot.lanes, lanes)
        unchanged_retry = tuple(
            sorted(
                lane.lane_id
                for lane in snapshot.lanes
                if lane.retry_requested
                and lane.failure_fingerprint
                and lane.failure_fingerprint == lane.prior_failure_fingerprint
                and not lane.failure_predicate_changed
            )
        )
        if unchanged_retry:
            violations.append("UNCHANGED_FAILURE_ROUTE_RETRY:" + ",".join(unchanged_retry))
            ready = tuple(item for item in ready if item not in unchanged_retry)

        blocked = tuple(
            sorted(
                lane.lane_id
                for lane in snapshot.lanes
                if lane.state
                in {
                    LaneState.BLOCKED,
                    LaneState.FAILED,
                    LaneState.OWNER_HELD,
                    LaneState.PROVIDER_HELD,
                }
            )
        )

        if snapshot.global_halt_asserted and ready:
            violations.append("BLOCKER_SCOPE_LEAK:INDEPENDENT_READY_LANES=" + ",".join(ready))

        if (
            snapshot.scheduled_deferral_proposed
            and not snapshot.user_requested_schedule
            and ready
        ):
            violations.append("IMMEDIATE_WORK_DEFERRED_TO_SCHEDULE:" + ",".join(ready))

        epoch = snapshot.build_epoch
        build_epoch_violation = bool(
            epoch.admission_in_progress
            and (
                epoch.scope_change_proposed
                or (
                    epoch.frozen_candidate_head
                    and epoch.observed_candidate_head
                    and epoch.frozen_candidate_head != epoch.observed_candidate_head
                )
            )
        )
        if build_epoch_violation:
            violations.append(
                "BUILD_EPOCH_MUTATED_DURING_ADMISSION:"
                + (epoch.epoch_id or "UNIDENTIFIED_EPOCH")
            )

        if snapshot.machine_resolvable_owner_tasks:
            violations.append(
                "MACHINE_RESOLVABLE_WORK_OFFLOADED_TO_OWNER:"
                + ",".join(sorted(snapshot.machine_resolvable_owner_tasks))
            )

        prevention_missing = bool(
            snapshot.owner_rescue_incident and not snapshot.prevention_evidence_ref.strip()
        )
        if prevention_missing:
            violations.append("OWNER_RESCUE_PREVENTION_BINDING_MISSING")

        required_outcomes = set(snapshot.required_outcomes)
        proven_outcomes = set(snapshot.proven_outcomes)
        outcomes_complete = required_outcomes.issubset(proven_outcomes)
        required_lanes_complete = all(
            (not lane.required) or lane.terminal for lane in snapshot.lanes
        )
        completion_verified = bool(
            snapshot.objective_satisfied
            and outcomes_complete
            and required_lanes_complete
        )
        if snapshot.completion_claim_requested and not completion_verified:
            violations.append("PREMATURE_COMPLETION_CLAIM")

        # Decision priority is intentional: identity and build-epoch integrity precede
        # ordinary continuation; then prevention/ready work; completion comes only
        # after all machine-resolvable work is exhausted.
        if stale_mission:
            decision = GuardDecision.RECONCILE_MISSION_POINTER
        elif build_epoch_violation:
            decision = GuardDecision.HOLD_BUILD_EPOCH
        elif prevention_missing:
            decision = GuardDecision.PREVENTION_BINDING_REQUIRED
        elif ready or snapshot.machine_resolvable_owner_tasks:
            decision = GuardDecision.CONTINUE_AUTOMATICALLY
        elif unchanged_retry:
            decision = GuardDecision.CHANGED_ROUTE_REQUIRED
        elif completion_verified:
            decision = GuardDecision.ALLOW_VERIFIED_COMPLETE
        elif snapshot.genuine_owner_decisions:
            decision = GuardDecision.OWNER_DECISION_REQUIRED
        elif (
            snapshot.irreducible_blocker.strip()
            and snapshot.exhaustion_evidence_ref.strip()
            and all(
                lane.terminal or lane.recovery_exhausted or lane.owner_only
                for lane in snapshot.lanes
            )
        ):
            decision = GuardDecision.BLOCKED_IRREDUCIBLY
        else:
            decision = GuardDecision.CONTINUE_RECOVERY

        final_response_allowed = decision in {
            GuardDecision.ALLOW_VERIFIED_COMPLETE,
            GuardDecision.OWNER_DECISION_REQUIRED,
            GuardDecision.BLOCKED_IRREDUCIBLY,
        }
        auto_continue_required = not final_response_allowed

        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": snapshot.mission_id,
            "decision": decision.value,
            "violations": tuple(sorted(violations)),
            "executable_lanes": ready,
            "blocked_lanes": blocked,
            "owner_decisions": tuple(sorted(snapshot.genuine_owner_decisions)),
            "owner_tasks_rejected": tuple(sorted(snapshot.machine_resolvable_owner_tasks)),
            "completion_verified": completion_verified,
            "final_response_allowed": final_response_allowed,
            "auto_continue_required": auto_continue_required,
        }
        return OwnerProtectionReceipt(
            schema=SCHEMA,
            version=VERSION,
            mission_id=snapshot.mission_id,
            decision=decision,
            violations=tuple(sorted(violations)),
            executable_lanes=ready,
            blocked_lanes=blocked,
            owner_decisions=tuple(sorted(snapshot.genuine_owner_decisions)),
            owner_tasks_rejected=tuple(sorted(snapshot.machine_resolvable_owner_tasks)),
            completion_verified=completion_verified,
            final_response_allowed=final_response_allowed,
            auto_continue_required=auto_continue_required,
            receipt_digest=_digest(material),
        )

    @staticmethod
    def _dependency_ready_lanes(
        lane_list: Sequence[MissionLane],
        lanes: Mapping[str, MissionLane],
    ) -> tuple[str, ...]:
        ready: list[str] = []
        for lane in lane_list:
            if lane.state is not LaneState.READY:
                continue
            if not (lane.safe and lane.authorized and lane.available) or lane.owner_only:
                continue
            if all(lanes[dependency].terminal for dependency in lane.dependencies):
                ready.append(lane.lane_id)
        return tuple(sorted(ready))

    @staticmethod
    def _validate(snapshot: OwnerProtectionSnapshot) -> None:
        if not snapshot.mission_id.strip():
            raise ValueError("mission_id is required")
        if not snapshot.objective.strip():
            raise ValueError("objective is required")
        lane_ids = [lane.lane_id for lane in snapshot.lanes]
        if any(not lane_id.strip() for lane_id in lane_ids):
            raise ValueError("lane_id is required")
        if len(lane_ids) != len(set(lane_ids)):
            raise ValueError("duplicate lane_id")
        known = set(lane_ids)
        for lane in snapshot.lanes:
            missing = set(lane.dependencies) - known
            if missing:
                raise ValueError(
                    f"unknown lane dependency for {lane.lane_id}: {sorted(missing)}"
                )
            if lane.lane_id in lane.dependencies:
                raise ValueError("lane cannot depend on itself")


__all__ = [
    "BuildEpochState",
    "GuardDecision",
    "LaneState",
    "MissionLane",
    "OwnerProtectionGuard",
    "OwnerProtectionReceipt",
    "OwnerProtectionSnapshot",
]
