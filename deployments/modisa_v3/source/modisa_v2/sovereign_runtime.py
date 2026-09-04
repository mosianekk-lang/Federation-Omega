"""MODISA v3 sovereign execution fabric.

The fabric converts a complete directive into a durable, dependency-aware
mission.  It runs every ready lawful lane, isolates blocked lanes, verifies
fruit independently, and records an event chain that can be replayed after a
crash.  External effects remain behind exact, signed owner approvals.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthorityClass(IntEnum):
    A0 = 0
    A1 = 1
    A2 = 2
    A3 = 3
    A4 = 4
    A5 = 5


class EffectClass(StrEnum):
    NONE = "NONE"
    INTERNAL = "INTERNAL"
    EXTERNAL_REVERSIBLE = "EXTERNAL_REVERSIBLE"
    EXTERNAL_IRREVERSIBLE = "EXTERNAL_IRREVERSIBLE"


class LaneState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    SUCCEEDED = "SUCCEEDED"
    BLOCKED_EXTERNAL_TRUST = "BLOCKED_EXTERNAL_TRUST"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    BLOCKED_BUDGET = "BLOCKED_BUDGET"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    QUARANTINED = "QUARANTINED"
    DEAD_LETTER = "DEAD_LETTER"
    INAPPLICABLE = "INAPPLICABLE"
    SUPERSEDED = "SUPERSEDED"


COMPLETE_STATES = {LaneState.SUCCEEDED, LaneState.INAPPLICABLE, LaneState.SUPERSEDED}


@dataclass(frozen=True)
class ResourceBudget:
    max_tool_calls: int = 64
    max_cost_units: int = 0
    max_wall_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_tool_calls < 0 or self.max_cost_units < 0 or self.max_wall_seconds <= 0:
            raise ValueError("Invalid resource budget")


@dataclass(frozen=True)
class LaneSpec:
    lane_id: str
    description: str
    sequence: int
    dependencies: tuple[str, ...] = ()
    authority: AuthorityClass = AuthorityClass.A0
    effect: EffectClass = EffectClass.NONE
    capability: str = "deterministic"
    proof_requirements: tuple[str, ...] = ()
    max_attempts: int = 2
    timeout_seconds: float = 30.0
    tool_calls: int = 1
    cost_units: int = 0
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.lane_id or not self.description.strip() or not self.capability:
            raise ValueError("Lane id, description, and capability are required")
        if self.sequence < 0 or self.max_attempts < 1 or self.timeout_seconds <= 0:
            raise ValueError("Invalid lane execution bounds")
        if self.tool_calls < 0 or self.cost_units < 0:
            raise ValueError("Lane resource claims cannot be negative")
        if self.effect is not EffectClass.NONE and not self.idempotency_key:
            raise ValueError("Effectful lanes require an idempotency key")

    def as_dict(self) -> JsonObject:
        return {
            "lane_id": self.lane_id,
            "description": self.description,
            "sequence": self.sequence,
            "dependencies": list(self.dependencies),
            "authority": self.authority.name,
            "effect": self.effect.value,
            "capability": self.capability,
            "proof_requirements": list(self.proof_requirements),
            "max_attempts": self.max_attempts,
            "timeout_seconds": self.timeout_seconds,
            "tool_calls": self.tool_calls,
            "cost_units": self.cost_units,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class MissionIR:
    mission_id: str
    version: int
    source: str
    lanes: tuple[LaneSpec, ...]
    authorized_through: AuthorityClass = AuthorityClass.A1
    max_parallelism: int = 4
    budget: ResourceBudget = field(default_factory=ResourceBudget)
    cancel_requested: bool = False

    def __post_init__(self) -> None:
        if not self.mission_id or self.version < 1 or not self.source.strip():
            raise ValueError("Mission identity, version, and source are required")
        if not self.lanes or self.max_parallelism < 1:
            raise ValueError("A mission requires lanes and positive parallelism")
        lane_ids = [lane.lane_id for lane in self.lanes]
        if len(set(lane_ids)) != len(lane_ids):
            raise ValueError("Duplicate lane id")
        known = set(lane_ids)
        for lane in self.lanes:
            missing = set(lane.dependencies) - known
            if missing:
                raise ValueError(f"Unknown lane dependencies: {sorted(missing)}")
            if lane.lane_id in lane.dependencies:
                raise ValueError("A lane cannot depend on itself")
        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        graph = {lane.lane_id: lane.dependencies for lane in self.lanes}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(lane_id: str) -> None:
            if lane_id in visited:
                return
            if lane_id in visiting:
                raise ValueError("Mission dependency graph contains a cycle")
            visiting.add(lane_id)
            for dependency in graph[lane_id]:
                visit(dependency)
            visiting.remove(lane_id)
            visited.add(lane_id)

        for lane_id in graph:
            visit(lane_id)

    def as_dict(self) -> JsonObject:
        return {
            "mission_id": self.mission_id,
            "version": self.version,
            "source": self.source,
            "lanes": [lane.as_dict() for lane in sorted(self.lanes, key=lambda item: item.sequence)],
            "authorized_through": self.authorized_through.name,
            "max_parallelism": self.max_parallelism,
            "budget": {
                "max_tool_calls": self.budget.max_tool_calls,
                "max_cost_units": self.budget.max_cost_units,
                "max_wall_seconds": self.budget.max_wall_seconds,
            },
            "cancel_requested": self.cancel_requested,
        }

    @property
    def fingerprint(self) -> str:
        return _sha256(_canonical(self.as_dict()))


@dataclass(frozen=True)
class ProofArtifact:
    proof_id: str
    kind: str
    source_id: str
    digest: str
    valid: bool = True

    def __post_init__(self) -> None:
        if not self.proof_id or not self.kind or not self.source_id:
            raise ValueError("Proof identity, kind, and source are required")
        if not self.digest.startswith("sha256:") or len(self.digest) != 71:
            raise ValueError("Proof digest must be a complete SHA-256 value")


@dataclass(frozen=True)
class LaneResult:
    output: JsonObject
    proofs: tuple[ProofArtifact, ...]

    @property
    def digest(self) -> str:
        return _sha256(_canonical(self.output))


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    missing_kinds: tuple[str, ...]
    invalid_proof_ids: tuple[str, ...]
    proof_digest: str


class IndependentVerifier:
    """Checks observable fruit without consulting the executing handler."""

    def verify(self, lane: LaneSpec, result: LaneResult) -> VerificationResult:
        invalid = tuple(sorted(proof.proof_id for proof in result.proofs if not proof.valid))
        valid_kinds = {proof.kind for proof in result.proofs if proof.valid}
        missing = tuple(sorted(set(lane.proof_requirements) - valid_kinds))
        material = {
            "lane": lane.lane_id,
            "result": result.digest,
            "proofs": [
                {
                    "id": proof.proof_id,
                    "kind": proof.kind,
                    "source": proof.source_id,
                    "digest": proof.digest,
                    "valid": proof.valid,
                }
                for proof in sorted(result.proofs, key=lambda item: item.proof_id)
            ],
        }
        return VerificationResult(not missing and not invalid, missing, invalid, _sha256(_canonical(material)))


@dataclass(frozen=True)
class JournalEvent:
    sequence: int
    mission_id: str
    lane_id: str | None
    event_type: str
    payload: JsonObject
    previous_hash: str
    event_hash: str


class DurableJournal:
    """SQLite event history with transactional sequence and hash-chain fencing."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS missions(
                    mission_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    ir_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    lane_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(mission_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS effects(
                    effect_key TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    lane_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    result_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consumed_approvals(
                    approval_id TEXT PRIMARY KEY,
                    consumed_at REAL NOT NULL
                );
                """
            )

    def register(self, mission: MissionIR) -> None:
        with self._lock, self._connection as connection:
            row = connection.execute(
                "SELECT fingerprint FROM missions WHERE mission_id=?", (mission.mission_id,)
            ).fetchone()
            if row is not None and row["fingerprint"] != mission.fingerprint:
                raise ValueError("Mission id is already bound to different immutable IR")
            connection.execute(
                "INSERT OR IGNORE INTO missions(mission_id,version,fingerprint,ir_json) VALUES(?,?,?,?)",
                (mission.mission_id, mission.version, mission.fingerprint, _canonical(mission.as_dict())),
            )

    def append(
        self, mission_id: str, event_type: str, payload: Mapping[str, Any], lane_id: str | None = None
    ) -> JournalEvent:
        payload_dict = dict(payload)
        payload_json = _canonical(payload_dict)
        with self._lock, self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT sequence,event_hash FROM events WHERE mission_id=? ORDER BY sequence DESC LIMIT 1",
                (mission_id,),
            ).fetchone()
            sequence = 1 if row is None else int(row["sequence"]) + 1
            previous_hash = "GENESIS" if row is None else str(row["event_hash"])
            event_hash = self._event_hash(
                mission_id, sequence, lane_id, event_type, payload_json, previous_hash
            )
            connection.execute(
                """INSERT INTO events(
                    mission_id,sequence,lane_id,event_type,payload_json,previous_hash,event_hash,created_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    mission_id,
                    sequence,
                    lane_id,
                    event_type,
                    payload_json,
                    previous_hash,
                    event_hash,
                    time.time(),
                ),
            )
            return JournalEvent(
                sequence, mission_id, lane_id, event_type, payload_dict, previous_hash, event_hash
            )

    @staticmethod
    def _event_hash(
        mission_id: str,
        sequence: int,
        lane_id: str | None,
        event_type: str,
        payload_json: str,
        previous_hash: str,
    ) -> str:
        return _sha256(
            _canonical(
                {
                    "mission_id": mission_id,
                    "sequence": sequence,
                    "lane_id": lane_id,
                    "event_type": event_type,
                    "payload": json.loads(payload_json),
                    "previous_hash": previous_hash,
                }
            )
        )

    def events(self, mission_id: str) -> tuple[JournalEvent, ...]:
        with self._lock, self._connection as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE mission_id=? ORDER BY sequence", (mission_id,)
            ).fetchall()
        return tuple(
            JournalEvent(
                int(row["sequence"]),
                str(row["mission_id"]),
                str(row["lane_id"]) if row["lane_id"] is not None else None,
                str(row["event_type"]),
                json.loads(str(row["payload_json"])),
                str(row["previous_hash"]),
                str(row["event_hash"]),
            )
            for row in rows
        )

    def verify_chain(self, mission_id: str) -> bool:
        previous = "GENESIS"
        for event in self.events(mission_id):
            if event.previous_hash != previous:
                return False
            expected = self._event_hash(
                event.mission_id,
                event.sequence,
                event.lane_id,
                event.event_type,
                _canonical(event.payload),
                event.previous_hash,
            )
            if not hmac.compare_digest(expected, event.event_hash):
                return False
            previous = event.event_hash
        return True

    def latest_states(self, mission_id: str) -> dict[str, LaneState]:
        states: dict[str, LaneState] = {}
        for event in self.events(mission_id):
            if event.lane_id and "state" in event.payload:
                states[event.lane_id] = LaneState(str(event.payload["state"]))
        return states

    def latest_proof_digests(self, mission_id: str) -> dict[str, str]:
        """Rehydrate verified proof bindings when a durable mission is resumed."""
        digests: dict[str, str] = {}
        for event in self.events(mission_id):
            if event.lane_id and event.event_type == "LANE_PROVEN":
                digest = event.payload.get("proof_digest")
                if isinstance(digest, str):
                    digests[event.lane_id] = digest
        return digests

    def close(self) -> None:
        """Release the persistent SQLite connection explicitly."""
        with self._lock:
            self._connection.close()

    def effect(self, effect_key: str) -> JsonObject | None:
        with self._lock, self._connection as connection:
            row = connection.execute(
                "SELECT status,result_json FROM effects WHERE effect_key=?", (effect_key,)
            ).fetchone()
        return json.loads(str(row["result_json"])) if row and row["status"] == "COMPLETE" else None

    def claim_effect(self, effect_key: str, mission_id: str, lane_id: str) -> bool:
        with self._lock, self._connection as connection:
            try:
                connection.execute(
                    "INSERT INTO effects(effect_key,mission_id,lane_id,status,result_json,result_hash) VALUES(?,?,?,?,?,?)",
                    (effect_key, mission_id, lane_id, "PENDING", "{}", "PENDING"),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def complete_effect(self, effect_key: str, result: JsonObject) -> None:
        result_json = _canonical(result)
        with self._lock, self._connection as connection:
            cursor = connection.execute(
                "UPDATE effects SET status='COMPLETE',result_json=?,result_hash=? WHERE effect_key=? AND status='PENDING'",
                (result_json, _sha256(result_json), effect_key),
            )
            if cursor.rowcount != 1:
                raise ValueError("Effect reservation is missing or already complete")

    def abandon_effect(self, effect_key: str) -> None:
        with self._lock, self._connection as connection:
            connection.execute("DELETE FROM effects WHERE effect_key=? AND status='PENDING'", (effect_key,))

    def consume_approval(self, approval_id: str) -> bool:
        with self._lock, self._connection as connection:
            try:
                connection.execute(
                    "INSERT INTO consumed_approvals(approval_id,consumed_at) VALUES(?,?)",
                    (approval_id, time.time()),
                )
            except sqlite3.IntegrityError:
                return False
        return True


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_OWNER_APPROVAL = "REQUIRE_OWNER_APPROVAL"
    DENY = "DENY"


@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str


class PolicyKernel:
    """Separates policy decisions from the code that would perform effects."""

    def evaluate(self, mission: MissionIR, lane: LaneSpec) -> PolicyResult:
        if mission.cancel_requested:
            return PolicyResult(PolicyDecision.DENY, "mission_cancelled")
        if lane.authority > mission.authorized_through:
            return PolicyResult(PolicyDecision.DENY, "authority_unavailable")
        if lane.effect in {EffectClass.EXTERNAL_REVERSIBLE, EffectClass.EXTERNAL_IRREVERSIBLE}:
            return PolicyResult(PolicyDecision.REQUIRE_OWNER_APPROVAL, "external_effect")
        return PolicyResult(PolicyDecision.ALLOW, "within_internal_authority")


@dataclass(frozen=True)
class ApprovalReceipt:
    approval_id: str
    mission_fingerprint: str
    lane_id: str
    effect_key: str
    decision: str
    valid_until: float
    nonce: str
    signature: str

    def unsigned(self) -> JsonObject:
        return {
            "approval_id": self.approval_id,
            "mission_fingerprint": self.mission_fingerprint,
            "lane_id": self.lane_id,
            "effect_key": self.effect_key,
            "decision": self.decision,
            "valid_until": self.valid_until,
            "nonce": self.nonce,
        }


class ApprovalVerifier:
    """Verifies receipts issued by a separate trusted owner-approval surface."""

    def __init__(self, verification_secret: bytes, *, clock: Callable[[], float] = time.time) -> None:
        if len(verification_secret) < 32:
            raise ValueError("Approval verification secret must be at least 32 bytes")
        self._secret = verification_secret
        self._clock = clock

    def signature(self, unsigned: Mapping[str, Any]) -> str:
        return hmac.new(self._secret, _canonical(dict(unsigned)).encode(), hashlib.sha256).hexdigest()

    def verify(
        self, receipt: ApprovalReceipt, mission: MissionIR, lane: LaneSpec, effect_key: str
    ) -> bool:
        expected = self.signature(receipt.unsigned())
        return (
            hmac.compare_digest(expected, receipt.signature)
            and receipt.decision == "APPROVE"
            and receipt.valid_until >= self._clock()
            and receipt.mission_fingerprint == mission.fingerprint
            and receipt.lane_id == lane.lane_id
            and receipt.effect_key == effect_key
        )


class EffectHeld(RuntimeError):
    pass


class EffectDenied(RuntimeError):
    pass


class EffectBroker:
    """The only effect path: policy, approval, idempotency, execution, readback."""

    def __init__(
        self, journal: DurableJournal, policy: PolicyKernel, approvals: ApprovalVerifier | None = None
    ) -> None:
        self.journal = journal
        self.policy = policy
        self.approvals = approvals

    @staticmethod
    def effect_key(mission: MissionIR, lane: LaneSpec) -> str:
        return _sha256(f"{mission.fingerprint}:{lane.lane_id}:{lane.idempotency_key}")

    def execute(
        self,
        mission: MissionIR,
        lane: LaneSpec,
        operation: Callable[[], JsonObject],
        *,
        approval: ApprovalReceipt | None = None,
        dry_run: bool = False,
    ) -> JsonObject:
        policy = self.policy.evaluate(mission, lane)
        if policy.decision is PolicyDecision.DENY:
            raise EffectDenied(policy.reason)
        key = self.effect_key(mission, lane)
        existing = self.journal.effect(key)
        if existing is not None:
            return existing
        if dry_run:
            return {"dry_run": True, "effect_key": key, "decision": policy.decision.value}
        if policy.decision is PolicyDecision.REQUIRE_OWNER_APPROVAL:
            if approval is None or self.approvals is None:
                raise EffectHeld("owner_approval_required")
            if not self.approvals.verify(approval, mission, lane, key):
                raise EffectDenied("approval_invalid_or_mismatched")
            if not self.journal.consume_approval(approval.approval_id):
                raise EffectDenied("approval_replayed")
        if not self.journal.claim_effect(key, mission.mission_id, lane.lane_id):
            existing = self.journal.effect(key)
            if existing is not None:
                return existing
            raise EffectHeld("effect_in_progress")
        try:
            result = operation()
            self.journal.complete_effect(key, result)
        except Exception:
            self.journal.abandon_effect(key)
            raise
        return result


class RetryableProviderError(RuntimeError):
    pass


class ExternalTrustError(RuntimeError):
    pass


class NonRetryableExecutionError(RuntimeError):
    pass


@dataclass
class ProviderRoute:
    route_id: str
    capability: str
    invoke: Callable[[JsonObject], JsonObject]
    priority: int = 100
    failure_threshold: int = 2
    failures: int = 0
    quarantined: bool = False


class ProviderMesh:
    """Provider-neutral failover with circuit isolation and deterministic order."""

    def __init__(self, routes: Sequence[ProviderRoute]) -> None:
        self.routes = list(routes)
        self._lock = threading.Lock()

    def invoke(self, capability: str, payload: JsonObject) -> JsonObject:
        failures: list[str] = []
        candidates = sorted(
            (route for route in self.routes if route.capability == capability),
            key=lambda route: (route.priority, route.route_id),
        )
        for route in candidates:
            with self._lock:
                if route.quarantined:
                    continue
            try:
                result = route.invoke(payload)
            except RetryableProviderError as exc:
                with self._lock:
                    route.failures += 1
                    if route.failures >= route.failure_threshold:
                        route.quarantined = True
                failures.append(f"{route.route_id}:{exc}")
                continue
            except ExternalTrustError:
                raise
            except Exception as exc:
                raise NonRetryableExecutionError(f"{route.route_id}:{type(exc).__name__}") from exc
            with self._lock:
                route.failures = 0
            return {"route_id": route.route_id, "result": result}
        if failures:
            raise RetryableProviderError(";".join(failures))
        raise ExternalTrustError(f"no_available_route:{capability}")


class RepairAction(StrEnum):
    RETRY = "RETRY"
    WAIT_FOR_TRUST = "WAIT_FOR_TRUST"
    QUARANTINE = "QUARANTINE"
    DEAD_LETTER = "DEAD_LETTER"


class RepairController:
    def classify(self, error: Exception, attempt: int, max_attempts: int) -> RepairAction:
        if isinstance(error, ExternalTrustError):
            return RepairAction.WAIT_FOR_TRUST
        if isinstance(error, (EffectDenied, NonRetryableExecutionError)):
            return RepairAction.QUARANTINE
        if isinstance(error, (RetryableProviderError, TimeoutError)) and attempt < max_attempts:
            return RepairAction.RETRY
        return RepairAction.DEAD_LETTER


@dataclass(frozen=True)
class LaneContext:
    mission: MissionIR
    lane: LaneSpec
    attempt: int
    correlation_id: str


LaneHandler = Callable[[LaneContext], LaneResult]


@dataclass(frozen=True)
class MissionReceipt:
    mission_id: str
    mission_fingerprint: str
    complete: bool
    claim_allowed: bool
    lane_states: Mapping[str, LaneState]
    proof_digests: Mapping[str, str]
    blocked_lanes: tuple[str, ...]
    failed_lanes: tuple[str, ...]
    event_chain_valid: bool
    manual_user_tasks: tuple[str, ...] = ()


class SovereignOrchestrator:
    """Executes all ready lanes, then converges through one verified receipt."""

    def __init__(
        self,
        journal: DurableJournal,
        *,
        policy: PolicyKernel | None = None,
        verifier: IndependentVerifier | None = None,
        repair: RepairController | None = None,
    ) -> None:
        self.journal = journal
        self.policy = policy or PolicyKernel()
        self.verifier = verifier or IndependentVerifier()
        self.repair = repair or RepairController()

    def run(self, mission: MissionIR, handlers: Mapping[str, LaneHandler]) -> MissionReceipt:
        self.journal.register(mission)
        if not self.journal.events(mission.mission_id):
            self.journal.append(
                mission.mission_id,
                "MISSION_ACCEPTED",
                {"fingerprint": mission.fingerprint, "state": LaneState.PENDING.value},
            )
        states = {lane.lane_id: LaneState.PENDING for lane in mission.lanes}
        states.update(self.journal.latest_states(mission.mission_id))
        proof_digests = self.journal.latest_proof_digests(mission.mission_id)
        tool_calls_used = 0
        cost_used = 0
        started = time.monotonic()

        if mission.cancel_requested:
            for lane in mission.lanes:
                if states[lane.lane_id] not in COMPLETE_STATES:
                    states[lane.lane_id] = LaneState.SUPERSEDED
                    self._record_state(mission, lane, LaneState.SUPERSEDED, "mission_cancelled")
            return self._receipt(mission, states, proof_digests)

        while True:
            ready = [
                lane
                for lane in sorted(mission.lanes, key=lambda item: (item.sequence, item.lane_id))
                if states[lane.lane_id]
                in {LaneState.PENDING, LaneState.READY, LaneState.RETRY_SCHEDULED}
                and all(states[dependency] in COMPLETE_STATES for dependency in lane.dependencies)
            ]
            if not ready:
                break
            admitted: list[LaneSpec] = []
            for lane in ready:
                if time.monotonic() - started >= mission.budget.max_wall_seconds:
                    states[lane.lane_id] = LaneState.BLOCKED_BUDGET
                    self._record_state(mission, lane, LaneState.BLOCKED_BUDGET, "wall_budget")
                    continue
                if tool_calls_used + lane.tool_calls > mission.budget.max_tool_calls:
                    states[lane.lane_id] = LaneState.BLOCKED_BUDGET
                    self._record_state(mission, lane, LaneState.BLOCKED_BUDGET, "tool_budget")
                    continue
                if cost_used + lane.cost_units > mission.budget.max_cost_units:
                    states[lane.lane_id] = LaneState.BLOCKED_BUDGET
                    self._record_state(mission, lane, LaneState.BLOCKED_BUDGET, "cost_budget")
                    continue
                decision = self.policy.evaluate(mission, lane)
                if decision.decision is PolicyDecision.DENY:
                    states[lane.lane_id] = LaneState.BLOCKED_POLICY
                    self._record_state(mission, lane, LaneState.BLOCKED_POLICY, decision.reason)
                    continue
                if decision.decision is PolicyDecision.REQUIRE_OWNER_APPROVAL:
                    states[lane.lane_id] = LaneState.BLOCKED_EXTERNAL_TRUST
                    self._record_state(
                        mission, lane, LaneState.BLOCKED_EXTERNAL_TRUST, "owner_approval_required"
                    )
                    continue
                tool_calls_used += lane.tool_calls
                cost_used += lane.cost_units
                states[lane.lane_id] = LaneState.READY
                admitted.append(lane)
            if not admitted:
                continue
            with ThreadPoolExecutor(max_workers=min(mission.max_parallelism, len(admitted))) as pool:
                futures = {
                    pool.submit(self._execute_lane, mission, lane, handlers.get(lane.lane_id)): lane
                    for lane in admitted
                }
                for future in as_completed(futures):
                    lane = futures[future]
                    state, proof_digest = future.result()
                    states[lane.lane_id] = state
                    if proof_digest:
                        proof_digests[lane.lane_id] = proof_digest

        for lane in mission.lanes:
            if states[lane.lane_id] in {LaneState.PENDING, LaneState.READY}:
                states[lane.lane_id] = LaneState.WAITING_DEPENDENCY
                self._record_state(
                    mission, lane, LaneState.WAITING_DEPENDENCY, "dependency_not_proven"
                )
        return self._receipt(mission, states, proof_digests)

    def _execute_lane(
        self, mission: MissionIR, lane: LaneSpec, handler: LaneHandler | None
    ) -> tuple[LaneState, str | None]:
        if handler is None:
            self._record_state(mission, lane, LaneState.BLOCKED_POLICY, "handler_missing")
            return LaneState.BLOCKED_POLICY, None
        for attempt in range(1, lane.max_attempts + 1):
            self._record_state(mission, lane, LaneState.RUNNING, f"attempt:{attempt}")
            before = time.monotonic()
            try:
                result = handler(
                    LaneContext(mission, lane, attempt, secrets.token_hex(12))
                )
                if time.monotonic() - before > lane.timeout_seconds:
                    raise TimeoutError("lane_timeout")
                verified = self.verifier.verify(lane, result)
                if not verified.valid:
                    self.journal.append(
                        mission.mission_id,
                        "LANE_PROOF_REJECTED",
                        {
                            "state": LaneState.QUARANTINED.value,
                            "missing": list(verified.missing_kinds),
                            "invalid": list(verified.invalid_proof_ids),
                        },
                        lane.lane_id,
                    )
                    return LaneState.QUARANTINED, verified.proof_digest
                self.journal.append(
                    mission.mission_id,
                    "LANE_PROVEN",
                    {
                        "state": LaneState.SUCCEEDED.value,
                        "result_digest": result.digest,
                        "proof_digest": verified.proof_digest,
                    },
                    lane.lane_id,
                )
                return LaneState.SUCCEEDED, verified.proof_digest
            except Exception as exc:
                action = self.repair.classify(exc, attempt, lane.max_attempts)
                if action is RepairAction.RETRY:
                    self._record_state(
                        mission,
                        lane,
                        LaneState.RETRY_SCHEDULED,
                        f"{type(exc).__name__}:attempt:{attempt}",
                    )
                    continue
                state = {
                    RepairAction.WAIT_FOR_TRUST: LaneState.BLOCKED_EXTERNAL_TRUST,
                    RepairAction.QUARANTINE: LaneState.QUARANTINED,
                    RepairAction.DEAD_LETTER: LaneState.DEAD_LETTER,
                }[action]
                self._record_state(mission, lane, state, type(exc).__name__)
                return state, None
        self._record_state(mission, lane, LaneState.DEAD_LETTER, "attempts_exhausted")
        return LaneState.DEAD_LETTER, None

    def _record_state(
        self, mission: MissionIR, lane: LaneSpec, state: LaneState, reason: str
    ) -> None:
        self.journal.append(
            mission.mission_id,
            "LANE_STATE",
            {"state": state.value, "reason": reason},
            lane.lane_id,
        )

    def _receipt(
        self, mission: MissionIR, states: Mapping[str, LaneState], proof_digests: Mapping[str, str]
    ) -> MissionReceipt:
        complete = all(state in COMPLETE_STATES for state in states.values())
        blocked = tuple(
            sorted(
                lane_id
                for lane_id, state in states.items()
                if state
                in {
                    LaneState.BLOCKED_EXTERNAL_TRUST,
                    LaneState.BLOCKED_POLICY,
                    LaneState.BLOCKED_BUDGET,
                    LaneState.WAITING_DEPENDENCY,
                }
            )
        )
        failed = tuple(
            sorted(
                lane_id
                for lane_id, state in states.items()
                if state in {LaneState.QUARANTINED, LaneState.DEAD_LETTER}
            )
        )
        chain_valid = self.journal.verify_chain(mission.mission_id)
        return MissionReceipt(
            mission.mission_id,
            mission.fingerprint,
            complete,
            complete and not blocked and not failed and chain_valid,
            dict(sorted(states.items())),
            dict(sorted(proof_digests.items())),
            blocked,
            failed,
            chain_valid,
        )
