"""Durable, effect-free multi-stream execution bridge for the CFBE vNext kernel.

The bridge turns a frozen mission into an immutable execution DAG.  Logical
agents may work on collision-free paths in parallel, but all state convergence
is serialized through SQLite and one sovereign fan-in per stream.  Fan-in may
select an *effect candidate*; it never performs an external effect or grants
provider authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import asyncio
import json
import math
import random
import sqlite3
import statistics
import time
from typing import Any, Iterable, Mapping, Sequence

from .core import CFBEKernelError, EvidenceProof, IdempotencyConflict, MissionExecutionKernel


SCHEMA = "CFBE-VNEXT-MULTISTREAM-EXECUTION-1"
MATURITY = "DETERMINISTIC_TESTED_LOCAL"
AGENT_ROLES = (
    "ROUTE", "BUILDER", "FALSIFIER", "EVIDENCE", "WITNESS", "SENTINEL", "RECOVERY"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise CFBEKernelError("TIME_INVALID") from exc
    if parsed.tzinfo is None:
        raise CFBEKernelError("TIME_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    value = str(value).strip()
    if not value or len(value) > 200:
        raise CFBEKernelError(f"{label}_INVALID")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:/-")
    if value[0] not in allowed or any(character not in allowed for character in value):
        raise CFBEKernelError(f"{label}_INVALID")
    return value


def _items(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _finite(value: float, label: str, *, nonnegative: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CFBEKernelError(f"{label}_MUST_BE_FINITE")
    if nonnegative and value < 0:
        raise CFBEKernelError(f"{label}_MUST_BE_NONNEGATIVE")
    return float(value)


class PathResultState(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CONSTRAINED = "CONSTRAINED"


class BenchmarkMode(StrEnum):
    SIMULATED = "SIMULATED"
    EQUAL_QUALITY = "EQUAL_QUALITY"


@dataclass(frozen=True, slots=True)
class CapabilityAttestation:
    capability: str
    state: str
    proof_ref: str

    def validate(self) -> "CapabilityAttestation":
        _identifier(self.capability, "CAPABILITY")
        _identifier(self.state, "CAPABILITY_STATE")
        if not str(self.proof_ref).strip():
            raise CFBEKernelError("CAPABILITY_PROOF_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    snapshot_id: str
    capabilities: tuple[str, ...]
    observed_at: str
    snapshot_sha256: str = ""

    @classmethod
    def create(
        cls, snapshot_id: str, capabilities: Iterable[str], *, observed_at: str | None = None
    ) -> "CapabilitySnapshot":
        candidate = cls(
            _identifier(snapshot_id, "CAPABILITY_SNAPSHOT_ID"),
            tuple(sorted(_items(capabilities))),
            observed_at or _now(),
        )
        _time(candidate.observed_at)
        body = {
            "snapshot_id": candidate.snapshot_id,
            "capabilities": candidate.capabilities,
            "observed_at": candidate.observed_at,
        }
        return replace(candidate, snapshot_sha256=_digest(body))

    @classmethod
    def from_attestations(
        cls,
        snapshot_id: str,
        attestations: Iterable[CapabilityAttestation],
        *,
        observed_at: str | None = None,
    ) -> "CapabilitySnapshot":
        verified: list[str] = []
        for attestation in attestations:
            attestation.validate()
            if attestation.state == "VERIFIED_LIVE":
                verified.append(attestation.capability)
        return cls.create(snapshot_id, verified, observed_at=observed_at)

    def validate(self) -> "CapabilitySnapshot":
        expected = CapabilitySnapshot.create(
            self.snapshot_id, self.capabilities, observed_at=self.observed_at
        )
        if self.snapshot_sha256 != expected.snapshot_sha256:
            raise CFBEKernelError("CAPABILITY_SNAPSHOT_HASH_MISMATCH")
        return self


@dataclass(frozen=True, slots=True)
class StreamNode:
    stream_id: str
    requirement_ids: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    collision_keys: tuple[str, ...] = ()
    effect_group_key: str = ""
    minimum_verified_paths: int = 1

    def validate(self) -> "StreamNode":
        _identifier(self.stream_id, "STREAM_ID")
        if not self.requirement_ids:
            raise CFBEKernelError("STREAM_REQUIREMENTS_REQUIRED")
        for item in self.requirement_ids:
            _identifier(item, "STREAM_REQUIREMENT_ID")
        for item in (*self.depends_on, *self.collision_keys):
            _identifier(item, "STREAM_REFERENCE")
        if self.effect_group_key:
            _identifier(self.effect_group_key, "EFFECT_GROUP_KEY")
        if isinstance(self.minimum_verified_paths, bool) or self.minimum_verified_paths < 1:
            raise CFBEKernelError("MINIMUM_VERIFIED_PATHS_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class PathCandidate:
    path_id: str
    stream_id: str
    family: str
    independent_group: str
    required_capabilities: tuple[str, ...] = ()
    collision_keys: tuple[str, ...] = ()
    expected_quality: float = 1.0
    estimated_cost: float = 0.0
    priority: int = 0
    logical_only: bool = True
    external_effect: bool = False

    def validate(self) -> "PathCandidate":
        for value, label in (
            (self.path_id, "PATH_ID"),
            (self.stream_id, "PATH_STREAM_ID"),
            (self.family, "PATH_FAMILY"),
            (self.independent_group, "INDEPENDENT_GROUP"),
        ):
            _identifier(value, label)
        for item in (*self.required_capabilities, *self.collision_keys):
            _identifier(item, "PATH_REFERENCE")
        _finite(self.expected_quality, "EXPECTED_QUALITY")
        _finite(self.estimated_cost, "ESTIMATED_COST")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise CFBEKernelError("PATH_PRIORITY_INVALID")
        if self.logical_only is not True or self.external_effect is not False:
            raise CFBEKernelError("MULTISTREAM_PATH_MUST_BE_LOGICAL_EFFECT_FREE")
        return self


@dataclass(frozen=True, slots=True)
class ExecutionGraph:
    graph_id: str
    mission_id: str
    mission_version: int
    contract_sha256: str
    formation_plan_sha256: str
    streams: tuple[StreamNode, ...]
    paths: tuple[PathCandidate, ...]
    max_parallel: int
    maximum_total_cost: float
    baseline_quality: float
    graph_sha256: str = ""

    @classmethod
    def create(
        cls,
        *,
        graph_id: str,
        mission_id: str,
        mission_version: int,
        contract_sha256: str,
        formation_plan_sha256: str,
        streams: Iterable[StreamNode],
        paths: Iterable[PathCandidate],
        max_parallel: int = 4,
        maximum_total_cost: float = 0,
        baseline_quality: float = 1,
    ) -> "ExecutionGraph":
        candidate = cls(
            graph_id=_identifier(graph_id, "GRAPH_ID"),
            mission_id=_identifier(mission_id, "MISSION_ID"),
            mission_version=mission_version,
            contract_sha256=str(contract_sha256).strip(),
            formation_plan_sha256=str(formation_plan_sha256).strip(),
            streams=tuple(streams),
            paths=tuple(paths),
            max_parallel=max_parallel,
            maximum_total_cost=maximum_total_cost,
            baseline_quality=baseline_quality,
        )
        candidate.validate()
        return replace(candidate, graph_sha256=_digest(candidate.body()))

    def validate(self) -> "ExecutionGraph":
        if isinstance(self.mission_version, bool) or self.mission_version < 1:
            raise CFBEKernelError("GRAPH_MISSION_VERSION_INVALID")
        if len(self.contract_sha256) < 16 or len(self.formation_plan_sha256) < 16:
            raise CFBEKernelError("GRAPH_SOURCE_HASH_REQUIRED")
        if not self.streams or not self.paths:
            raise CFBEKernelError("FINITE_EXECUTION_GRAPH_REQUIRED")
        if isinstance(self.max_parallel, bool) or self.max_parallel < 1:
            raise CFBEKernelError("MAX_PARALLEL_INVALID")
        _finite(self.maximum_total_cost, "MAXIMUM_TOTAL_COST")
        _finite(self.baseline_quality, "BASELINE_QUALITY")
        for stream in self.streams:
            stream.validate()
        for path in self.paths:
            path.validate()
        stream_ids = [item.stream_id for item in self.streams]
        path_ids = [item.path_id for item in self.paths]
        if len(stream_ids) != len(set(stream_ids)):
            raise CFBEKernelError("DUPLICATE_STREAM_ID")
        if len(path_ids) != len(set(path_ids)):
            raise CFBEKernelError("DUPLICATE_PATH_ID")
        known = set(stream_ids)
        for stream in self.streams:
            unknown = set(stream.depends_on) - known
            if unknown or stream.stream_id in stream.depends_on:
                raise CFBEKernelError("STREAM_DEPENDENCY_INVALID")
        for path in self.paths:
            if path.stream_id not in known:
                raise CFBEKernelError("PATH_STREAM_UNKNOWN")
        missing = known - {item.stream_id for item in self.paths}
        if missing:
            raise CFBEKernelError("STREAM_WITHOUT_PATH:" + ",".join(sorted(missing)))
        self._validate_acyclic()
        if sum(item.estimated_cost for item in self.paths) < 0:
            raise CFBEKernelError("GRAPH_COST_INVALID")
        if self.graph_sha256 and self.graph_sha256 != _digest(self.body()):
            raise CFBEKernelError("GRAPH_HASH_MISMATCH")
        return self

    def _validate_acyclic(self) -> None:
        dependencies = {item.stream_id: set(item.depends_on) for item in self.streams}
        remaining = set(dependencies)
        while remaining:
            ready = {item for item in remaining if not (dependencies[item] & remaining)}
            if not ready:
                raise CFBEKernelError("EXECUTION_GRAPH_CYCLE")
            remaining -= ready

    def body(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "graph_id": self.graph_id,
            "mission_id": self.mission_id,
            "mission_version": self.mission_version,
            "contract_sha256": self.contract_sha256,
            "formation_plan_sha256": self.formation_plan_sha256,
            "streams": [asdict(item) for item in self.streams],
            "paths": [asdict(item) for item in self.paths],
            "max_parallel": self.max_parallel,
            "maximum_total_cost": self.maximum_total_cost,
            "baseline_quality": self.baseline_quality,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "graph_sha256": self.graph_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionGraph":
        graph = cls(
            graph_id=value["graph_id"],
            mission_id=value["mission_id"],
            mission_version=value["mission_version"],
            contract_sha256=value["contract_sha256"],
            formation_plan_sha256=value["formation_plan_sha256"],
            streams=tuple(
                StreamNode(**{**item, "requirement_ids": tuple(item["requirement_ids"]), "depends_on": tuple(item["depends_on"]), "collision_keys": tuple(item["collision_keys"])})
                for item in value["streams"]
            ),
            paths=tuple(
                PathCandidate(**{**item, "required_capabilities": tuple(item["required_capabilities"]), "collision_keys": tuple(item["collision_keys"])})
                for item in value["paths"]
            ),
            max_parallel=value["max_parallel"],
            maximum_total_cost=value["maximum_total_cost"],
            baseline_quality=value["baseline_quality"],
            graph_sha256=value["graph_sha256"],
        )
        return graph.validate()


@dataclass(frozen=True, slots=True)
class DispatchPacket:
    packet_id: str
    graph_sha256: str
    mission_id: str
    mission_version: int
    stream_id: str
    path_id: str
    required_capabilities: tuple[str, ...]
    collision_keys: tuple[str, ...]
    expected_proof_claim: str
    logical_only: bool = True
    external_effect_authorized: bool = False


@dataclass(frozen=True, slots=True)
class LogicalAgentEnvelope:
    agent_id: str
    role: str
    packet: DispatchPacket
    authority_ceiling: str = "A1_INTERNAL"
    logical_only: bool = True
    may_self_certify: bool = False


@dataclass(frozen=True, slots=True)
class PathClaim:
    claim_id: str
    graph_sha256: str
    stream_id: str
    path_id: str
    worker_identity: str
    fence: int
    issued_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class PathResult:
    path_id: str
    claim_id: str
    claim_fence: int
    state: PathResultState
    proof_ids: tuple[str, ...] = ()
    measured_quality: float = 0
    benchmark_mode: BenchmarkMode = BenchmarkMode.SIMULATED
    failure_fingerprint: str = ""
    retry_after_predicate: str = ""
    critical_conflict: bool = False
    producer_identity: str = ""
    verifier_identity: str = ""

    def validate(self) -> "PathResult":
        _identifier(self.path_id, "RESULT_PATH_ID")
        _identifier(self.claim_id, "CLAIM_ID")
        if isinstance(self.claim_fence, bool) or self.claim_fence < 1:
            raise CFBEKernelError("CLAIM_FENCE_INVALID")
        _finite(self.measured_quality, "MEASURED_QUALITY")
        if self.state is PathResultState.VERIFIED and not self.proof_ids:
            raise CFBEKernelError("VERIFIED_PATH_REQUIRES_PROOF")
        if self.state is PathResultState.VERIFIED:
            _identifier(self.producer_identity, "RESULT_PRODUCER_IDENTITY")
            _identifier(self.verifier_identity, "RESULT_VERIFIER_IDENTITY")
            if self.producer_identity == self.verifier_identity:
                raise CFBEKernelError("INDEPENDENT_VERIFIER_REQUIRED")
        if self.state is PathResultState.FAILED and not self.failure_fingerprint.strip():
            raise CFBEKernelError("FAILED_PATH_REQUIRES_FINGERPRINT")
        if not isinstance(self.critical_conflict, bool):
            raise CFBEKernelError("CRITICAL_CONFLICT_TYPE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class FanInReceipt:
    graph_sha256: str
    stream_id: str
    selected_path_id: str
    corroborating_path_ids: tuple[str, ...]
    rejected_path_ids: tuple[str, ...]
    proof_ids: tuple[str, ...]
    benchmark_state: str
    effect_group_key: str
    decision_sha256: str
    maturity: str = MATURITY
    external_effect_executed: bool = False


@dataclass(frozen=True, slots=True)
class LogicalWorkerOutcome:
    packet_id: str
    path_id: str
    state: str
    elapsed_seconds: float
    value: Any = None
    failure_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class PairedBenchmarkObservation:
    serial_seconds: float
    parallel_seconds: float
    serial_quality: float
    parallel_quality: float
    proof_equivalent: bool = True
    security_equivalent: bool = True
    cost_not_increased: bool = True
    measurement_scope: str = "SYNTHETIC_SCHEDULER"

    def validate(self) -> "PairedBenchmarkObservation":
        if _finite(self.serial_seconds, "SERIAL_SECONDS") <= 0:
            raise CFBEKernelError("SERIAL_SECONDS_MUST_BE_POSITIVE")
        if _finite(self.parallel_seconds, "PARALLEL_SECONDS") <= 0:
            raise CFBEKernelError("PARALLEL_SECONDS_MUST_BE_POSITIVE")
        _finite(self.serial_quality, "SERIAL_QUALITY")
        _finite(self.parallel_quality, "PARALLEL_QUALITY")
        if self.measurement_scope not in {"SYNTHETIC_SCHEDULER", "REAL_MISSION"}:
            raise CFBEKernelError("BENCHMARK_MEASUREMENT_SCOPE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ThroughputClaimReceipt:
    state: str
    sample_count: int
    median_speedup: float
    one_sided_95_lower_bound: float
    quality_preserved: bool
    proof_preserved: bool
    security_preserved: bool
    cost_preserved: bool
    measurement_scope: str
    claim_sha256: str


def evaluate_throughput_claim(
    observations: Sequence[PairedBenchmarkObservation],
    *,
    minimum_samples: int = 30,
    target_speedup: float = 2.0,
    bootstrap_samples: int = 5000,
    seed: int = 20260909,
) -> ThroughputClaimReceipt:
    """Issue an evidence-grade speed claim only under equal-or-better outcomes."""
    if len(observations) < minimum_samples:
        raise CFBEKernelError("THROUGHPUT_SAMPLE_COUNT_INSUFFICIENT")
    if bootstrap_samples < 1000:
        raise CFBEKernelError("BOOTSTRAP_SAMPLE_COUNT_INSUFFICIENT")
    checked = tuple(item.validate() for item in observations)
    ratios = tuple(item.serial_seconds / item.parallel_seconds for item in checked)
    quality = all(item.parallel_quality >= item.serial_quality for item in checked)
    proof = all(item.proof_equivalent for item in checked)
    security = all(item.security_equivalent for item in checked)
    cost = all(item.cost_not_increased for item in checked)
    scope = (
        "REAL_MISSION"
        if all(item.measurement_scope == "REAL_MISSION" for item in checked)
        else "SYNTHETIC_SCHEDULER"
    )
    rng = random.Random(seed)
    medians = sorted(
        statistics.median(ratios[rng.randrange(len(ratios))] for _ in ratios)
        for _ in range(bootstrap_samples)
    )
    lower = medians[max(0, int(bootstrap_samples * 0.05) - 1)]
    median = statistics.median(ratios)
    preserved = quality and proof and security and cost
    if preserved and lower >= target_speedup and scope == "REAL_MISSION":
        state = "MEASURED_CAPABILITY_UPGRADE_GE_2X"
    elif preserved and lower >= target_speedup:
        state = "SIMULATED_SCHEDULING_SPEEDUP_ONLY"
    else:
        state = "MEASURED_NOT_PROVEN_GE_2X"
    body = {
        "state": state,
        "sample_count": len(checked),
        "median_speedup": median,
        "one_sided_95_lower_bound": lower,
        "quality_preserved": quality,
        "proof_preserved": proof,
        "security_preserved": security,
        "cost_preserved": cost,
        "measurement_scope": scope,
    }
    return ThroughputClaimReceipt(**body, claim_sha256=_digest(body))


async def execute_logical_wave(
    packets: Sequence[DispatchPacket],
    worker: Any,
    *,
    max_parallel: int,
) -> tuple[LogicalWorkerOutcome, ...]:
    """Run logical packets concurrently while containing failures per path."""
    if isinstance(max_parallel, bool) or max_parallel < 1:
        raise CFBEKernelError("MAX_PARALLEL_INVALID")
    semaphore = asyncio.Semaphore(max_parallel)

    async def run(packet: DispatchPacket) -> LogicalWorkerOutcome:
        if packet.logical_only is not True or packet.external_effect_authorized is not False:
            raise CFBEKernelError("UNSAFE_DISPATCH_PACKET")
        started = time.perf_counter()
        try:
            async with semaphore:
                value = await worker(packet)
            return LogicalWorkerOutcome(
                packet.packet_id, packet.path_id, "SUCCEEDED",
                time.perf_counter() - started, value=value,
            )
        except Exception as exc:  # failure is returned, not propagated to healthy siblings
            fingerprint = _digest({"type": type(exc).__name__, "message": str(exc)})
            return LogicalWorkerOutcome(
                packet.packet_id, packet.path_id, "FAILED",
                time.perf_counter() - started, failure_fingerprint=fingerprint,
            )

    outcomes = await asyncio.gather(*(run(packet) for packet in packets))
    return tuple(sorted(outcomes, key=lambda item: item.packet_id))


class MultiStreamExecutionBridge:
    """SQLite-backed execution state attached to one MissionExecutionKernel."""

    def __init__(self, kernel: MissionExecutionKernel):
        self.kernel = kernel
        self.database_path = kernel.store.path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cfbe_multistream_graphs (
                    graph_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL,
                    graph_sha256 TEXT NOT NULL UNIQUE,
                    graph_json TEXT NOT NULL,
                    state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cfbe_multistream_claims (
                    graph_sha256 TEXT NOT NULL,
                    path_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL UNIQUE,
                    worker_identity TEXT NOT NULL,
                    fence INTEGER NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    PRIMARY KEY(graph_sha256,path_id)
                );
                CREATE TABLE IF NOT EXISTS cfbe_multistream_results (
                    graph_sha256 TEXT NOT NULL,
                    path_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    result_sha256 TEXT NOT NULL,
                    PRIMARY KEY(graph_sha256,path_id)
                );
                CREATE TABLE IF NOT EXISTS cfbe_multistream_cancellations (
                    graph_sha256 TEXT NOT NULL,
                    path_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    cancelled_at TEXT NOT NULL,
                    PRIMARY KEY(graph_sha256,path_id)
                );
                CREATE TABLE IF NOT EXISTS cfbe_multistream_fanins (
                    graph_sha256 TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    decision_sha256 TEXT NOT NULL UNIQUE,
                    PRIMARY KEY(graph_sha256,stream_id)
                );
                CREATE TABLE IF NOT EXISTS cfbe_multistream_effect_winners (
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL,
                    effect_group_key TEXT NOT NULL,
                    graph_sha256 TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    path_id TEXT NOT NULL,
                    decision_sha256 TEXT NOT NULL,
                    PRIMARY KEY(mission_id,mission_version,effect_group_key)
                );
                """
            )

    def register_graph(self, graph: ExecutionGraph) -> ExecutionGraph:
        graph.validate()
        mission = self.kernel.project(graph.mission_id)
        if mission.contract.mission_version != graph.mission_version:
            raise CFBEKernelError("STALE_GRAPH_MISSION_VERSION")
        if mission.contract.contract_sha256 != graph.contract_sha256:
            raise CFBEKernelError("GRAPH_CONTRACT_HASH_MISMATCH")
        requirements = set(mission.requirement_states)
        graph_requirements = {item for stream in graph.streams for item in stream.requirement_ids}
        if not graph_requirements.issubset(requirements):
            raise CFBEKernelError("GRAPH_REQUIREMENT_UNKNOWN")
        if not set(mission.contract.critical_path).issubset(graph_requirements):
            raise CFBEKernelError("GRAPH_MUST_COVER_CRITICAL_PATH")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT graph_sha256 FROM cfbe_multistream_graphs WHERE graph_id=?", (graph.graph_id,)
            ).fetchone()
            if existing:
                if existing[0] != graph.graph_sha256:
                    raise IdempotencyConflict("GRAPH_ID_ALREADY_BOUND")
                return self.graph(graph.graph_id)
            connection.execute(
                "INSERT INTO cfbe_multistream_graphs VALUES(?,?,?,?,?,'ACTIVE')",
                (graph.graph_id, graph.mission_id, graph.mission_version, graph.graph_sha256, _canonical(graph.to_dict())),
            )
        return graph

    def graph(self, graph_id: str) -> ExecutionGraph:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT graph_json FROM cfbe_multistream_graphs WHERE graph_id=?", (graph_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"EXECUTION_GRAPH_UNKNOWN:{graph_id}")
        return ExecutionGraph.from_dict(json.loads(row[0]))

    def _graph_state(self, graph: ExecutionGraph) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM cfbe_multistream_graphs WHERE graph_sha256=?", (graph.graph_sha256,)
            ).fetchone()
        if row is None:
            raise KeyError(f"EXECUTION_GRAPH_UNKNOWN:{graph.graph_id}")
        return str(row[0])

    def _assert_current(self, graph: ExecutionGraph, *, require_active: bool = True) -> None:
        mission = self.kernel.project(graph.mission_id)
        if mission.contract.mission_version != graph.mission_version or mission.contract.contract_sha256 != graph.contract_sha256:
            raise CFBEKernelError("STALE_EXECUTION_GRAPH")
        if mission.mission_state.value != "OPEN":
            raise CFBEKernelError("EXECUTION_GRAPH_NOT_ACTIVE")
        if require_active and self._graph_state(graph) != "ACTIVE":
            raise CFBEKernelError("EXECUTION_GRAPH_NOT_ACTIVE")

    def _fanins(self, graph: ExecutionGraph) -> dict[str, FanInReceipt]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT stream_id,receipt_json FROM cfbe_multistream_fanins WHERE graph_sha256=?",
                (graph.graph_sha256,),
            ).fetchall()
        return {str(row[0]): self._receipt(json.loads(row[1])) for row in rows}

    @staticmethod
    def _receipt(value: Mapping[str, Any]) -> FanInReceipt:
        return FanInReceipt(
            **{
                **value,
                "corroborating_path_ids": tuple(value["corroborating_path_ids"]),
                "rejected_path_ids": tuple(value["rejected_path_ids"]),
                "proof_ids": tuple(value["proof_ids"]),
            }
        )

    def _result_rows(self, graph: ExecutionGraph) -> dict[str, Mapping[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path_id,result_json FROM cfbe_multistream_results WHERE graph_sha256=?",
                (graph.graph_sha256,),
            ).fetchall()
        return {str(row[0]): json.loads(row[1]) for row in rows}

    def _cancelled(self, graph: ExecutionGraph) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path_id FROM cfbe_multistream_cancellations WHERE graph_sha256=?",
                (graph.graph_sha256,),
            ).fetchall()
        return {str(row[0]) for row in rows}

    def ready_wave(
        self, graph_id: str, snapshot: CapabilitySnapshot, *, now: str | None = None
    ) -> tuple[DispatchPacket, ...]:
        graph = self.graph(graph_id)
        self._assert_current(graph)
        snapshot.validate()
        current_time = _time(now or _now())
        completed = set(self._fanins(graph))
        results = self._result_rows(graph)
        cancelled = self._cancelled(graph)
        streams = {item.stream_id: item for item in graph.streams}
        with self._connect() as connection:
            claim_rows = connection.execute(
                    "SELECT path_id,state,expires_at FROM cfbe_multistream_claims WHERE graph_sha256=?",
                    (graph.graph_sha256,),
                ).fetchall()
        claimed_paths = {str(row[0]) for row in claim_rows}
        actively_claimed = {
            str(row[0])
            for row in claim_rows
            if row[1] == "ACTIVE" and current_time < _time(row[2])
        }
        path_by_id = {item.path_id: item for item in graph.paths}
        candidates = [
            path
            for path in graph.paths
            if path.path_id not in results
            and path.path_id not in cancelled
            and path.path_id not in actively_claimed
            and path.stream_id not in completed
            and set(streams[path.stream_id].depends_on).issubset(completed)
            and set(path.required_capabilities).issubset(snapshot.capabilities)
        ]
        candidates.sort(key=lambda item: (-item.priority, -item.expected_quality, item.path_id))
        selected: list[PathCandidate] = []
        collision_keys: set[str] = set()
        for active_path_id in actively_claimed:
            active_path = path_by_id[active_path_id]
            collision_keys.update(streams[active_path.stream_id].collision_keys)
            collision_keys.update(active_path.collision_keys)
        total_cost = sum(path_by_id[item].estimated_cost for item in claimed_paths)
        for path in candidates:
            stream = streams[path.stream_id]
            keys = set(stream.collision_keys) | set(path.collision_keys)
            if keys & collision_keys:
                continue
            incremental_cost = 0 if path.path_id in claimed_paths else path.estimated_cost
            if total_cost + incremental_cost > graph.maximum_total_cost:
                continue
            selected.append(path)
            collision_keys |= keys
            total_cost += incremental_cost
            if len(selected) + len(actively_claimed) >= graph.max_parallel:
                break
        return tuple(
            DispatchPacket(
                packet_id=f"{graph.graph_id}:{path.path_id}",
                graph_sha256=graph.graph_sha256,
                mission_id=graph.mission_id,
                mission_version=graph.mission_version,
                stream_id=path.stream_id,
                path_id=path.path_id,
                required_capabilities=path.required_capabilities,
                collision_keys=tuple(sorted(set(streams[path.stream_id].collision_keys) | set(path.collision_keys))),
                expected_proof_claim=f"path:{path.path_id}",
            )
            for path in selected
        )

    def logical_agent_envelopes(self, packet: DispatchPacket) -> tuple[LogicalAgentEnvelope, ...]:
        if packet.logical_only is not True or packet.external_effect_authorized is not False:
            raise CFBEKernelError("UNSAFE_DISPATCH_PACKET")
        return tuple(
            LogicalAgentEnvelope(
                agent_id=f"{packet.packet_id}:{role.lower()}", role=role, packet=packet
            )
            for role in AGENT_ROLES
        )

    def claim_path(
        self,
        graph_id: str,
        path_id: str,
        worker_identity: str,
        snapshot: CapabilitySnapshot,
        *,
        ttl_seconds: int = 300,
        now: str | None = None,
    ) -> PathClaim:
        graph = self.graph(graph_id)
        self._assert_current(graph)
        _identifier(worker_identity, "WORKER_IDENTITY")
        snapshot.validate()
        path_by_id = {item.path_id: item for item in graph.paths}
        if path_id not in path_by_id:
            raise CFBEKernelError("PATH_UNKNOWN")
        if not set(path_by_id[path_id].required_capabilities).issubset(snapshot.capabilities):
            raise CFBEKernelError("PATH_NOT_READY_OR_CAPABLE")
        if isinstance(ttl_seconds, bool) or ttl_seconds < 1:
            raise CFBEKernelError("CLAIM_TTL_INVALID")
        issued = now or _now()
        with self._connect() as connection:
            prior = connection.execute(
                "SELECT * FROM cfbe_multistream_claims WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, path_id),
            ).fetchone()
        if prior and prior["state"] == "ACTIVE" and _time(issued) < _time(prior["expires_at"]):
            if prior["worker_identity"] != worker_identity:
                raise CFBEKernelError("PATH_ALREADY_CLAIMED")
            stream_id = next(
                item.stream_id for item in graph.paths if item.path_id == path_id
            )
            return replace(self._claim(prior), stream_id=stream_id)
        packets = {item.path_id: item for item in self.ready_wave(graph_id, snapshot, now=now)}
        if path_id not in packets:
            raise CFBEKernelError("PATH_NOT_READY_OR_CAPABLE")
        expires = (_time(issued) + timedelta(seconds=ttl_seconds)).isoformat()
        streams = {item.stream_id: item for item in graph.streams}
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM cfbe_multistream_cancellations WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, path_id),
            ).fetchone():
                raise CFBEKernelError("PATH_CANCELLED")
            row = connection.execute(
                "SELECT * FROM cfbe_multistream_claims WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, path_id),
            ).fetchone()
            if row and row["state"] == "ACTIVE" and _time(issued) < _time(row["expires_at"]):
                if row["worker_identity"] == worker_identity:
                    connection.rollback()
                    return replace(self._claim(row), stream_id=packets[path_id].stream_id)
                raise CFBEKernelError("PATH_ALREADY_CLAIMED")
            if connection.execute(
                "SELECT 1 FROM cfbe_multistream_results WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, path_id),
            ).fetchone():
                raise CFBEKernelError("PATH_ALREADY_COMPLETED")
            completed = {
                str(item[0]) for item in connection.execute(
                    "SELECT stream_id FROM cfbe_multistream_fanins WHERE graph_sha256=?",
                    (graph.graph_sha256,),
                ).fetchall()
            }
            path = path_by_id[path_id]
            if path.stream_id in completed or not set(streams[path.stream_id].depends_on).issubset(completed):
                raise CFBEKernelError("PATH_NOT_READY_OR_CAPABLE")
            active_rows = connection.execute(
                "SELECT path_id,expires_at FROM cfbe_multistream_claims "
                "WHERE graph_sha256=? AND state='ACTIVE'",
                (graph.graph_sha256,),
            ).fetchall()
            active_path_ids = {
                str(item["path_id"]) for item in active_rows if _time(issued) < _time(item["expires_at"])
            }
            if len(active_path_ids) >= graph.max_parallel:
                raise CFBEKernelError("MAX_PARALLEL_EXHAUSTED")
            occupied_keys: set[str] = set()
            for active_path_id in active_path_ids:
                active_path = path_by_id[active_path_id]
                occupied_keys.update(streams[active_path.stream_id].collision_keys)
                occupied_keys.update(active_path.collision_keys)
            requested_keys = set(streams[path.stream_id].collision_keys) | set(path.collision_keys)
            if requested_keys & occupied_keys:
                raise CFBEKernelError("COLLISION_KEY_ALREADY_CLAIMED")
            claimed_path_ids = {
                str(item[0]) for item in connection.execute(
                    "SELECT path_id FROM cfbe_multistream_claims WHERE graph_sha256=?",
                    (graph.graph_sha256,),
                ).fetchall()
            }
            reserved_cost = sum(
                path_by_id[item].estimated_cost for item in claimed_path_ids if item != path_id
            )
            if reserved_cost + path.estimated_cost > graph.maximum_total_cost:
                raise CFBEKernelError("GRAPH_TOTAL_COST_EXHAUSTED")
            fence = 1 if row is None else int(row["fence"]) + 1
            claim_id = "CFBE-CLAIM-" + _digest(
                [graph.graph_sha256, path_id, worker_identity, fence, issued]
            )[:24].upper()
            connection.execute(
                "INSERT OR REPLACE INTO cfbe_multistream_claims VALUES(?,?,?,?,?,?,?,'ACTIVE')",
                (graph.graph_sha256, path_id, claim_id, worker_identity, fence, issued, expires),
            )
            connection.commit()
        return PathClaim(claim_id, graph.graph_sha256, packets[path_id].stream_id, path_id, worker_identity, fence, issued, expires)

    @staticmethod
    def _claim(row: sqlite3.Row) -> PathClaim:
        return PathClaim(
            claim_id=row["claim_id"], graph_sha256=row["graph_sha256"], stream_id="",
            path_id=row["path_id"], worker_identity=row["worker_identity"], fence=row["fence"],
            issued_at=row["issued_at"], expires_at=row["expires_at"],
        )

    def _validate_path_proofs(
        self, graph: ExecutionGraph, path_id: str, proof_ids: Sequence[str], now: str
    ) -> tuple[EvidenceProof, ...]:
        projection = self.kernel.project(graph.mission_id)
        proofs: list[EvidenceProof] = []
        for proof_id in proof_ids:
            proof = projection.proofs.get(proof_id)
            if proof is None or proof_id in projection.invalidated_proofs:
                raise CFBEKernelError("CURRENT_PATH_PROOF_REQUIRED")
            if proof.mission_version != graph.mission_version or proof.claim_id != f"path:{path_id}":
                raise CFBEKernelError("PATH_PROOF_SCOPE_MISMATCH")
            if proof.independence_level < 1 or not self.kernel._proof_is_current(proof, now):
                raise CFBEKernelError("INDEPENDENT_CURRENT_PATH_PROOF_REQUIRED")
            proofs.append(proof)
        return tuple(proofs)

    def submit_path_result(self, graph_id: str, result: PathResult, *, now: str | None = None) -> str:
        graph = self.graph(graph_id)
        self._assert_current(graph)
        result.validate()
        when = now or _now()
        paths = {item.path_id: item for item in graph.paths}
        if result.path_id not in paths:
            raise CFBEKernelError("RESULT_PATH_UNKNOWN")
        verified_proofs: tuple[EvidenceProof, ...] = ()
        if result.state is PathResultState.VERIFIED:
            verified_proofs = self._validate_path_proofs(
                graph, result.path_id, result.proof_ids, when
            )
            if result.measured_quality < graph.baseline_quality:
                raise CFBEKernelError("BENCHMARK_QUALITY_REGRESSION")
        body = {
            **asdict(result),
            "state": result.state.value,
            "benchmark_mode": result.benchmark_mode.value,
        }
        result_sha = _digest(body)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM cfbe_multistream_cancellations WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, result.path_id),
            ).fetchone():
                raise CFBEKernelError("CANCELLED_PATH_RESULT_REJECTED")
            claim = connection.execute(
                "SELECT * FROM cfbe_multistream_claims WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, result.path_id),
            ).fetchone()
            if claim is None or claim["claim_id"] != result.claim_id or claim["fence"] != result.claim_fence:
                raise CFBEKernelError("STALE_OR_UNKNOWN_PATH_CLAIM")
            if result.state is PathResultState.VERIFIED:
                if result.producer_identity != claim["worker_identity"]:
                    raise CFBEKernelError("RESULT_PRODUCER_CLAIM_MISMATCH")
                if result.verifier_identity == claim["worker_identity"]:
                    raise CFBEKernelError("INDEPENDENT_VERIFIER_REQUIRED")
                if any(
                    proof.authority_fingerprint != result.verifier_identity
                    for proof in verified_proofs
                ):
                    raise CFBEKernelError("VERIFIER_PROOF_AUTHORITY_MISMATCH")
            if claim["state"] != "ACTIVE" or _time(when) >= _time(claim["expires_at"]):
                raise CFBEKernelError("PATH_CLAIM_NOT_ACTIVE")
            existing = connection.execute(
                "SELECT result_sha256 FROM cfbe_multistream_results WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, result.path_id),
            ).fetchone()
            if existing:
                if existing[0] != result_sha:
                    raise IdempotencyConflict("PATH_RESULT_CONFLICT")
                connection.rollback()
                return result_sha
            connection.execute(
                "INSERT INTO cfbe_multistream_results VALUES(?,?,?,?)",
                (graph.graph_sha256, result.path_id, _canonical(body), result_sha),
            )
            connection.execute(
                "UPDATE cfbe_multistream_claims SET state='COMPLETED' WHERE graph_sha256=? AND path_id=? AND fence=?",
                (graph.graph_sha256, result.path_id, result.claim_fence),
            )
            connection.commit()
        return result_sha

    def cancel_path(self, graph_id: str, path_id: str, reason: str, *, now: str | None = None) -> None:
        graph = self.graph(graph_id)
        self._assert_current(graph)
        if path_id not in {item.path_id for item in graph.paths}:
            raise CFBEKernelError("PATH_UNKNOWN")
        reason = " ".join(str(reason).split())
        if not reason:
            raise CFBEKernelError("CANCELLATION_REASON_REQUIRED")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT reason FROM cfbe_multistream_cancellations WHERE graph_sha256=? AND path_id=?",
                (graph.graph_sha256, path_id),
            ).fetchone()
            if row and row[0] != reason:
                raise IdempotencyConflict("PATH_CANCELLATION_CONFLICT")
            connection.execute(
                "INSERT OR IGNORE INTO cfbe_multistream_cancellations VALUES(?,?,?,?)",
                (graph.graph_sha256, path_id, reason, now or _now()),
            )
            connection.execute(
                "UPDATE cfbe_multistream_claims SET state='CANCELLED' WHERE graph_sha256=? AND path_id=? AND state='ACTIVE'",
                (graph.graph_sha256, path_id),
            )
            connection.commit()

    def cancel_stream(self, graph_id: str, stream_id: str, reason: str, *, cascade: bool = True) -> tuple[str, ...]:
        graph = self.graph(graph_id)
        streams = {item.stream_id: item for item in graph.streams}
        if stream_id not in streams:
            raise CFBEKernelError("STREAM_UNKNOWN")
        targets = {stream_id}
        if cascade:
            changed = True
            while changed:
                changed = False
                for item in graph.streams:
                    if item.stream_id not in targets and set(item.depends_on) & targets:
                        targets.add(item.stream_id)
                        changed = True
        path_ids = tuple(sorted(item.path_id for item in graph.paths if item.stream_id in targets))
        for path_id in path_ids:
            self.cancel_path(graph_id, path_id, reason)
        return path_ids

    def sovereign_fan_in(self, graph_id: str, stream_id: str, *, now: str | None = None) -> FanInReceipt:
        graph = self.graph(graph_id)
        self._assert_current(graph, require_active=False)
        when = now or _now()
        streams = {item.stream_id: item for item in graph.streams}
        stream = streams.get(stream_id)
        if stream is None:
            raise CFBEKernelError("STREAM_UNKNOWN")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT receipt_json FROM cfbe_multistream_fanins WHERE graph_sha256=? AND stream_id=?",
                (graph.graph_sha256, stream_id),
            ).fetchone()
        if existing:
            return self._receipt(json.loads(existing[0]))
        if self._graph_state(graph) != "ACTIVE":
            raise CFBEKernelError("EXECUTION_GRAPH_NOT_ACTIVE")
        completed = set(self._fanins(graph))
        if not set(stream.depends_on).issubset(completed):
            raise CFBEKernelError("STREAM_DEPENDENCIES_UNRESOLVED")
        results = self._result_rows(graph)
        cancelled = self._cancelled(graph)
        eligible: list[tuple[PathCandidate, Mapping[str, Any]]] = []
        for path in graph.paths:
            if path.stream_id != stream_id or path.path_id not in results or path.path_id in cancelled:
                continue
            result = results[path.path_id]
            if result["state"] != PathResultState.VERIFIED.value or result["critical_conflict"]:
                continue
            self._validate_path_proofs(graph, path.path_id, result["proof_ids"], when)
            if float(result["measured_quality"]) >= graph.baseline_quality:
                eligible.append((path, result))
        groups = {path.independent_group for path, _ in eligible}
        if len(groups) < stream.minimum_verified_paths:
            raise CFBEKernelError("FANIN_CORROBORATION_INCOMPLETE")
        eligible.sort(
            key=lambda item: (-float(item[1]["measured_quality"]), -item[0].expected_quality, -item[0].priority, item[0].path_id)
        )
        selected, selected_result = eligible[0]
        corroborating = tuple(sorted(path.path_id for path, _ in eligible))
        rejected = tuple(sorted(path.path_id for path in graph.paths if path.stream_id == stream_id and path.path_id != selected.path_id))
        proof_ids = tuple(sorted({proof_id for _, result in eligible for proof_id in result["proof_ids"]}))
        body = {
            "graph_sha256": graph.graph_sha256,
            "stream_id": stream_id,
            "selected_path_id": selected.path_id,
            "corroborating_path_ids": corroborating,
            "rejected_path_ids": rejected,
            "proof_ids": proof_ids,
            "benchmark_state": "SIMULATED_EQUAL_OR_BETTER",
            "effect_group_key": stream.effect_group_key,
            "maturity": MATURITY,
            "external_effect_executed": False,
        }
        decision_sha = _digest(body)
        receipt = FanInReceipt(**body, decision_sha256=decision_sha)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT receipt_json FROM cfbe_multistream_fanins WHERE graph_sha256=? AND stream_id=?",
                (graph.graph_sha256, stream_id),
            ).fetchone()
            if existing:
                prior = self._receipt(json.loads(existing[0]))
                connection.rollback()
                return prior
            if stream.effect_group_key:
                winner = connection.execute(
                    "SELECT path_id,decision_sha256 FROM cfbe_multistream_effect_winners WHERE mission_id=? AND mission_version=? AND effect_group_key=?",
                    (graph.mission_id, graph.mission_version, stream.effect_group_key),
                ).fetchone()
                if winner and (winner[0] != selected.path_id or winner[1] != decision_sha):
                    raise IdempotencyConflict("EFFECT_GROUP_ALREADY_HAS_WINNER")
                connection.execute(
                    "INSERT OR IGNORE INTO cfbe_multistream_effect_winners VALUES(?,?,?,?,?,?,?)",
                    (graph.mission_id, graph.mission_version, stream.effect_group_key, graph.graph_sha256, stream_id, selected.path_id, decision_sha),
                )
            connection.execute(
                "INSERT INTO cfbe_multistream_fanins VALUES(?,?,?,?)",
                (graph.graph_sha256, stream_id, _canonical(asdict(receipt)), decision_sha),
            )
            for path_id in rejected:
                connection.execute(
                    "INSERT OR IGNORE INTO cfbe_multistream_cancellations VALUES(?,?,? ,?)",
                    (graph.graph_sha256, path_id, f"SOVEREIGN_FANIN_SELECTED:{selected.path_id}", when),
                )
                connection.execute(
                    "UPDATE cfbe_multistream_claims SET state='CANCELLED' WHERE graph_sha256=? AND path_id=? AND state='ACTIVE'",
                    (graph.graph_sha256, path_id),
                )
            fanin_count = connection.execute(
                "SELECT COUNT(*) FROM cfbe_multistream_fanins WHERE graph_sha256=?", (graph.graph_sha256,)
            ).fetchone()[0]
            if fanin_count == len(graph.streams):
                connection.execute(
                    "UPDATE cfbe_multistream_graphs SET state='CLOSED' WHERE graph_sha256=?",
                    (graph.graph_sha256,),
                )
            connection.commit()
        return receipt

    def shared_proof_state(self, graph_id: str) -> Mapping[str, tuple[str, ...]]:
        graph = self.graph(graph_id)
        results = self._result_rows(graph)
        return {
            path_id: tuple(value["proof_ids"])
            for path_id, value in sorted(results.items())
            if value["state"] == PathResultState.VERIFIED.value
        }

    def projection(self, graph_id: str) -> Mapping[str, Any]:
        graph = self.graph(graph_id)
        fanins = self._fanins(graph)
        with self._connect() as connection:
            claims = connection.execute(
                "SELECT path_id,fence,state FROM cfbe_multistream_claims WHERE graph_sha256=? ORDER BY path_id",
                (graph.graph_sha256,),
            ).fetchall()
            winners = connection.execute(
                "SELECT effect_group_key,path_id FROM cfbe_multistream_effect_winners WHERE graph_sha256=? ORDER BY effect_group_key",
                (graph.graph_sha256,),
            ).fetchall()
        return {
            "schema": SCHEMA,
            "maturity": MATURITY,
            "graph_id": graph.graph_id,
            "graph_sha256": graph.graph_sha256,
            "state": self._graph_state(graph),
            "fanin_streams": tuple(sorted(fanins)),
            "claims": tuple((row["path_id"], row["fence"], row["state"]) for row in claims),
            "cancelled_paths": tuple(sorted(self._cancelled(graph))),
            "shared_proofs": self.shared_proof_state(graph_id),
            "effect_winners": tuple((row["effect_group_key"], row["path_id"]) for row in winners),
            "external_effects_executed": 0,
        }


__all__ = [
    "AGENT_ROLES",
    "BenchmarkMode",
    "CapabilityAttestation",
    "CapabilitySnapshot",
    "DispatchPacket",
    "ExecutionGraph",
    "FanInReceipt",
    "LogicalAgentEnvelope",
    "LogicalWorkerOutcome",
    "MATURITY",
    "MultiStreamExecutionBridge",
    "PathCandidate",
    "PathClaim",
    "PathResult",
    "PathResultState",
    "PairedBenchmarkObservation",
    "SCHEMA",
    "StreamNode",
    "ThroughputClaimReceipt",
    "evaluate_throughput_claim",
    "execute_logical_wave",
]
