"""Deterministic CFBE vNext mission state, authority, proof, and terminality.

This module is deliberately provider-neutral. It can authorize and execute a
caller-supplied local callback, but it grants no provider, financial,
publication, IAM, secret, or traffic authority. Provider adapters belong to a
later release and must retain these gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any, Callable, Iterable, Mapping, Sequence


SCHEMA = "CFBE-VNEXT-MISSION-EXECUTION-KERNEL-1"
AUTHORITY_RANK = {f"A{rank}": rank for rank in range(6)}
SECRET_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "client_secret",
        "credential_value",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "token",
    }
)
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)
TERMINAL_REQUIREMENT_STATES = frozenset({"PROVEN", "INAPPLICABLE"})
ACTIVE_REQUIREMENT_STATES = frozenset(
    {
        "OPEN",
        "PARTIAL_PROVEN",
        "READY",
        "AUTHORIZED",
        "GAP",
        "BLOCKED_EXTERNAL_AUTHORITY",
        "FAILED",
    }
)


class CFBEKernelError(ValueError):
    """Fail-closed contract or execution error."""


class EventConflict(CFBEKernelError):
    """Optimistic concurrency or event-chain conflict."""


class IdempotencyConflict(CFBEKernelError):
    """An idempotency identity was reused with different semantics."""


class RequirementState(StrEnum):
    OPEN = "OPEN"
    PARTIAL_PROVEN = "PARTIAL_PROVEN"
    READY = "READY"
    AUTHORIZED = "AUTHORIZED"
    PROVEN = "PROVEN"
    INAPPLICABLE = "INAPPLICABLE"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    GAP = "GAP"
    BLOCKED_EXTERNAL_AUTHORITY = "BLOCKED_EXTERNAL_AUTHORITY"
    FAILED = "FAILED"


class MissionState(StrEnum):
    OPEN = "OPEN"
    CANCELLED = "CANCELLED"
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"


class AuthorityState(StrEnum):
    PROVEN = "PROVEN"
    UNPROVEN = "UNPROVEN"
    INAPPLICABLE = "INAPPLICABLE"
    EXPIRED = "EXPIRED"


class ActionDecision(StrEnum):
    EXECUTE = "EXECUTE"
    STOP = "STOP"
    CANCEL = "CANCEL"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class OutwardState(StrEnum):
    RUNNING = "RUNNING"
    WAITING_AUTOMATICALLY = "WAITING_AUTOMATICALLY"
    BLOCKED_EXTERNAL_AUTHORITY = "BLOCKED_EXTERNAL_AUTHORITY"
    FAILED_CHECKPOINTED = "FAILED_CHECKPOINTED"
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CFBEKernelError("TIME_REQUIRED")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CFBEKernelError("TIME_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _validate_identifier(value: str, label: str) -> str:
    value = str(value).strip()
    if not value or len(value) > 200 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", value):
        raise CFBEKernelError(f"{label.upper().replace(' ', '_')}_INVALID")
    return value


def _validate_number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CFBEKernelError(f"{label.upper()}_MUST_BE_FINITE_NUMBER")
    if nonnegative and value < 0:
        raise CFBEKernelError(f"{label.upper()}_MUST_BE_NONNEGATIVE")
    return float(value)


def _reject_secret_material(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in SECRET_KEYS:
                raise CFBEKernelError(f"SECRET_FIELD_PROHIBITED:{path}.{key}")
            _reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise CFBEKernelError(f"SECRET_SHAPED_VALUE_PROHIBITED:{path}")


@dataclass(frozen=True, slots=True)
class Requirement:
    requirement_id: str
    description: str
    source: str = "OWNER"
    initial_state: RequirementState = RequirementState.OPEN
    optional: bool = False

    def validate(self) -> "Requirement":
        _validate_identifier(self.requirement_id, "requirement id")
        if len(" ".join(self.description.split())) < 5:
            raise CFBEKernelError("REQUIREMENT_DESCRIPTION_TOO_SHORT")
        if self.source not in {"OWNER", "NECESSARY_CONTROL"}:
            raise CFBEKernelError("REQUIREMENT_SOURCE_INVALID")
        if self.optional:
            raise CFBEKernelError("OPTIONAL_REQUIREMENT_CANNOT_ENTER_FROZEN_DENOMINATOR")
        if self.initial_state not in {RequirementState.OPEN, RequirementState.INAPPLICABLE}:
            raise CFBEKernelError("REQUIREMENT_INITIAL_STATE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class FruitCriterion:
    fruit_id: str
    measure: str

    def validate(self) -> "FruitCriterion":
        _validate_identifier(self.fruit_id, "fruit id")
        if len(" ".join(self.measure.split())) < 5:
            raise CFBEKernelError("TERMINAL_FRUIT_MEASURE_TOO_SHORT")
        return self


@dataclass(frozen=True, slots=True)
class TerminalAction:
    action_id: str
    required_authority: str
    route_state: AuthorityState
    route_ref: str = ""

    def validate(self) -> "TerminalAction":
        _validate_identifier(self.action_id, "terminal action id")
        if self.required_authority not in AUTHORITY_RANK:
            raise CFBEKernelError("TERMINAL_ACTION_AUTHORITY_INVALID")
        if self.route_state is AuthorityState.PROVEN and not self.route_ref.strip():
            raise CFBEKernelError("PROVEN_TERMINAL_ROUTE_REQUIRES_REFERENCE")
        return self


@dataclass(frozen=True, slots=True)
class MissionConstraints:
    authorized_classes: tuple[str, ...] = ("A0", "A1")
    maximum_cost: float = 0
    zero_new_recurring_cost: bool = True
    maximum_user_burden: float = 0
    external_effects_allowed: bool = False

    def validate(self) -> "MissionConstraints":
        if not self.authorized_classes or any(item not in AUTHORITY_RANK for item in self.authorized_classes):
            raise CFBEKernelError("AUTHORIZED_CLASSES_INVALID")
        _validate_number(self.maximum_cost, "maximum_cost", nonnegative=True)
        _validate_number(self.maximum_user_burden, "maximum_user_burden", nonnegative=True)
        if not isinstance(self.zero_new_recurring_cost, bool) or not isinstance(self.external_effects_allowed, bool):
            raise CFBEKernelError("CONSTRAINT_BOOLEAN_TYPE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class MissionContract:
    mission_id: str
    mission_version: int
    owner_outcome: str
    terminal_fruit: tuple[FruitCriterion, ...]
    requirements: tuple[Requirement, ...]
    exclusions: tuple[str, ...]
    constraints: MissionConstraints
    terminal_actions: tuple[TerminalAction, ...]
    critical_path: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    contract_sha256: str = ""

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        mission_version: int,
        owner_outcome: str,
        terminal_fruit: Iterable[FruitCriterion],
        requirements: Iterable[Requirement],
        exclusions: Iterable[str] = (),
        constraints: MissionConstraints | None = None,
        terminal_actions: Iterable[TerminalAction] = (),
        critical_path: Iterable[str] = (),
        stop_conditions: Iterable[str] = ("all fruit proven", "owner supersession"),
    ) -> "MissionContract":
        candidate = cls(
            mission_id=str(mission_id).strip(),
            mission_version=mission_version,
            owner_outcome=" ".join(str(owner_outcome).split()),
            terminal_fruit=tuple(terminal_fruit),
            requirements=tuple(requirements),
            exclusions=_clean(exclusions),
            constraints=constraints or MissionConstraints(),
            terminal_actions=tuple(terminal_actions),
            critical_path=_clean(critical_path),
            stop_conditions=_clean(stop_conditions),
        )
        candidate.validate()
        return replace(candidate, contract_sha256=_digest(candidate.body()))

    def validate(self) -> "MissionContract":
        _validate_identifier(self.mission_id, "mission id")
        if isinstance(self.mission_version, bool) or not isinstance(self.mission_version, int) or self.mission_version < 1:
            raise CFBEKernelError("MISSION_VERSION_INVALID")
        if len(self.owner_outcome) < 8:
            raise CFBEKernelError("OWNER_OUTCOME_TOO_SHORT")
        if not self.terminal_fruit or not self.requirements:
            raise CFBEKernelError("FINITE_MISSION_DENOMINATOR_REQUIRED")
        if not self.stop_conditions:
            raise CFBEKernelError("STOP_CONDITIONS_REQUIRED")
        for item in self.terminal_fruit:
            item.validate()
        for item in self.requirements:
            item.validate()
        for item in self.terminal_actions:
            item.validate()
        self.constraints.validate()
        requirement_ids = [item.requirement_id for item in self.requirements]
        fruit_ids = [item.fruit_id for item in self.terminal_fruit]
        action_ids = [item.action_id for item in self.terminal_actions]
        for values, label in ((requirement_ids, "REQUIREMENT"), (fruit_ids, "FRUIT"), (action_ids, "TERMINAL_ACTION")):
            if len(values) != len(set(values)):
                raise CFBEKernelError(f"DUPLICATE_{label}_ID")
        if not self.critical_path or not set(self.critical_path).issubset(requirement_ids):
            raise CFBEKernelError("CRITICAL_PATH_MUST_REFERENCE_FROZEN_REQUIREMENTS")
        _reject_secret_material(self.body())
        if self.contract_sha256 and self.contract_sha256 != _digest(self.body()):
            raise CFBEKernelError("MISSION_CONTRACT_HASH_MISMATCH")
        return self

    def body(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "mission_version": self.mission_version,
            "owner_outcome": self.owner_outcome,
            "terminal_fruit": [asdict(item) for item in self.terminal_fruit],
            "requirements": [
                {**asdict(item), "initial_state": item.initial_state.value} for item in self.requirements
            ],
            "exclusions": list(self.exclusions),
            "constraints": asdict(self.constraints),
            "terminal_actions": [
                {**asdict(item), "route_state": item.route_state.value} for item in self.terminal_actions
            ],
            "critical_path": list(self.critical_path),
            "stop_conditions": list(self.stop_conditions),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "contract_sha256": self.contract_sha256}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MissionContract":
        constraints = dict(value["constraints"])
        contract = cls(
            mission_id=str(value["mission_id"]),
            mission_version=int(value["mission_version"]),
            owner_outcome=str(value["owner_outcome"]),
            terminal_fruit=tuple(FruitCriterion(**item) for item in value["terminal_fruit"]),
            requirements=tuple(
                Requirement(**{**item, "initial_state": RequirementState(item["initial_state"])})
                for item in value["requirements"]
            ),
            exclusions=tuple(value.get("exclusions", ())),
            constraints=MissionConstraints(**{**constraints, "authorized_classes": tuple(constraints["authorized_classes"])}),
            terminal_actions=tuple(
                TerminalAction(**{**item, "route_state": AuthorityState(item["route_state"])})
                for item in value.get("terminal_actions", ())
            ),
            critical_path=tuple(value["critical_path"]),
            stop_conditions=tuple(value["stop_conditions"]),
            contract_sha256=str(value["contract_sha256"]),
        )
        return contract.validate()


@dataclass(frozen=True, slots=True)
class ActionProposal:
    action_id: str
    mission_id: str
    mission_version: int
    requirement_ids: tuple[str, ...]
    authority_class: str = "A1"
    estimated_cost: float = 0
    recurring_cost: float = 0
    estimated_user_burden: float = 0
    expected_outcome_delta: float = 0
    expected_information_gain: float = 0
    effectful: bool = False
    resource_key: str = "local"
    operation_key: str = "execute"
    idempotency_key: str = ""
    creates_obligations: tuple[str, ...] = ()
    necessary_safety_action: bool = False

    def validate(self) -> "ActionProposal":
        _validate_identifier(self.action_id, "action id")
        _validate_identifier(self.mission_id, "mission id")
        if isinstance(self.mission_version, bool) or not isinstance(self.mission_version, int) or self.mission_version < 1:
            raise CFBEKernelError("ACTION_MISSION_VERSION_INVALID")
        if not self.requirement_ids:
            raise CFBEKernelError("ACTION_REQUIREMENTS_REQUIRED")
        if self.authority_class not in AUTHORITY_RANK:
            raise CFBEKernelError("ACTION_AUTHORITY_INVALID")
        for label, value in (
            ("estimated_cost", self.estimated_cost),
            ("recurring_cost", self.recurring_cost),
            ("estimated_user_burden", self.estimated_user_burden),
        ):
            _validate_number(value, label, nonnegative=True)
        _validate_number(self.expected_outcome_delta, "expected_outcome_delta")
        _validate_number(self.expected_information_gain, "expected_information_gain")
        if not isinstance(self.effectful, bool) or not isinstance(self.necessary_safety_action, bool):
            raise CFBEKernelError("ACTION_BOOLEAN_TYPE_INVALID")
        if not self.resource_key.strip() or not self.operation_key.strip():
            raise CFBEKernelError("ACTION_RESOURCE_OPERATION_REQUIRED")
        if self.effectful and not self.idempotency_key.strip():
            raise CFBEKernelError("EFFECT_IDENTITY_REQUIRED")
        _reject_secret_material(asdict(self))
        return self

    @property
    def action_sha256(self) -> str:
        """Bind a permit to the complete normalized action, not only its label."""
        self.validate()
        body = asdict(self)
        body["requirement_ids"] = sorted(self.requirement_ids)
        body["creates_obligations"] = sorted(self.creates_obligations)
        return _digest(body)


@dataclass(frozen=True, slots=True)
class EvidenceProof:
    proof_id: str
    claim_id: str
    mission_id: str
    mission_version: int
    artifact_hashes: tuple[str, ...]
    dependency_hashes: Mapping[str, str]
    environment_fingerprint: str
    authority_fingerprint: str
    created_at: str
    max_age_seconds: int
    invalidation_predicates: tuple[str, ...]
    independence_level: int
    result: str = "PASS"

    def validate(self) -> "EvidenceProof":
        for value, label in (
            (self.proof_id, "proof id"),
            (self.claim_id, "claim id"),
            (self.mission_id, "mission id"),
        ):
            _validate_identifier(value, label)
        if self.mission_version < 1 or not self.artifact_hashes or not self.dependency_hashes:
            raise CFBEKernelError("PROOF_IDENTITY_INCOMPLETE")
        if not self.environment_fingerprint or not self.authority_fingerprint:
            raise CFBEKernelError("PROOF_CONTEXT_INCOMPLETE")
        _parse_time(self.created_at)
        if self.max_age_seconds < 1 or self.independence_level < 0:
            raise CFBEKernelError("PROOF_POLICY_INVALID")
        if self.result != "PASS":
            raise CFBEKernelError("ONLY_PASSING_PROOF_CAN_BIND")
        _reject_secret_material(asdict(self))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "dependency_hashes": dict(self.dependency_hashes)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceProof":
        return cls(
            **{
                **value,
                "artifact_hashes": tuple(value["artifact_hashes"]),
                "dependency_hashes": dict(value["dependency_hashes"]),
                "invalidation_predicates": tuple(value.get("invalidation_predicates", ())),
            }
        ).validate()


@dataclass(frozen=True, slots=True)
class WaitRegistration:
    job_id: str
    mission_id: str
    mission_version: int
    worker_identity: str
    checkpoint_ref: str
    subscription_ref: str
    resume_action_id: str
    readback_endpoint: str
    active: bool = True

    @property
    def automatic(self) -> bool:
        values = (
            self.job_id,
            self.worker_identity,
            self.checkpoint_ref,
            self.subscription_ref,
            self.resume_action_id,
            self.readback_endpoint,
        )
        forbidden = {"USER_MESSAGE", "CHAT_INPUT", "OWNER_N", "MANUAL"}
        return self.active and all(str(value).strip() for value in values) and self.subscription_ref.upper() not in forbidden


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    path: str
    status: str
    old_path: str = ""


@dataclass(frozen=True, slots=True)
class TestRunEvidence:
    runner: str
    discovered: int
    executed: int
    passed: int
    failed: int
    skipped: int = 0

    def validate(self) -> "TestRunEvidence":
        if not self.runner.strip():
            raise CFBEKernelError("TEST_RUNNER_REQUIRED")
        values = (self.discovered, self.executed, self.passed, self.failed, self.skipped)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise CFBEKernelError("TEST_COUNTS_INVALID")
        if self.discovered == 0 or self.executed == 0:
            raise CFBEKernelError("ZERO_TEST_SUCCESS_PROHIBITED")
        if self.executed != self.passed + self.failed + self.skipped:
            raise CFBEKernelError("TEST_COUNT_MISMATCH")
        if self.executed != self.discovered:
            raise CFBEKernelError("DISCOVERED_TESTS_NOT_EXECUTED")
        if self.failed:
            raise CFBEKernelError("TEST_FAILURE_PRESENT")
        return self


@dataclass(frozen=True, slots=True)
class DecisionReceipt:
    decision: ActionDecision
    authorized: bool
    reasons: tuple[str, ...]
    mission_id: str
    mission_version: int
    action_id: str


@dataclass(frozen=True, slots=True)
class TerminalityReport:
    complete: bool
    state: OutwardState
    gaps: tuple[str, ...]
    proof_refs: tuple[str, ...]
    report_sha256: str


@dataclass(frozen=True, slots=True)
class MissionProjection:
    contract: MissionContract
    mission_state: MissionState
    requirement_states: Mapping[str, RequirementState]
    fruit_proofs: Mapping[str, str]
    requirement_proofs: Mapping[str, str]
    proofs: Mapping[str, EvidenceProof]
    invalidated_proofs: frozenset[str]
    last_event_hash: str | None
    cancellation_reason: str = ""


@dataclass(frozen=True, slots=True)
class _Event:
    sequence: int
    event_id: str
    mission_id: str
    mission_version: int
    event_type: str
    payload: Mapping[str, Any]
    occurred_at: str
    previous_hash: str | None
    event_hash: str
    idempotency_key: str


class _SQLiteMissionStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    previous_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE,
                    idempotency_key TEXT NOT NULL,
                    UNIQUE(mission_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS events_mission_sequence
                    ON events(mission_id, sequence);
                CREATE TABLE IF NOT EXISTS permits (
                    token_hash TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL,
                    action_id TEXT NOT NULL,
                    requirement_ids_json TEXT NOT NULL,
                    action_sha256 TEXT,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT,
                    cancelled_at TEXT
                );
                CREATE TABLE IF NOT EXISTS effects (
                    mission_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    receipt_json TEXT,
                    PRIMARY KEY(mission_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS wait_jobs (
                    job_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    mission_version INTEGER NOT NULL,
                    worker_identity TEXT NOT NULL,
                    checkpoint_ref TEXT NOT NULL,
                    subscription_ref TEXT NOT NULL,
                    resume_action_id TEXT NOT NULL,
                    readback_endpoint TEXT NOT NULL,
                    active INTEGER NOT NULL
                );
                """
            )
            permit_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(permits)").fetchall()
            }
            if "action_sha256" not in permit_columns:
                connection.execute("ALTER TABLE permits ADD COLUMN action_sha256 TEXT")

    @staticmethod
    def _event_hash(
        *,
        event_id: str,
        mission_id: str,
        mission_version: int,
        event_type: str,
        payload: Mapping[str, Any],
        occurred_at: str,
        previous_hash: str | None,
        idempotency_key: str,
    ) -> str:
        return _digest(
            {
                "event_id": event_id,
                "mission_id": mission_id,
                "mission_version": mission_version,
                "event_type": event_type,
                "payload": dict(payload),
                "occurred_at": occurred_at,
                "previous_hash": previous_hash,
                "idempotency_key": idempotency_key,
            }
        )

    def append(
        self,
        *,
        mission_id: str,
        mission_version: int,
        event_type: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        expected_head: str | None = None,
        occurred_at: str | None = None,
    ) -> _Event:
        payload = json.loads(_canonical(dict(payload)))
        _reject_secret_material(payload)
        identity = {
            "mission_id": mission_id,
            "mission_version": mission_version,
            "event_type": event_type,
            "payload": payload,
            "idempotency_key": idempotency_key,
        }
        event_id = "CFBE-EVT-" + _digest(identity)[:28].upper()
        when = occurred_at or _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM events WHERE mission_id=? AND idempotency_key=?",
                (mission_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["event_id"] != event_id:
                    raise IdempotencyConflict("EVENT_IDEMPOTENCY_PAYLOAD_CONFLICT")
                connection.rollback()
                return self._row_to_event(existing)
            head = connection.execute(
                "SELECT event_hash FROM events WHERE mission_id=? ORDER BY sequence DESC LIMIT 1",
                (mission_id,),
            ).fetchone()
            previous = str(head[0]) if head else None
            if expected_head is not None and expected_head != previous:
                raise EventConflict("MISSION_HEAD_COMPARE_AND_SWAP_FAILED")
            event_hash = self._event_hash(
                event_id=event_id,
                mission_id=mission_id,
                mission_version=mission_version,
                event_type=event_type,
                payload=payload,
                occurred_at=when,
                previous_hash=previous,
                idempotency_key=idempotency_key,
            )
            cursor = connection.execute(
                "INSERT INTO events(event_id,mission_id,mission_version,event_type,payload_json,occurred_at,previous_hash,event_hash,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?)",
                (event_id, mission_id, mission_version, event_type, _canonical(payload), when, previous, event_hash, idempotency_key),
            )
            sequence = int(cursor.lastrowid)
            connection.commit()
        return _Event(sequence, event_id, mission_id, mission_version, event_type, payload, when, previous, event_hash, idempotency_key)

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> _Event:
        return _Event(
            sequence=int(row["sequence"]),
            event_id=str(row["event_id"]),
            mission_id=str(row["mission_id"]),
            mission_version=int(row["mission_version"]),
            event_type=str(row["event_type"]),
            payload=json.loads(row["payload_json"]),
            occurred_at=str(row["occurred_at"]),
            previous_hash=str(row["previous_hash"]) if row["previous_hash"] else None,
            event_hash=str(row["event_hash"]),
            idempotency_key=str(row["idempotency_key"]),
        )

    def events(self, mission_id: str) -> tuple[_Event, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE mission_id=? ORDER BY sequence", (mission_id,)
            ).fetchall()
        return tuple(self._row_to_event(row) for row in rows)

    def verify(self, mission_id: str) -> dict[str, Any]:
        previous: str | None = None
        events = self.events(mission_id)
        for index, event in enumerate(events, 1):
            expected = self._event_hash(
                event_id=event.event_id,
                mission_id=event.mission_id,
                mission_version=event.mission_version,
                event_type=event.event_type,
                payload=event.payload,
                occurred_at=event.occurred_at,
                previous_hash=previous,
                idempotency_key=event.idempotency_key,
            )
            if event.previous_hash != previous or event.event_hash != expected:
                raise EventConflict(f"EVENT_CHAIN_INVALID:{index}")
            previous = event.event_hash
        return {"state": "VERIFIED", "event_count": len(events), "head_hash": previous}

    def save_permit(
        self,
        *,
        token_hash: str,
        action: ActionProposal,
        issued_at: str,
        expires_at: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO permits(token_hash,mission_id,mission_version,action_id,requirement_ids_json,action_sha256,issued_at,expires_at,consumed_at,cancelled_at) VALUES(?,?,?,?,?,?,?,?,NULL,NULL)",
                (
                    token_hash,
                    action.mission_id,
                    action.mission_version,
                    action.action_id,
                    _canonical(sorted(action.requirement_ids)),
                    action.action_sha256,
                    issued_at,
                    expires_at,
                ),
            )

    def consume_permit(self, token_hash: str, action: ActionProposal, now: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM permits WHERE token_hash=?", (token_hash,)).fetchone()
            if row is None:
                raise CFBEKernelError("PERMIT_UNKNOWN")
            if not row["action_sha256"]:
                raise CFBEKernelError("LEGACY_PERMIT_REISSUE_REQUIRED")
            expected = (action.mission_id, action.mission_version, action.action_id, _canonical(sorted(action.requirement_ids)))
            actual = (row["mission_id"], row["mission_version"], row["action_id"], row["requirement_ids_json"])
            if actual != expected:
                raise CFBEKernelError("PERMIT_BINDING_MISMATCH")
            if row["action_sha256"] != action.action_sha256:
                raise CFBEKernelError("PERMIT_ACTION_FINGERPRINT_MISMATCH")
            if row["cancelled_at"]:
                raise CFBEKernelError("PERMIT_CANCELLED")
            if row["consumed_at"]:
                raise CFBEKernelError("PERMIT_ALREADY_CONSUMED")
            if _parse_time(now) >= _parse_time(row["expires_at"]):
                raise CFBEKernelError("PERMIT_EXPIRED")
            changed = connection.execute(
                "UPDATE permits SET consumed_at=? WHERE token_hash=? AND consumed_at IS NULL AND cancelled_at IS NULL",
                (now, token_hash),
            ).rowcount
            if changed != 1:
                raise CFBEKernelError("PERMIT_CONSUME_RACE_LOST")
            connection.commit()

    def cancel_descendants(self, mission_id: str, old_version: int, now: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE permits SET cancelled_at=? WHERE mission_id=? AND mission_version=? AND consumed_at IS NULL AND cancelled_at IS NULL",
                (now, mission_id, old_version),
            )
            connection.execute(
                "UPDATE wait_jobs SET active=0 WHERE mission_id=? AND mission_version=?",
                (mission_id, old_version),
            )

    def effect(self, mission_id: str, idempotency_key: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM effects WHERE mission_id=? AND idempotency_key=?",
                (mission_id, idempotency_key),
            ).fetchone()

    def reserve_effect(self, mission_id: str, idempotency_key: str, payload_sha256: str) -> None:
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO effects VALUES(?,?,?,'RESERVED',NULL)",
                    (mission_id, idempotency_key, payload_sha256),
                )
            except sqlite3.IntegrityError as exc:
                row = connection.execute(
                    "SELECT payload_sha256 FROM effects WHERE mission_id=? AND idempotency_key=?",
                    (mission_id, idempotency_key),
                ).fetchone()
                if row is None or row[0] != payload_sha256:
                    raise IdempotencyConflict("EFFECT_IDEMPOTENCY_PAYLOAD_CONFLICT") from exc
                raise CFBEKernelError("EFFECT_ALREADY_RESERVED") from exc

    def complete_effect(self, mission_id: str, idempotency_key: str, receipt: Mapping[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE effects SET state='COMPLETED',receipt_json=? WHERE mission_id=? AND idempotency_key=? AND state='RESERVED'",
                (_canonical(dict(receipt)), mission_id, idempotency_key),
            )

    def fail_effect(self, mission_id: str, idempotency_key: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE effects SET state='FAILED',receipt_json=? WHERE mission_id=? AND idempotency_key=? AND state='RESERVED'",
                (_canonical({"error": error}), mission_id, idempotency_key),
            )

    def register_wait(self, item: WaitRegistration) -> None:
        with self._connect() as connection:
            existing = connection.execute("SELECT * FROM wait_jobs WHERE job_id=?", (item.job_id,)).fetchone()
            body = asdict(item)
            if existing is not None:
                prior = dict(existing)
                prior["active"] = bool(prior["active"])
                if prior != body:
                    raise IdempotencyConflict("WAIT_JOB_IDENTITY_CONFLICT")
                return
            connection.execute(
                "INSERT INTO wait_jobs VALUES(?,?,?,?,?,?,?,?,?)",
                (item.job_id, item.mission_id, item.mission_version, item.worker_identity, item.checkpoint_ref, item.subscription_ref, item.resume_action_id, item.readback_endpoint, int(item.active)),
            )

    def wait_jobs(self, mission_id: str, mission_version: int) -> tuple[WaitRegistration, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wait_jobs WHERE mission_id=? AND mission_version=? ORDER BY job_id",
                (mission_id, mission_version),
            ).fetchall()
        return tuple(
            WaitRegistration(
                job_id=row["job_id"], mission_id=row["mission_id"], mission_version=row["mission_version"],
                worker_identity=row["worker_identity"], checkpoint_ref=row["checkpoint_ref"],
                subscription_ref=row["subscription_ref"], resume_action_id=row["resume_action_id"],
                readback_endpoint=row["readback_endpoint"], active=bool(row["active"]),
            )
            for row in rows
        )


class MissionExecutionKernel:
    """Local deterministic reference kernel for CFBE vNext Phase 0-1."""

    def __init__(self, database_path: str | Path):
        self.store = _SQLiteMissionStore(database_path)

    def open_mission(self, contract: MissionContract) -> MissionProjection:
        contract.validate()
        existing = self.store.events(contract.mission_id)
        if existing:
            projection = self.project(contract.mission_id)
            if projection.contract.contract_sha256 != contract.contract_sha256:
                raise IdempotencyConflict("MISSION_ID_ALREADY_BOUND_TO_DIFFERENT_CONTRACT")
            return projection
        self.store.append(
            mission_id=contract.mission_id,
            mission_version=contract.mission_version,
            event_type="MISSION_OPENED",
            payload={"contract": contract.to_dict()},
            idempotency_key=f"mission:{contract.contract_sha256}",
        )
        return self.project(contract.mission_id)

    def revise_mission(self, contract: MissionContract) -> MissionProjection:
        current = self.project(contract.mission_id)
        contract.validate()
        if current.mission_state is not MissionState.OPEN:
            raise CFBEKernelError("TERMINAL_MISSION_CANNOT_BE_REVISED")
        if contract.mission_version != current.contract.mission_version + 1:
            raise CFBEKernelError("MISSION_REVISION_MUST_INCREMENT_BY_ONE")
        old_requirements = set(current.requirement_states)
        new_requirements = {item.requirement_id for item in contract.requirements}
        removed = sorted(old_requirements - new_requirements)
        now = _now()
        event = self.store.append(
            mission_id=contract.mission_id,
            mission_version=contract.mission_version,
            event_type="MISSION_REVISED",
            payload={"contract": contract.to_dict(), "removed_requirement_ids": removed},
            idempotency_key=f"revision:{contract.contract_sha256}",
            expected_head=current.last_event_hash,
            occurred_at=now,
        )
        self.store.cancel_descendants(contract.mission_id, current.contract.mission_version, now)
        self.store.append(
            mission_id=contract.mission_id,
            mission_version=contract.mission_version,
            event_type="STALE_DESCENDANTS_CANCELLED",
            payload={"prior_version": current.contract.mission_version, "removed_requirement_ids": removed},
            idempotency_key=f"cancel-descendants:{event.event_hash}",
            expected_head=event.event_hash,
            occurred_at=now,
        )
        return self.project(contract.mission_id)

    def project(self, mission_id: str) -> MissionProjection:
        events = self.store.events(mission_id)
        if not events:
            raise KeyError(f"MISSION_UNKNOWN:{mission_id}")
        contract: MissionContract | None = None
        mission_state = MissionState.OPEN
        requirement_states: dict[str, RequirementState] = {}
        proofs: dict[str, EvidenceProof] = {}
        invalidated: set[str] = set()
        requirement_proofs: dict[str, str] = {}
        fruit_proofs: dict[str, str] = {}
        cancellation_reason = ""
        current_version = 0
        for event in events:
            if event.event_type in {"MISSION_OPENED", "MISSION_REVISED"}:
                contract = MissionContract.from_dict(event.payload["contract"])
                current_version = contract.mission_version
                mission_state = MissionState.OPEN
                requirement_states = {
                    item.requirement_id: item.initial_state for item in contract.requirements
                }
                proofs = {}
                invalidated = set()
                requirement_proofs = {}
                fruit_proofs = {}
                cancellation_reason = ""
                continue
            if contract is None or event.mission_version != current_version:
                continue
            if event.event_type == "REQUIREMENT_STATE_SET":
                requirement_states[event.payload["requirement_id"]] = RequirementState(event.payload["state"])
            elif event.event_type == "PROOF_BOUND":
                proof = EvidenceProof.from_dict(event.payload["proof"])
                proofs[proof.proof_id] = proof
            elif event.event_type == "PROOF_INVALIDATED":
                for proof_id in event.payload["proof_ids"]:
                    invalidated.add(proof_id)
                    for req_id, linked in list(requirement_proofs.items()):
                        if linked == proof_id:
                            requirement_states[req_id] = RequirementState.OPEN
                            requirement_proofs.pop(req_id, None)
                    for fruit_id, linked in list(fruit_proofs.items()):
                        if linked == proof_id:
                            fruit_proofs.pop(fruit_id, None)
            elif event.event_type == "REQUIREMENT_PROVEN":
                requirement_states[event.payload["requirement_id"]] = RequirementState.PROVEN
                requirement_proofs[event.payload["requirement_id"]] = event.payload["proof_id"]
            elif event.event_type == "FRUIT_PROVEN":
                fruit_proofs[event.payload["fruit_id"]] = event.payload["proof_id"]
            elif event.event_type == "MISSION_CANCELLED":
                mission_state = MissionState.CANCELLED
                cancellation_reason = str(event.payload["reason"])
            elif event.event_type == "MISSION_TERMINALIZED":
                mission_state = MissionState.COMPLETE_VERIFIED
        assert contract is not None
        self.store.verify(mission_id)
        return MissionProjection(
            contract=contract,
            mission_state=mission_state,
            requirement_states=requirement_states,
            fruit_proofs=fruit_proofs,
            requirement_proofs=requirement_proofs,
            proofs=proofs,
            invalidated_proofs=frozenset(invalidated),
            last_event_hash=events[-1].event_hash,
            cancellation_reason=cancellation_reason,
        )

    def set_requirement_state(
        self,
        mission_id: str,
        mission_version: int,
        requirement_id: str,
        state: RequirementState,
    ) -> MissionProjection:
        projection = self.project(mission_id)
        if mission_version != projection.contract.mission_version:
            raise CFBEKernelError("STALE_MISSION_VERSION")
        if projection.mission_state is not MissionState.OPEN:
            raise CFBEKernelError("MISSION_NOT_ACTIVE")
        if requirement_id not in projection.requirement_states:
            raise CFBEKernelError("REQUIREMENT_UNKNOWN")
        state = RequirementState(state)
        if state in {RequirementState.PROVEN, RequirementState.SUPERSEDED, RequirementState.CANCELLED}:
            raise CFBEKernelError("DIRECT_TERMINAL_REQUIREMENT_TRANSITION_PROHIBITED")
        self.store.append(
            mission_id=mission_id,
            mission_version=mission_version,
            event_type="REQUIREMENT_STATE_SET",
            payload={"requirement_id": requirement_id, "state": state.value},
            idempotency_key=f"requirement:{requirement_id}:{state.value}",
            expected_head=projection.last_event_hash,
        )
        return self.project(mission_id)

    def bind_proof(self, proof: EvidenceProof) -> MissionProjection:
        proof.validate()
        projection = self.project(proof.mission_id)
        if proof.mission_version != projection.contract.mission_version:
            raise CFBEKernelError("STALE_PROOF_MISSION_VERSION")
        if projection.mission_state is not MissionState.OPEN:
            raise CFBEKernelError("MISSION_NOT_ACTIVE")
        self.store.append(
            mission_id=proof.mission_id,
            mission_version=proof.mission_version,
            event_type="PROOF_BOUND",
            payload={"proof": proof.to_dict()},
            idempotency_key=f"proof:{proof.proof_id}:{_digest(proof.to_dict())}",
            expected_head=projection.last_event_hash,
        )
        return self.project(proof.mission_id)

    @staticmethod
    def _proof_is_current(proof: EvidenceProof, now: str | None = None) -> bool:
        current = _parse_time(now or _now())
        return current < _parse_time(proof.created_at) + timedelta(seconds=proof.max_age_seconds)

    def prove_requirement(self, mission_id: str, mission_version: int, requirement_id: str, proof_id: str) -> MissionProjection:
        projection = self.project(mission_id)
        if mission_version != projection.contract.mission_version:
            raise CFBEKernelError("STALE_MISSION_VERSION")
        if requirement_id not in projection.requirement_states:
            raise CFBEKernelError("REQUIREMENT_UNKNOWN")
        proof = projection.proofs.get(proof_id)
        if proof is None or proof_id in projection.invalidated_proofs:
            raise CFBEKernelError("CURRENT_PROOF_REQUIRED")
        if proof.claim_id != f"requirement:{requirement_id}" or not self._proof_is_current(proof):
            raise CFBEKernelError("PROOF_CLAIM_OR_FRESHNESS_MISMATCH")
        self.store.append(
            mission_id=mission_id,
            mission_version=mission_version,
            event_type="REQUIREMENT_PROVEN",
            payload={"requirement_id": requirement_id, "proof_id": proof_id},
            idempotency_key=f"prove-requirement:{requirement_id}:{proof_id}",
            expected_head=projection.last_event_hash,
        )
        return self.project(mission_id)

    def prove_fruit(self, mission_id: str, mission_version: int, fruit_id: str, proof_id: str) -> MissionProjection:
        projection = self.project(mission_id)
        if mission_version != projection.contract.mission_version:
            raise CFBEKernelError("STALE_MISSION_VERSION")
        if fruit_id not in {item.fruit_id for item in projection.contract.terminal_fruit}:
            raise CFBEKernelError("FRUIT_UNKNOWN")
        proof = projection.proofs.get(proof_id)
        if proof is None or proof_id in projection.invalidated_proofs:
            raise CFBEKernelError("CURRENT_PROOF_REQUIRED")
        if proof.claim_id != f"fruit:{fruit_id}" or not self._proof_is_current(proof):
            raise CFBEKernelError("PROOF_CLAIM_OR_FRESHNESS_MISMATCH")
        self.store.append(
            mission_id=mission_id,
            mission_version=mission_version,
            event_type="FRUIT_PROVEN",
            payload={"fruit_id": fruit_id, "proof_id": proof_id},
            idempotency_key=f"prove-fruit:{fruit_id}:{proof_id}",
            expected_head=projection.last_event_hash,
        )
        return self.project(mission_id)

    def invalidate_dependencies(self, mission_id: str, observed_hashes: Mapping[str, str]) -> tuple[str, ...]:
        projection = self.project(mission_id)
        affected = sorted(
            proof_id
            for proof_id, proof in projection.proofs.items()
            if proof_id not in projection.invalidated_proofs
            and any(observed_hashes.get(dep) != expected for dep, expected in proof.dependency_hashes.items() if dep in observed_hashes)
        )
        if not affected:
            return ()
        self.store.append(
            mission_id=mission_id,
            mission_version=projection.contract.mission_version,
            event_type="PROOF_INVALIDATED",
            payload={"proof_ids": affected, "observed_dependency_hashes": dict(sorted(observed_hashes.items()))},
            idempotency_key=f"invalidate:{_digest({'proof_ids': affected, 'observed': dict(observed_hashes)})}",
            expected_head=projection.last_event_hash,
        )
        return tuple(affected)

    def decide_action(self, action: ActionProposal) -> DecisionReceipt:
        action.validate()
        projection = self.project(action.mission_id)
        reasons: list[str] = []
        if action.mission_version != projection.contract.mission_version:
            return DecisionReceipt(ActionDecision.CANCEL, False, ("STALE_MISSION_VERSION",), action.mission_id, action.mission_version, action.action_id)
        if projection.mission_state is MissionState.CANCELLED:
            return DecisionReceipt(ActionDecision.STOP, False, ("MISSION_CANCELLED",), action.mission_id, action.mission_version, action.action_id)
        if projection.mission_state is MissionState.COMPLETE_VERIFIED:
            return DecisionReceipt(ActionDecision.STOP, False, ("OUTCOME_ERROR_ZERO",), action.mission_id, action.mission_version, action.action_id)
        unknown = sorted(set(action.requirement_ids) - set(projection.requirement_states))
        inactive = sorted(
            req_id for req_id in action.requirement_ids
            if projection.requirement_states.get(req_id, RequirementState.CANCELLED).value not in ACTIVE_REQUIREMENT_STATES
        )
        if unknown:
            reasons.append("UNKNOWN_REQUIREMENTS:" + ",".join(unknown))
        if inactive:
            reasons.append("INACTIVE_REQUIREMENTS:" + ",".join(inactive))
        if reasons:
            return DecisionReceipt(ActionDecision.CANCEL, False, tuple(reasons), action.mission_id, action.mission_version, action.action_id)
        constraints = projection.contract.constraints
        if action.recurring_cost > 0 and constraints.zero_new_recurring_cost:
            reasons.append("RECURRING_COST_PROHIBITED")
        if action.estimated_cost > constraints.maximum_cost:
            reasons.append("MAXIMUM_COST_EXCEEDED")
        if action.estimated_user_burden > constraints.maximum_user_burden:
            reasons.append("MAXIMUM_USER_BURDEN_EXCEEDED")
        if action.creates_obligations and action.expected_outcome_delta <= 0 and action.expected_information_gain <= 0:
            reasons.append("SELF_GENERATED_OBLIGATION_RECURSION")
        if not action.necessary_safety_action and action.expected_outcome_delta <= 0 and action.expected_information_gain <= 0:
            reasons.append("NO_CAUSAL_VALUE")
        if reasons:
            return DecisionReceipt(ActionDecision.DENY, False, tuple(reasons), action.mission_id, action.mission_version, action.action_id)
        if action.authority_class not in constraints.authorized_classes:
            return DecisionReceipt(ActionDecision.APPROVAL_REQUIRED, False, ("AUTHORITY_CLASS_NOT_AUTHORIZED",), action.mission_id, action.mission_version, action.action_id)
        if action.effectful and not constraints.external_effects_allowed:
            return DecisionReceipt(ActionDecision.APPROVAL_REQUIRED, False, ("EXTERNAL_EFFECT_NOT_AUTHORIZED",), action.mission_id, action.mission_version, action.action_id)
        return DecisionReceipt(ActionDecision.EXECUTE, True, ("DETERMINISTIC_GATES_PASSED",), action.mission_id, action.mission_version, action.action_id)

    def issue_permit(self, action: ActionProposal, *, ttl_seconds: int = 300, issued_at: str | None = None) -> str:
        decision = self.decide_action(action)
        if decision.decision is not ActionDecision.EXECUTE:
            raise CFBEKernelError("PERMIT_DENIED:" + "|".join(decision.reasons))
        if ttl_seconds < 1:
            raise CFBEKernelError("PERMIT_TTL_INVALID")
        issued = issued_at or _now()
        expires = (_parse_time(issued) + timedelta(seconds=ttl_seconds)).isoformat()
        token = secrets.token_urlsafe(32)
        token_hash = sha256(token.encode("utf-8")).hexdigest()
        self.store.save_permit(token_hash=token_hash, action=action, issued_at=issued, expires_at=expires)
        projection = self.project(action.mission_id)
        self.store.append(
            mission_id=action.mission_id,
            mission_version=action.mission_version,
            event_type="PERMIT_ISSUED",
            payload={"token_hash": token_hash, "action_id": action.action_id, "action_sha256": action.action_sha256, "requirement_ids": sorted(action.requirement_ids), "expires_at": expires},
            idempotency_key=f"permit:{token_hash}",
            expected_head=projection.last_event_hash,
            occurred_at=issued,
        )
        return token

    def consume_permit(self, token: str, action: ActionProposal, *, now: str | None = None) -> None:
        if not token:
            raise CFBEKernelError("PERMIT_REQUIRED")
        decision = self.decide_action(action)
        if decision.decision is not ActionDecision.EXECUTE:
            raise CFBEKernelError("ACTION_NO_LONGER_AUTHORIZED")
        self.store.consume_permit(sha256(token.encode("utf-8")).hexdigest(), action, now or _now())

    def execute_once(
        self,
        action: ActionProposal,
        token: str,
        payload: Mapping[str, Any],
        executor: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> dict[str, Any]:
        if not action.effectful:
            raise CFBEKernelError("EXECUTE_ONCE_REQUIRES_EFFECTFUL_ACTION")
        _reject_secret_material(payload)
        payload_sha = _digest(dict(payload))
        effect_identity_sha = _digest(
            {
                "mission_version": action.mission_version,
                "resource_key": action.resource_key,
                "operation_key": action.operation_key,
                "payload": dict(payload),
            }
        )
        self.consume_permit(token, action)
        existing = self.store.effect(action.mission_id, action.idempotency_key)
        if existing is not None:
            if existing["payload_sha256"] != effect_identity_sha:
                raise IdempotencyConflict("EFFECT_IDEMPOTENCY_PAYLOAD_CONFLICT")
            if existing["state"] == "COMPLETED":
                receipt = json.loads(existing["receipt_json"])
                return {**receipt, "execution_state": "IDEMPOTENT_REPLAY"}
            raise CFBEKernelError(f"EFFECT_NOT_RETRYABLE_UNCHANGED:{existing['state']}")
        self.store.reserve_effect(action.mission_id, action.idempotency_key, effect_identity_sha)
        try:
            result = dict(executor(dict(payload)))
            _reject_secret_material(result)
        except Exception as exc:
            self.store.fail_effect(action.mission_id, action.idempotency_key, exc.__class__.__name__)
            raise
        receipt = {
            "schema": SCHEMA,
            "mission_id": action.mission_id,
            "mission_version": action.mission_version,
            "action_id": action.action_id,
            "idempotency_key": action.idempotency_key,
            "resource_key": action.resource_key,
            "operation_key": action.operation_key,
            "payload_sha256": payload_sha,
            "effect_identity_sha256": effect_identity_sha,
            "result": result,
            "execution_state": "EXECUTED_ONCE",
        }
        receipt["receipt_sha256"] = _digest(receipt)
        self.store.complete_effect(action.mission_id, action.idempotency_key, receipt)
        projection = self.project(action.mission_id)
        self.store.append(
            mission_id=action.mission_id,
            mission_version=action.mission_version,
            event_type="EFFECT_COMPLETED",
            payload={key: value for key, value in receipt.items() if key != "result"},
            idempotency_key=f"effect:{action.idempotency_key}:{receipt['receipt_sha256']}",
            expected_head=projection.last_event_hash,
        )
        return receipt

    def preflight_terminal_authority(self, mission_id: str) -> dict[str, Any]:
        projection = self.project(mission_id)
        actions = projection.contract.terminal_actions
        proven = [item.action_id for item in actions if item.route_state in {AuthorityState.PROVEN, AuthorityState.INAPPLICABLE}]
        gaps = [item.action_id for item in actions if item.route_state not in {AuthorityState.PROVEN, AuthorityState.INAPPLICABLE}]
        total = len(actions)
        return {
            "coverage": 1.0 if total == 0 else len(proven) / total,
            "proven_action_ids": tuple(proven),
            "gap_action_ids": tuple(gaps),
            "full_completion_promise_allowed": not gaps,
        }

    def register_wait(self, item: WaitRegistration) -> OutwardState:
        projection = self.project(item.mission_id)
        if item.mission_version != projection.contract.mission_version:
            raise CFBEKernelError("STALE_WAIT_REGISTRATION")
        self.store.register_wait(item)
        return self.waiting_state(item.mission_id)

    def waiting_state(self, mission_id: str) -> OutwardState:
        projection = self.project(mission_id)
        if projection.mission_state is MissionState.COMPLETE_VERIFIED:
            return OutwardState.COMPLETE_VERIFIED
        if projection.mission_state is MissionState.CANCELLED:
            return OutwardState.FAILED_CHECKPOINTED
        jobs = self.store.wait_jobs(mission_id, projection.contract.mission_version)
        if any(item.automatic for item in jobs):
            return OutwardState.WAITING_AUTOMATICALLY
        if self.preflight_terminal_authority(mission_id)["gap_action_ids"]:
            return OutwardState.BLOCKED_EXTERNAL_AUTHORITY
        return OutwardState.FAILED_CHECKPOINTED

    def terminality_report(self, mission_id: str, *, now: str | None = None) -> TerminalityReport:
        projection = self.project(mission_id)
        gaps: list[str] = []
        refs: list[str] = []
        if projection.mission_state is MissionState.CANCELLED:
            gaps.append("MISSION_CANCELLED")
        for requirement_id, state in projection.requirement_states.items():
            if state.value not in TERMINAL_REQUIREMENT_STATES:
                gaps.append(f"REQUIREMENT:{requirement_id}:{state.value}")
            elif state is RequirementState.PROVEN:
                proof_id = projection.requirement_proofs.get(requirement_id, "")
                proof = projection.proofs.get(proof_id)
                if not proof or proof_id in projection.invalidated_proofs or proof.independence_level < 1 or not self._proof_is_current(proof, now):
                    gaps.append(f"REQUIREMENT_PROOF:{requirement_id}")
                else:
                    refs.append(proof_id)
        for fruit in projection.contract.terminal_fruit:
            proof_id = projection.fruit_proofs.get(fruit.fruit_id, "")
            proof = projection.proofs.get(proof_id)
            if not proof_id or not proof or proof_id in projection.invalidated_proofs:
                gaps.append(f"FRUIT:{fruit.fruit_id}")
            elif proof.independence_level < 1 or not self._proof_is_current(proof, now):
                gaps.append(f"FRUIT_PROOF:{fruit.fruit_id}")
            else:
                refs.append(proof_id)
        gaps.extend(f"AUTHORITY:{item}" for item in self.preflight_terminal_authority(mission_id)["gap_action_ids"])
        # An execution graph is part of the same mission denominator. The
        # optional table check keeps Phase-1 databases backward compatible.
        with self.store._connect() as connection:
            has_graphs = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cfbe_multistream_graphs'"
            ).fetchone()
            if has_graphs:
                graph_rows = connection.execute(
                    "SELECT graph_id,state FROM cfbe_multistream_graphs "
                    "WHERE mission_id=? AND mission_version=? AND state!='CLOSED' ORDER BY graph_id",
                    (mission_id, projection.contract.mission_version),
                ).fetchall()
                gaps.extend(f"EXECUTION_GRAPH:{row['graph_id']}:{row['state']}" for row in graph_rows)
        complete = not gaps
        body = {
            "mission_id": mission_id,
            "mission_version": projection.contract.mission_version,
            "contract_sha256": projection.contract.contract_sha256,
            "complete": complete,
            "gaps": sorted(gaps),
            "proof_refs": sorted(set(refs)),
        }
        return TerminalityReport(
            complete=complete,
            state=OutwardState.COMPLETE_VERIFIED if complete else (
                OutwardState.BLOCKED_EXTERNAL_AUTHORITY
                if any(item.startswith("AUTHORITY:") for item in gaps)
                else OutwardState.FAILED_CHECKPOINTED
            ),
            gaps=tuple(sorted(gaps)),
            proof_refs=tuple(sorted(set(refs))),
            report_sha256=_digest(body),
        )

    def terminalize(self, mission_id: str, *, now: str | None = None) -> TerminalityReport:
        report = self.terminality_report(mission_id, now=now)
        if not report.complete:
            raise CFBEKernelError("FALSE_COMPLETION_BLOCKED:" + "|".join(report.gaps))
        projection = self.project(mission_id)
        self.store.append(
            mission_id=mission_id,
            mission_version=projection.contract.mission_version,
            event_type="MISSION_TERMINALIZED",
            payload={"report_sha256": report.report_sha256, "proof_refs": list(report.proof_refs)},
            idempotency_key=f"terminalize:{report.report_sha256}",
            expected_head=projection.last_event_hash,
            occurred_at=now,
        )
        return report

    def reconcile(self, mission_id: str) -> dict[str, Any]:
        projection = self.project(mission_id)
        if projection.mission_state is MissionState.COMPLETE_VERIFIED:
            return {"decision": "STOP", "state": OutwardState.COMPLETE_VERIFIED.value, "requirement_id": None}
        if projection.mission_state is MissionState.CANCELLED:
            return {"decision": "STOP", "state": OutwardState.FAILED_CHECKPOINTED.value, "requirement_id": None}
        for requirement_id in projection.contract.critical_path:
            state = projection.requirement_states[requirement_id]
            if state.value not in TERMINAL_REQUIREMENT_STATES:
                return {
                    "decision": "NEXT_REQUIREMENT",
                    "state": OutwardState.RUNNING.value,
                    "requirement_id": requirement_id,
                    "requirement_state": state.value,
                }
        report = self.terminality_report(mission_id)
        return {
            "decision": "TERMINALIZE" if report.complete else "HOLD",
            "state": report.state.value,
            "requirement_id": None,
            "gaps": report.gaps,
        }

    def cancel_mission(self, mission_id: str, reason: str) -> MissionProjection:
        projection = self.project(mission_id)
        if projection.mission_state is MissionState.COMPLETE_VERIFIED:
            raise CFBEKernelError("COMPLETED_MISSION_CANNOT_BE_CANCELLED")
        if not str(reason).strip():
            raise CFBEKernelError("CANCELLATION_REASON_REQUIRED")
        now = _now()
        self.store.append(
            mission_id=mission_id,
            mission_version=projection.contract.mission_version,
            event_type="MISSION_CANCELLED",
            payload={"reason": " ".join(str(reason).split())},
            idempotency_key=f"cancel:{_digest(reason)}",
            expected_head=projection.last_event_hash,
            occurred_at=now,
        )
        self.store.cancel_descendants(mission_id, projection.contract.mission_version, now)
        return self.project(mission_id)


def classify_changes(changes: Iterable[ChangeRecord]) -> tuple[ChangeRecord, ...]:
    """Validate Git-style changes without dropping zero-text or deletion-only entries."""
    allowed = {"A", "M", "D", "R", "C", "T", "U"}
    result: list[ChangeRecord] = []
    for item in changes:
        if item.status not in allowed or not item.path.strip():
            raise CFBEKernelError("CHANGE_RECORD_INVALID")
        if item.status in {"R", "C"} and not item.old_path.strip():
            raise CFBEKernelError("RENAME_OR_COPY_REQUIRES_OLD_PATH")
        result.append(item)
    if not result:
        raise CFBEKernelError("NO_CHANGED_PATHS")
    return tuple(result)


def parse_coordination_record(value: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on malformed lock heads; never infer availability from a noop."""
    required = {"schema", "lease_id", "fencing_token", "state", "holder", "expires_at"}
    if set(value) < required or value.get("schema") != "FEDERATION-COORDINATION-LEASE-1":
        raise CFBEKernelError("MALFORMED_COORDINATION_RECORD")
    if isinstance(value.get("fencing_token"), bool) or not isinstance(value.get("fencing_token"), int) or value["fencing_token"] < 1:
        raise CFBEKernelError("FENCING_TOKEN_INVALID")
    state = str(value.get("state"))
    if state not in {"ACTIVE", "RELEASED"}:
        raise CFBEKernelError("LEASE_STATE_INVALID")
    _parse_time(str(value["expires_at"]))
    if state == "RELEASED" and not str(value.get("released_at", "")).strip():
        raise CFBEKernelError("RELEASE_PROOF_MISSING")
    return dict(value)


def validate_capability_skip(
    capability: str,
    *,
    available: bool,
    registered_unavailable: Iterable[str],
) -> str:
    """Permit a reduced-export skip only through an explicit capability manifest."""
    capability = _validate_identifier(capability, "capability")
    if available:
        return "RUN_REQUIRED"
    if capability not in set(_clean(registered_unavailable)):
        raise CFBEKernelError("UNREGISTERED_CAPABILITY_SKIP_PROHIBITED")
    return "REGISTERED_UNAVAILABLE_SKIP"


def validate_failure_class(value: str, allowed: Iterable[str]) -> str:
    """Reject unsupported failure taxonomy before a hosted execution starts."""
    value = _validate_identifier(value, "failure class")
    if value not in set(_clean(allowed)):
        raise CFBEKernelError("UNSUPPORTED_FAILURE_CLASS")
    return value
