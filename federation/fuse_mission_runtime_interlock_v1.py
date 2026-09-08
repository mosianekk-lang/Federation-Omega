"""Deterministic FUSE mission-runtime liveness and terminal interlock v1.

This is a non-sovereign enforcement adapter. It composes the admitted
OwnerProtectionGuard and ChatGov PRE_FINAL_RESPONSE gate; it does not create a
new mission truth store, scheduler, authority plane, proof store, or provider
runtime. Hosts supply current mission/task/proof state and must obey the emitted
next action or terminal verdict.

The primary invariant is simple: a model/worker may propose completion, but only
this interlock may authorize a terminal commit, and only after all required work
and current proof are closed under the same mission epoch/ledger tail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping

from federation.fuse_owner_protection_guard_v1 import (
    GuardDecision,
    LaneState,
    MissionLane,
    OwnerProtectionGuard,
    OwnerProtectionSnapshot,
)
from bubbles.chat_governor_omega3.pre_final import (
    GapState,
    MissionClosureState,
    PreFinalGate,
    TerminalState,
)

SCHEMA = "FUSE-MISSION-RUNTIME-INTERLOCK-V1"
VERSION = "1.0.0"


class RuntimeTaskState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    OWNER_HELD = "OWNER_HELD"
    PROVIDER_HELD = "PROVIDER_HELD"
    EFFECT_AMBIGUOUS = "EFFECT_AMBIGUOUS"
    READBACK_PENDING = "READBACK_PENDING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class RuntimeAction(str, Enum):
    DISPATCH_TASK = "DISPATCH_TASK"
    RECOVER_ORPHAN = "RECOVER_ORPHAN"
    READBACK_EFFECT = "READBACK_EFFECT"
    REVERIFY_PROOF = "REVERIFY_PROOF"
    REJECT_OWNER_HANDOFF = "REJECT_OWNER_HANDOFF"
    CONTINUE_RECOVERY = "CONTINUE_RECOVERY"
    ALLOW_STATUS_CONTINUE = "ALLOW_STATUS_CONTINUE"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
    BLOCKED_IRREDUCIBLY = "BLOCKED_IRREDUCIBLY"
    PREPARE_TERMINAL = "PREPARE_TERMINAL"
    TERMINAL_COMMIT_CONFLICT = "TERMINAL_COMMIT_CONFLICT"
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"


@dataclass(frozen=True, slots=True)
class ProofBinding:
    proof_id: str
    task_id: str
    dependency: str
    bound_epoch: str
    current_epoch: str
    fresh: bool = True

    @property
    def valid(self) -> bool:
        return bool(
            self.proof_id.strip()
            and self.task_id.strip()
            and self.dependency.strip()
            and self.fresh
            and self.bound_epoch == self.current_epoch
        )


@dataclass(frozen=True, slots=True)
class RuntimeTask:
    task_id: str
    state: RuntimeTaskState
    required: bool = True
    dependencies: tuple[str, ...] = ()
    safe: bool = True
    authorized: bool = True
    available: bool = True
    owner_only: bool = False
    priority: int = 0
    lease_expires_at_epoch: float = 0.0
    heartbeat_at_epoch: float = 0.0
    heartbeat_ttl_seconds: float = 120.0
    effect_id: str = ""
    effect_possible: bool = False
    required_proof_ids: tuple[str, ...] = ()
    recovery_exhausted: bool = False


@dataclass(frozen=True, slots=True)
class MissionRuntimeSnapshot:
    mission_id: str
    current_mission_id: str
    objective: str
    contract_epoch: int
    ledger_tail: int
    tasks: tuple[RuntimeTask, ...] = ()
    proofs: tuple[ProofBinding, ...] = ()
    objective_satisfied: bool = False
    completion_claim_requested: bool = False
    candidate_response: str = ""
    status_only_requested: bool = False
    proposed_owner_message: str = ""
    genuine_owner_decisions: tuple[str, ...] = ()
    irreducible_blocker: str = ""
    exhaustion_evidence_ref: str = ""


@dataclass(frozen=True, slots=True)
class TerminalPrepareReceipt:
    schema: str
    version: str
    mission_id: str
    contract_epoch: int
    ledger_tail: int
    state_digest: str


@dataclass(frozen=True, slots=True)
class MissionRuntimeDecision:
    schema: str
    version: str
    mission_id: str
    action: RuntimeAction
    next_task_id: str
    reasons: tuple[str, ...]
    final_response_allowed: bool
    auto_continue_required: bool
    completion_verified: bool
    owner_guard_decision: str
    pre_final_mode: str
    prepare: TerminalPrepareReceipt | None
    receipt_digest: str


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class MissionRuntimeInterlock:
    """Pure reducer for liveness, manualization, proof currentness, and terminality."""

    def __init__(
        self,
        *,
        owner_guard: OwnerProtectionGuard | None = None,
        pre_final_gate: PreFinalGate | None = None,
    ) -> None:
        self.owner_guard = owner_guard or OwnerProtectionGuard()
        self.pre_final_gate = pre_final_gate or PreFinalGate()

    def decide(
        self,
        snapshot: MissionRuntimeSnapshot,
        *,
        now_epoch: float,
    ) -> MissionRuntimeDecision:
        facts = self._facts(snapshot, now_epoch=now_epoch)
        owner_receipt, pre_final = self._control_receipts(snapshot, facts)

        # Status is a UI event, not a mission terminal event. Permit the response
        # while keeping the mission live and carrying the best next machine action.
        if snapshot.status_only_requested:
            next_task = self._best_ready(facts["ready_tasks"])
            return self._decision(
                snapshot,
                RuntimeAction.ALLOW_STATUS_CONTINUE,
                next_task_id=next_task.task_id if next_task else "",
                reasons=("STATUS_ONLY_DOES_NOT_TERMINATE_MISSION",),
                final_response_allowed=True,
                auto_continue_required=not facts["terminal_ready"],
                completion_verified=False,
                owner_guard_decision=owner_receipt.decision.value,
                pre_final_mode=pre_final.mode,
            )

        if facts["ambiguous_effect_tasks"]:
            task = self._best_priority(facts["ambiguous_effect_tasks"])
            return self._blocked_decision(
                snapshot,
                RuntimeAction.READBACK_EFFECT,
                task.task_id,
                ("AMBIGUOUS_EFFECT_REQUIRES_PROVIDER_READBACK_BEFORE_RETRY",),
                owner_receipt.decision.value,
                pre_final.mode,
            )

        if facts["orphan_effect_tasks"]:
            task = self._best_priority(facts["orphan_effect_tasks"])
            return self._blocked_decision(
                snapshot,
                RuntimeAction.READBACK_EFFECT,
                task.task_id,
                ("ORPHAN_WITH_POSSIBLE_EFFECT_REQUIRES_READBACK",),
                owner_receipt.decision.value,
                pre_final.mode,
            )

        if facts["orphan_tasks"]:
            task = self._best_priority(facts["orphan_tasks"])
            return self._blocked_decision(
                snapshot,
                RuntimeAction.RECOVER_ORPHAN,
                task.task_id,
                ("EXPIRED_WORKER_LEASE_RECLAIMABLE_WITHOUT_EFFECT_RETRY",),
                owner_receipt.decision.value,
                pre_final.mode,
            )

        if facts["stale_proof_tasks"]:
            task = self._best_priority(facts["stale_proof_tasks"])
            return self._blocked_decision(
                snapshot,
                RuntimeAction.REVERIFY_PROOF,
                task.task_id,
                ("STALE_OR_EPOCH_MISMATCHED_PROOF_INVALIDATES_TASK_TERMINALITY",),
                owner_receipt.decision.value,
                pre_final.mode,
            )

        if facts["machine_owner_handoffs"]:
            task = self._best_priority(facts["machine_owner_handoffs"])
            return self._blocked_decision(
                snapshot,
                RuntimeAction.REJECT_OWNER_HANDOFF,
                task.task_id,
                ("MACHINE_RESOLVABLE_OWNER_HANDOFF_REJECTED",),
                owner_receipt.decision.value,
                pre_final.mode,
            )

        if facts["ready_tasks"]:
            task = self._best_ready(facts["ready_tasks"])
            return self._blocked_decision(
                snapshot,
                RuntimeAction.DISPATCH_TASK,
                task.task_id if task else "",
                ("REQUIRED_MACHINE_WORK_REMAINS",),
                owner_receipt.decision.value,
                pre_final.mode,
            )

        if facts["terminal_ready"]:
            prepare = self.prepare_terminal(snapshot, now_epoch=now_epoch)
            return self._decision(
                snapshot,
                RuntimeAction.PREPARE_TERMINAL,
                next_task_id="",
                reasons=("TWO_PHASE_TERMINAL_PREPARE_REQUIRED",),
                final_response_allowed=False,
                auto_continue_required=True,
                completion_verified=False,
                owner_guard_decision=owner_receipt.decision.value,
                pre_final_mode=pre_final.mode,
                prepare=prepare,
            )

        if snapshot.genuine_owner_decisions and not facts["machine_work_exists"]:
            return self._decision(
                snapshot,
                RuntimeAction.OWNER_DECISION_REQUIRED,
                next_task_id="",
                reasons=("GENUINE_OWNER_ONLY_DECISION_REMAINS",),
                final_response_allowed=True,
                auto_continue_required=False,
                completion_verified=False,
                owner_guard_decision=owner_receipt.decision.value,
                pre_final_mode=pre_final.mode,
            )

        if (
            snapshot.irreducible_blocker.strip()
            and snapshot.exhaustion_evidence_ref.strip()
            and not facts["machine_work_exists"]
            and all(task.recovery_exhausted or task.owner_only or self._verified_done(task, facts["proofs_by_id"]) for task in snapshot.tasks)
        ):
            return self._decision(
                snapshot,
                RuntimeAction.BLOCKED_IRREDUCIBLY,
                next_task_id="",
                reasons=("ROUTE_EXHAUSTION_PROVED",),
                final_response_allowed=True,
                auto_continue_required=False,
                completion_verified=False,
                owner_guard_decision=owner_receipt.decision.value,
                pre_final_mode=pre_final.mode,
            )

        return self._blocked_decision(
            snapshot,
            RuntimeAction.CONTINUE_RECOVERY,
            "",
            ("NONTERMINAL_MISSION_HAS_NO_VALID_STOP_STATE",),
            owner_receipt.decision.value,
            pre_final.mode,
        )

    def prepare_terminal(
        self,
        snapshot: MissionRuntimeSnapshot,
        *,
        now_epoch: float,
    ) -> TerminalPrepareReceipt:
        facts = self._facts(snapshot, now_epoch=now_epoch)
        if not facts["terminal_ready"]:
            raise ValueError("TERMINAL_PREPARE_REQUIRES_ZERO_REQUIRED_DEBT")
        state_digest = self._state_digest(snapshot, facts["proofs_by_id"])
        return TerminalPrepareReceipt(
            schema=SCHEMA,
            version=VERSION,
            mission_id=snapshot.mission_id,
            contract_epoch=snapshot.contract_epoch,
            ledger_tail=snapshot.ledger_tail,
            state_digest=state_digest,
        )

    def commit_terminal(
        self,
        snapshot: MissionRuntimeSnapshot,
        prepare: TerminalPrepareReceipt,
        *,
        now_epoch: float,
    ) -> MissionRuntimeDecision:
        facts = self._facts(snapshot, now_epoch=now_epoch)
        owner_receipt, pre_final = self._control_receipts(snapshot, facts)
        observed_digest = self._state_digest(snapshot, facts["proofs_by_id"])
        conflict = bool(
            prepare.schema != SCHEMA
            or prepare.version != VERSION
            or prepare.mission_id != snapshot.mission_id
            or prepare.contract_epoch != snapshot.contract_epoch
            or prepare.ledger_tail != snapshot.ledger_tail
            or prepare.state_digest != observed_digest
        )
        if conflict or not facts["terminal_ready"]:
            return self._blocked_decision(
                snapshot,
                RuntimeAction.TERMINAL_COMMIT_CONFLICT,
                "",
                ("TERMINAL_COMPARE_AND_SWAP_PRECONDITION_CHANGED",),
                owner_receipt.decision.value,
                pre_final.mode,
            )
        if not owner_receipt.final_response_allowed or not pre_final.allow_final:
            return self._blocked_decision(
                snapshot,
                RuntimeAction.TERMINAL_COMMIT_CONFLICT,
                "",
                ("UNDERLYING_FUSE_TERMINAL_CONTROLS_DID_NOT_ALLOW_FINAL",),
                owner_receipt.decision.value,
                pre_final.mode,
            )
        return self._decision(
            snapshot,
            RuntimeAction.COMPLETE_VERIFIED,
            next_task_id="",
            reasons=("TERMINAL_COMPARE_AND_SWAP_COMMITTED",),
            final_response_allowed=True,
            auto_continue_required=False,
            completion_verified=True,
            owner_guard_decision=owner_receipt.decision.value,
            pre_final_mode=pre_final.mode,
        )

    def _facts(self, snapshot: MissionRuntimeSnapshot, *, now_epoch: float) -> dict[str, object]:
        self._validate(snapshot)
        proofs_by_id = {proof.proof_id: proof for proof in snapshot.proofs}
        tasks_by_id = {task.task_id: task for task in snapshot.tasks}

        verified_done = {
            task.task_id
            for task in snapshot.tasks
            if self._verified_done(task, proofs_by_id)
        }
        stale_proof_tasks = tuple(
            task
            for task in snapshot.tasks
            if task.state is RuntimeTaskState.DONE
            and task.required_proof_ids
            and task.task_id not in verified_done
        )
        ready_tasks = tuple(
            task
            for task in snapshot.tasks
            if task.state is RuntimeTaskState.READY
            and task.safe
            and task.authorized
            and task.available
            and not task.owner_only
            and all(dependency in verified_done for dependency in task.dependencies)
        )
        ambiguous_effect_tasks = tuple(
            task
            for task in snapshot.tasks
            if task.state in {RuntimeTaskState.EFFECT_AMBIGUOUS, RuntimeTaskState.READBACK_PENDING}
        )
        orphan_effect_tasks: list[RuntimeTask] = []
        orphan_tasks: list[RuntimeTask] = []
        for task in snapshot.tasks:
            if task.state is not RuntimeTaskState.RUNNING:
                continue
            lease_expired = bool(task.lease_expires_at_epoch and now_epoch >= task.lease_expires_at_epoch)
            heartbeat_expired = bool(
                task.heartbeat_at_epoch
                and task.heartbeat_ttl_seconds >= 0
                and now_epoch >= task.heartbeat_at_epoch + task.heartbeat_ttl_seconds
            )
            if lease_expired or heartbeat_expired:
                (orphan_effect_tasks if task.effect_possible or task.effect_id else orphan_tasks).append(task)

        machine_owner_handoffs = tuple(
            task
            for task in snapshot.tasks
            if task.state is RuntimeTaskState.OWNER_HELD
            and not task.owner_only
            and task.safe
            and task.authorized
            and task.available
        )
        required_incomplete = tuple(
            task
            for task in snapshot.tasks
            if task.required and task.task_id not in verified_done
        )
        machine_work_exists = bool(
            ready_tasks
            or ambiguous_effect_tasks
            or orphan_effect_tasks
            or orphan_tasks
            or stale_proof_tasks
            or machine_owner_handoffs
            or any(
                task.required
                and not task.owner_only
                and not task.recovery_exhausted
                and task.task_id not in verified_done
                for task in snapshot.tasks
            )
        )
        terminal_ready = bool(
            snapshot.objective_satisfied
            and not required_incomplete
            and not ambiguous_effect_tasks
            and not orphan_effect_tasks
            and not orphan_tasks
            and not machine_owner_handoffs
        )
        return {
            "tasks_by_id": tasks_by_id,
            "proofs_by_id": proofs_by_id,
            "verified_done": verified_done,
            "stale_proof_tasks": stale_proof_tasks,
            "ready_tasks": ready_tasks,
            "ambiguous_effect_tasks": ambiguous_effect_tasks,
            "orphan_effect_tasks": tuple(orphan_effect_tasks),
            "orphan_tasks": tuple(orphan_tasks),
            "machine_owner_handoffs": machine_owner_handoffs,
            "required_incomplete": required_incomplete,
            "machine_work_exists": machine_work_exists,
            "terminal_ready": terminal_ready,
        }

    def _control_receipts(self, snapshot: MissionRuntimeSnapshot, facts: Mapping[str, object]):
        proofs_by_id = facts["proofs_by_id"]
        assert isinstance(proofs_by_id, dict)
        lanes = tuple(self._to_lane(task, proofs_by_id) for task in snapshot.tasks)
        machine_owner_tasks = tuple(
            task.task_id for task in facts["machine_owner_handoffs"]  # type: ignore[index]
        )
        required = tuple(task.task_id for task in snapshot.tasks if task.required)
        proven = tuple(sorted(facts["verified_done"]))  # type: ignore[arg-type]
        owner_snapshot = OwnerProtectionSnapshot(
            mission_id=snapshot.mission_id,
            current_mission_id=snapshot.current_mission_id,
            objective=snapshot.objective,
            lanes=lanes,
            required_outcomes=required,
            proven_outcomes=proven,
            objective_satisfied=snapshot.objective_satisfied,
            completion_claim_requested=snapshot.completion_claim_requested,
            final_response_requested=True,
            status_only_requested=snapshot.status_only_requested,
            proposed_owner_message=snapshot.proposed_owner_message or snapshot.candidate_response,
            machine_resolvable_owner_tasks=machine_owner_tasks,
            genuine_owner_decisions=snapshot.genuine_owner_decisions,
            irreducible_blocker=snapshot.irreducible_blocker,
            exhaustion_evidence_ref=snapshot.exhaustion_evidence_ref,
            machine_routes_exhausted=not bool(facts["machine_work_exists"]),
        )
        owner_receipt = self.owner_guard.evaluate(owner_snapshot)

        gaps = tuple(
            GapState(
                gap_id=task.task_id,
                summary=f"runtime task {task.task_id}",
                material=task.required,
                route_known=task.available,
                safe=task.safe,
                authorized=task.authorized,
                available=task.available,
                recovery_exhausted=task.recovery_exhausted,
                owner_only=task.owner_only,
            )
            for task in snapshot.tasks
            if task.task_id not in facts["verified_done"]  # type: ignore[operator]
        )
        terminal_state = TerminalState.ACTIVE
        if facts["terminal_ready"]:
            terminal_state = TerminalState.VERIFIED_COMPLETE
        elif snapshot.genuine_owner_decisions and not facts["machine_work_exists"]:
            terminal_state = TerminalState.OWNER_DECISION_REQUIRED
        elif (
            snapshot.irreducible_blocker.strip()
            and snapshot.exhaustion_evidence_ref.strip()
            and not facts["machine_work_exists"]
        ):
            terminal_state = TerminalState.BLOCKED_IRREDUCIBLY
        pre_final = self.pre_final_gate.evaluate(
            mission=MissionClosureState(
                mission_id=snapshot.mission_id,
                objective=snapshot.objective,
                terminal_state=terminal_state,
                objective_satisfied=snapshot.objective_satisfied,
                gaps=gaps,
                owner_decision_request=(snapshot.genuine_owner_decisions[0] if snapshot.genuine_owner_decisions else ""),
                irreducible_blocker=snapshot.irreducible_blocker,
                exhaustion_evidence_ref=snapshot.exhaustion_evidence_ref,
                currently_executable_work=bool(facts["machine_work_exists"]),
                outcome_first_continue_recovery=bool(facts["machine_work_exists"] and not facts["terminal_ready"]),
            ),
            candidate_response=snapshot.candidate_response,
        )
        return owner_receipt, pre_final

    @staticmethod
    def _to_lane(task: RuntimeTask, proofs_by_id: Mapping[str, ProofBinding]) -> MissionLane:
        state = task.state
        if state is RuntimeTaskState.DONE and not MissionRuntimeInterlock._verified_done(task, proofs_by_id):
            lane_state = LaneState.READY
        else:
            lane_state = {
                RuntimeTaskState.READY: LaneState.READY,
                RuntimeTaskState.RUNNING: LaneState.RUNNING,
                RuntimeTaskState.DONE: LaneState.DONE,
                RuntimeTaskState.BLOCKED: LaneState.BLOCKED,
                RuntimeTaskState.FAILED: LaneState.FAILED,
                RuntimeTaskState.OWNER_HELD: LaneState.OWNER_HELD,
                RuntimeTaskState.PROVIDER_HELD: LaneState.PROVIDER_HELD,
                RuntimeTaskState.EFFECT_AMBIGUOUS: LaneState.BLOCKED,
                RuntimeTaskState.READBACK_PENDING: LaneState.BLOCKED,
                RuntimeTaskState.RECOVERY_REQUIRED: LaneState.FAILED,
            }[state]
        return MissionLane(
            lane_id=task.task_id,
            state=lane_state,
            required=task.required,
            dependencies=task.dependencies,
            safe=task.safe,
            authorized=task.authorized,
            available=task.available,
            owner_only=task.owner_only,
            recovery_exhausted=task.recovery_exhausted,
            proof_refs=task.required_proof_ids,
        )

    @staticmethod
    def _verified_done(task: RuntimeTask, proofs_by_id: Mapping[str, ProofBinding]) -> bool:
        if task.state is not RuntimeTaskState.DONE:
            return False
        if not task.required_proof_ids:
            return True
        for proof_id in task.required_proof_ids:
            proof = proofs_by_id.get(proof_id)
            if proof is None or proof.task_id != task.task_id or not proof.valid:
                return False
        return True

    @staticmethod
    def _best_priority(tasks: Iterable[RuntimeTask]) -> RuntimeTask:
        return sorted(tasks, key=lambda task: (-task.priority, task.task_id))[0]

    @staticmethod
    def _best_ready(tasks: Iterable[RuntimeTask]) -> RuntimeTask | None:
        items = tuple(tasks)
        return MissionRuntimeInterlock._best_priority(items) if items else None

    def _state_digest(self, snapshot: MissionRuntimeSnapshot, proofs_by_id: Mapping[str, ProofBinding]) -> str:
        material = {
            "mission_id": snapshot.mission_id,
            "contract_epoch": snapshot.contract_epoch,
            "ledger_tail": snapshot.ledger_tail,
            "objective_satisfied": snapshot.objective_satisfied,
            "tasks": [asdict(task) for task in sorted(snapshot.tasks, key=lambda item: item.task_id)],
            "proofs": [asdict(proof) for proof in sorted(proofs_by_id.values(), key=lambda item: item.proof_id)],
        }
        return _digest(material)

    def _blocked_decision(
        self,
        snapshot: MissionRuntimeSnapshot,
        action: RuntimeAction,
        next_task_id: str,
        reasons: tuple[str, ...],
        owner_guard_decision: str,
        pre_final_mode: str,
    ) -> MissionRuntimeDecision:
        return self._decision(
            snapshot,
            action,
            next_task_id=next_task_id,
            reasons=reasons,
            final_response_allowed=False,
            auto_continue_required=True,
            completion_verified=False,
            owner_guard_decision=owner_guard_decision,
            pre_final_mode=pre_final_mode,
        )

    def _decision(
        self,
        snapshot: MissionRuntimeSnapshot,
        action: RuntimeAction,
        *,
        next_task_id: str,
        reasons: tuple[str, ...],
        final_response_allowed: bool,
        auto_continue_required: bool,
        completion_verified: bool,
        owner_guard_decision: str,
        pre_final_mode: str,
        prepare: TerminalPrepareReceipt | None = None,
    ) -> MissionRuntimeDecision:
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": snapshot.mission_id,
            "action": action.value,
            "next_task_id": next_task_id,
            "reasons": reasons,
            "final_response_allowed": final_response_allowed,
            "auto_continue_required": auto_continue_required,
            "completion_verified": completion_verified,
            "owner_guard_decision": owner_guard_decision,
            "pre_final_mode": pre_final_mode,
            "prepare": asdict(prepare) if prepare else None,
        }
        return MissionRuntimeDecision(
            schema=SCHEMA,
            version=VERSION,
            mission_id=snapshot.mission_id,
            action=action,
            next_task_id=next_task_id,
            reasons=reasons,
            final_response_allowed=final_response_allowed,
            auto_continue_required=auto_continue_required,
            completion_verified=completion_verified,
            owner_guard_decision=owner_guard_decision,
            pre_final_mode=pre_final_mode,
            prepare=prepare,
            receipt_digest=_digest(material),
        )

    @staticmethod
    def _validate(snapshot: MissionRuntimeSnapshot) -> None:
        if not snapshot.mission_id.strip():
            raise ValueError("mission_id is required")
        if not snapshot.current_mission_id.strip():
            raise ValueError("current_mission_id is required")
        if not snapshot.objective.strip():
            raise ValueError("objective is required")
        if snapshot.contract_epoch < 0 or snapshot.ledger_tail < 0:
            raise ValueError("contract_epoch and ledger_tail must be non-negative")
        task_ids = [task.task_id for task in snapshot.tasks]
        if any(not task_id.strip() for task_id in task_ids):
            raise ValueError("task_id is required")
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("duplicate task_id")
        known = set(task_ids)
        for task in snapshot.tasks:
            missing = set(task.dependencies) - known
            if missing:
                raise ValueError(f"unknown task dependency for {task.task_id}: {sorted(missing)}")
            if task.task_id in task.dependencies:
                raise ValueError("task cannot depend on itself")
        proof_ids = [proof.proof_id for proof in snapshot.proofs]
        if len(proof_ids) != len(set(proof_ids)):
            raise ValueError("duplicate proof_id")
        for proof in snapshot.proofs:
            if proof.task_id not in known:
                raise ValueError(f"unknown proof task_id: {proof.task_id}")


__all__ = [
    "MissionRuntimeDecision",
    "MissionRuntimeInterlock",
    "MissionRuntimeSnapshot",
    "ProofBinding",
    "RuntimeAction",
    "RuntimeTask",
    "RuntimeTaskState",
    "SCHEMA",
    "TerminalPrepareReceipt",
    "VERSION",
]
