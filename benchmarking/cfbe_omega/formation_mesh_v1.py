"""CFBE Ω Formation Mesh v1.

Load-bearing composition of CFBE portfolio selection, Formation Ω route economics,
FUSE AI-bot multi-stream planning and Alpha→Omega convergence semantics.
The layer is provider-neutral and effect-free.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import (
    BubblesWorkNode, ClosureWaveReceipt, plan_bubbles_work_graph,
)
from federation.fuse_ai_bot_multistream_fabric_v1 import (
    FUSEAIBotMultiStreamFabric, MultiStreamPlan, OmegaWitness, PathOutcome, StreamPath,
)
from formation_omega.autonomic_fabric import AuthorityCeiling

SCHEMA = "CFBE-OMEGA-FORMATION-MESH-V1"
VERSION = "1.0.0"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CFBEPathSpec:
    path_id: str
    work_id: str
    family: str
    objective: str
    independent_group: str
    closure_leverage: float = 0.8
    information_gain: float = 0.7
    success_probability: float = 0.7
    reversibility: float = 0.9
    cost: float = 0.1
    risk: float = 0.1
    latency: float = 0.1
    unlock_count: int = 0
    mutation_domain: str = ""
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    external_effect: bool = False
    required_capabilities: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        for label, value in (("PATH_ID", self.path_id), ("WORK_ID", self.work_id), ("FAMILY", self.family), ("OBJECTIVE", self.objective), ("INDEPENDENT_GROUP", self.independent_group)):
            if not str(value).strip():
                raise ValueError(f"{label}_REQUIRED")

    def as_stream_path(self) -> StreamPath:
        self.validate()
        return StreamPath(
            path_id=self.path_id, stream_id=self.work_id, objective=self.objective,
            independent_group=self.independent_group, closure_leverage=self.closure_leverage,
            information_gain=self.information_gain, success_probability=self.success_probability,
            reversibility=self.reversibility, cost=self.cost, risk=self.risk, latency=self.latency,
            unlock_count=self.unlock_count, mutation_domain=self.mutation_domain,
            authority_ceiling=self.authority_ceiling, external_effect=self.external_effect,
            required_capabilities=self.required_capabilities, evidence_refs=self.evidence_refs,
        )


@dataclass(frozen=True, slots=True)
class CFBEWorkPacket:
    packet_id: str
    work_id: str
    path_id: str
    bot_role: str
    alpha_omega_stage: str
    objective: str
    held_until_failure: bool = False
    logical_only: bool = True


@dataclass(frozen=True, slots=True)
class CFBEMeshPlan:
    schema: str
    version: str
    mission_id: str
    objective: str
    cfbe_wave: ClosureWaveReceipt
    formation_plan: MultiStreamPlan
    selected_path_ids: tuple[str, ...]
    work_packets: tuple[CFBEWorkPacket, ...]
    stream_coverage: tuple[str, ...]
    duplicate_suppressed: tuple[str, ...]
    collision_serialized: tuple[str, ...]
    provider_native_worker_count: int
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class CFBEMeshWitness:
    schema: str
    mission_id: str
    state: str
    alpha_omega_state: str
    formation_witness: OmegaWitness
    completed_streams: tuple[str, ...]
    failed_paths: tuple[str, ...]
    recovery_packet_ids: tuple[str, ...]
    completion_allowed: bool
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    witness_sha256: str


def _score(path: CFBEPathSpec) -> float:
    return path.as_stream_path().as_action().score


def _semantic_key(path: CFBEPathSpec) -> tuple[str, str, str]:
    return (path.work_id.strip().casefold(), path.family.strip().casefold(), " ".join(path.objective.split()).casefold())


def _coverage_first_wave(paths: Sequence[CFBEPathSpec], *, required_streams: Sequence[str], max_parallel: int) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if max_parallel < 1:
        raise ValueError("MAX_PARALLEL_MUST_BE_POSITIVE")
    by_stream: dict[str, list[CFBEPathSpec]] = {item: [] for item in required_streams}
    duplicates: list[str] = []
    seen_semantics: set[tuple[str, str, str]] = set()
    ordered = sorted(paths, key=lambda item: (-_score(item), item.path_id))
    for path in ordered:
        key = _semantic_key(path)
        if key in seen_semantics:
            duplicates.append(path.path_id)
            continue
        seen_semantics.add(key)
        if path.work_id in by_stream:
            by_stream[path.work_id].append(path)

    selected: list[str] = []
    mutation_domains: set[str] = set()
    collisions: list[str] = []
    for stream in required_streams:
        for path in by_stream[stream]:
            if path.mutation_domain and path.mutation_domain in mutation_domains:
                collisions.append(path.path_id)
                continue
            selected.append(path.path_id)
            if path.mutation_domain:
                mutation_domains.add(path.mutation_domain)
            break
        if len(selected) >= max_parallel:
            return tuple(selected), tuple(sorted(set(duplicates))), tuple(sorted(set(collisions)))

    already = set(selected)
    for path in ordered:
        if path.path_id in already or path.path_id in duplicates:
            continue
        if path.mutation_domain and path.mutation_domain in mutation_domains:
            collisions.append(path.path_id)
            continue
        selected.append(path.path_id)
        already.add(path.path_id)
        if path.mutation_domain:
            mutation_domains.add(path.mutation_domain)
        if len(selected) >= max_parallel:
            break
    return tuple(selected), tuple(sorted(set(duplicates))), tuple(sorted(set(collisions)))


def _packets(mission_id: str, selected: Sequence[CFBEPathSpec]) -> tuple[CFBEWorkPacket, ...]:
    packets: list[CFBEWorkPacket] = []
    for path in selected:
        base = f"{mission_id}:{path.work_id}:{path.path_id}"
        for role, stage in (("ROUTE", "ALPHA_FORM"), ("BUILDER", "BETA_EXECUTE"), ("FALSIFIER", "GAMMA_CHALLENGE"), ("EVIDENCE", "DELTA_PROVE"), ("WITNESS", "OMEGA_WITNESS")):
            packets.append(CFBEWorkPacket(f"{base}:{role.lower()}", path.work_id, path.path_id, role, stage, path.objective))
        packets.append(CFBEWorkPacket(f"{base}:recovery", path.work_id, path.path_id, "RECOVERY", "FAILURE_WIN", path.objective, held_until_failure=True))
    packets.append(CFBEWorkPacket(f"{mission_id}:sentinel", "*", "*", "SENTINEL", "CONTINUOUS_GUARD", "Watch cross-stream regressions, stale state and collision risk."))
    return tuple(packets)


def compile_cfbe_formation_mesh(*, mission_id: str, objective: str, nodes: Sequence[BubblesWorkNode], paths: Sequence[CFBEPathSpec], max_parallel: int = 6, active_ids: Iterable[str] = (), completed_ids: Iterable[str] = (), critical_regression_ids: Iterable[str] = (), live_ready_ids: Iterable[str] = (), readiness_blockers: Mapping[str, Iterable[str]] | None = None) -> CFBEMeshPlan:
    if not mission_id.strip() or not objective.strip():
        raise ValueError("MISSION_ID_AND_OBJECTIVE_REQUIRED")
    cfbe_wave = plan_bubbles_work_graph(nodes, active_ids=active_ids, completed_ids=completed_ids, critical_regression_ids=critical_regression_ids, live_ready_ids=live_ready_ids, readiness_blockers=readiness_blockers)
    required_streams = tuple(item.capability_id for item in cfbe_wave.selected)
    if not required_streams:
        raise ValueError("CFBE_WAVE_HAS_NO_ACTIONABLE_STREAMS")
    path_by_id: dict[str, CFBEPathSpec] = {}
    for path in paths:
        path.validate()
        if path.path_id in path_by_id:
            raise ValueError(f"DUPLICATE_PATH_ID:{path.path_id}")
        path_by_id[path.path_id] = path
    unknown = sorted({path.work_id for path in paths} - set(required_streams))
    if unknown:
        raise ValueError("PATH_FOR_NONSELECTED_CFBE_WORK:" + ",".join(unknown))
    missing = tuple(stream for stream in required_streams if not any(p.work_id == stream for p in paths))
    if missing:
        raise ValueError("CFBE_SELECTED_STREAM_WITHOUT_PATH:" + ",".join(missing))
    formation = FUSEAIBotMultiStreamFabric(authority_ceiling=AuthorityCeiling.A1_INTERNAL, max_parallel=max_parallel, corroboration_required_per_stream=1).plan(mission_id=mission_id, objective=objective, required_streams=required_streams, paths=tuple(path.as_stream_path() for path in paths))
    selected_ids, duplicates, collisions = _coverage_first_wave(paths, required_streams=required_streams, max_parallel=max_parallel)
    selected_specs = tuple(path_by_id[item] for item in selected_ids)
    coverage = tuple(sorted({item.work_id for item in selected_specs}))
    packets = _packets(mission_id, selected_specs)
    body = {"schema": SCHEMA, "version": VERSION, "mission_id": mission_id, "objective": " ".join(objective.split()), "cfbe_receipt": cfbe_wave.receipt_sha256, "formation_plan": formation.plan_sha256, "selected_path_ids": selected_ids, "stream_coverage": coverage, "duplicate_suppressed": duplicates, "collision_serialized": collisions, "work_packets": [item.packet_id for item in packets], "provider_native_worker_count": 0, "provider_effect_authorized": False, "financial_effect_authorized": False}
    return CFBEMeshPlan(SCHEMA, VERSION, mission_id, body["objective"], cfbe_wave, formation, selected_ids, packets, coverage, duplicates, collisions, 0, False, False, _digest(body))


def reconcile_cfbe_formation_mesh(plan: CFBEMeshPlan, outcomes: Sequence[PathOutcome]) -> CFBEMeshWitness:
    fabric = FUSEAIBotMultiStreamFabric(authority_ceiling=AuthorityCeiling.A1_INTERNAL, max_parallel=max(1, len(plan.selected_path_ids)), corroboration_required_per_stream=1)
    fw = fabric.reconcile(plan.formation_plan, outcomes)
    completed = tuple(sorted(item.stream_id for item in fw.stream_assessments if item.complete))
    failed = tuple(sorted(item.path_id for item in outcomes if item.state.value == "FAILED"))
    recovery = tuple(sorted(packet.packet_id for packet in plan.work_packets if packet.held_until_failure and packet.path_id in failed))
    completion = bool(fw.completion_allowed and set(plan.stream_coverage) == set(completed))
    state = "CFBE_FORMATION_OMEGA_VERIFIED" if completion else "CFBE_FORMATION_CONTINUE"
    alpha_state = "OMEGA" if completion else "ALPHA_TO_OMEGA_IN_PROGRESS"
    body = {"schema": SCHEMA, "mission_id": plan.mission_id, "plan_sha256": plan.plan_sha256, "formation_witness": fw.witness_sha256, "state": state, "alpha_omega_state": alpha_state, "completed_streams": completed, "failed_paths": failed, "recovery_packet_ids": recovery, "completion_allowed": completion}
    return CFBEMeshWitness(SCHEMA, plan.mission_id, state, alpha_state, fw, completed, failed, recovery, completion, False, False, _digest(body))


__all__ = ["CFBEPathSpec", "CFBEWorkPacket", "CFBEMeshPlan", "CFBEMeshWitness", "SCHEMA", "VERSION", "compile_cfbe_formation_mesh", "reconcile_cfbe_formation_mesh"]
