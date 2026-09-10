"""Provider-neutral resident execution substrate for Federation Omega.

This module extends, rather than replaces, the local SQLite ``RunStore``.  It
defines the atomic document contract required from a provider adapter and adds
durable work handles, bounded admission, deterministic result/failure caching,
desired-state reconciliation, and a reusable conformance court.

The included in-memory adapter is a deterministic test double.  Importing this
module does not prove that a cloud provider adapter is deployed or callable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import threading
import time
from typing import Any, Callable, Mapping, Protocol


SCHEMA = "FUSE-RESIDENT-EXECUTION-SUBSTRATE-V1"
VERSION = "1.0.0"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + sha256(canonical(value).encode("utf-8")).hexdigest()


class AtomicConflict(RuntimeError):
    """The provider-native create/CAS precondition did not hold."""


class IdempotencyCollision(RuntimeError):
    """An idempotency key was reused for a different semantic request."""


class FenceViolation(RuntimeError):
    """A stale worker attempted to mutate a fenced work handle."""


class AtomicDocumentBackend(Protocol):
    """Minimum provider contract; implementations must be linearizable per key."""

    def read(self, key: str) -> tuple[int, Mapping[str, Any]] | None: ...

    def create(self, key: str, value: Mapping[str, Any]) -> int: ...

    def compare_and_swap(
        self, key: str, expected_version: int, value: Mapping[str, Any]
    ) -> int: ...


class InMemoryAtomicDocumentBackend:
    """Thread-safe conformance adapter for tests and deterministic local use."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, tuple[int, dict[str, Any]]] = {}

    def read(self, key: str) -> tuple[int, Mapping[str, Any]] | None:
        with self._lock:
            item = self._records.get(key)
            return None if item is None else (item[0], dict(item[1]))

    def create(self, key: str, value: Mapping[str, Any]) -> int:
        with self._lock:
            if key in self._records:
                raise AtomicConflict("ATOMIC_CREATE_CONFLICT")
            self._records[key] = (1, dict(value))
            return 1

    def compare_and_swap(
        self, key: str, expected_version: int, value: Mapping[str, Any]
    ) -> int:
        with self._lock:
            current = self._records.get(key)
            if current is None or current[0] != expected_version:
                actual = None if current is None else current[0]
                raise AtomicConflict(
                    f"ATOMIC_CAS_CONFLICT:EXPECTED:{expected_version}:ACTUAL:{actual}"
                )
            version = expected_version + 1
            self._records[key] = (version, dict(value))
            return version


class WorkState(str, Enum):
    READY = "READY"
    LEASED = "LEASED"
    READBACK_REQUIRED = "READBACK_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = frozenset({WorkState.SUCCEEDED, WorkState.FAILED, WorkState.CANCELLED})


@dataclass(frozen=True, slots=True)
class WorkSpec:
    mission_id: str
    work_id: str
    transition_id: str
    provider: str
    target: str
    operation: str
    semantic_request_sha256: str
    idempotency_key: str
    source_epoch: str
    effect_class: str
    risk_class: str
    expected_readback: str
    rollback_ref: str

    def validate(self) -> None:
        required = asdict(self)
        missing = sorted(key for key, value in required.items() if not str(value).strip())
        if missing:
            raise ValueError("WORK_SPEC_REQUIRED:" + ",".join(missing))
        if not self.semantic_request_sha256.startswith("sha256:"):
            raise ValueError("SEMANTIC_REQUEST_SHA256_REQUIRED")


@dataclass(frozen=True, slots=True)
class DurableWorkHandle:
    handle_id: str
    spec: WorkSpec
    state: WorkState
    version: int
    fencing_token: int
    lease_owner: str = ""
    lease_expires_at: float = 0.0
    result_ref: str = ""
    proof_refs: tuple[str, ...] = ()
    failure_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    capacity: int
    active: int
    queued: int


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    state: str
    admitted: bool
    retry_after_seconds: float = 0.0


