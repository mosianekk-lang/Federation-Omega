"""Omega-One multi-stream completion engine.

This is an additive control layer over the exact SOL 6.1 runtime, durable worker
plane and adaptive routing sources materialized with this package.  It fills the
unifying-DAG, fair-routing, fencing and independent-proof gaps without replacing
the inherited primitives.  No live provider adapter or credential is used here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Mapping
from uuid import uuid4

from .interop import EffectClass
from .source_proof import assert_sources_verified
from .transaction_store import (
    IdempotencyReservationConflict,
    SQLiteStateStore,
    StateRevisionConflict,
    canonical_digest,
)


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOL_ROOT = _PROJECT_ROOT / "sol_61_runtime"
_SOURCE_MANIFEST = _PROJECT_ROOT / "SOURCE_BASE.json"
if not _SOURCE_MANIFEST.exists():
    _SOURCE_MANIFEST = Path(__file__).with_name("SOURCE_BASE.json")
if str(_SOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOL_ROOT))

# These imports intentionally bind to the exact reconciled SOL source snapshot.
from adaptive import AdaptiveExecutionFabric, ProviderRoute  # type: ignore  # noqa: E402
from runtime import (  # type: ignore  # noqa: E402
    CompletionContract,
    Mission,
    SolRuntime,
    Workstream,
    digest,
    utc_now,
)
from worker import DurableWorkerPlane, Job  # type: ignore  # noqa: E402


AUTHORITY_RANK = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}
PRIVACY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class TaskState(str, Enum):
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    RETRY_WAIT = "RETRY_WAIT"
    RECONCILING = "RECONCILING"
    PROVEN = "PROVEN"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass(frozen=True)
class MissionEnvelope:
    mission_id: str
    version: int
    objective: str
    success_definition: tuple[str, ...]
    constraints: tuple[str, ...] = ()

    def validate(self) -> "MissionEnvelope":
        if not self.mission_id.strip() or not self.objective.strip() or not self.success_definition:
            raise ValueError("MISSION_FIELDS_REQUIRED")
        if self.version < 1:
            raise ValueError("MISSION_VERSION_INVALID")
        return self


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    mission_id: str
    dependencies: tuple[str, ...]
    capability: str
    input_digest: str
    tenant_id: str = "default"
    flow_weight: int = 1
    priority: int = 50
    service_units: int = 1
    authority: str = "A0"
    privacy: str = "P1"
    data_zone: str = "internal"
    effect_class: EffectClass = EffectClass.READ
    idempotency_key: str | None = None
    proof_policy: tuple[str, ...] = ("schema", "semantic", "policy")
    max_attempts: int = 3
    max_cost: float = 0.0
    latency_slo_ms: float = 120_000.0

    def validate(self) -> "TaskEnvelope":
        if not self.task_id.strip() or not self.mission_id.strip() or not self.capability.strip():
            raise ValueError("TASK_FIELDS_REQUIRED")
        if self.task_id in self.dependencies:
            raise ValueError("TASK_SELF_DEPENDENCY")
        if self.flow_weight < 1 or self.service_units < 1 or self.max_attempts < 1:
            raise ValueError("TASK_BUDGET_INVALID")
        if self.authority not in AUTHORITY_RANK or self.privacy not in PRIVACY_RANK:
            raise ValueError("TASK_POLICY_CLASS_INVALID")
        if self.max_cost < 0 or self.latency_slo_ms <= 0:
            raise ValueError("TASK_LIMIT_INVALID")
        if self.effect_class != EffectClass.READ and (not self.idempotency_key or not self.proof_policy):
            raise ValueError("EFFECT_CONTRACT_INCOMPLETE")
        return self


@dataclass(frozen=True)
class WorkerDescriptor:
    worker_id: str
    capabilities: tuple[str, ...]
    authority_grants: tuple[str, ...] = ("A0",)
    privacy_ceiling: str = "P1"
    data_zones: tuple[str, ...] = ("internal",)
    capacity: int = 1
    predicted_latency_ms: float = 1000.0
    unit_cost: float = 0.0
    error_rate: float = 0.0
    proof_failure_rate: float = 0.0
    health: str = "HEALTHY"
    generation: int = 1

    def validate(self) -> "WorkerDescriptor":
        if not self.worker_id.strip() or not self.capabilities or self.capacity < 1:
            raise ValueError("WORKER_FIELDS_INVALID")
        if self.privacy_ceiling not in PRIVACY_RANK or not self.authority_grants:
            raise ValueError("WORKER_POLICY_INVALID")
        if any(item not in AUTHORITY_RANK for item in self.authority_grants):
            raise ValueError("WORKER_AUTHORITY_INVALID")
        if self.unit_cost < 0 or self.predicted_latency_ms < 0:
            raise ValueError("WORKER_METRICS_INVALID")
        return self


@dataclass(frozen=True)
class LeaseReceipt:
    lease_id: str
    task_key: str
    worker_id: str
    mission_version: int
    fencing_token: int
    attempt: int
    input_digest: str


@dataclass(frozen=True)
class ConcurrencyPlan:
    requested_parallelism: int
    ready_frontier: int
    routable_frontier: int
    spare_worker_capacity: int
    target_parallelism: int
    mode: str
    effect_slots: int
    selected_task_keys: tuple[str, ...]


@dataclass(frozen=True)
class ProofBundle:
    verifier_id: str
    output_digest: str
    schema_valid: bool
    semantic_valid: bool
    policy_valid: bool
    readback_valid: bool = True
    evidence_refs: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.schema_valid and self.semantic_valid and self.policy_valid and self.readback_valid and bool(self.evidence_refs)


@dataclass(frozen=True)
class CompletionCertificate:
    certificate_id: str
    task_key: str
    mission_version: int
    output_digest: str
    proof_digest: str
    verifier_id: str
    decision: str = "PROVEN"


def output_digest(value: Any) -> str:
    return digest(value)


class OmegaCompletionEngine:
    """Durable, deterministic scheduler whose only completion state is PROVEN."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        verify_source: bool = True,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        if verify_source:
            assert_sources_verified(_SOURCE_MANIFEST, _PROJECT_ROOT)
        self.root = Path(state_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.legacy_control_file = self.root / "control-state.json"
        self.store = SQLiteStateStore(self.root / "control-state.sqlite3")
        self.store.migrate_legacy(self.legacy_control_file, self._blank())
        self.control_file = self.store.path
        self.sol = SolRuntime(self.root / "sol")
        self.worker_plane = DurableWorkerPlane(self.root / "worker")
        self.adaptive = AdaptiveExecutionFabric()
        self._lock = threading.RLock()
        self._fault_injector = fault_injector
        self._outbox_claim_token = f"omega-engine:{uuid4()}"
        self._transition_claim_token = f"omega-transition:{uuid4()}"
        self.state = self._load()
        self._drain_admission_outbox()
        self._drain_transition_outbox()

    @staticmethod
    def _blank() -> dict[str, Any]:
        return {
            "missions": {}, "tasks": {}, "workers": {}, "leases": {}, "fences": {},
            "dispatch_counts": {}, "effects": {}, "permits": {}, "certificates": {}, "events": [],
        }

    def _load(self) -> dict[str, Any]:
        loaded, revision = self.store.load(self._blank())
        self._revision = revision
        return loaded

    def _persist(self) -> None:
        receipt = self.store.commit(self.state, expected_revision=self._revision)
        self._revision = receipt.revision_after

    def _refresh_from_store(self, *, force: bool = False) -> None:
        current = self.store.current_revision()
        if not force and current == self._revision:
            return
        self.state, self._revision = self.store.load(self._blank())
        self.sol._replay()
        self.worker_plane._replay()

    def _inject_fault(self, point: str) -> None:
        if self._fault_injector:
            self._fault_injector(point)

    def _event(self, kind: str, body: Mapping[str, Any]) -> None:
        previous = self.state["events"][-1]["hash"] if self.state["events"] else "GENESIS"
        row = {"type": kind, "body": dict(body), "at": utc_now(), "previous": previous}
        row["hash"] = digest(row)
        self.state["events"].append(row)

    @staticmethod
    def _task_key(mission_id: str, version: int, task_id: str) -> str:
        return f"{mission_id}:v{version}:{task_id}"

    def _admission_plan(
        self,
        mission: MissionEnvelope,
        tasks: tuple[TaskEnvelope, ...],
    ) -> tuple[tuple[TaskEnvelope, str, str], ...]:
        """Preflight every queue identity before mutating either state plane."""
        planned: list[tuple[TaskEnvelope, str, str]] = []
        batch_idempotency: set[str] = set()
        for task in tasks:
            key = self._task_key(mission.mission_id, mission.version, task.task_id)
            idempotency_key = task.idempotency_key or key
            if idempotency_key in batch_idempotency:
                raise ValueError("DUPLICATE_IDEMPOTENCY_KEY")
            reservation = self.store.reservation(idempotency_key)
            if reservation is not None and str(reservation["task_key"]) != key:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            existing_job_id = self.worker_plane.state.idempotency.get(idempotency_key)
            if existing_job_id is not None and existing_job_id != key:
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            batch_idempotency.add(idempotency_key)
            planned.append((task, key, idempotency_key))
        return tuple(planned)

    def register_worker(self, worker: WorkerDescriptor) -> dict[str, Any]:
        worker.validate()
        with self._lock:
            row = asdict(worker) | {"running": 0, "registered_at": utc_now()}
            self.state["workers"][worker.worker_id] = row
            self.worker_plane.heartbeat(worker.worker_id, worker.capabilities)
            self._event("WORKER_REGISTERED", {"worker_id": worker.worker_id, "generation": worker.generation})
            self._persist()
            return row

    def register_provider_route(self, route: ProviderRoute) -> None:
        self.adaptive.register_route(route)

    def route_provider(self, *, capability: str, max_cost: float, latency_slo_ms: float, min_success_rate: float = 0.9) -> dict[str, Any]:
        return self.adaptive.route(
            capability=capability, now_epoch=int(datetime.now(timezone.utc).timestamp()),
            max_unit_cost=max_cost, max_latency_ms=latency_slo_ms, min_success_rate=min_success_rate,
        )

    @staticmethod
    def _validate_graph(tasks: tuple[TaskEnvelope, ...]) -> None:
        ids = {task.task_id for task in tasks}
        if len(ids) != len(tasks):
            raise ValueError("DUPLICATE_TASK_ID")
        for task in tasks:
            unknown = set(task.dependencies) - ids
            if unknown:
                raise ValueError("DANGLING_DEPENDENCY:" + ",".join(sorted(unknown)))
        visiting: set[str] = set()
        visited: set[str] = set()
        by_id = {task.task_id: task for task in tasks}

        def walk(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("CYCLIC_DAG")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in by_id[task_id].dependencies:
                walk(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in sorted(ids):
            walk(task_id)

    def submit_mission(self, mission: MissionEnvelope, tasks: tuple[TaskEnvelope, ...]) -> dict[str, Any]:
        mission.validate()
        if not tasks:
            raise ValueError("MISSION_TASKS_REQUIRED")
        for task in tasks:
            task.validate()
            if task.mission_id != mission.mission_id:
                raise ValueError("TASK_MISSION_MISMATCH")
        self._validate_graph(tasks)
        for attempt in range(2):
            with self._lock:
                self._refresh_from_store()
                current = self.state["missions"].get(mission.mission_id)
                if current and mission.version <= current["version"]:
                    raise ValueError("STALE_MISSION_VERSION")
                admission_plan = self._admission_plan(mission, tasks)
                previous_state = self.state
                self.state = deepcopy(previous_state)
                if current:
                    self._supersede(mission.mission_id, int(current["version"]))
                self.state["missions"][mission.mission_id] = asdict(mission) | {"state": "ACTIVE"}
                for task, key, _ in admission_plan:
                    workstream_id = key
                    action_class = f"{task.capability}::{key}"
                    self.state["tasks"][key] = {
                        "spec": asdict(task), "workstream_id": workstream_id, "action_class": action_class,
                        "state": TaskState.READY.value if not task.dependencies else TaskState.BLOCKED.value,
                        "created_seq": len(self.state["events"]), "lease_id": None, "last_error": None,
                    }
                self._event("MISSION_SUBMITTED", {"mission_id": mission.mission_id, "version": mission.version, "tasks": len(tasks)})
                reservations = [
                    {
                        "idempotency_key": idempotency_key,
                        "task_key": key,
                        "mission_id": mission.mission_id,
                        "mission_version": mission.version,
                    }
                    for _, key, idempotency_key in admission_plan
                ]
                outbox = {
                    "outbox_id": f"admission:{mission.mission_id}:v{mission.version}",
                    "mission_id": mission.mission_id,
                    "mission_version": mission.version,
                    "payload": {"mission": asdict(mission), "tasks": [asdict(task) for task in tasks]},
                }
                try:
                    receipt = self.store.commit(
                        self.state,
                        expected_revision=self._revision,
                        reservations=reservations,
                        outbox=outbox,
                    )
                except StateRevisionConflict:
                    self.state = previous_state
                    self._refresh_from_store(force=True)
                    if attempt == 0:
                        continue
                    raise
                except IdempotencyReservationConflict as exc:
                    self.state = previous_state
                    raise ValueError(str(exc)) from exc
                except Exception:
                    self.state = previous_state
                    raise
                self._revision = receipt.revision_after
                self._inject_fault("after_admission_commit")
                self._drain_admission_outbox()
                return self.mission_status(mission.mission_id)
        raise RuntimeError("ADMISSION_RETRY_EXHAUSTED")

    def _materialize_admission(self, payload: Mapping[str, Any]) -> None:
        mission_row = payload["mission"]
        runtime_mission = Mission(
            str(mission_row["mission_id"]),
            str(mission_row["objective"]),
            tuple(mission_row["success_definition"]),
            tuple(mission_row.get("constraints") or ()),
            int(mission_row["version"]),
        )
        existing_mission = self.sol.state.missions.get(runtime_mission.mission_id)
        expected_mission = asdict(runtime_mission)
        if existing_mission is None:
            self.sol.register_mission(runtime_mission)
        elif runtime_mission.version > int(existing_mission.get("version", 0)):
            self.sol.register_mission(runtime_mission)
        elif digest(existing_mission) != digest(expected_mission):
            raise RuntimeError("SOL_MISSION_MATERIALIZATION_CONFLICT")

        for task_row in payload["tasks"]:
            task_id = str(task_row["task_id"])
            key = self._task_key(runtime_mission.mission_id, runtime_mission.version, task_id)
            workstream = Workstream(
                key,
                runtime_mission.mission_id,
                task_id,
                (),
                int(task_row["priority"]),
                str(task_row["effect_class"]) == EffectClass.READ.value,
            )
            existing_workstream = self.sol.state.workstreams.get(key)
            if existing_workstream is None:
                self.sol.register_workstream(workstream)
            elif (
                str(existing_workstream.get("mission_id")) != runtime_mission.mission_id
                or str(existing_workstream.get("objective")) != task_id
            ):
                raise RuntimeError("SOL_WORKSTREAM_MATERIALIZATION_CONFLICT")
            idempotency_key = str(task_row.get("idempotency_key") or key)
            admitted = self.worker_plane.enqueue(
                Job(
                    key,
                    runtime_mission.mission_id,
                    key,
                    f"{task_row['capability']}::{key}",
                    {"input_digest": task_row["input_digest"]},
                    idempotency_key,
                    int(task_row["max_attempts"]),
                    int(task_row["priority"]),
                )
            )
            if admitted.get("job_id") != key:
                raise RuntimeError("WORKER_ADMISSION_DIVERGENCE")

    def _drain_admission_outbox(self) -> None:
        self.store.recover_stale_outbox()
        self.sol._replay()
        self.worker_plane._replay()
        while True:
            item = self.store.claim_outbox(self._outbox_claim_token)
            if item is None:
                return
            try:
                self._materialize_admission(item["payload"])
            except Exception as exc:
                self.store.mark_outbox_failed(item["outbox_id"], self._outbox_claim_token, str(exc))
                raise
            self.store.mark_outbox_applied(item["outbox_id"], self._outbox_claim_token)

    def persistence_status(self) -> dict[str, Any]:
        status = self.store.status()
        status["database_bytes"] = self.control_file.stat().st_size
        status["legacy_snapshot_present"] = self.legacy_control_file.exists()
        return status

    def backup_state(self, destination: str | Path) -> dict[str, Any]:
        return self.store.backup_to(destination)

    def _supersede(self, mission_id: str, version: int) -> None:
        for key, row in self.state["tasks"].items():
            spec = row["spec"]
            if spec["mission_id"] == mission_id and f":v{version}:" in key and row["state"] not in {TaskState.PROVEN.value, TaskState.CANCELLED.value}:
                row["state"] = TaskState.SUPERSEDED.value
        for permit in self.state["permits"].values():
            if permit["mission_id"] == mission_id and permit["state"] == "ISSUED":
                permit["state"] = "REVOKED"
        self._event("MISSION_SUPERSEDED", {"mission_id": mission_id, "version": version})

    def _refresh_ready(self) -> int:
        changed = 0
        for key, row in self.state["tasks"].items():
            if row["state"] not in {TaskState.BLOCKED.value, TaskState.RETRY_WAIT.value}:
                continue
            spec = row["spec"]
            current = self.state["missions"].get(spec["mission_id"])
            if not current or int(current["version"]) != int(key.split(":v", 1)[1].split(":", 1)[0]):
                row["state"] = TaskState.SUPERSEDED.value
                changed += 1
                continue
            dependency_keys = [self._task_key(spec["mission_id"], current["version"], item) for item in spec["dependencies"]]
            if all(self.state["tasks"][item]["state"] == TaskState.PROVEN.value for item in dependency_keys):
                worker_job = self.worker_plane.state.jobs.get(key)
                if worker_job and worker_job["status"] in {"QUEUED", "RETRY_READY"}:
                    row["state"] = TaskState.READY.value
                    changed += 1
        return changed

    @staticmethod
    def _eligible(worker: Mapping[str, Any], spec: Mapping[str, Any]) -> bool:
        return (
            worker["health"] == "HEALTHY"
            and spec["capability"] in worker["capabilities"]
            and any(AUTHORITY_RANK[item] >= AUTHORITY_RANK[spec["authority"]] for item in worker["authority_grants"])
            and PRIVACY_RANK[worker["privacy_ceiling"]] >= PRIVACY_RANK[spec["privacy"]]
            and spec["data_zone"] in worker["data_zones"]
            and int(worker["running"]) < int(worker["capacity"])
            and float(worker["unit_cost"]) <= float(spec["max_cost"])
        )

    @staticmethod
    def _worker_score(worker: Mapping[str, Any], spec: Mapping[str, Any]) -> float:
        load = float(worker["running"]) / float(worker["capacity"])
        latency = min(2.0, float(worker["predicted_latency_ms"]) / float(spec["latency_slo_ms"]))
        cost = 0.0 if float(spec["max_cost"]) == 0 else min(2.0, float(worker["unit_cost"]) / float(spec["max_cost"]))
        risk = float(worker["error_rate"]) + float(worker["proof_failure_rate"])
        return 0.35 * load + 0.25 * latency + 0.20 * cost + 0.20 * risk

    def _critical_depth(self, task_key: str, memo: dict[str, int]) -> int:
        if task_key in memo:
            return memo[task_key]
        row = self.state["tasks"][task_key]
        mission_id = row["spec"]["mission_id"]
        version = int(task_key.split(":v", 1)[1].split(":", 1)[0])
        task_id = str(row["spec"]["task_id"])
        children = [
            key
            for key, candidate in self.state["tasks"].items()
            if candidate["spec"]["mission_id"] == mission_id
            and f":v{version}:" in key
            and task_id in candidate["spec"]["dependencies"]
        ]
        memo[task_key] = 1 + max((self._critical_depth(child, memo) for child in children), default=0)
        return memo[task_key]

    def _plan_wave(self, max_concurrency: int) -> tuple[ConcurrencyPlan, list[tuple[str, dict[str, Any], dict[str, Any]]]]:
        ready = [(key, row) for key, row in self.state["tasks"].items() if row["state"] == TaskState.READY.value]
        simulated_workers = deepcopy(self.state["workers"])
        simulated_dispatch = dict(self.state["dispatch_counts"])
        effect_running = any(
            row["state"] == TaskState.RUNNING.value
            and row["spec"]["effect_class"] != EffectClass.READ.value
            for row in self.state["tasks"].values()
        )
        effect_slots = 0 if effect_running else 1
        selected: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        remaining = list(ready)
        depth_memo: dict[str, int] = {}

        while remaining and len(selected) < max_concurrency:
            routable: list[tuple[str, dict[str, Any], list[dict[str, Any]]]] = []
            for key, row in remaining:
                is_effect = row["spec"]["effect_class"] != EffectClass.READ.value
                if is_effect and (effect_slots <= 0 or selected):
                    continue
                workers = [
                    worker
                    for worker in simulated_workers.values()
                    if self._eligible(worker, row["spec"])
                ]
                job = self.worker_plane.state.jobs.get(key)
                if workers and job and job["status"] in {"QUEUED", "RETRY_READY"}:
                    routable.append((key, row, workers))
            if not routable:
                break
            read_only = [
                item for item in routable
                if item[1]["spec"]["effect_class"] == EffectClass.READ.value
            ]
            if read_only:
                routable = read_only

            def task_rank(item: tuple[str, dict[str, Any], list[dict[str, Any]]]) -> tuple[float, int, int, int, str]:
                key, row, _ = item
                spec = row["spec"]
                served = float(simulated_dispatch.get(spec["tenant_id"], 0)) / float(spec["flow_weight"])
                return (served, -int(spec["priority"]), -self._critical_depth(key, depth_memo), int(row["created_seq"]), key)

            key, row, workers = min(routable, key=task_rank)
            worker = min(workers, key=lambda item: (self._worker_score(item, row["spec"]), item["worker_id"]))
            selected.append((key, row, worker))
            worker["running"] += 1
            spec = row["spec"]
            simulated_dispatch[spec["tenant_id"]] = int(simulated_dispatch.get(spec["tenant_id"], 0)) + int(spec["service_units"])
            if spec["effect_class"] != EffectClass.READ.value:
                effect_slots -= 1
            remaining = [(candidate_key, candidate) for candidate_key, candidate in remaining if candidate_key != key]

        routable_frontier = sum(
            1
            for key, row in ready
            if self.worker_plane.state.jobs.get(key, {}).get("status") in {"QUEUED", "RETRY_READY"}
            and any(self._eligible(worker, row["spec"]) for worker in self.state["workers"].values())
        )
        spare_capacity = sum(
            max(0, int(worker["capacity"]) - int(worker["running"]))
            for worker in self.state["workers"].values()
            if worker["health"] == "HEALTHY"
        )
        target = len(selected)
        plan = ConcurrencyPlan(
            requested_parallelism=max_concurrency,
            ready_frontier=len(ready),
            routable_frontier=routable_frontier,
            spare_worker_capacity=spare_capacity,
            target_parallelism=target,
            mode="HOLD" if target == 0 else "SERIAL_FRONTIER" if target == 1 else "PARALLEL_FRONTIER",
            effect_slots=0 if effect_running else 1,
            selected_task_keys=tuple(item[0] for item in selected),
        )
        return plan, selected

    def concurrency_plan(self, *, max_concurrency: int = 3) -> ConcurrencyPlan:
        if max_concurrency < 1:
            raise ValueError("MAX_CONCURRENCY_INVALID")
        with self._lock:
            changed = self._refresh_ready()
            plan, _ = self._plan_wave(max_concurrency)
            if changed:
                self._persist()
            return plan

    def schedule_next(self, *, lease_seconds: int = 60) -> LeaseReceipt | None:
        with self._lock:
            self._drain_transition_outbox()
            ready_changed = self._refresh_ready()
            ready = [(key, row) for key, row in self.state["tasks"].items() if row["state"] == TaskState.READY.value]
            routable = []
            for key, row in ready:
                workers = [worker for worker in self.state["workers"].values() if self._eligible(worker, row["spec"])]
                if workers:
                    routable.append((key, row, workers))
            if not routable:
                if ready_changed:
                    self._persist()
                return None
            def task_rank(item: tuple[str, dict[str, Any], list[dict[str, Any]]]) -> tuple[float, int, int, str]:
                key, row, _ = item
                spec = row["spec"]
                served = float(self.state["dispatch_counts"].get(spec["tenant_id"], 0)) / float(spec["flow_weight"])
                return (served, -int(spec["priority"]), int(row["created_seq"]), key)
            key, row, workers = min(routable, key=task_rank)
            worker = min(workers, key=lambda item: (self._worker_score(item, row["spec"]), item["worker_id"]))
            leased = self.worker_plane.lease(worker["worker_id"], row["action_class"], lease_seconds)
            if not leased or leased["job_id"] != key:
                raise RuntimeError("SOL_LEASE_DIVERGENCE")
            fence = int(self.state["fences"].get(key, 0)) + 1
            self.state["fences"][key] = fence
            lease_id = str(uuid4())
            receipt = LeaseReceipt(lease_id, key, worker["worker_id"], int(key.split(":v", 1)[1].split(":", 1)[0]), fence, int(leased["attempts"]), row["spec"]["input_digest"])
            self.state["leases"][lease_id] = asdict(receipt) | {"active": True}
            row["state"] = TaskState.RUNNING.value
            row["lease_id"] = lease_id
            worker["running"] += 1
            tenant = row["spec"]["tenant_id"]
            self.state["dispatch_counts"][tenant] = int(self.state["dispatch_counts"].get(tenant, 0)) + int(row["spec"]["service_units"])
            self._event("TASK_LEASED", {"task_key": key, "worker_id": worker["worker_id"], "fence": fence})
            self._persist()
            return receipt

    def _materialize_dispatch_wave(self, payload: Mapping[str, Any]) -> None:
        for assignment in payload.get("assignments") or []:
            task_key = str(assignment["task_key"])
            worker_id = str(assignment["worker_id"])
            expected_attempt = int(assignment["attempt"])
            row = self.state["tasks"].get(task_key)
            lease = self.state["leases"].get(str(assignment["lease_id"]))
            if (
                not row
                or row["state"] != TaskState.RUNNING.value
                or not lease
                or lease.get("active") is not True
                or lease.get("worker_id") != worker_id
                or int(lease.get("attempt", 0)) != expected_attempt
            ):
                raise RuntimeError("DISPATCH_CONTROL_BINDING_DIVERGENCE")
            job = self.worker_plane.state.jobs.get(task_key)
            if not job:
                raise RuntimeError("DISPATCH_WORKER_JOB_MISSING")
            if job["status"] == "LEASED":
                if job.get("leased_by") != worker_id or int(job.get("attempts", 0)) != expected_attempt:
                    raise RuntimeError("DISPATCH_EXISTING_LEASE_DIVERGENCE")
                continue
            if job["status"] not in {"QUEUED", "RETRY_READY"}:
                raise RuntimeError(f"DISPATCH_WORKER_STATE_DIVERGENCE:{job['status']}")
            leased = self.worker_plane.lease(worker_id, row["action_class"], int(payload["lease_seconds"]))
            if (
                not leased
                or leased["job_id"] != task_key
                or leased.get("leased_by") != worker_id
                or int(leased.get("attempts", 0)) != expected_attempt
            ):
                raise RuntimeError("DISPATCH_MATERIALIZATION_DIVERGENCE")

    def _drain_transition_outbox(self) -> None:
        self.store.recover_stale_transitions()
        self.sol._replay()
        self.worker_plane._replay()
        while True:
            item = self.store.claim_transition(self._transition_claim_token)
            if item is None:
                return
            try:
                if item["transition_kind"] == "DISPATCH_WAVE":
                    self._materialize_dispatch_wave(item["payload"])
                    self.store.mark_transition_applied(item["transition_id"], self._transition_claim_token)
                elif item["transition_kind"] == "PROOF_FINALIZATION":
                    self._materialize_proof_finalization(
                        item["payload"],
                        transition_id=item["transition_id"],
                        claim_token=self._transition_claim_token,
                    )
                else:
                    raise RuntimeError(f"UNKNOWN_TRANSITION_KIND:{item['transition_kind']}")
            except Exception as exc:
                self.store.mark_transition_failed(item["transition_id"], self._transition_claim_token, str(exc))
                raise

    def _record_sol_receipt_once(
        self,
        *,
        workstream_id: str,
        receipt_type: str,
        body: Mapping[str, Any],
        publication_id: str,
    ) -> dict[str, Any]:
        base_body = dict(body)
        binding = digest(
            {
                "workstream_id": workstream_id,
                "receipt_type": receipt_type,
                "provider": "omega-work-engine",
                "body": base_body,
            }
        )
        matches = [
            event["payload"]
            for event in self.sol._events()
            if event.get("event_type") == "RECEIPT_RECORDED"
            and event.get("payload", {}).get("workstream_id") == workstream_id
            and event.get("payload", {}).get("receipt_type") == receipt_type
            and event.get("payload", {}).get("body", {}).get("omega_publication_id") == publication_id
        ]
        if len(matches) > 1:
            raise RuntimeError("SOL_RECEIPT_RAW_DUPLICATE")
        if matches:
            existing = matches[0]
            if existing.get("body", {}).get("omega_binding_sha256") != binding:
                raise RuntimeError("SOL_RECEIPT_IDEMPOTENCY_CONFLICT")
            return dict(existing)
        enriched = base_body | {
            "omega_publication_id": publication_id,
            "omega_binding_sha256": binding,
        }
        return self.sol.record_receipt(
            workstream_id,
            receipt_type,
            "omega-work-engine",
            enriched,
        )

    def _evaluate_sol_completion_once(self, workstream_id: str, publication_id: str) -> dict[str, Any]:
        matches = [
            event["payload"]
            for event in self.sol._events()
            if event.get("event_type") == "COMPLETION_EVALUATED"
            and event.get("payload", {}).get("workstream_id") == workstream_id
            and event.get("payload", {}).get("omega_publication_id") == publication_id
        ]
        if len(matches) > 1:
            raise RuntimeError("SOL_COMPLETION_RAW_DUPLICATE")
        if matches:
            return dict(matches[0])
        present = {
            row["receipt_type"]
            for row in self.sol.state.receipts.values()
            if row["workstream_id"] == workstream_id
        }
        missing = sorted({"RESULT", "INDEPENDENT_PROOF"} - present)
        payload = {
            "workstream_id": workstream_id,
            "state": "VERIFIED" if not missing else "PARTIALLY_VERIFIED",
            "missing": missing,
            "omega_publication_id": publication_id,
        }
        self.sol.append_event("COMPLETION_EVALUATED", payload)
        return payload

    def _update_sol_reliability_once(self, action_class: str, publication_id: str) -> dict[str, Any]:
        matches = [
            event["payload"]
            for event in self.sol._events()
            if event.get("event_type") == "RELIABILITY_UPDATED"
            and event.get("payload", {}).get("omega_publication_id") == publication_id
        ]
        if len(matches) > 1:
            raise RuntimeError("SOL_RELIABILITY_RAW_DUPLICATE")
        if matches:
            return dict(matches[0])
        current = self.sol.state.reliability.get(action_class, {"attempts": 0, "verified_successes": 0})
        attempts = int(current.get("attempts", 0)) + 1
        successes = int(current.get("verified_successes", 0)) + 1
        success_rate = successes / attempts
        autonomy = (
            "AUTOMATIC" if success_rate >= 0.98
            else "EXTRA_VERIFICATION" if success_rate >= 0.90
            else "SHADOW_FIRST" if success_rate >= 0.75
            else "CONTROLLED"
        )
        payload = {
            "action_class": action_class,
            "attempts": attempts,
            "verified_successes": successes,
            "success_rate": success_rate,
            "autonomy": autonomy,
            "omega_publication_id": publication_id,
        }
        self.sol.append_event("RELIABILITY_UPDATED", payload)
        return payload

    def _materialize_proof_finalization(
        self,
        payload: Mapping[str, Any],
        *,
        transition_id: str,
        claim_token: str,
    ) -> CompletionCertificate:
        task_key = str(payload["task_key"])
        publication_id = str(payload["publication_id"])
        row = self.state["tasks"].get(task_key)
        if row is None or row["state"] != TaskState.VERIFYING.value:
            raise RuntimeError("PROOF_FINALIZATION_STATE_DIVERGENCE")
        lease_id = str(payload["lease_id"])
        lease = self.state["leases"].get(lease_id)
        if (
            not lease
            or lease.get("active") is not True
            or int(lease.get("fencing_token", 0)) != int(payload["fencing_token"])
            or int(self.state["fences"].get(task_key, 0)) != int(payload["fencing_token"])
            or int(lease.get("mission_version", 0)) != int(payload["mission_version"])
        ):
            raise RuntimeError("PROOF_FINALIZATION_STALE_FENCE")

        worker_receipt = self.worker_plane.complete(
            task_key,
            str(payload["worker_id"]),
            {"output_digest": str(payload["output_digest"]), "omega_publication_id": publication_id},
        )
        if worker_receipt.get("result", {}).get("output_digest") != payload["output_digest"]:
            raise RuntimeError("WORKER_RESULT_IDEMPOTENCY_CONFLICT")
        self._inject_fault("after_proof_worker_completion")

        workstream_id = str(payload["workstream_id"])
        self._record_sol_receipt_once(
            workstream_id=workstream_id,
            receipt_type="RESULT",
            body={"output_digest": str(payload["output_digest"])},
            publication_id=publication_id,
        )
        self._inject_fault("after_proof_result_receipt")
        self._record_sol_receipt_once(
            workstream_id=workstream_id,
            receipt_type="INDEPENDENT_PROOF",
            body=dict(payload["proof_body"]),
            publication_id=publication_id,
        )
        self._inject_fault("after_proof_independent_receipt")
        verdict = self._evaluate_sol_completion_once(workstream_id, publication_id)
        if verdict["state"] != "VERIFIED":
            raise RuntimeError("SOL_COMPLETION_DIVERGENCE")
        self._update_sol_reliability_once(str(payload["action_class"]), publication_id)
        self._inject_fault("after_proof_publication")

        certificate = CompletionCertificate(
            str(payload["certificate_id"]),
            task_key,
            int(payload["mission_version"]),
            str(payload["output_digest"]),
            str(payload["proof_digest"]),
            str(payload["verifier_id"]),
        )
        previous_state = deepcopy(self.state)
        self.state["certificates"][task_key] = asdict(certificate)
        row["state"] = TaskState.PROVEN.value
        self.state["leases"][lease_id]["active"] = False
        self.state["workers"][str(payload["worker_id"])]["running"] -= 1
        self._event("TASK_PROVEN", {"task_key": task_key, "certificate_id": certificate.certificate_id})
        self._refresh_ready()
        try:
            commit = self.store.commit(
                self.state,
                expected_revision=self._revision,
                applied_transition={"transition_id": transition_id, "claim_token": claim_token},
            )
        except Exception:
            self.state = previous_state
            raise
        self._revision = commit.revision_after
        return certificate

    def schedule_wave(self, *, max_concurrency: int = 3, lease_seconds: int = 60) -> tuple[LeaseReceipt, ...]:
        if max_concurrency < 1:
            raise ValueError("MAX_CONCURRENCY_INVALID")
        with self._lock:
            self._drain_transition_outbox()
            ready_changed = self._refresh_ready()
            _, assignments = self._plan_wave(max_concurrency)
            if not assignments:
                if ready_changed:
                    self._persist()
                return ()
            if len(assignments) == 1:
                lease = self.schedule_next(lease_seconds=lease_seconds)
                return (lease,) if lease else ()

            previous_state = deepcopy(self.state)
            receipts: list[LeaseReceipt] = []
            for key, row, worker in assignments:
                job = self.worker_plane.state.jobs[key]
                fence = int(self.state["fences"].get(key, 0)) + 1
                self.state["fences"][key] = fence
                lease_id = str(uuid4())
                receipt = LeaseReceipt(
                    lease_id,
                    key,
                    worker["worker_id"],
                    int(key.split(":v", 1)[1].split(":", 1)[0]),
                    fence,
                    int(job["attempts"]) + 1,
                    row["spec"]["input_digest"],
                )
                receipts.append(receipt)
                self.state["leases"][lease_id] = asdict(receipt) | {"active": True}
                row["state"] = TaskState.RUNNING.value
                row["lease_id"] = lease_id
                self.state["workers"][worker["worker_id"]]["running"] += 1
                spec = row["spec"]
                tenant = spec["tenant_id"]
                self.state["dispatch_counts"][tenant] = int(self.state["dispatch_counts"].get(tenant, 0)) + int(spec["service_units"])
                self._event("TASK_LEASED", {"task_key": key, "worker_id": worker["worker_id"], "fence": fence, "wave": True})

            transition_id = f"dispatch:{uuid4()}"
            transition = {
                "transition_id": transition_id,
                "transition_kind": "DISPATCH_WAVE",
                "mission_id": self.state["tasks"][receipts[0].task_key]["spec"]["mission_id"],
                "mission_version": receipts[0].mission_version,
                "payload": {
                    "lease_seconds": lease_seconds,
                    "assignments": [
                        {
                            "lease_id": receipt.lease_id,
                            "task_key": receipt.task_key,
                            "worker_id": receipt.worker_id,
                            "attempt": receipt.attempt,
                        }
                        for receipt in receipts
                    ],
                },
            }
            try:
                commit = self.store.commit(
                    self.state,
                    expected_revision=self._revision,
                    transition_outbox=transition,
                )
            except Exception:
                self.state = previous_state
                raise
            self._revision = commit.revision_after
            self._inject_fault("after_dispatch_wave_commit")
            self._drain_transition_outbox()
            return tuple(receipts)

    def issue_effect_permit(self, lease: LeaseReceipt, action_digest: str, *, owner_authorized: bool = False) -> dict[str, Any]:
        with self._lock:
            row = self._active_lease(lease)
            spec = row["spec"]
            if spec["effect_class"] == EffectClass.READ.value:
                raise ValueError("READ_TASK_NEEDS_NO_EFFECT_PERMIT")
            if AUTHORITY_RANK[spec["authority"]] >= AUTHORITY_RANK["A2"] and not owner_authorized:
                raise PermissionError("OWNER_AUTHORITY_REQUIRED")
            permit_id = str(uuid4())
            permit = {"permit_id": permit_id, "mission_id": spec["mission_id"], "task_key": lease.task_key,
                      "mission_version": lease.mission_version, "fencing_token": lease.fencing_token,
                      "action_digest": action_digest, "state": "ISSUED", "single_use": True}
            self.state["permits"][permit_id] = permit
            self._event("EFFECT_PERMIT_ISSUED", {"permit_id": permit_id, "task_key": lease.task_key})
            self._persist()
            return dict(permit)

    def record_simulated_effect(self, lease: LeaseReceipt, permit_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Exercise effect invariants locally; this method performs no external effect."""
        with self._lock:
            row = self._active_lease(lease)
            permit = self.state["permits"].get(permit_id)
            action_digest = digest(payload)
            if not permit or permit["state"] not in {"ISSUED", "CONSUMED"} or permit["task_key"] != lease.task_key:
                raise PermissionError("INVALID_EFFECT_PERMIT")
            if permit["fencing_token"] != lease.fencing_token or permit["action_digest"] != action_digest:
                raise PermissionError("EFFECT_PERMIT_BINDING_MISMATCH")
            key = row["spec"]["idempotency_key"]
            existing = self.state["effects"].get(key)
            if existing:
                if existing["action_digest"] != action_digest:
                    row["state"] = TaskState.DEAD_LETTER.value
                    self._persist()
                    raise ValueError("IDEMPOTENCY_INTEGRITY_CONFLICT")
                return dict(existing)
            if permit["state"] != "ISSUED":
                raise PermissionError("EFFECT_PERMIT_ALREADY_CONSUMED")
            permit["state"] = "CONSUMED"
            receipt = {"idempotency_key": key, "task_key": lease.task_key, "fencing_token": lease.fencing_token,
                       "action_digest": action_digest, "readback_verified": True,
                       "status": "LOCAL_SIMULATION_ONLY", "external_effect": False}
            receipt["receipt_digest"] = digest(receipt)
            self.state["effects"][key] = receipt
            self._event("SIMULATED_EFFECT_RECORDED", {"task_key": lease.task_key, "receipt_digest": receipt["receipt_digest"]})
            self._persist()
            return dict(receipt)

    def _active_lease(self, lease: LeaseReceipt) -> dict[str, Any]:
        stored = self.state["leases"].get(lease.lease_id)
        if not stored or not stored["active"] or stored["fencing_token"] != lease.fencing_token:
            raise ValueError("STALE_OR_UNKNOWN_LEASE")
        if int(self.state["fences"].get(lease.task_key, 0)) != lease.fencing_token:
            raise ValueError("STALE_FENCE")
        row = self.state["tasks"][lease.task_key]
        current = self.state["missions"].get(row["spec"]["mission_id"])
        if not current or int(current["version"]) != lease.mission_version or row["state"] != TaskState.RUNNING.value:
            raise ValueError("STALE_MISSION_OR_TASK_STATE")
        return row

    def submit_candidate(self, lease: LeaseReceipt, output: Any, proof: ProofBundle, *, effect_receipt: Mapping[str, Any] | None = None) -> CompletionCertificate:
        with self._lock:
            row = self._active_lease(lease)
            if proof.verifier_id == lease.worker_id:
                raise ValueError("SELF_VERIFICATION_PROHIBITED")
            observed_digest = output_digest(output)
            if proof.output_digest != observed_digest or not proof.valid:
                raise ValueError("INDEPENDENT_PROOF_FAILED")
            spec = row["spec"]
            if spec["effect_class"] != EffectClass.READ.value:
                if not effect_receipt or not effect_receipt.get("readback_verified") or effect_receipt.get("fencing_token") != lease.fencing_token:
                    raise ValueError("EFFECT_READBACK_PROOF_REQUIRED")
            proof_body = asdict(proof)
            publication_id = f"proof-finalize:{lease.task_key}"
            proof_digest = digest(proof_body)
            effect_digest = digest(dict(effect_receipt)) if effect_receipt is not None else None
            binding = canonical_digest(
                {
                    "publication_id": publication_id,
                    "task_key": lease.task_key,
                    "workstream_id": row["workstream_id"],
                    "mission_version": lease.mission_version,
                    "lease_id": lease.lease_id,
                    "worker_id": lease.worker_id,
                    "attempt": lease.attempt,
                    "fencing_token": lease.fencing_token,
                    "input_digest": lease.input_digest,
                    "output_digest": observed_digest,
                    "proof_digest": proof_digest,
                    "verifier_id": proof.verifier_id,
                    "effect_receipt_digest": effect_digest,
                }
            )
            certificate_id = f"cert-{binding[:24]}"
            transition = {
                "transition_id": publication_id,
                "transition_kind": "PROOF_FINALIZATION",
                "mission_id": str(spec["mission_id"]),
                "mission_version": lease.mission_version,
                "payload": {
                    "publication_id": publication_id,
                    "binding_sha256": binding,
                    "task_key": lease.task_key,
                    "workstream_id": row["workstream_id"],
                    "action_class": str(spec["capability"]),
                    "mission_version": lease.mission_version,
                    "lease_id": lease.lease_id,
                    "worker_id": lease.worker_id,
                    "attempt": lease.attempt,
                    "fencing_token": lease.fencing_token,
                    "input_digest": lease.input_digest,
                    "output_digest": observed_digest,
                    "proof_body": proof_body,
                    "proof_digest": proof_digest,
                    "verifier_id": proof.verifier_id,
                    "effect_receipt_digest": effect_digest,
                    "certificate_id": certificate_id,
                },
            }
            previous_state = deepcopy(self.state)
            row["state"] = TaskState.VERIFYING.value
            self._event("PROOF_FINALIZATION_INTENT", {"task_key": lease.task_key, "publication_id": publication_id, "binding_sha256": binding})
            try:
                commit = self.store.commit(
                    self.state,
                    expected_revision=self._revision,
                    transition_outbox=transition,
                )
            except Exception:
                self.state = previous_state
                raise
            self._revision = commit.revision_after
            self._inject_fault("after_proof_intent_commit")
            self._drain_transition_outbox()
            return CompletionCertificate(**self.state["certificates"][lease.task_key])

    def fail_task(self, lease: LeaseReceipt, failure_class: str, message: str, *, backoff_seconds: int = 0) -> str:
        with self._lock:
            row = self._active_lease(lease)
            job = self.worker_plane.fail(lease.task_key, lease.worker_id, failure_class, message, backoff_seconds)
            state = TaskState.DEAD_LETTER if job["status"] == "DEAD_LETTER" else TaskState.RETRY_WAIT
            row["state"] = state.value
            row["last_error"] = {"class": failure_class, "message": message}
            self.state["leases"][lease.lease_id]["active"] = False
            self.state["workers"][lease.worker_id]["running"] -= 1
            self.sol.update_reliability(row["spec"]["capability"], False)
            self._event("TASK_FAILED", {"task_key": lease.task_key, "state": state.value})
            self._persist()
            return state.value

    def cancel_mission(self, mission_id: str) -> dict[str, Any]:
        with self._lock:
            mission = self.state["missions"].get(mission_id)
            if not mission:
                raise KeyError("MISSION_NOT_FOUND")
            mission["state"] = "CANCELLED"
            for row in self.state["tasks"].values():
                if row["spec"]["mission_id"] != mission_id or row["state"] in {TaskState.PROVEN.value, TaskState.CANCELLED.value}:
                    continue
                row["state"] = TaskState.CANCELLING.value if row["state"] == TaskState.RUNNING.value else TaskState.CANCELLED.value
                lease_id = row.get("lease_id")
                if lease_id and lease_id in self.state["leases"]:
                    lease_row = self.state["leases"][lease_id]
                    if lease_row["active"]:
                        worker_row = self.state["workers"].get(lease_row["worker_id"])
                        if worker_row:
                            worker_row["running"] = max(0, int(worker_row["running"]) - 1)
                    lease_row["active"] = False
            for permit in self.state["permits"].values():
                if permit["mission_id"] == mission_id and permit["state"] == "ISSUED":
                    permit["state"] = "REVOKED"
            self._event("MISSION_CANCELLED", {"mission_id": mission_id, "version": mission["version"]})
            self._persist()
            return self.mission_status(mission_id)

    def recover_expired_leases(self, *, as_of: str | None = None) -> tuple[str, ...]:
        with self._lock:
            recovered = tuple(self.worker_plane.recover_expired_leases(as_of))
            for key in recovered:
                row = self.state["tasks"][key]
                job = self.worker_plane.state.jobs[key]
                lease_id = row.get("lease_id")
                if lease_id and self.state["leases"].get(lease_id, {}).get("active"):
                    worker_id = self.state["leases"][lease_id]["worker_id"]
                    self.state["leases"][lease_id]["active"] = False
                    self.state["workers"][worker_id]["running"] = max(0, self.state["workers"][worker_id]["running"] - 1)
                row["state"] = TaskState.DEAD_LETTER.value if job["status"] == "DEAD_LETTER" else TaskState.RETRY_WAIT.value
            if recovered:
                self._event("LEASES_RECOVERED", {"task_keys": recovered})
                self._persist()
            return recovered

    def mission_status(self, mission_id: str) -> dict[str, Any]:
        mission = self.state["missions"].get(mission_id)
        if not mission:
            raise KeyError("MISSION_NOT_FOUND")
        version = int(mission["version"])
        tasks = {key: row["state"] for key, row in self.state["tasks"].items() if row["spec"]["mission_id"] == mission_id and f":v{version}:" in key}
        terminal = bool(tasks) and all(state in {TaskState.PROVEN.value, TaskState.CANCELLED.value, TaskState.DEAD_LETTER.value} for state in tasks.values())
        proven = bool(tasks) and all(state == TaskState.PROVEN.value for state in tasks.values())
        return {"mission_id": mission_id, "version": version, "state": "PROVEN" if proven else mission["state"], "terminal": terminal, "tasks": dict(sorted(tasks.items()))}

    def verify_integrity(self) -> bool:
        if not self.store.verify_integrity() or self.store.status()["pending_outbox"] != 0:
            return False
        previous = "GENESIS"
        for row in self.state["events"]:
            if row["previous"] != previous or digest({k: v for k, v in row.items() if k != "hash"}) != row["hash"]:
                return False
            previous = row["hash"]
        observed_idempotency: dict[str, str] = {}
        for key, row in self.state["tasks"].items():
            job = self.worker_plane.state.jobs.get(key)
            idempotency_key = row["spec"].get("idempotency_key") or key
            reservation = self.store.reservation(idempotency_key)
            if (
                not job
                or job.get("job_id") != key
                or job.get("idempotency_key") != idempotency_key
                or self.worker_plane.state.idempotency.get(idempotency_key) != key
                or not reservation
                or reservation.get("task_key") != key
                or idempotency_key in observed_idempotency
            ):
                return False
            observed_idempotency[idempotency_key] = key
        for idempotency_key, key in self.worker_plane.state.idempotency.items():
            job = self.worker_plane.state.jobs.get(key)
            if not job or job.get("idempotency_key") != idempotency_key:
                return False
        return self.sol.verify_event_chain() and self.worker_plane.verify_event_chain()
