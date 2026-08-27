from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

from .failure_win_v2 import (
    CausalHypothesis,
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
    WinEvidence,
)
from .horizon import HorizonOmega
from .models import FederationEvent, PerformanceVector
from .science_and_routes import FormationEngine


class BehavioralOrigin(str, Enum):
    """Evidence origin classes used to separate empirical fruit from test/config state."""

    REAL_PROVIDER = "REAL_PROVIDER"
    REAL_RUNTIME = "REAL_RUNTIME"
    REAL_OWNER_CORRECTION = "REAL_OWNER_CORRECTION"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    CONFIGURATION = "CONFIGURATION"
    DOCUMENTATION = "DOCUMENTATION"
    UNKNOWN = "UNKNOWN"


EMPIRICAL_ORIGINS = {
    BehavioralOrigin.REAL_PROVIDER,
    BehavioralOrigin.REAL_RUNTIME,
    BehavioralOrigin.REAL_OWNER_CORRECTION,
}


class BehavioralEvidenceKind(str, Enum):
    CAUSAL_MODEL = "CAUSAL_MODEL"
    FALSIFICATION = "FALSIFICATION"
    AUTHORITY_CURRENT = "AUTHORITY_CURRENT"
    COST_ALLOWED = "COST_ALLOWED"
    FAILURE_FIRST = "FAILURE_FIRST"
    HEALTHY_PATH = "HEALTHY_PATH"
    ROLLBACK = "ROLLBACK"
    FORWARD_CANARY = "FORWARD_CANARY"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"
    POSITIVE_VALUE = "POSITIVE_VALUE"
    NO_REGRESSION = "NO_REGRESSION"
    OWNER_BURDEN_NOT_INCREASED = "OWNER_BURDEN_NOT_INCREASED"
    PROVIDER_RECEIPT = "PROVIDER_RECEIPT"
    SUCCESS = "SUCCESS"


class BehavioralConvergenceState(str, Enum):
    INVOCATION_ONLY_NON_EMPIRICAL = "INVOCATION_ONLY_NON_EMPIRICAL"
    BEHAVIOR_PROOF_OPEN = "BEHAVIOR_PROOF_OPEN"
    BEHAVIOR_BOUNDED_WIN_SOAK_OPEN = "BEHAVIOR_BOUNDED_WIN_SOAK_OPEN"
    V2_BEHAVIOR_PROVEN = "V2_BEHAVIOR_PROVEN"


class BehavioralReceiptConflict(ValueError):
    """Raised when an event id is replayed with different canonical content."""


@dataclass(frozen=True)
class BehavioralProofReceipt:
    event_id: str
    receiver_id: str
    kind: BehavioralEvidenceKind
    origin: BehavioralOrigin
    observed_at: str
    proof_refs: tuple[str, ...]
    independent_readback: bool
    current: bool = True
    source_version: str = ""
    note: str = ""

    @property
    def empirical(self) -> bool:
        return self.origin in EMPIRICAL_ORIGINS

    @property
    def qualifies(self) -> bool:
        return self.empirical and self.independent_readback and self.current and bool(self.proof_refs)


@dataclass(frozen=True)
class BehavioralLedgerRecord:
    sequence: int
    record_type: str
    event_id: str
    receiver_id: str
    fingerprint: str
    payload_sha256: str
    qualifies: bool
    prev_hash: str
    record_hash: str


