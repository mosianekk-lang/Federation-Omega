from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Callable, Iterable, Mapping, Sequence


class WorkerKind(str, Enum):
    AGENT = "AGENT"
    BOT = "BOT"


class EffectClass(str, Enum):
    INTERNAL = "INTERNAL"
    READ_ONLY_PROVIDER = "READ_ONLY_PROVIDER"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    CONSEQUENTIAL_WRITE = "CONSEQUENTIAL_WRITE"


_EFFECT_RANK = {
    EffectClass.INTERNAL: 0,
    EffectClass.READ_ONLY_PROVIDER: 1,
    EffectClass.REVERSIBLE_WRITE: 2,
    EffectClass.CONSEQUENTIAL_WRITE: 3,
}


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CONSTRAINT = "CONSTRAINT"


class MissionState(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    label: str
    kind: WorkerKind
    capabilities: tuple[str, ...]
    effect_ceiling: EffectClass = EffectClass.INTERNAL
    deterministic: bool = False
    independent_verifier: bool = False
    max_parallel: int = 1


@dataclass(frozen=True)
class DirectiveTask:
    task_id: str
    objective: str
    capabilities: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    target: str = "INTERNAL"
    effect: EffectClass = EffectClass.INTERNAL
    required: bool = True
    retryable: bool = True
    preferred_agents: tuple[str, ...] = ()
    idempotency_key: str | None = None

    @property
    def fingerprint(self) -> str:
        raw = json.dumps(
            {
                "task_id": self.task_id,
                "objective": self.objective.strip(),
                "capabilities": sorted(x.casefold() for x in self.capabilities),
                "depends_on": sorted(self.depends_on),
                "target": self.target.strip(),
                "effect": self.effect.value,
                "required": self.required,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DirectiveMission:
    mission_id: str
    objective: str
    tasks: tuple[DirectiveTask, ...]
    max_safe_parallel: int = 4
    max_effect_lanes: int = 1


@dataclass(frozen=True)
class TaskAssignment:
    task_id: str
    wave: int
    primary_agents: tuple[str, ...]
    support_bots: tuple[str, ...]
    uncovered_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectPermit:
    permit_id: str
    mission_id: str
    task_id: str
    target: str
    effect: EffectClass
    route_fingerprint: str


@dataclass(frozen=True)
class AgentReceipt:
    receipt_id: str
    mission_id: str
    task_id: str
    state: TaskState
    agent_ids: tuple[str, ...]
    bot_ids: tuple[str, ...]
    route_fingerprint: str
    evidence_refs: tuple[str, ...] = ()
    result: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


@dataclass(frozen=True)
class MissionPlan:
    mission_id: str
    objective: str
    assignments: tuple[TaskAssignment, ...]
    waves: tuple[tuple[str, ...], ...]
    unresolved_tasks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "assignments": [asdict(item) for item in self.assignments],
            "waves": [list(wave) for wave in self.waves],
            "unresolved_tasks": list(self.unresolved_tasks),
        }


@dataclass
class WorkerTelemetry:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    constraints: int = 0
    elapsed_ms_total: float = 0.0

    @property
    def reliability(self) -> float:
        return 0.5 if not self.attempts else self.successes / self.attempts


Guard = Callable[[DirectiveTask], tuple[bool, str]]
Executor = Callable[[DirectiveTask, TaskAssignment], Mapping[str, Any]]
Verifier = Callable[[DirectiveTask, Mapping[str, Any]], tuple[bool, str, Sequence[str]]]


DEFAULT_WORKERS = (
    WorkerSpec("BUBBLES-OMEGA-CONTROLLER", "Bubbles Omega Controller", WorkerKind.AGENT, ("orchestration", "planning", "synthesis", "completion")),
    WorkerSpec("BUBBLES-OMEGA-FORGE", "Forge Agent", WorkerKind.AGENT, ("software", "testing", "runtime", "implementation"), max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-SCOUT", "Scout Agent", WorkerKind.AGENT, ("research", "discovery", "source-analysis", "hypothesis"), max_parallel=3),
    WorkerSpec("BUBBLES-OMEGA-BRIDGE", "Bridge Agent", WorkerKind.AGENT, ("integration", "connector", "provider-read", "automation", "routing"), EffectClass.READ_ONLY_PROVIDER, max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-LEDGER", "Ledger Agent", WorkerKind.AGENT, ("evidence", "provenance", "proof", "readback", "claims"), independent_verifier=True, max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-PATCH", "Patch Agent", WorkerKind.AGENT, ("recovery", "retry", "rollback", "resilience", "anti-stall"), max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-SENTINEL", "Sentinel Agent", WorkerKind.AGENT, ("security", "privacy", "preflight", "risk", "integrity"), independent_verifier=True, max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-PULSE", "Pulse Agent", WorkerKind.AGENT, ("benchmark", "metrics", "evaluation", "optimization", "cfbe"), independent_verifier=True, max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-PRISM", "Prism Agent", WorkerKind.AGENT, ("presentation", "summary", "explainability", "ux"), max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-BEACON", "Beacon Agent", WorkerKind.AGENT, ("handoff", "next-action", "coordination", "checkpoint"), max_parallel=2),
    WorkerSpec("BUBBLES-OMEGA-QUEUE-BOT", "Queue Bot", WorkerKind.BOT, ("queue", "dependency-order"), deterministic=True, max_parallel=8),
    WorkerSpec("BUBBLES-OMEGA-DEDUP-BOT", "Dedup Bot", WorkerKind.BOT, ("dedup", "idempotency"), deterministic=True, max_parallel=8),
    WorkerSpec("BUBBLES-OMEGA-CHECKPOINT-BOT", "Checkpoint Bot", WorkerKind.BOT, ("checkpoint", "resume"), deterministic=True, max_parallel=8),
    WorkerSpec("BUBBLES-OMEGA-PROOF-BOT", "Proof Bot", WorkerKind.BOT, ("proof-capture", "terminal-receipt"), deterministic=True, max_parallel=8),
    WorkerSpec("BUBBLES-OMEGA-RETRY-BOT", "Retry Bot", WorkerKind.BOT, ("retry-control", "route-quarantine"), deterministic=True, max_parallel=8),
    WorkerSpec("BUBBLES-OMEGA-HANDOFF-BOT", "Handoff Bot", WorkerKind.BOT, ("handoff-packet", "dependency-release"), deterministic=True, max_parallel=8),
    WorkerSpec("BUBBLES-OMEGA-COMPLETION-BOT", "Completion Bot", WorkerKind.BOT, ("completion-gate", "directive-fruit"), deterministic=True, max_parallel=8),
)


class BubblesOmegaAgentFabric:
    """Provider-neutral Bubbles Omega agent/bot fabric.

    Source deployment does not create hidden background agents or provider authority.
    Provider effects require an injected executor and exact route-bound single-use permit.
    Write effects additionally require an injected guard and independent semantic verifier.
    Permit/idempotency/task-output state in this class is process-local; provider-write
    promotion additionally requires a durable external permit/idempotency ledger and readback.
    """

    version = "BUBBLES-OMEGA-AGENT-FABRIC-V1"

    def __init__(self, workers: Iterable[WorkerSpec] = DEFAULT_WORKERS) -> None:
        self.workers = {item.worker_id: item for item in workers}
        if "BUBBLES-OMEGA-CONTROLLER" not in self.workers:
            raise ValueError("BUBBLES-OMEGA-CONTROLLER is required")
        if any(worker.max_parallel < 1 for worker in self.workers.values()):
            raise ValueError("worker max_parallel must be at least 1")
        self.receipts: dict[str, AgentReceipt] = {}
        self.receipt_by_idempotency: dict[str, str] = {}
        self.task_state: dict[tuple[str, str], TaskState] = {}
        self.task_outputs: dict[tuple[str, str], Mapping[str, Any]] = {}
        self.last_failed_route: dict[tuple[str, str], str] = {}
        self.consumed_permits: set[str] = set()
        self.telemetry = {key: WorkerTelemetry() for key in self.workers}

    @staticmethod
    def _tasks(mission: DirectiveMission) -> dict[str, DirectiveTask]:
        if not mission.tasks:
            raise ValueError("mission must contain at least one task")
        if mission.max_safe_parallel < 1:
            raise ValueError("max_safe_parallel must be at least 1")
        if mission.max_effect_lanes < 0:
            raise ValueError("max_effect_lanes cannot be negative")
        tasks = {task.task_id: task for task in mission.tasks}
        if len(tasks) != len(mission.tasks):
            raise ValueError("Task IDs must be unique")
        for task in mission.tasks:
            missing = set(task.depends_on).difference(tasks)
            if missing:
                raise ValueError(f"missing dependencies for {task.task_id}: {sorted(missing)}")
        return tasks

    @classmethod
    def _waves(cls, mission: DirectiveMission) -> tuple[tuple[str, ...], ...]:
        tasks = cls._tasks(mission)
        indegree = {key: 0 for key in tasks}
        children = {key: [] for key in tasks}
        for task in tasks.values():
            for parent in task.depends_on:
                indegree[task.task_id] += 1
                children[parent].append(task.task_id)
        ready = sorted(key for key, value in indegree.items() if value == 0)
        waves: list[tuple[str, ...]] = []
        visited = 0
        while ready:
            wave = tuple(ready)
            waves.append(wave)
            next_ready: list[str] = []
            for key in wave:
                visited += 1
                for child in children[key]:
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        next_ready.append(child)
            ready = sorted(next_ready)
        if visited != len(tasks):
            raise ValueError("Directive graph contains a cycle")
        return tuple(waves)

    def _agents_for(self, task: DirectiveTask) -> tuple[tuple[str, ...], tuple[str, ...]]:
        required = {item.casefold() for item in task.capabilities}
        if not required:
            return ("BUBBLES-OMEGA-CONTROLLER",), ()
        uncovered = set(required)
        selected: list[str] = []
        preferred = set(task.preferred_agents)
        candidates = [
            worker for worker in self.workers.values()
            if worker.kind == WorkerKind.AGENT
            and _EFFECT_RANK[worker.effect_ceiling] >= _EFFECT_RANK[task.effect]
        ]
        candidates.sort(key=lambda worker: (
            0 if worker.worker_id in preferred else 1,
            -self.telemetry[worker.worker_id].reliability,
            worker.worker_id,
        ))
        for worker in candidates:
            coverage = {item.casefold() for item in worker.capabilities}.intersection(uncovered)
            if coverage:
                selected.append(worker.worker_id)
                uncovered.difference_update(coverage)
            if not uncovered:
                break
        return tuple(selected), tuple(sorted(uncovered))

    @staticmethod
    def _bots_for(task: DirectiveTask) -> tuple[str, ...]:
        bots = ["BUBBLES-OMEGA-QUEUE-BOT", "BUBBLES-OMEGA-DEDUP-BOT", "BUBBLES-OMEGA-PROOF-BOT", "BUBBLES-OMEGA-COMPLETION-BOT"]
        if task.depends_on:
            bots += ["BUBBLES-OMEGA-CHECKPOINT-BOT", "BUBBLES-OMEGA-HANDOFF-BOT"]
        if task.retryable:
            bots.append("BUBBLES-OMEGA-RETRY-BOT")
        return tuple(bots)

    def compile(self, mission: DirectiveMission) -> MissionPlan:
        tasks = self._tasks(mission)
        waves = self._waves(mission)
        wave_of = {task_id: index for index, wave in enumerate(waves, 1) for task_id in wave}
        assignments: list[TaskAssignment] = []
        unresolved: list[str] = []
        for task_id, task in tasks.items():
            agents, missing = self._agents_for(task)
            unresolved += [task_id] if missing else []
            assignments.append(TaskAssignment(task_id, wave_of[task_id], agents, self._bots_for(task), missing))
        assignments.sort(key=lambda item: (item.wave, item.task_id))
        return MissionPlan(mission.mission_id, mission.objective, tuple(assignments), waves, tuple(sorted(unresolved)))

    def _state(self, mission_id: str, task_id: str) -> TaskState:
        return self.task_state.get((mission_id, task_id), TaskState.PENDING)

    @staticmethod
    def _idempotency_token(mission: DirectiveMission, task: DirectiveTask) -> str:
        material = task.idempotency_key or task.fingerprint
        return f"{mission.mission_id}|{task.task_id}|{task.target}|{task.effect.value}|{material}"

    @staticmethod
    def _receipt_projection(result: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "payload_persisted": False,
            "result_keys": tuple(sorted(str(key) for key in result)),
        }

    def ready_tasks(self, mission: DirectiveMission) -> tuple[str, ...]:
        tasks = self._tasks(mission)
        plan = self.compile(mission)
        assignments = {item.task_id: item for item in plan.assignments}
        worker_load: Counter[str] = Counter()
        running_total = 0
        running_effects = 0
        for task in tasks.values():
            if self._state(mission.mission_id, task.task_id) != TaskState.RUNNING:
                continue
            running_total += 1
            running_effects += int(task.effect != EffectClass.INTERNAL)
            for agent_id in assignments[task.task_id].primary_agents:
                worker_load[agent_id] += 1

        parallel_slots = max(0, mission.max_safe_parallel - running_total)
        effect_slots = max(0, mission.max_effect_lanes - running_effects)
        if parallel_slots == 0:
            return ()

        ready: list[str] = []
        for task in mission.tasks:
            assignment = assignments[task.task_id]
            if assignment.uncovered_capabilities:
                continue
            if self._state(mission.mission_id, task.task_id) != TaskState.PENDING:
                continue
            if not all(self._state(mission.mission_id, dep) == TaskState.SUCCESS for dep in task.depends_on):
                continue
            if any(worker_load[agent_id] >= self.workers[agent_id].max_parallel for agent_id in assignment.primary_agents):
                continue
            if task.effect != EffectClass.INTERNAL:
                if effect_slots <= 0:
                    continue
                effect_slots -= 1
            ready.append(task.task_id)
            for agent_id in assignment.primary_agents:
                worker_load[agent_id] += 1
            if len(ready) >= parallel_slots:
                break
        return tuple(ready)

    @staticmethod
    def _permit_matches(
        permit: EffectPermit | None,
        mission: DirectiveMission,
        task: DirectiveTask,
        route_fingerprint: str,
    ) -> bool:
        if task.effect == EffectClass.INTERNAL:
            return True
        return bool(
            permit
            and permit.mission_id == mission.mission_id
            and permit.task_id == task.task_id
            and permit.target == task.target
            and permit.effect == task.effect
            and permit.route_fingerprint == route_fingerprint
        )

    @staticmethod
    def _receipt_id(mission_id: str, task_id: str, route: str, state: TaskState) -> str:
        raw = f"{mission_id}|{task_id}|{route}|{state.value}".encode()
        return "BO-" + hashlib.sha256(raw).hexdigest()[:24]

    def _constraint(self, mission: DirectiveMission, task: DirectiveTask, assignment: TaskAssignment, route: str, note: str) -> AgentReceipt:
        receipt = AgentReceipt(self._receipt_id(mission.mission_id, task.task_id, route, TaskState.CONSTRAINT), mission.mission_id, task.task_id, TaskState.CONSTRAINT, assignment.primary_agents, assignment.support_bots, route, note=note)
        self.receipts[receipt.receipt_id] = receipt
        self.task_state[(mission.mission_id, task.task_id)] = TaskState.CONSTRAINT
        self.task_outputs.pop((mission.mission_id, task.task_id), None)
        self.last_failed_route[(mission.mission_id, task.task_id)] = route
        return receipt

    def run_task(self, *, mission: DirectiveMission, task_id: str, executor: Executor, route_fingerprint: str, permit: EffectPermit | None = None, guard: Guard | None = None, verifier: Verifier | None = None) -> AgentReceipt:
        task = self._tasks(mission)[task_id]
        assignment = next(item for item in self.compile(mission).assignments if item.task_id == task_id)
        if assignment.uncovered_capabilities:
            return self._constraint(mission, task, assignment, route_fingerprint, "UNRESOLVED_CAPABILITY_GAP")
        if not all(self._state(mission.mission_id, dep) == TaskState.SUCCESS for dep in task.depends_on):
            return self._constraint(mission, task, assignment, route_fingerprint, "DEPENDENCIES_NOT_SUCCESSFUL")
        idem = self._idempotency_token(mission, task)
        if idem in self.receipt_by_idempotency:
            return self.receipts[self.receipt_by_idempotency[idem]]
        if self.last_failed_route.get((mission.mission_id, task_id)) == route_fingerprint:
            return self._constraint(mission, task, assignment, route_fingerprint, "UNCHANGED_FAILED_ROUTE_QUARANTINED")
        if task.effect in {EffectClass.REVERSIBLE_WRITE, EffectClass.CONSEQUENTIAL_WRITE} and guard is None:
            return self._constraint(mission, task, assignment, route_fingerprint, "WRITE_GUARD_REQUIRED")
        if task.effect in {EffectClass.REVERSIBLE_WRITE, EffectClass.CONSEQUENTIAL_WRITE} and verifier is None:
            return self._constraint(mission, task, assignment, route_fingerprint, "INDEPENDENT_VERIFIER_REQUIRED")
        if not self._permit_matches(permit, mission, task, route_fingerprint):
            return self._constraint(mission, task, assignment, route_fingerprint, "EFFECT_PERMIT_REQUIRED_OR_MISMATCH")
        if permit and permit.permit_id in self.consumed_permits:
            return self._constraint(mission, task, assignment, route_fingerprint, "EFFECT_PERMIT_ALREADY_CONSUMED")
        if guard:
            try:
                allowed, note = guard(task)
            except Exception as exc:
                return self._constraint(mission, task, assignment, route_fingerprint, f"GUARD_ERROR:{type(exc).__name__}")
            if not allowed:
                return self._constraint(mission, task, assignment, route_fingerprint, f"GUARD_HOLD:{note}")

        # Consume a non-internal permit immediately before dispatch so a provider
        # effect cannot occur and then become replayable merely because local
        # result handling fails. A failed dispatch therefore requires a fresh permit.
        if permit and task.effect != EffectClass.INTERNAL:
            self.consumed_permits.add(permit.permit_id)

        self.task_state[(mission.mission_id, task_id)] = TaskState.RUNNING
        self.task_outputs.pop((mission.mission_id, task_id), None)
        started = time.perf_counter()
        try:
            full_result = dict(executor(task, assignment))
            state = TaskState(str(full_result.pop("state", TaskState.SUCCESS.value)))
            if state not in {TaskState.SUCCESS, TaskState.FAILURE, TaskState.CONSTRAINT}:
                raise ValueError("executor must return SUCCESS, FAILURE or CONSTRAINT")
            note = str(full_result.pop("note", ""))
            evidence = tuple(str(item) for item in full_result.pop("evidence_refs", ()))
        except Exception as exc:
            state = TaskState.FAILURE
            full_result = {"error_type": type(exc).__name__}
            note = f"EXECUTOR_ERROR:{type(exc).__name__}"
            evidence = ()
        elapsed = (time.perf_counter() - started) * 1000
        if state == TaskState.SUCCESS and verifier:
            try:
                verified, verify_note, verify_refs = verifier(task, full_result)
            except Exception as exc:
                verified, verify_note, verify_refs = False, f"VERIFIER_ERROR:{type(exc).__name__}", ()
            if not verified:
                state, note = TaskState.CONSTRAINT, f"VERIFICATION_HOLD:{verify_note}"
            evidence = tuple(dict.fromkeys((*evidence, *(str(item) for item in verify_refs))))
        if state == TaskState.SUCCESS and task.effect != EffectClass.INTERNAL and not evidence:
            state, note = TaskState.CONSTRAINT, "PROVIDER_READBACK_EVIDENCE_REQUIRED"

        if state == TaskState.SUCCESS:
            self.task_outputs[(mission.mission_id, task_id)] = dict(full_result)
        else:
            self.task_outputs.pop((mission.mission_id, task_id), None)

        receipt_result = self._receipt_projection(full_result)
        receipt = AgentReceipt(self._receipt_id(mission.mission_id, task_id, route_fingerprint, state), mission.mission_id, task_id, state, assignment.primary_agents, assignment.support_bots, route_fingerprint, evidence, receipt_result, note, elapsed)
        self.receipts[receipt.receipt_id] = receipt
        self.receipt_by_idempotency[idem] = receipt.receipt_id
        self.task_state[(mission.mission_id, task_id)] = state
        if state in {TaskState.FAILURE, TaskState.CONSTRAINT}:
            self.last_failed_route[(mission.mission_id, task_id)] = route_fingerprint
        for agent_id in receipt.agent_ids:
            t = self.telemetry[agent_id]
            t.attempts += 1
            t.elapsed_ms_total += elapsed
            t.successes += int(state == TaskState.SUCCESS)
            t.failures += int(state == TaskState.FAILURE)
            t.constraints += int(state == TaskState.CONSTRAINT)
        return receipt

    def task_output(self, mission_id: str, task_id: str) -> Mapping[str, Any] | None:
        """Return process-local successful output for an explicitly addressed task."""
        return self.task_outputs.get((mission_id, task_id))

    def reopen_task(self, mission: DirectiveMission, task_id: str, *, changed_route_fingerprint: str) -> None:
        task = self._tasks(mission)[task_id]
        if self.last_failed_route.get((mission.mission_id, task_id)) == changed_route_fingerprint:
            raise ValueError("retry route must materially differ")
        self.task_state[(mission.mission_id, task_id)] = TaskState.PENDING
        self.task_outputs.pop((mission.mission_id, task_id), None)
        idem = self._idempotency_token(mission, task)
        prior = self.receipt_by_idempotency.get(idem)
        if prior and self.receipts[prior].state != TaskState.SUCCESS:
            self.receipt_by_idempotency.pop(idem, None)

    def mission_state(self, mission: DirectiveMission) -> MissionState:
        self._tasks(mission)
        required = [task for task in mission.tasks if task.required]
        states = {task.task_id: self._state(mission.mission_id, task.task_id) for task in mission.tasks}
        if not required:
            return MissionState.COMPLETE if all(state == TaskState.SUCCESS for state in states.values()) else MissionState.ACTIVE
        if all(states[task.task_id] == TaskState.SUCCESS for task in required):
            return MissionState.COMPLETE
        if any(states[task.task_id] in {TaskState.FAILURE, TaskState.CONSTRAINT} for task in required):
            return MissionState.BLOCKED
        if any(state in {TaskState.RUNNING, TaskState.SUCCESS} for state in states.values()):
            return MissionState.ACTIVE
        return MissionState.PLANNED

    def completion_receipt(self, mission: DirectiveMission) -> dict[str, Any]:
        state = self.mission_state(mission)
        return {
            "schema": "BUBBLES-OMEGA-DIRECTIVE-COMPLETION-V1",
            "mission_id": mission.mission_id,
            "objective": mission.objective,
            "state": state.value,
            "directive_complete": state == MissionState.COMPLETE,
            "task_states": {task.task_id: self._state(mission.mission_id, task.task_id).value for task in mission.tasks},
            "proof_refs": sorted({ref for receipt in self.receipts.values() if receipt.mission_id == mission.mission_id for ref in receipt.evidence_refs}),
            "truth_boundary": "COMPLETE requires SUCCESS for every required task; source, tests and plans cannot self-certify provider effects.",
        }

    def benchmark_snapshot(self) -> dict[str, Any]:
        return {
            key: {
                "attempts": value.attempts,
                "successes": value.successes,
                "failures": value.failures,
                "constraints": value.constraints,
                "reliability": round(value.reliability, 6),
            }
            for key, value in sorted(self.telemetry.items())
            if self.workers[key].kind == WorkerKind.AGENT
        }
