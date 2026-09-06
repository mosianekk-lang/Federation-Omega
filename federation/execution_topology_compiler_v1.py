"""FUSE Execution Topology Compiler v1.

Compiles an admitted MissionIR into an executable worker topology using only current,
heartbeat-verified worker attestations and the existing CFBE hyperperformance planner.
It never turns role definitions or stale registrations into swarm capacity.

Provider-neutral and effect-free: this module plans assignments; it does not spawn
workers, grant authority, or execute provider effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from federation.cfbe_chat_hyperperformance_v1 import (
    EffectClass,
    ExecutionPlan,
    FreshResultCache,
    HyperperformancePlanner,
    PerformanceBudget,
    RouteProfile,
    WorkUnit,
)
from federation.live_worker_attestation_v1 import (
    CapabilityEpoch,
    WorkerAttestation,
    WorkerAttestationCourt,
)
from federation.mission_capability_admission_v1 import MissionAdmissionReceipt
from federation.mission_ir import MissionIR

SCHEMA = "FUSE-EXECUTION-TOPOLOGY-COMPILER-V1"
VERSION = "1.0.0"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class TopologyMode(str, Enum):
    NONE = "NONE"
    SINGLE_WORKER = "SINGLE_WORKER"
    PARALLEL_SWARM = "PARALLEL_SWARM"


@dataclass(frozen=True, slots=True)
class TopologyTask:
    unit: WorkUnit
    capability_id: str
    mutation_domain: str = ""

    def validate(self) -> "TopologyTask":
        self.unit.validate()
        if not self.capability_id.strip():
            raise ValueError("TOPOLOGY_TASK_CAPABILITY_REQUIRED")
        if self.unit.effect_class is not EffectClass.READ_ONLY and not self.mutation_domain.strip():
            raise ValueError("MUTATING_TASK_REQUIRES_MUTATION_DOMAIN")
        return self


@dataclass(frozen=True, slots=True)
class WorkerAssignment:
    unit_id: str
    worker_id: str
    runtime_id: str
    capability_id: str
    mutation_domain: str
    cfbe_state: str


@dataclass(frozen=True, slots=True)
class TopologyWave:
    wave_index: int
    unit_ids: tuple[str, ...]
    worker_ids: tuple[str, ...]
    mutation_domains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExecutionTopologyReceipt:
    mission_id: str
    mission_digest: str
    admission_receipt_digest: str
    state: str
    mode: TopologyMode
    assignments: tuple[WorkerAssignment, ...]
    waves: tuple[TopologyWave, ...]
    blocked_units: tuple[str, ...]
    live_worker_ids: tuple[str, ...]
    cfbe_plan_id: str
    receipt_digest: str

    @property
    def executable(self) -> bool:
        return self.state in {"TOPOLOGY_READY", "TOPOLOGY_READY_SINGLE_WORKER"}


class ExecutionTopologyCompiler:
    """Bind admitted capability demand to verified runtime supply and CFBE waves."""

    def __init__(
        self,
        budget: PerformanceBudget | None = None,
        worker_court: WorkerAttestationCourt | None = None,
    ) -> None:
        self.budget = budget or PerformanceBudget()
        self.worker_court = worker_court or WorkerAttestationCourt()
        self.planner = HyperperformancePlanner(self.budget)

    def _live_candidates(
        self,
        *,
        mission: MissionIR,
        capability_id: str,
        attestations: Sequence[WorkerAttestation],
        epochs: Mapping[str, CapabilityEpoch],
        now: str,
    ) -> tuple[WorkerAttestation, ...]:
        epoch = epochs.get(capability_id)
        if epoch is None:
            return ()
        live: list[WorkerAttestation] = []
        for item in attestations:
            if item.capability_id != capability_id or item.mission_id != mission.mission_id:
                continue
            if self.worker_court.decide(item, epoch, now=now).live:
                live.append(item)
        return tuple(sorted(live, key=lambda x: (x.worker_id, x.runtime_id, x.attestation_id)))

    @staticmethod
    def _admitted_capabilities(admission: MissionAdmissionReceipt) -> frozenset[str]:
        admitted: set[str] = set()
        for decision in admission.decisions:
            if not decision.satisfied or decision.state == "OPTIONAL_UNSATISFIED":
                continue
            admitted.add(decision.capability_id)
            if decision.selected_capability_id:
                admitted.add(decision.selected_capability_id)
        return frozenset(admitted)

    @staticmethod
    def _serialize_mutation_domains(
        plan: ExecutionPlan,
        assignments: Mapping[str, WorkerAssignment],
        tasks: Mapping[str, TopologyTask],
    ) -> tuple[TopologyWave, ...]:
        output: list[TopologyWave] = []
        index = 0
        for source_wave in plan.waves:
            buckets: list[list[str]] = []
            domains_per_bucket: list[set[str]] = []
            for unit_id in source_wave.unit_ids:
                assignment = assignments.get(unit_id)
                if assignment is None:
                    continue
                task = tasks[unit_id]
                domain = task.mutation_domain.strip()
                mutating = task.unit.effect_class is not EffectClass.READ_ONLY
                placed = False
                for pos, bucket in enumerate(buckets):
                    if mutating and domain and domain in domains_per_bucket[pos]:
                        continue
                    bucket.append(unit_id)
                    if mutating and domain:
                        domains_per_bucket[pos].add(domain)
                    placed = True
                    break
                if not placed:
                    buckets.append([unit_id])
                    domains_per_bucket.append({domain} if mutating and domain else set())
            for bucket, domains in zip(buckets, domains_per_bucket):
                worker_ids = tuple(sorted({assignments[u].worker_id for u in bucket}))
                output.append(TopologyWave(index, tuple(bucket), worker_ids, tuple(sorted(domains))))
                index += 1
        return tuple(output)

    def compile(
        self,
        *,
        mission: MissionIR,
        admission: MissionAdmissionReceipt,
        tasks: Sequence[TopologyTask],
        routes: Sequence[RouteProfile],
        attestations: Sequence[WorkerAttestation],
        epochs: Mapping[str, CapabilityEpoch],
        now: str,
        cache: FreshResultCache | None = None,
        require_swarm: bool = False,
    ) -> ExecutionTopologyReceipt:
        mission.validate()
        if admission.mission_id != mission.mission_id or admission.mission_digest != mission.digest():
            raise ValueError("TOPOLOGY_ADMISSION_MISSION_MISMATCH")
        if not admission.admitted:
            return self._receipt(mission, admission, "TOPOLOGY_HELD_MISSION_NOT_ADMITTED", TopologyMode.NONE, (), (), (), (), "")

        by_id: dict[str, TopologyTask] = {}
        for task in tasks:
            task.validate()
            if task.unit.unit_id in by_id:
                raise ValueError("DUPLICATE_TOPOLOGY_UNIT_ID")
            by_id[task.unit.unit_id] = task

        admitted_capabilities = self._admitted_capabilities(admission)
        capability_workers: dict[str, tuple[WorkerAttestation, ...]] = {}
        blocked: set[str] = set()
        all_live: dict[str, WorkerAttestation] = {}
        for task in tasks:
            if task.capability_id not in admitted_capabilities:
                blocked.add(task.unit.unit_id)
                continue
            workers = capability_workers.setdefault(
                task.capability_id,
                self._live_candidates(
                    mission=mission,
                    capability_id=task.capability_id,
                    attestations=attestations,
                    epochs=epochs,
                    now=now,
                ),
            )
            if not workers:
                blocked.add(task.unit.unit_id)
            for worker in workers:
                all_live[worker.worker_id] = worker

        if blocked:
            return self._receipt(
                mission, admission, "TOPOLOGY_HELD_NO_LIVE_CAPACITY", TopologyMode.NONE,
                (), (), tuple(sorted(blocked)), tuple(sorted(all_live)), "",
            )

        distinct_runtimes = {item.runtime_id for item in all_live.values() if item.runtime_id}
        if require_swarm and len(distinct_runtimes) < 2:
            return self._receipt(
                mission, admission, "TOPOLOGY_HELD_SWARM_NOT_PROVEN", TopologyMode.NONE,
                (), (), tuple(sorted(by_id)), tuple(sorted(all_live)), "",
            )

        cfbe = self.planner.compile([task.unit for task in tasks], routes, cache)
        cfbe_blocked = set(cfbe.blocked_units)
        if cfbe_blocked:
            return self._receipt(
                mission, admission, "TOPOLOGY_HELD_CFBE_ROUTE_GAP", TopologyMode.NONE,
                (), (), tuple(sorted(cfbe_blocked)), tuple(sorted(all_live)), cfbe.plan_id,
            )

        assignments: list[WorkerAssignment] = []
        per_capability_cursor: dict[str, int] = {}
        for planned in cfbe.planned_units:
            task = by_id[planned.unit.unit_id]
            workers = capability_workers[task.capability_id]
            cursor = per_capability_cursor.get(task.capability_id, 0)
            worker = workers[cursor % len(workers)]
            per_capability_cursor[task.capability_id] = cursor + 1
            assignments.append(WorkerAssignment(
                unit_id=task.unit.unit_id,
                worker_id=worker.worker_id,
                runtime_id=worker.runtime_id,
                capability_id=task.capability_id,
                mutation_domain=task.mutation_domain,
                cfbe_state=planned.state,
            ))

        assignment_map = {item.unit_id: item for item in assignments}
        waves = self._serialize_mutation_domains(cfbe, assignment_map, by_id)
        used_runtime_ids = {item.runtime_id for item in assignments if item.runtime_id}
        mode = TopologyMode.PARALLEL_SWARM if len(used_runtime_ids) >= 2 else TopologyMode.SINGLE_WORKER
        state = "TOPOLOGY_READY" if mode is TopologyMode.PARALLEL_SWARM else "TOPOLOGY_READY_SINGLE_WORKER"
        return self._receipt(
            mission, admission, state, mode, tuple(assignments), waves, (),
            tuple(sorted(all_live)), cfbe.plan_id,
        )

    def _receipt(
        self,
        mission: MissionIR,
        admission: MissionAdmissionReceipt,
        state: str,
        mode: TopologyMode,
        assignments: tuple[WorkerAssignment, ...],
        waves: tuple[TopologyWave, ...],
        blocked: tuple[str, ...],
        live_workers: tuple[str, ...],
        cfbe_plan_id: str,
    ) -> ExecutionTopologyReceipt:
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission.mission_id,
            "mission_digest": mission.digest(),
            "admission": admission.receipt_digest,
            "state": state,
            "mode": mode.value,
            "assignments": [vars(x) if hasattr(x, "__dict__") else {
                "unit_id": x.unit_id, "worker_id": x.worker_id, "runtime_id": x.runtime_id,
                "capability_id": x.capability_id, "mutation_domain": x.mutation_domain,
                "cfbe_state": x.cfbe_state,
            } for x in assignments],
            "waves": [{"i": w.wave_index, "units": w.unit_ids, "workers": w.worker_ids, "domains": w.mutation_domains} for w in waves],
            "blocked": blocked,
            "live_workers": live_workers,
            "cfbe_plan_id": cfbe_plan_id,
        }
        return ExecutionTopologyReceipt(
            mission_id=mission.mission_id,
            mission_digest=mission.digest(),
            admission_receipt_digest=admission.receipt_digest,
            state=state,
            mode=mode,
            assignments=assignments,
            waves=waves,
            blocked_units=blocked,
            live_worker_ids=live_workers,
            cfbe_plan_id=cfbe_plan_id,
            receipt_digest=_digest(material),
        )


__all__ = [
    "SCHEMA", "VERSION", "TopologyMode", "TopologyTask", "WorkerAssignment",
    "TopologyWave", "ExecutionTopologyReceipt", "ExecutionTopologyCompiler",
]