@dataclass(frozen=True)
class BehavioralConvergenceResult:
    receiver_id: str
    fingerprint: str
    state: BehavioralConvergenceState
    behavior_proven: bool
    empirical_failure_seen: bool
    qualifying_receipts: int
    rejected_receipts: int
    repeated_successes: int
    soak_seconds: float
    ledger_head: str
    kernel_result: dict[str, Any]
    next_actions: tuple[str, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value


@dataclass
class _Incident:
    receiver_id: str
    fingerprint: str
    observation: FailureObservation
    initial_event_id: str
    initial_origin: BehavioralOrigin
    initial_proof_refs: tuple[str, ...]
    initial_independent_readback: bool
    initial_current: bool
    incumbent: PerformanceVector = field(default_factory=PerformanceVector)
    routes: tuple[RecoveryRoute, ...] = ()
    hypotheses: tuple[CausalHypothesis, ...] = ()
    provider_dependent: bool = False
    required_repeated_successes: int = 3
    required_soak_seconds: float = 300.0
    receipts: list[BehavioralProofReceipt] = field(default_factory=list)

    @property
    def empirical_failure_seen(self) -> bool:
        return (
            self.initial_origin in EMPIRICAL_ORIGINS
            and self.initial_independent_readback
            and self.initial_current
            and bool(self.initial_proof_refs)
        )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _origin(value: str | BehavioralOrigin | None) -> BehavioralOrigin:
    if isinstance(value, BehavioralOrigin):
        return value
    try:
        return BehavioralOrigin(str(value or "UNKNOWN").upper())
    except ValueError:
        return BehavioralOrigin.UNKNOWN


_EVENT_TYPE_MAP = {
    "TOOL_FAILURE": FailureEventType.FAILURE,
    "FAILURE": FailureEventType.FAILURE,
    "TIMEOUT": FailureEventType.TIMEOUT,
    "REGRESSION": FailureEventType.REGRESSION,
    "CLAIM_FRUIT_CONTRADICTION": FailureEventType.CLAIM_FRUIT_CONTRADICTION,
    "PROVIDER_ERROR": FailureEventType.PROVIDER_ERROR,
    "OWNER_CORRECTION": FailureEventType.OWNER_CORRECTION,
    "SLO_BREACH": FailureEventType.SLO_BREACH,
    "CANARY_FAILURE": FailureEventType.CANARY_FAILURE,
    "PRECURSOR_RISK": FailureEventType.PRECURSOR_RISK,
}


class BehavioralConvergenceEngine:
    """Empirical lifecycle layer for Failure-to-Operational-Win v2.

    The existing v2 kernel remains the decision/proof engine. This layer adds the
    missing empirical boundary: event-origin classification, append-only receipt
    hashing, exact-id replay protection, evidence accumulation, and derivation of
    repeated-success/soak from independently read back real observations.

    This class does not create provider effects or durable provider storage. Its
    hash-chain snapshot is designed to be persisted by an authorised adapter.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        *,
        kernel: FailureToOperationalWinKernelV2 | None = None,
        horizon: HorizonOmega | None = None,
        formation: FormationEngine | None = None,
    ) -> None:
        self._shared_kernel = kernel or FailureToOperationalWinKernelV2(
            horizon=horizon,
            formation=formation,
        )
        self._horizon = self._shared_kernel.horizon
        self._formation = self._shared_kernel.formation
        self._incidents: dict[str, _Incident] = {}
        self._event_hashes: dict[str, str] = {}
        self._event_to_fingerprint: dict[str, str] = {}
        self._ledger: list[BehavioralLedgerRecord] = []

    def _stateless_kernel(self) -> FailureToOperationalWinKernelV2:
        # Re-assessment must not manufacture failure recurrences merely because
        # another proof receipt arrived. Real recurrence is carried by events.
        return FailureToOperationalWinKernelV2(
            horizon=self._horizon,
            formation=self._formation,
        )

    @staticmethod
    def _event_payload(event: FederationEvent, origin: BehavioralOrigin) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.source,
            "workstream": event.workstream,
            "idempotency_key": event.idempotency_key,
            "timestamp": event.timestamp,
            "target": event.target,
            "proof_class": event.proof_class,
            "authority_class": event.authority_class,
            "origin": origin.value,
            "payload": event.payload,
        }

    def _register_event(
        self,
        *,
        event_id: str,
        receiver_id: str,
        fingerprint: str,
        record_type: str,
        payload: Any,
        qualifies: bool,
    ) -> bool:
        payload_hash = _sha256(payload)
        prior = self._event_hashes.get(event_id)
        if prior is not None:
            if prior != payload_hash:
                raise BehavioralReceiptConflict(f"EVENT_ID_PAYLOAD_CONFLICT:{event_id}")
            return False

        prev_hash = self._ledger[-1].record_hash if self._ledger else "GENESIS"
        body = {
            "sequence": len(self._ledger) + 1,
            "record_type": record_type,
            "event_id": event_id,
            "receiver_id": receiver_id,
            "fingerprint": fingerprint,
            "payload_sha256": payload_hash,
            "qualifies": qualifies,
            "prev_hash": prev_hash,
        }
        record_hash = hashlib.sha256((prev_hash + "\n" + _canonical_json(body)).encode("utf-8")).hexdigest()
        self._ledger.append(
            BehavioralLedgerRecord(
                sequence=body["sequence"],
                record_type=record_type,
                event_id=event_id,
                receiver_id=receiver_id,
                fingerprint=fingerprint,
                payload_sha256=payload_hash,
                qualifies=qualifies,
                prev_hash=prev_hash,
                record_hash=record_hash,
            )
        )
        self._event_hashes[event_id] = payload_hash
        self._event_to_fingerprint[event_id] = fingerprint
        return True

    @staticmethod
    def _observation(event: FederationEvent) -> FailureObservation:
        payload = event.payload
        event_type = _EVENT_TYPE_MAP.get(event.event_type, FailureEventType.FAILURE)
        return FailureObservation(
            event_id=event.event_id,
            event_type=event_type,
            system_id=event.source or "UNKNOWN",
            objective=str(payload.get("objective", event.workstream or "Preserve owner objective")),
            claim=str(payload.get("claim", "Material operation should produce the requested fruit")),
            observed_fruit=str(payload.get("observed_fruit", payload.get("error", event.event_type))),
            desired_outcome=str(payload.get("desired_outcome", payload.get("objective", "Operational completion"))),
            failure_code=str(payload.get("failure_code", payload.get("failure_type", event.event_type))),
            provider=str(payload.get("provider", "")),
            configuration_hash=str(payload.get("configuration_hash", "")),
            dependency_refs=tuple(map(str, payload.get("dependency_refs", ()) or ())),
            failed_route_id=str(payload.get("route_id", "")),
            material=bool(payload.get("material", event_type != FailureEventType.PRECURSOR_RISK)),
            recurrence_count=max(1, int(payload.get("recurrence_count", 1))),
            owner_burden_delta=float(payload.get("owner_burden_delta", 0.0)),
            precursor_signals=tuple(map(str, payload.get("precursor_signals", ()) or ())),
            recent_route_history=tuple(map(str, payload.get("recent_route_history", ()) or ())),
        )

    def observe_federation_event(
        self,
        event: FederationEvent,
        *,
        origin: BehavioralOrigin | str | None = None,
        incumbent: PerformanceVector | None = None,
        routes: Iterable[RecoveryRoute] = (),
        hypotheses: Iterable[CausalHypothesis] = (),
        provider_dependent: bool | None = None,
        required_repeated_successes: int = 3,
        required_soak_seconds: float = 300.0,
    ) -> BehavioralConvergenceResult:
        resolved_origin = _origin(origin or event.payload.get("behavioral_origin"))
        observation = self._observation(event)
        fingerprint = FailureToOperationalWinKernelV2.fingerprint(observation)
        proof_refs = tuple(map(str, event.payload.get("proof_refs", ()) or ()))
        independent = bool(event.payload.get("independent_readback", False))
        current = bool(event.payload.get("current", False))
        empirical_failure = resolved_origin in EMPIRICAL_ORIGINS and independent and current and bool(proof_refs)

        event_payload = self._event_payload(event, resolved_origin)
        added = self._register_event(
            event_id=event.event_id,
            receiver_id=observation.system_id,
            fingerprint=fingerprint,
            record_type="FAILURE_EVENT",
            payload=event_payload,
            qualifies=empirical_failure,
        )

        if not added:
            return self.assess(fingerprint)

        incident = self._incidents.get(fingerprint)
        if incident is None:
            incident = _Incident(
                receiver_id=observation.system_id,
                fingerprint=fingerprint,
                observation=observation,
                initial_event_id=event.event_id,
                initial_origin=resolved_origin,
                initial_proof_refs=proof_refs,
                initial_independent_readback=independent,
                initial_current=current,
                incumbent=incumbent or PerformanceVector(),
                routes=tuple(routes),
                hypotheses=tuple(hypotheses),
                provider_dependent=(
                    bool(event.payload.get("provider_dependent", False))
                    if provider_dependent is None
                    else provider_dependent
                ),
                required_repeated_successes=max(1, int(required_repeated_successes)),
                required_soak_seconds=max(0.0, float(required_soak_seconds)),
            )
            self._incidents[fingerprint] = incident
        else:
            # A later empirical observation of the same failure fingerprint can
            # replace an earlier synthetic/config-only opening as the behavior root.
            if empirical_failure and not incident.empirical_failure_seen:
                incident.observation = observation
                incident.initial_event_id = event.event_id
                incident.initial_origin = resolved_origin
                incident.initial_proof_refs = proof_refs
                incident.initial_independent_readback = independent
                incident.initial_current = current
            if routes:
                incident.routes = tuple(routes)
            if hypotheses:
                incident.hypotheses = tuple(hypotheses)

        # Preserve the existing kernel's failure genome on actual new failure
        # events while all subsequent proof re-assessment remains stateless.
        self._shared_kernel.evaluate(
            FailureWinRequest(
                observation=observation,
                incumbent=incident.incumbent,
                routes=incident.routes,
                hypotheses=incident.hypotheses,
                provider_dependent=incident.provider_dependent,
            )
        )
        return self.assess(fingerprint)

    def record_proof(
        self,
        fingerprint: str,
        receipt: BehavioralProofReceipt,
    ) -> BehavioralConvergenceResult:
        incident = self._incidents.get(fingerprint)
        if incident is None:
            raise KeyError(f"UNKNOWN_FAILURE_FINGERPRINT:{fingerprint}")
        if receipt.receiver_id != incident.receiver_id:
            raise ValueError("RECEIVER_MISMATCH")

        added = self._register_event(
            event_id=receipt.event_id,
            receiver_id=receipt.receiver_id,
            fingerprint=fingerprint,
            record_type="PROOF_EVENT",
            payload={
                **asdict(receipt),
                "kind": receipt.kind.value,
                "origin": receipt.origin.value,
            },
            qualifies=receipt.qualifies,
        )
        if added:
            incident.receipts.append(receipt)
        return self.assess(fingerprint)

    @staticmethod
    def _qualifying_by_kind(incident: _Incident) -> dict[BehavioralEvidenceKind, list[BehavioralProofReceipt]]:
        result: dict[BehavioralEvidenceKind, list[BehavioralProofReceipt]] = {}
        for receipt in incident.receipts:
            if receipt.qualifies:
                result.setdefault(receipt.kind, []).append(receipt)
        return result

    @staticmethod
    def _success_metrics(receipts: list[BehavioralProofReceipt]) -> tuple[int, float]:
        if not receipts:
            return 0, 0.0
        unique = {receipt.event_id: receipt for receipt in receipts}
        times = sorted(_parse_time(item.observed_at) for item in unique.values())
        soak = max(0.0, (times[-1] - times[0]).total_seconds()) if len(times) > 1 else 0.0
        return len(unique), soak

    def _evidence(self, incident: _Incident) -> WinEvidence:
        by_kind = self._qualifying_by_kind(incident)
        successes, soak = self._success_metrics(by_kind.get(BehavioralEvidenceKind.SUCCESS, []))
        proof_refs = set(incident.initial_proof_refs if incident.empirical_failure_seen else ())
        for receipts in by_kind.values():
            for receipt in receipts:
                proof_refs.update(receipt.proof_refs)

        def has(kind: BehavioralEvidenceKind) -> bool:
            return bool(by_kind.get(kind))

        return WinEvidence(
            failure_fact_preserved=incident.empirical_failure_seen,
            causal_model_recorded=has(BehavioralEvidenceKind.CAUSAL_MODEL),
            falsification_executed=has(BehavioralEvidenceKind.FALSIFICATION),
            authority_current=has(BehavioralEvidenceKind.AUTHORITY_CURRENT),
            cost_allowed=has(BehavioralEvidenceKind.COST_ALLOWED),
            failure_first_test_passed=has(BehavioralEvidenceKind.FAILURE_FIRST),
            healthy_path_test_passed=has(BehavioralEvidenceKind.HEALTHY_PATH),
            rollback_test_passed=has(BehavioralEvidenceKind.ROLLBACK),
            forward_canary_passed=has(BehavioralEvidenceKind.FORWARD_CANARY),
            independent_semantic_readback=has(BehavioralEvidenceKind.SEMANTIC_READBACK),
            positive_value=has(BehavioralEvidenceKind.POSITIVE_VALUE),
            no_regression=has(BehavioralEvidenceKind.NO_REGRESSION),
            owner_burden_not_increased=has(BehavioralEvidenceKind.OWNER_BURDEN_NOT_INCREASED),
            provider_receipt_present=has(BehavioralEvidenceKind.PROVIDER_RECEIPT),
            repeated_successes=successes,
            soak_seconds=soak,
            proof_refs=tuple(sorted(proof_refs)),
        )

    def assess(self, fingerprint: str) -> BehavioralConvergenceResult:
        incident = self._incidents.get(fingerprint)
        if incident is None:
            raise KeyError(f"UNKNOWN_FAILURE_FINGERPRINT:{fingerprint}")
        evidence = self._evidence(incident)
        kernel = self._stateless_kernel()
        kernel_result = kernel.evaluate(
            FailureWinRequest(
                observation=incident.observation,
                incumbent=incident.incumbent,
                routes=incident.routes,
                hypotheses=incident.hypotheses,
                evidence=evidence,
                provider_dependent=incident.provider_dependent,
                required_repeated_successes=incident.required_repeated_successes,
                required_soak_seconds=incident.required_soak_seconds,
            )
        )

        if not incident.empirical_failure_seen:
            state = BehavioralConvergenceState.INVOCATION_ONLY_NON_EMPIRICAL
        elif kernel_result.state == FailureWinState.OPERATIONAL_WIN_VERIFIED:
            state = BehavioralConvergenceState.V2_BEHAVIOR_PROVEN
        elif kernel_result.state == FailureWinState.BOUNDED_WIN:
            state = BehavioralConvergenceState.BEHAVIOR_BOUNDED_WIN_SOAK_OPEN
        else:
            state = BehavioralConvergenceState.BEHAVIOR_PROOF_OPEN

        qualifying = sum(1 for item in incident.receipts if item.qualifies)
        rejected = len(incident.receipts) - qualifying
        next_actions = list(kernel_result.next_actions)
        if not incident.empirical_failure_seen:
            next_actions.insert(0, "WAIT_FOR_EMPIRICAL_FAILURE_OR_PRECURSOR_WITH_INDEPENDENT_READBACK")
        if state == BehavioralConvergenceState.BEHAVIOR_BOUNDED_WIN_SOAK_OPEN:
            next_actions.insert(0, "ACCUMULATE_DISTINCT_REAL_SUCCESS_RECEIPTS_UNTIL_REPEAT_AND_SOAK_THRESHOLDS_PASS")

        return BehavioralConvergenceResult(
            receiver_id=incident.receiver_id,
            fingerprint=fingerprint,
            state=state,
            behavior_proven=state == BehavioralConvergenceState.V2_BEHAVIOR_PROVEN,
            empirical_failure_seen=incident.empirical_failure_seen,
            qualifying_receipts=qualifying,
            rejected_receipts=rejected,
            repeated_successes=evidence.repeated_successes,
            soak_seconds=evidence.soak_seconds,
            ledger_head=self.ledger_head,
            kernel_result=kernel_result.to_dict(),
            next_actions=tuple(dict.fromkeys(next_actions)),
            truth_boundary=(
                "Behavioral promotion is empirical-only. Synthetic tests, configuration, documentation, "
                "source presence and invocation can be preserved but cannot satisfy behavior proof. "
                "Every qualifying proof event requires a non-empty proof reference, current state and "
                "independent readback. Repeated-success count and soak are derived from distinct qualifying "
                "real success receipts; this engine never accepts caller-declared success counters as proof."
            ),
        )

    @property
    def ledger_head(self) -> str:
        return self._ledger[-1].record_hash if self._ledger else "GENESIS"

    def ledger_snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(record) for record in self._ledger)

    @staticmethod
    def verify_ledger_snapshot(records: Iterable[dict[str, Any]]) -> tuple[int, str]:
        previous = "GENESIS"
        count = 0
        for raw in records:
            count += 1
            expected_sequence = count
            if int(raw.get("sequence", -1)) != expected_sequence:
                raise ValueError("BEHAVIOR_LEDGER_SEQUENCE_MISMATCH")
            if raw.get("prev_hash") != previous:
                raise ValueError("BEHAVIOR_LEDGER_PARENT_MISMATCH")
            body = {
                "sequence": expected_sequence,
                "record_type": raw.get("record_type"),
                "event_id": raw.get("event_id"),
                "receiver_id": raw.get("receiver_id"),
                "fingerprint": raw.get("fingerprint"),
                "payload_sha256": raw.get("payload_sha256"),
                "qualifies": bool(raw.get("qualifies")),
                "prev_hash": previous,
            }
            expected = hashlib.sha256((previous + "\n" + _canonical_json(body)).encode("utf-8")).hexdigest()
            if raw.get("record_hash") != expected:
                raise ValueError("BEHAVIOR_LEDGER_HASH_MISMATCH")
            previous = expected
        return count, previous
