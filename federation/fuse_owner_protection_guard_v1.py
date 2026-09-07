"""FUSE Owner Protection Guard v1.

A non-sovereign, provider-neutral continuation and anti-dilution court that protects
owner time and mission completion. It composes existing FUSE/ChatGov/Failure-to-Win
semantics; it does not create a scheduler, authority plane, proof store, memory root,
or provider runtime.

The guard makes failure-prevention rules machine-checkable, including:
* dependency-scoped blocker radius and automatic safe-lane continuation;
* immediate work before unrequested timer deferral;
* changed-predicate retry and frozen build epochs;
* no machine-resolvable owner offload;
* owner-rescue prevention binding;
* stale mission reconciliation;
* completion only after required outcomes/lanes are proven; and
* PRE_OWNER_PROMPT / PRE_FINAL_RESPONSE interception of excuse-shaped output or
  platform-fault offload while safe materially different machine routes remain.

This module is effect-free. It evaluates supplied state and emits a deterministic
receipt. Host enforcement is a separate proof dimension.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence


SCHEMA = "FUSE-OWNER-PROTECTION-GUARD-V1"
VERSION = "1.3.0"


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
    INTERCEPT_ASSISTANT_OUTPUT = "INTERCEPT_ASSISTANT_OUTPUT"
    ALLOW_STATUS_ONLY = "ALLOW_STATUS_ONLY"
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

    # v1.3 output-protection inputs. These are supplied by routed hosts/controllers;
    # the guard does not infer provider authority or call providers itself.
    owner_prompt_proposed: bool = False
    status_only_requested: bool = False
    proposed_owner_message: str = ""
    assistant_excuse_signals: tuple[str, ...] = ()
    platform_fault_signals: tuple[str, ...] = ()
    known_safe_route_substitutions: tuple[str, ...] = ()
    attempted_route_substitutions: tuple[str, ...] = ()
    machine_routes_exhausted: bool = False


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
    """Fail-closed owner-burden, continuation, and output-interception guard."""

    _EXCUSE_PHRASES = (
        "you need to",
        "need you to",
        "please retry",
        "try again later",
        "i cannot",
        "i can't",
        "cannot complete",
        "can't complete",
        "waiting for",
        "blocked by",
        "not available",
        "unavailable",
    )

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

        untried_substitutions = tuple(
            sorted(
                set(snapshot.known_safe_route_substitutions)
                - set(snapshot.attempted_route_substitutions)
            )
        )
        for route in untried_substitutions:
            violations.append(f"KNOWN_SUBSTITUTE_ROUTE_NOT_ATTEMPTED:{route}")

        explicit_excuse_signals = tuple(
            sorted(
                {
                    signal.strip()
                    for signal in snapshot.assistant_excuse_signals
                    if signal.strip()
                }
            )
        )
        platform_faults = tuple(
            sorted(
                {
                    signal.strip()
                    for signal in snapshot.platform_fault_signals
                    if signal.strip()
                }
            )
        )
        message_signals = self._message_excuse_signals(snapshot.proposed_owner_message)
        excuse_signals = tuple(sorted(set(explicit_excuse_signals) | set(message_signals)))

        machine_debt_remains = bool(
            ready
            or snapshot.machine_resolvable_owner_tasks
            or untried_substitutions
            or (
                (excuse_signals or platform_faults)
                and not snapshot.machine_routes_exhausted
            )
        )

        owner_surface_proposed = bool(
            snapshot.final_response_requested
            or snapshot.owner_prompt_proposed
            or snapshot.proposed_owner_message.strip()
        )

        if owner_surface_proposed and machine_debt_remains and not snapshot.status_only_requested:
            if excuse_signals:
                violations.append(
                    "ASSISTANT_EXCUSE_SURFACE_ATTEMPT:" + ",".join(excuse_signals)
                )
            if platform_faults:
                violations.append(
                    "PLATFORM_FAULT_OFFLOADED_TO_OWNER:" + ",".join(platform_faults)
                )
            violations.append("PRE_FINAL_RESPONSE_MACHINE_DEBT_REMAINS")

        explanation_without_prevention = bool(
            owner_surface_proposed
            and (excuse_signals or platform_faults)
            and not snapshot.status_only_requested
            and not snapshot.prevention_evidence_ref.strip()
            and machine_debt_remains
        )
        if explanation_without_prevention:
            violations.append("EXPLANATION_WITHOUT_PREVENTION_BINDING")

        output_intercept = bool(
            owner_surface_proposed
            and machine_debt_remains
            and not snapshot.status_only_requested
            and not completion_verified
        )

        # Decision priority: identity/build integrity and owner-rescue prevention first;
        # then intercept excuse-shaped output before it reaches the owner.
        if stale_mission:
            decision = GuardDecision.RECONCILE_MISSION_POINTER
        elif build_epoch_violation:
            decision = GuardDecision.HOLD_BUILD_EPOCH
        elif prevention_missing:
            decision = GuardDecision.PREVENTION_BINDING_REQUIRED
        elif output_intercept:
            decision = GuardDecision.INTERCEPT_ASSISTANT_OUTPUT
        elif snapshot.status_only_requested and owner_surface_proposed:
            decision = GuardDecision.ALLOW_STATUS_ONLY
        elif ready or snapshot.machine_resolvable_owner_tasks or untried_substitutions:
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
            and not untried_substitutions
            and all(
                lane.terminal or lane.recovery_exhausted or lane.owner_only
                for lane in snapshot.lanes
            )
        ):
            decision = GuardDecision.BLOCKED_IRREDUCIBLY
        else:
            decision = GuardDecision.CONTINUE_RECOVERY

        final_response_allowed = decision in {
            GuardDecision.ALLOW_STATUS_ONLY,
            GuardDecision.ALLOW_VERIFIED_COMPLETE,
            GuardDecision.OWNER_DECISION_REQUIRED,
            GuardDecision.BLOCKED_IRREDUCIBLY,
        }
        auto_continue_required = decision not in {
            GuardDecision.ALLOW_VERIFIED_COMPLETE,
            GuardDecision.OWNER_DECISION_REQUIRED,
            GuardDecision.BLOCKED_IRREDUCIBLY,
        }

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

    @classmethod
    def _message_excuse_signals(cls, message: str) -> tuple[str, ...]:
        normalized = " ".join(message.lower().split())
        if not normalized:
            return ()
        return tuple(
            sorted(phrase for phrase in cls._EXCUSE_PHRASES if phrase in normalized)
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