class WorkAdmissionController:
    """Fail-closed capacity and queue admission with explicit backpressure."""

    def __init__(self, *, max_active: int, max_queued: int) -> None:
        if max_active < 1 or max_queued < 0:
            raise ValueError("ADMISSION_LIMIT_INVALID")
        self.max_active = max_active
        self.max_queued = max_queued

    def decide(self, snapshot: AdmissionSnapshot) -> AdmissionDecision:
        if min(snapshot.capacity, snapshot.active, snapshot.queued) < 0:
            raise ValueError("ADMISSION_SNAPSHOT_INVALID")
        capacity = min(self.max_active, snapshot.capacity)
        if snapshot.active < capacity:
            return AdmissionDecision("ADMITTED", True)
        if snapshot.queued < self.max_queued:
            return AdmissionDecision("QUEUED_BACKPRESSURE", False, 1.0)
        return AdmissionDecision("REJECTED_SATURATED", False, 5.0)


class ResidentExecutionStore:
    """Durable handle state machine over a provider-native atomic backend."""

    def __init__(self, backend: AtomicDocumentBackend, *, clock: Callable[[], float] = time.time) -> None:
        self.backend = backend
        self.clock = clock

    @staticmethod
    def _key(idempotency_key: str) -> str:
        return "work/" + digest({"idempotency_key": idempotency_key})[7:]

    @staticmethod
    def _to_handle(version: int, value: Mapping[str, Any]) -> DurableWorkHandle:
        spec = WorkSpec(**value["spec"])
        return DurableWorkHandle(
            handle_id=str(value["handle_id"]),
            spec=spec,
            state=WorkState(value["state"]),
            version=version,
            fencing_token=int(value["fencing_token"]),
            lease_owner=str(value.get("lease_owner", "")),
            lease_expires_at=float(value.get("lease_expires_at", 0.0)),
            result_ref=str(value.get("result_ref", "")),
            proof_refs=tuple(value.get("proof_refs", ())),
            failure_fingerprint=str(value.get("failure_fingerprint", "")),
        )

    @staticmethod
    def _value(handle: DurableWorkHandle) -> dict[str, Any]:
        value = asdict(handle)
        value.pop("version")
        value["state"] = handle.state.value
        return value

    def issue(self, spec: WorkSpec) -> DurableWorkHandle:
        spec.validate()
        key = self._key(spec.idempotency_key)
        handle = DurableWorkHandle(
            handle_id="WORK-" + digest(asdict(spec))[7:31],
            spec=spec,
            state=WorkState.READY,
            version=1,
            fencing_token=0,
        )
        try:
            self.backend.create(key, self._value(handle))
            return handle
        except AtomicConflict:
            current = self.backend.read(key)
            if current is None:
                raise
            existing = self._to_handle(*current)
            if existing.spec.semantic_request_sha256 != spec.semantic_request_sha256:
                raise IdempotencyCollision("IDEMPOTENCY_KEY_SEMANTIC_COLLISION")
            if existing.spec != spec:
                raise IdempotencyCollision("IDEMPOTENCY_KEY_CONSTRAINT_COLLISION")
            return existing

    def read(self, idempotency_key: str) -> DurableWorkHandle | None:
        current = self.backend.read(self._key(idempotency_key))
        return None if current is None else self._to_handle(*current)

    def acquire(self, idempotency_key: str, *, owner: str, lease_seconds: float) -> DurableWorkHandle:
        if not owner.strip() or lease_seconds <= 0:
            raise ValueError("LEASE_ARGUMENT_INVALID")
        key = self._key(idempotency_key)
        current = self.backend.read(key)
        if current is None:
            raise KeyError("WORK_HANDLE_MISSING")
        version, value = current
        handle = self._to_handle(version, value)
        now = self.clock()
        if handle.state in TERMINAL_STATES:
            raise AtomicConflict("TERMINAL_WORK_CANNOT_BE_LEASED")
        if handle.lease_owner and handle.lease_expires_at > now and handle.lease_owner != owner:
            raise AtomicConflict("WORK_LEASE_HELD")
        candidate = DurableWorkHandle(
            handle_id=handle.handle_id,
            spec=handle.spec,
            state=WorkState.LEASED,
            version=version + 1,
            fencing_token=handle.fencing_token + 1,
            lease_owner=owner,
            lease_expires_at=now + lease_seconds,
            result_ref=handle.result_ref,
            proof_refs=handle.proof_refs,
            failure_fingerprint=handle.failure_fingerprint,
        )
        new_version = self.backend.compare_and_swap(key, version, self._value(candidate))
        return DurableWorkHandle(**{**asdict(candidate), "version": new_version})

    def transition(
        self,
        idempotency_key: str,
        *,
        owner: str,
        fencing_token: int,
        state: WorkState,
        result_ref: str = "",
        proof_refs: tuple[str, ...] = (),
        failure_fingerprint: str = "",
    ) -> DurableWorkHandle:
        key = self._key(idempotency_key)
        current = self.backend.read(key)
        if current is None:
            raise KeyError("WORK_HANDLE_MISSING")
        version, value = current
        handle = self._to_handle(version, value)
        if handle.state in TERMINAL_STATES:
            raise AtomicConflict("TERMINAL_WORK_IS_IMMUTABLE")
        if handle.lease_owner != owner or handle.fencing_token != fencing_token:
            raise FenceViolation("STALE_OR_FOREIGN_WORKER")
        if handle.lease_expires_at <= self.clock():
            raise FenceViolation("WORK_LEASE_EXPIRED")
        allowed = {
            WorkState.LEASED: {
                WorkState.READBACK_REQUIRED,
                WorkState.SUCCEEDED,
                WorkState.FAILED,
                WorkState.CANCELLED,
            },
            WorkState.READBACK_REQUIRED: {
                WorkState.READBACK_REQUIRED,
                WorkState.SUCCEEDED,
                WorkState.FAILED,
                WorkState.CANCELLED,
            },
        }
        if state not in allowed.get(handle.state, set()):
            raise AtomicConflict(f"WORK_STATE_TRANSITION_INVALID:{handle.state.value}:{state.value}")
        if (
            handle.spec.effect_class == "EXTERNAL_EFFECT"
            and state is WorkState.SUCCEEDED
            and handle.state is not WorkState.READBACK_REQUIRED
        ):
            raise ValueError("EXTERNAL_EFFECT_REQUIRES_READBACK_BEFORE_SUCCESS")
        if state is WorkState.SUCCEEDED and (not result_ref.strip() or not proof_refs):
            raise ValueError("SUCCESS_REQUIRES_RESULT_AND_PROOF")
        if state is WorkState.FAILED and not failure_fingerprint.strip():
            raise ValueError("FAILURE_FINGERPRINT_REQUIRED")
        candidate = DurableWorkHandle(
            handle_id=handle.handle_id,
            spec=handle.spec,
            state=state,
            version=version + 1,
            fencing_token=handle.fencing_token,
            lease_owner=handle.lease_owner,
            lease_expires_at=handle.lease_expires_at,
            result_ref=result_ref,
            proof_refs=tuple(sorted(set(proof_refs))),
            failure_fingerprint=failure_fingerprint,
        )
        new_version = self.backend.compare_and_swap(key, version, self._value(candidate))
        return DurableWorkHandle(**{**asdict(candidate), "version": new_version})


