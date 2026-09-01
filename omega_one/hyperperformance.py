"""Bounded, proof-carrying hyperperformance controls for Omega-One.

These controls are local and non-effectful. They provide deterministic exactly-once
finalization, bounded retry/backoff, adaptive concurrency, SLO/error-budget decisions,
paired mission measurement, and DORA-style delivery metrics. They grant no provider
authority and make no deployment or value claim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
from statistics import median
from threading import RLock
from typing import Any, Iterable, Mapping


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: object) -> str:
    """Return the canonical JSON SHA-256 used by Omega-One replay controls."""
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


_sha256 = canonical_sha256


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value


def _require_sha256(value: str, field: str) -> str:
    _require_text(value, field)
    prefix, separator, digest = value.partition(":")
    if (
        separator != ":"
        or prefix != "sha256"
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{field} must be a lowercase sha256 digest")
    return value


class OutcomeState(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class FinalizationDecision(str, Enum):
    COMMITTED = "COMMITTED"
    REPLAYED = "REPLAYED"
    HELD = "HELD"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class AdmissionResult:
    decision: str
    payload_sha256: str
    reason: str


@dataclass(frozen=True)
class CanonicalReceipt:
    operation_id: str
    payload_sha256: str
    result_sha256: str
    proof_sha256: str
    outcome: OutcomeState
    receipt_id: str

    def body(self) -> dict[str, str]:
        return {
            "operation_id": self.operation_id,
            "outcome": self.outcome.value,
            "payload_sha256": self.payload_sha256,
            "proof_sha256": self.proof_sha256,
            "result_sha256": self.result_sha256,
        }

    def verify(self) -> bool:
        return self.receipt_id == _sha256(self.body())


@dataclass(frozen=True)
class FinalizationResult:
    decision: FinalizationDecision
    receipt: CanonicalReceipt | None
    reason: str
    committed_count: int
    replay_count: int


class ExactlyOnceFinalizer:
    """Thread-safe content-addressed receipt finalizer.

    Identical replays return the original receipt; they never emit a second canonical
    receipt. Conflicting payloads, results, proofs, or terminal outcomes fail closed.
    UNKNOWN outcomes stay pending until explicit readback or terminal finalization.
    """

    SNAPSHOT_SCHEMA = "OMEGA-ONE-EXACTLY-ONCE-V1"

    def __init__(self) -> None:
        self._intents: dict[str, str] = {}
        self._receipts: dict[str, CanonicalReceipt] = {}
        self._replays: dict[str, int] = {}
        self._lock = RLock()

    @property
    def committed_count(self) -> int:
        with self._lock:
            return len(self._receipts)

    def begin(self, operation_id: str, payload: object) -> AdmissionResult:
        operation_id = _require_text(operation_id, "operation_id")
        payload_sha256 = _sha256(payload)
        with self._lock:
            prior = self._intents.get(operation_id)
            if prior is None:
                self._intents[operation_id] = payload_sha256
                return AdmissionResult("ADMITTED", payload_sha256, "FIRST_SEEN")
            if prior != payload_sha256:
                return AdmissionResult("CONFLICT", payload_sha256, "PAYLOAD_HASH_CONFLICT")
            if operation_id in self._receipts:
                return AdmissionResult("REPLAY", payload_sha256, "CANONICAL_RECEIPT_EXISTS")
            return AdmissionResult("HELD", payload_sha256, "IN_FLIGHT_OR_RECOVERED_INTENT")

    def finalize(
        self,
        operation_id: str,
        payload: object,
        result: object,
        proof: object,
        outcome: OutcomeState,
    ) -> FinalizationResult:
        if not isinstance(outcome, OutcomeState):
            raise TypeError("outcome must be an OutcomeState")
        return self.finalize_hashed(
            operation_id,
            payload_sha256=_sha256(payload),
            result_sha256=_sha256(result),
            proof_sha256=_sha256(proof),
            outcome=outcome,
        )

    def finalize_hashed(
        self,
        operation_id: str,
        *,
        payload_sha256: str,
        result_sha256: str,
        proof_sha256: str,
        outcome: OutcomeState,
    ) -> FinalizationResult:
        """Finalize with caller-reused canonical digests.

        The prehashed path is intended for trace-spine/idempotency envelopes that already
        carry verified content hashes. It avoids repeated JSON serialization and hashing
        on retries while retaining exact payload/result/proof conflict checks.
        """
        operation_id = _require_text(operation_id, "operation_id")
        payload_sha256 = _require_sha256(payload_sha256, "payload_sha256")
        result_sha256 = _require_sha256(result_sha256, "result_sha256")
        proof_sha256 = _require_sha256(proof_sha256, "proof_sha256")
        if not isinstance(outcome, OutcomeState):
            raise TypeError("outcome must be an OutcomeState")
        with self._lock:
            admitted_payload = self._intents.get(operation_id)
            if admitted_payload is None:
                self._intents[operation_id] = payload_sha256
            elif admitted_payload != payload_sha256:
                return self._result(
                    operation_id,
                    FinalizationDecision.CONFLICT,
                    self._receipts.get(operation_id),
                    "PAYLOAD_HASH_CONFLICT",
                )
            if outcome is OutcomeState.UNKNOWN:
                return self._result(
                    operation_id,
                    FinalizationDecision.HELD,
                    None,
                    "UNKNOWN_OUTCOME_REQUIRES_READBACK",
                )

            prior = self._receipts.get(operation_id)
            if prior is not None:
                if (
                    prior.payload_sha256 == payload_sha256
                    and prior.result_sha256 == result_sha256
                    and prior.proof_sha256 == proof_sha256
                    and prior.outcome is outcome
                ):
                    self._replays[operation_id] = self._replays.get(operation_id, 0) + 1
                    return self._result(
                        operation_id,
                        FinalizationDecision.REPLAYED,
                        prior,
                        "ORIGINAL_CANONICAL_RECEIPT_RETURNED",
                    )
                return self._result(
                    operation_id,
                    FinalizationDecision.CONFLICT,
                    prior,
                    "TERMINAL_RESULT_OR_PROOF_CONFLICT",
                )

            body = {
                "operation_id": operation_id,
                "outcome": outcome.value,
                "payload_sha256": payload_sha256,
                "proof_sha256": proof_sha256,
                "result_sha256": result_sha256,
            }
            candidate = CanonicalReceipt(
                operation_id=operation_id,
                payload_sha256=payload_sha256,
                result_sha256=result_sha256,
                proof_sha256=proof_sha256,
                outcome=outcome,
                receipt_id=_sha256(body),
            )
            self._receipts[operation_id] = candidate
            return self._result(
                operation_id,
                FinalizationDecision.COMMITTED,
                candidate,
                "CANONICAL_RECEIPT_COMMITTED",
            )

    def finalize_hashed_replay_batch(
        self,
        operation_id: str,
        *,
        payload_sha256: str,
        result_sha256: str,
        proof_sha256: str,
        outcome: OutcomeState,
        attempt_count: int,
    ) -> FinalizationResult:
        """Collapse a recovered batch of identical attempts under one atomic decision.

        This path is for a queue or recovery ledger that has already grouped attempts by
        operation and verified content digest. Live arrivals continue to use finalize or
        finalize_hashed. The batch records replay cardinality but emits one receipt.
        """
        if not isinstance(attempt_count, int) or not 1 <= attempt_count <= 1_000_000:
            raise ValueError("attempt_count must be between one and 1,000,000")
        with self._lock:
            result = self.finalize_hashed(
                operation_id,
                payload_sha256=payload_sha256,
                result_sha256=result_sha256,
                proof_sha256=proof_sha256,
                outcome=outcome,
            )
            if result.decision not in {
                FinalizationDecision.COMMITTED,
                FinalizationDecision.REPLAYED,
            }:
                return result
            additional_replays = attempt_count - 1
            if additional_replays > 0:
                self._replays[operation_id] = (
                    self._replays.get(operation_id, 0) + additional_replays
                )
            return self._result(
                operation_id,
                result.decision,
                result.receipt,
                "RECOVERED_REPLAY_BATCH_COLLAPSED",
            )

    def readback(self, operation_id: str, payload: object) -> FinalizationResult:
        operation_id = _require_text(operation_id, "operation_id")
        payload_sha256 = _sha256(payload)
        with self._lock:
            expected = self._intents.get(operation_id)
            if expected is None:
                return self._result(
                    operation_id, FinalizationDecision.HELD, None, "INTENT_NOT_FOUND"
                )
            if expected != payload_sha256:
                return self._result(
                    operation_id,
                    FinalizationDecision.CONFLICT,
                    None,
                    "PAYLOAD_HASH_CONFLICT",
                )
            receipt = self._receipts.get(operation_id)
            if receipt is None:
                return self._result(
                    operation_id,
                    FinalizationDecision.HELD,
                    None,
                    "TERMINAL_RECEIPT_NOT_FOUND",
                )
            self._replays[operation_id] = self._replays.get(operation_id, 0) + 1
            return self._result(
                operation_id,
                FinalizationDecision.REPLAYED,
                receipt,
                "CANONICAL_RECEIPT_READBACK",
            )

    def canonical_receipts(self) -> tuple[CanonicalReceipt, ...]:
        with self._lock:
            return tuple(self._receipts[key] for key in sorted(self._receipts))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema": self.SNAPSHOT_SCHEMA,
                "intents": dict(sorted(self._intents.items())),
                "receipts": {
                    key: {**receipt.body(), "receipt_id": receipt.receipt_id}
                    for key, receipt in sorted(self._receipts.items())
                },
                "replays": dict(sorted(self._replays.items())),
            }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> "ExactlyOnceFinalizer":
        if snapshot.get("schema") != cls.SNAPSHOT_SCHEMA:
            raise ValueError("unsupported exactly-once snapshot schema")
        intents = snapshot.get("intents")
        receipts = snapshot.get("receipts")
        replays = snapshot.get("replays")
        if not isinstance(intents, dict) or not isinstance(receipts, dict) or not isinstance(replays, dict):
            raise ValueError("snapshot maps are required")
        restored = cls()
        for operation_id, payload_sha256 in intents.items():
            _require_text(operation_id, "operation_id")
            _require_text(payload_sha256, "payload_sha256")
            restored._intents[operation_id] = payload_sha256
        for operation_id, raw in receipts.items():
            if not isinstance(raw, dict):
                raise ValueError("receipt snapshot entry must be an object")
            receipt = CanonicalReceipt(
                operation_id=str(raw.get("operation_id") or ""),
                payload_sha256=str(raw.get("payload_sha256") or ""),
                result_sha256=str(raw.get("result_sha256") or ""),
                proof_sha256=str(raw.get("proof_sha256") or ""),
                outcome=OutcomeState(str(raw.get("outcome") or "")),
                receipt_id=str(raw.get("receipt_id") or ""),
            )
            if operation_id != receipt.operation_id or not receipt.verify():
                raise ValueError("receipt integrity verification failed")
            if restored._intents.get(operation_id) != receipt.payload_sha256:
                raise ValueError("receipt does not match recovered intent")
            restored._receipts[operation_id] = receipt
        for operation_id, count in replays.items():
            if operation_id not in restored._intents or not isinstance(count, int) or count < 0:
                raise ValueError("invalid replay counter")
            restored._replays[operation_id] = count
        return restored

    def _result(
        self,
        operation_id: str,
        decision: FinalizationDecision,
        receipt: CanonicalReceipt | None,
        reason: str,
    ) -> FinalizationResult:
        return FinalizationResult(
            decision=decision,
            receipt=receipt,
            reason=reason,
            committed_count=len(self._receipts),
            replay_count=self._replays.get(operation_id, 0),
        )


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    max_retry_tokens: int = 100
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 5.0
    jitter_ratio: float = 0.2

    def validate(self) -> "RetryPolicy":
        if self.max_attempts < 1 or self.max_retry_tokens < 0:
            raise ValueError("retry counts must be non-negative and max_attempts at least one")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("retry delays are invalid")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between zero and one")
        return self


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: float
    reason: str
    tokens_remaining: int
    next_attempt: int | None


class BoundedRetryController:
    """Idempotent retry decisions with a finite token budget and hash-based jitter."""

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self.policy = (policy or RetryPolicy()).validate()
        self._tokens = self.policy.max_retry_tokens
        self._decisions: dict[tuple[str, int], tuple[str, RetryDecision]] = {}
        self._lock = RLock()

    @property
    def tokens_remaining(self) -> int:
        with self._lock:
            return self._tokens

    def decide(
        self,
        operation_id: str,
        completed_attempt: int,
        outcome: OutcomeState,
        *,
        retryable: bool = True,
        error_budget_allows: bool = True,
    ) -> RetryDecision:
        operation_id = _require_text(operation_id, "operation_id")
        if completed_attempt < 1:
            raise ValueError("completed_attempt must be at least one")
        if not isinstance(outcome, OutcomeState):
            raise TypeError("outcome must be an OutcomeState")
        fingerprint = _sha256(
            {
                "outcome": outcome.value,
                "retryable": retryable,
                "error_budget_allows": error_budget_allows,
            }
        )
        key = (operation_id, completed_attempt)
        with self._lock:
            prior = self._decisions.get(key)
            if prior is not None:
                if prior[0] != fingerprint:
                    raise ValueError("retry decision inputs changed for an existing attempt")
                return prior[1]

            if outcome is OutcomeState.UNKNOWN:
                decision = RetryDecision(
                    False, 0.0, "UNKNOWN_OUTCOME_REQUIRES_READBACK", self._tokens, None
                )
            elif outcome is OutcomeState.SUCCEEDED:
                decision = RetryDecision(False, 0.0, "TERMINAL_SUCCESS", self._tokens, None)
            elif not retryable:
                decision = RetryDecision(False, 0.0, "NON_RETRYABLE_FAILURE", self._tokens, None)
            elif not error_budget_allows:
                decision = RetryDecision(False, 0.0, "ERROR_BUDGET_EXHAUSTED", self._tokens, None)
            elif completed_attempt >= self.policy.max_attempts:
                decision = RetryDecision(False, 0.0, "MAX_ATTEMPTS_EXHAUSTED", self._tokens, None)
            elif self._tokens <= 0:
                decision = RetryDecision(False, 0.0, "RETRY_TOKEN_BUDGET_EXHAUSTED", 0, None)
            else:
                self._tokens -= 1
                decision = RetryDecision(
                    True,
                    self._delay(operation_id, completed_attempt),
                    "BOUNDED_RETRY_ADMITTED",
                    self._tokens,
                    completed_attempt + 1,
                )
            self._decisions[key] = (fingerprint, decision)
            return decision

    def _delay(self, operation_id: str, completed_attempt: int) -> float:
        raw = min(
            self.policy.max_delay_seconds,
            self.policy.base_delay_seconds * (2 ** (completed_attempt - 1)),
        )
        digest = hashlib.sha256(f"{operation_id}:{completed_attempt}".encode("utf-8")).digest()
        unit = int.from_bytes(digest[:8], "big") / float(2**64)
        factor = 1 + self.policy.jitter_ratio * ((2 * unit) - 1)
        return round(min(self.policy.max_delay_seconds, max(0.0, raw * factor)), 9)


class WorkPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    BULK = "BULK"


@dataclass(frozen=True)
class ConcurrencyPolicy:
    minimum: int = 1
    initial: int = 4
    maximum: int = 32
    target_latency_ms: float = 500.0
    decrease_ratio: float = 0.5
    success_window: int = 8
    critical_reserve: int = 1

    def validate(self) -> "ConcurrencyPolicy":
        if not 1 <= self.minimum <= self.initial <= self.maximum:
            raise ValueError("concurrency bounds are invalid")
        if self.target_latency_ms <= 0 or not 0 < self.decrease_ratio < 1:
            raise ValueError("latency target and decrease ratio are invalid")
        if self.success_window < 1 or self.critical_reserve < 0:
            raise ValueError("success_window and critical_reserve are invalid")
        return self


@dataclass(frozen=True)
class ConcurrencyDecision:
    previous_limit: int
    new_limit: int
    reason: str


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason: str
    effective_limit: int


class AdaptiveConcurrencyController:
    """A bounded AIMD controller with stabilization and priority load shedding."""

    def __init__(self, policy: ConcurrencyPolicy | None = None) -> None:
        self.policy = (policy or ConcurrencyPolicy()).validate()
        self._limit = self.policy.initial
        self._successes = 0
        self._lock = RLock()

    @property
    def limit(self) -> int:
        with self._lock:
            return self._limit

    def observe(
        self,
        latency_ms: float,
        *,
        error: bool = False,
        throttled: bool = False,
        queue_saturated: bool = False,
    ) -> ConcurrencyDecision:
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        with self._lock:
            previous = self._limit
            overloaded = error or throttled or queue_saturated or latency_ms > self.policy.target_latency_ms
            if overloaded:
                reduced = max(
                    self.policy.minimum,
                    min(self._limit - 1, math.floor(self._limit * self.policy.decrease_ratio)),
                )
                self._limit = max(self.policy.minimum, reduced)
                self._successes = 0
                return ConcurrencyDecision(previous, self._limit, "MULTIPLICATIVE_DECREASE")
            self._successes += 1
            if self._successes >= self.policy.success_window and self._limit < self.policy.maximum:
                self._limit += 1
                self._successes = 0
                return ConcurrencyDecision(previous, self._limit, "ADDITIVE_INCREASE")
            return ConcurrencyDecision(previous, self._limit, "STABILIZATION_HOLD")

    def admit(self, priority: WorkPriority, in_flight: int) -> AdmissionDecision:
        if not isinstance(priority, WorkPriority):
            raise TypeError("priority must be a WorkPriority")
        if in_flight < 0:
            raise ValueError("in_flight cannot be negative")
        with self._lock:
            reserve = self.policy.critical_reserve if priority is WorkPriority.CRITICAL else 0
            effective = min(self.policy.maximum, self._limit + reserve)
            if in_flight < effective:
                return AdmissionDecision(True, "WITHIN_ADAPTIVE_LIMIT", effective)
            reason = "BULK_LOAD_SHED" if priority is WorkPriority.BULK else "ADAPTIVE_LIMIT_REACHED"
            return AdmissionDecision(False, reason, effective)


@dataclass(frozen=True)
class SloPolicy:
    availability_target: float = 0.99
    latency_target: float = 0.99
    latency_threshold_ms: float = 1000.0
    minimum_events: int = 100

    def validate(self) -> "SloPolicy":
        if not 0 < self.availability_target < 1 or not 0 < self.latency_target < 1:
            raise ValueError("SLO targets must be between zero and one")
        if self.latency_threshold_ms <= 0 or self.minimum_events < 1:
            raise ValueError("SLO threshold and sample floor are invalid")
        return self


@dataclass(frozen=True)
class SloSnapshot:
    event_count: int
    availability: float
    latency_compliance: float
    availability_burn_rate: float
    latency_burn_rate: float
    worst_burn_rate: float
    release_allowed: bool
    reason: str
    snapshot_sha256: str


class SloErrorBudget:
    """Windowed availability/latency SLO compiler with a fail-closed release gate."""

    def __init__(self, policy: SloPolicy | None = None) -> None:
        self.policy = (policy or SloPolicy()).validate()
        self._events: list[tuple[bool, float]] = []
        self._lock = RLock()

    def record(self, *, success: bool, latency_ms: float) -> None:
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        with self._lock:
            self._events.append((bool(success), float(latency_ms)))

    def snapshot(self) -> SloSnapshot:
        with self._lock:
            total = len(self._events)
            if total == 0:
                availability = latency_compliance = 0.0
                availability_burn = latency_burn = float("inf")
            else:
                availability = sum(1 for success, _ in self._events if success) / total
                latency_compliance = (
                    sum(1 for _, latency in self._events if latency <= self.policy.latency_threshold_ms)
                    / total
                )
                availability_burn = (1 - availability) / (1 - self.policy.availability_target)
                latency_burn = (1 - latency_compliance) / (1 - self.policy.latency_target)
            worst = max(availability_burn, latency_burn)
            enough = total >= self.policy.minimum_events
            allowed = enough and worst <= 1.0 + 1e-12
            reason = (
                "INSUFFICIENT_OBSERVATIONS"
                if not enough
                else "ERROR_BUDGET_AVAILABLE"
                if allowed
                else "ERROR_BUDGET_EXHAUSTED"
            )
            body = {
                "availability": availability,
                "availability_burn_rate": availability_burn,
                "event_count": total,
                "latency_burn_rate": latency_burn,
                "latency_compliance": latency_compliance,
                "release_allowed": allowed,
                "reason": reason,
                "worst_burn_rate": worst,
            }
            digest_body = {**body, "policy": asdict(self.policy)}
            return SloSnapshot(snapshot_sha256=_sha256(digest_body), **body)


@dataclass(frozen=True)
class MissionMeasurement:
    mission_id: str
    oracle_sha256: str
    latency_ms: float
    quality_score: float
    canonical_receipt_count: int = 1
    cold_replay: bool = True
    source: str = "OBSERVED"

    def validate(self) -> "MissionMeasurement":
        _require_text(self.mission_id, "mission_id")
        _require_text(self.oracle_sha256, "oracle_sha256")
        if self.latency_ms <= 0 or not 0 <= self.quality_score <= 1:
            raise ValueError("latency and quality measurement are invalid")
        if self.canonical_receipt_count < 1:
            raise ValueError("canonical_receipt_count must be positive")
        if self.source not in {"OBSERVED", "SCENARIO"}:
            raise ValueError("source must be OBSERVED or SCENARIO")
        return self


@dataclass(frozen=True)
class PairedMissionObservation:
    baseline: MissionMeasurement
    candidate: MissionMeasurement

    def validate(self) -> "PairedMissionObservation":
        self.baseline.validate()
        self.candidate.validate()
        if self.baseline.mission_id != self.candidate.mission_id:
            raise ValueError("paired mission IDs must match")
        return self


@dataclass(frozen=True)
class CampaignPolicy:
    minimum_pairs: int = 30
    minimum_median_speedup: float = 1.0
    maximum_p95_latency_ratio: float = 1.0

    def validate(self) -> "CampaignPolicy":
        if self.minimum_pairs < 1 or self.minimum_median_speedup <= 0:
            raise ValueError("campaign pair and speedup floors are invalid")
        if self.maximum_p95_latency_ratio <= 0:
            raise ValueError("maximum p95 ratio must be positive")
        return self


@dataclass(frozen=True)
class CampaignVerdict:
    state: str
    observed_pairs: int
    semantic_mismatches: int
    quality_regressions: int
    receipt_violations: int
    non_cold_or_scenario_pairs: int
    duplicate_mission_ids: int
    median_speedup: float
    p95_latency_ratio: float
    measurement_sha256: str
    reasons: tuple[str, ...]
    truth_boundary: str = "LOCAL_OBSERVED_ONLY_NO_PROVIDER_DEPLOYMENT_OR_VALUE_INHERITANCE"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return float("inf")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def evaluate_paired_campaign(
    observations: Iterable[PairedMissionObservation],
    policy: CampaignPolicy | None = None,
) -> CampaignVerdict:
    policy = (policy or CampaignPolicy()).validate()
    pairs = tuple(item.validate() for item in observations)
    ids = [item.baseline.mission_id for item in pairs]
    duplicates = len(ids) - len(set(ids))
    semantic_mismatches = sum(
        item.baseline.oracle_sha256 != item.candidate.oracle_sha256 for item in pairs
    )
    quality_regressions = sum(
        item.candidate.quality_score < item.baseline.quality_score for item in pairs
    )
    receipt_violations = sum(item.candidate.canonical_receipt_count != 1 for item in pairs)
    non_cold_or_scenario = sum(
        not item.baseline.cold_replay
        or not item.candidate.cold_replay
        or item.baseline.source != "OBSERVED"
        or item.candidate.source != "OBSERVED"
        for item in pairs
    )
    speedups = [item.baseline.latency_ms / item.candidate.latency_ms for item in pairs]
    median_speedup = median(speedups) if speedups else 0.0
    baseline_p95 = _percentile([item.baseline.latency_ms for item in pairs], 0.95)
    candidate_p95 = _percentile([item.candidate.latency_ms for item in pairs], 0.95)
    p95_ratio = candidate_p95 / baseline_p95 if math.isfinite(baseline_p95) else float("inf")

    reasons: list[str] = []
    if len(pairs) < policy.minimum_pairs:
        reasons.append("MINIMUM_PAIRED_OBSERVATIONS_NOT_MET")
    if duplicates:
        reasons.append("DUPLICATE_MISSION_IDS")
    if semantic_mismatches:
        reasons.append("SEMANTIC_ORACLE_MISMATCH")
    if quality_regressions:
        reasons.append("QUALITY_REGRESSION")
    if receipt_violations:
        reasons.append("EXACTLY_ONCE_RECEIPT_VIOLATION")
    if non_cold_or_scenario:
        reasons.append("COLD_OBSERVED_PAIR_REQUIRED")
    if median_speedup < policy.minimum_median_speedup:
        reasons.append("MEDIAN_SPEEDUP_FLOOR_NOT_MET")
    if p95_ratio > policy.maximum_p95_latency_ratio:
        reasons.append("P95_LATENCY_REGRESSION")

    measurement_body = {
        "observations": [
            {"baseline": asdict(item.baseline), "candidate": asdict(item.candidate)}
            for item in pairs
        ],
        "policy": asdict(policy),
    }
    return CampaignVerdict(
        state="QUALIFIED_LOCAL" if not reasons else "HELD",
        observed_pairs=len(pairs),
        semantic_mismatches=semantic_mismatches,
        quality_regressions=quality_regressions,
        receipt_violations=receipt_violations,
        non_cold_or_scenario_pairs=non_cold_or_scenario,
        duplicate_mission_ids=duplicates,
        median_speedup=median_speedup,
        p95_latency_ratio=p95_ratio,
        measurement_sha256=_sha256(measurement_body),
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class DeploymentEvent:
    deployment_id: str
    committed_at: float
    deployed_at: float
    failed: bool = False
    rework: bool = False
    recovered_at: float | None = None

    def validate(self) -> "DeploymentEvent":
        _require_text(self.deployment_id, "deployment_id")
        if self.committed_at < 0 or self.deployed_at < self.committed_at:
            raise ValueError("deployment timestamps are invalid")
        if self.recovered_at is not None and self.recovered_at < self.deployed_at:
            raise ValueError("recovery cannot precede deployment")
        return self


@dataclass(frozen=True)
class DoraSnapshot:
    deployment_count: int
    deployments_per_day: float
    median_change_lead_time_seconds: float
    failed_deployment_rate: float
    deployment_rework_rate: float
    median_failed_deployment_recovery_seconds: float | None
    unrecovered_failures: int
    snapshot_sha256: str


def compile_dora_metrics(
    events: Iterable[DeploymentEvent],
    *,
    observation_days: float,
) -> DoraSnapshot:
    if observation_days <= 0:
        raise ValueError("observation_days must be positive")
    items = tuple(item.validate() for item in events)
    count = len(items)
    lead_times = [item.deployed_at - item.committed_at for item in items]
    recoveries = [
        item.recovered_at - item.deployed_at
        for item in items
        if item.failed and item.recovered_at is not None
    ]
    body: dict[str, Any] = {
        "deployment_count": count,
        "deployments_per_day": count / observation_days,
        "median_change_lead_time_seconds": median(lead_times) if lead_times else 0.0,
        "failed_deployment_rate": sum(item.failed for item in items) / count if count else 0.0,
        "deployment_rework_rate": sum(item.rework for item in items) / count if count else 0.0,
        "median_failed_deployment_recovery_seconds": median(recoveries) if recoveries else None,
        "unrecovered_failures": sum(
            item.failed and item.recovered_at is None for item in items
        ),
    }
    return DoraSnapshot(snapshot_sha256=_sha256(body), **body)


def otel_measurement_attributes(
    *,
    mission_id: str,
    operation_name: str,
    state: str,
    measurement_sha256: str,
) -> Mapping[str, str]:
    """Project a minimal stable OTel-compatible measurement attribute set."""
    return {
        "service.name": "omega-one",
        "gen_ai.operation.name": _require_text(operation_name, "operation_name"),
        "omega.mission.id": _require_text(mission_id, "mission_id"),
        "omega.measurement.state": _require_text(state, "state"),
        "omega.measurement.sha256": _require_text(
            measurement_sha256, "measurement_sha256"
        ),
        "omega.execution.authority": "NONE",
        "omega.truth.boundary": "LOCAL_OBSERVED_ONLY",
    }