@dataclass(frozen=True, slots=True)
class ResultCacheRecord:
    cache_key: str
    outcome: str
    payload_ref: str
    proof_refs: tuple[str, ...]
    invalidation_key: str
    expires_at: float
    deterministic: bool


class DurableResultCache:
    """Caches verified success or deterministic failure with explicit invalidation."""

    def __init__(self, backend: AtomicDocumentBackend, *, clock: Callable[[], float] = time.time) -> None:
        self.backend = backend
        self.clock = clock

    @staticmethod
    def _key(cache_key: str) -> str:
        return "cache/" + digest({"cache_key": cache_key})[7:]

    def record(self, record: ResultCacheRecord, *, effect_class: str) -> ResultCacheRecord:
        if effect_class == "EXTERNAL_EFFECT":
            raise ValueError("EXTERNAL_EFFECT_CANNOT_BE_CACHED")
        if record.outcome not in {"SUCCESS", "DETERMINISTIC_FAILURE"}:
            raise ValueError("CACHE_OUTCOME_INVALID")
        if record.outcome == "DETERMINISTIC_FAILURE" and not record.deterministic:
            raise ValueError("NEGATIVE_CACHE_REQUIRES_DETERMINISM")
        if not record.proof_refs or not record.invalidation_key or record.expires_at <= self.clock():
            raise ValueError("CACHE_PROOF_INVALIDATION_AND_FUTURE_EXPIRY_REQUIRED")
        key = self._key(record.cache_key)
        value = asdict(record)
        try:
            self.backend.create(key, value)
        except AtomicConflict:
            current = self.backend.read(key)
            if current is None or dict(current[1]) != value:
                raise IdempotencyCollision("CACHE_RECORD_CONFLICT")
        return record

    def lookup(self, cache_key: str, *, invalidation_key: str) -> ResultCacheRecord | None:
        current = self.backend.read(self._key(cache_key))
        if current is None:
            return None
        value = dict(current[1])
        value["proof_refs"] = tuple(value["proof_refs"])
        record = ResultCacheRecord(**value)
        if record.expires_at <= self.clock() or record.invalidation_key != invalidation_key:
            return None
        return record


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    state: str
    drift: Mapping[str, tuple[Any, Any]]
    actions: tuple[str, ...]


class DesiredStateReconciler:
    """Produces a deterministic diff; it does not execute provider effects."""

    def compare(
        self, desired: Mapping[str, Any], observed: Mapping[str, Any], *, managed_fields: tuple[str, ...]
    ) -> ReconciliationDecision:
        drift = {
            field: (observed.get(field), desired.get(field))
            for field in sorted(set(managed_fields))
            if observed.get(field) != desired.get(field)
        }
        if not drift:
            return ReconciliationDecision("CONVERGED", {}, ())
        actions = tuple(f"SET:{field}" for field in drift)
        return ReconciliationDecision("DRIFT_DETECTED", drift, actions)


@dataclass(frozen=True, slots=True)
class ConformanceReceipt:
    state: str
    checks: tuple[str, ...]


class ProviderConformanceKit:
    """Minimal atomicity and isolation court for a candidate provider adapter."""

    def run(self, factory: Callable[[], AtomicDocumentBackend]) -> ConformanceReceipt:
        backend = factory()
        checks: list[str] = []
        assert backend.read("missing") is None
        checks.append("MISSING_READ_NONE")
        assert backend.create("k", {"value": 1}) == 1
        checks.append("CREATE_VERSION_ONE")
        try:
            backend.create("k", {"value": 2})
            raise AssertionError("DUPLICATE_CREATE_NOT_REJECTED")
        except AtomicConflict:
            checks.append("DUPLICATE_CREATE_REJECTED")
        assert backend.compare_and_swap("k", 1, {"value": 2}) == 2
        checks.append("CAS_ADVANCES_VERSION")
        try:
            backend.compare_and_swap("k", 1, {"value": 3})
            raise AssertionError("STALE_CAS_NOT_REJECTED")
        except AtomicConflict:
            checks.append("STALE_CAS_REJECTED")
        current = backend.read("k")
        assert current is not None and current[0] == 2 and current[1]["value"] == 2
        checks.append("READBACK_EXACT")
        return ConformanceReceipt("CONFORMANT_LOCAL_COURT", tuple(checks))


__all__ = [
    "SCHEMA", "VERSION", "AdmissionDecision", "AdmissionSnapshot", "AtomicConflict",
    "AtomicDocumentBackend", "ConformanceReceipt", "DesiredStateReconciler",
    "DurableResultCache", "DurableWorkHandle", "FenceViolation",
    "IdempotencyCollision", "InMemoryAtomicDocumentBackend", "ProviderConformanceKit",
    "ReconciliationDecision", "ResidentExecutionStore", "ResultCacheRecord",
    "WorkAdmissionController", "WorkSpec", "WorkState", "digest",
]
