from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Mapping, Sequence

from federation.bubbles_hyperperformance import (
    CurrentStateLease,
    CurrentStateLeaseError,
    IdempotencyEnvelope,
    IdempotencyLedger,
    TraceEvent,
    TraceSpine,
)


_STAGES = {"INPUT", "TOOL", "OUTPUT"}
_FAILURE_CLASSES = {"TRANSIENT", "INTERMITTENT", "PERMANENT", "CONTRADICTION"}


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GuardrailVerdict:
    name: str
    stage: str
    allowed: bool
    tripwire: bool = False
    reason: str = ""

    def validate(self) -> None:
        if not self.name or self.stage not in _STAGES:
            raise ValueError("GUARDRAIL_IDENTITY_REQUIRED")
        if self.tripwire and self.allowed:
            raise ValueError("GUARDRAIL_TRIPWIRE_CANNOT_ALLOW")


@dataclass(frozen=True)
class CompensationPlan:
    compensation_id: str
    operation_id: str
    action_ref: str
    idempotency_key: str
    registered_before_effect: bool

    def validate(self) -> None:
        if not all((self.compensation_id, self.operation_id, self.action_ref, self.idempotency_key)):
            raise ValueError("COMPENSATION_IDENTITY_REQUIRED")
        if not self.registered_before_effect:
            raise ValueError("COMPENSATION_MUST_PRECEDE_EFFECT")


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    objective_fit: float
    evidence_strength: float
    information_gain: float
    proof_closure: float
    risk: float
    burden: float
    latency_ms: int
    reversible: bool = True
    effect_class: str = "NONE"
    required_lease_ids: tuple[str, ...] = ()
    expected_authority: str = ""
    guardrails: tuple[GuardrailVerdict, ...] = ()
    idempotency: IdempotencyEnvelope | None = None
    compensation: CompensationPlan | None = None
    proof_refs: tuple[str, ...] = ()

    @property
    def effectful(self) -> bool:
        return self.effect_class.upper() != "NONE"

    def validate(self) -> None:
        if not self.route_id:
            raise ValueError("ROUTE_ID_REQUIRED")
        for name in (
            "objective_fit",
            "evidence_strength",
            "information_gain",
            "proof_closure",
            "risk",
            "burden",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"ROUTE_{name.upper()}_OUT_OF_RANGE")
        if self.latency_ms < 0:
            raise ValueError("ROUTE_LATENCY_NEGATIVE")
        for verdict in self.guardrails:
            verdict.validate()

    def score(self) -> float:
        latency_penalty = min(self.latency_ms / 20_000.0, 0.05)
        value = (
            0.29 * self.objective_fit
            + 0.27 * self.evidence_strength
            + 0.18 * self.proof_closure
            + 0.16 * self.information_gain
            + (0.07 if self.reversible else 0.0)
            - 0.02 * self.risk
            - 0.01 * self.burden
            - latency_penalty
        )
        return round(value, 9)


@dataclass(frozen=True)
class Counterfactual:
    route_id: str
    score: float
    delta_from_selected: float | None
    state: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class CourtReceipt:
    state: str
    mission_id: str
    selected_route_id: str
    selected_score: float | None
    effect_authorized: bool
    counterfactuals: tuple[Counterfactual, ...]
    trace_digest: str
    receipt_sha256: str
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class FailurePolicy:
    failure_class: str
    retry_allowed: bool
    max_attempts: int
    backoff_seconds: tuple[int, ...]
    compensation_required: bool


@dataclass(frozen=True)
class LearningCandidate:
    route_id: str
    state: str
    claim_fruit_delta: float
    failure_policy: FailurePolicy
    auto_promoted: bool
    proof_refs: tuple[str, ...] = ()


class CognitiveCourt:
    """Deterministic route court for Bubbles.

    The court ranks proof-eligible routes, records counterfactuals and emits a
    privacy-safe trace. It never grants provider, financial or production
    authority: an effectful winner is only READY_FOR_FORMATION.
    """

    def __init__(
        self,
        *,
        trace_spine: TraceSpine | None = None,
        idempotency_ledger: IdempotencyLedger | None = None,
    ) -> None:
        self.trace_spine = trace_spine or TraceSpine()
        self.idempotency_ledger = idempotency_ledger or IdempotencyLedger()

    @staticmethod
    def _blocking_reasons(candidate: RouteCandidate, leases: Mapping[str, CurrentStateLease], now: str) -> list[str]:
        reasons: list[str] = []
        for verdict in candidate.guardrails:
            if not verdict.allowed:
                suffix = f":{verdict.reason}" if verdict.reason else ""
                reasons.append(f"GUARDRAIL_{verdict.stage}_{verdict.name}{suffix}")
        for lease_id in candidate.required_lease_ids:
            lease = leases.get(lease_id)
            if lease is None:
                reasons.append(f"LEASE_MISSING:{lease_id}")
                continue
            try:
                lease.require_fresh(now=now, expected_authority=candidate.expected_authority or None)
            except CurrentStateLeaseError as exc:
                reasons.append(f"LEASE_INVALID:{lease_id}:{exc}")
        if candidate.effectful:
            if candidate.idempotency is None:
                reasons.append("IDEMPOTENCY_ENVELOPE_REQUIRED")
            else:
                try:
                    candidate.idempotency.validate(now=now)
                except ValueError as exc:
                    reasons.append(f"IDEMPOTENCY_INVALID:{exc}")
            if candidate.compensation is None:
                reasons.append("COMPENSATION_REQUIRED_BEFORE_EFFECT")
            else:
                try:
                    candidate.compensation.validate()
                except ValueError as exc:
                    reasons.append(str(exc))
                if candidate.idempotency and candidate.compensation.operation_id != candidate.idempotency.operation_id:
                    reasons.append("COMPENSATION_OPERATION_MISMATCH")
        return reasons

    def _append_trace(
        self,
        *,
        trace_id: str,
        mission_id: str,
        span_id: str,
        stage: str,
        state: str,
        now: str,
        parent_span_id: str = "",
        route: str = "",
        proof_refs: tuple[str, ...] = (),
    ) -> str:
        receipt = self.trace_spine.append(
            TraceEvent(
                trace_id=trace_id,
                span_id=span_id,
                mission_id=mission_id,
                stage=stage,
                state=state,
                occurred_at=now,
                parent_span_id=parent_span_id,
                route=route,
                proof_refs=proof_refs,
                sensitive_payload_present=False,
            )
        )
        return receipt.trace_digest

    def evaluate(
        self,
        *,
        mission_id: str,
        trace_id: str,
        now: str,
        candidates: Sequence[RouteCandidate],
        leases: Mapping[str, CurrentStateLease] | None = None,
    ) -> CourtReceipt:
        if not mission_id or not trace_id:
            raise ValueError("COURT_IDENTITY_REQUIRED")
        if not candidates:
            raise ValueError("COURT_CANDIDATE_REQUIRED")
        route_ids = [candidate.route_id for candidate in candidates]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("COURT_ROUTE_IDS_MUST_BE_UNIQUE")
        for candidate in candidates:
            candidate.validate()

        root_span = f"{trace_id}:court-input"
        trace_digest = self._append_trace(
            trace_id=trace_id,
            mission_id=mission_id,
            span_id=root_span,
            stage="COURT_INPUT",
            state="ADMITTED",
            now=now,
        )
        leases = leases or {}
        ranked: list[tuple[float, RouteCandidate]] = []
        held: dict[str, tuple[str, ...]] = {}
        for candidate in candidates:
            reasons = self._blocking_reasons(candidate, leases, now)
            if reasons:
                held[candidate.route_id] = tuple(reasons)
            else:
                ranked.append((candidate.score(), candidate))

        ranked.sort(key=lambda item: (-item[0], item[1].route_id))
        decision_reasons: list[str] = []
        selected: RouteCandidate | None = None
        selected_score: float | None = None
        while ranked:
            selected_score, selected = ranked[0]
            if not selected.effectful:
                break
            assert selected.idempotency is not None
            idempotency = self.idempotency_ledger.admit(selected.idempotency, now=now)
            if idempotency.execute:
                break
            held[selected.route_id] = (f"IDEMPOTENCY_{idempotency.state}",)
            decision_reasons.append(idempotency.reason)
            ranked.pop(0)
            selected = None
            selected_score = None

        if selected is None:
            state = "HOLD"
            selected_route_id = ""
            selected_score = None
            decision_reasons.append("NO_PROOF_ELIGIBLE_ROUTE")
        else:
            selected_route_id = selected.route_id
            state = "READY_FOR_FORMATION" if selected.effectful else "SELECTED_NO_EFFECT"

        score_by_id = {candidate.route_id: candidate.score() for candidate in candidates}
        counterfactuals = tuple(
            Counterfactual(
                route_id=candidate.route_id,
                score=score_by_id[candidate.route_id],
                delta_from_selected=(
                    round(selected_score - score_by_id[candidate.route_id], 9)
                    if selected_score is not None
                    else None
                ),
                state=("SELECTED" if candidate.route_id == selected_route_id else "HELD" if candidate.route_id in held else "NOT_SELECTED"),
                reasons=held.get(candidate.route_id, ()),
            )
            for candidate in sorted(candidates, key=lambda item: item.route_id)
        )
        proof_refs = selected.proof_refs if selected else ()
        trace_digest = self._append_trace(
            trace_id=trace_id,
            mission_id=mission_id,
            span_id=f"{trace_id}:court-decision",
            stage="COURT_DECISION",
            state=state,
            now=now,
            parent_span_id=root_span,
            route=selected_route_id,
            proof_refs=proof_refs,
        )
        payload = {
            "state": state,
            "mission_id": mission_id,
            "selected_route_id": selected_route_id,
            "selected_score": selected_score,
            "effect_authorized": False,
            "counterfactuals": [asdict(value) for value in counterfactuals],
            "trace_digest": trace_digest,
            "reasons": decision_reasons,
        }
        return CourtReceipt(
            state=state,
            mission_id=mission_id,
            selected_route_id=selected_route_id,
            selected_score=selected_score,
            effect_authorized=False,
            counterfactuals=counterfactuals,
            trace_digest=trace_digest,
            receipt_sha256=_digest(payload),
            reasons=tuple(decision_reasons),
        )

    @staticmethod
    def classify_failure(failure_class: str) -> FailurePolicy:
        normalized = failure_class.upper()
        if normalized not in _FAILURE_CLASSES:
            raise ValueError("FAILURE_CLASS_UNSUPPORTED")
        if normalized == "TRANSIENT":
            return FailurePolicy(normalized, True, 3, (1, 4), False)
        if normalized == "INTERMITTENT":
            return FailurePolicy(normalized, True, 2, (5,), False)
        if normalized == "CONTRADICTION":
            return FailurePolicy(normalized, False, 0, (), True)
        return FailurePolicy(normalized, False, 0, (), False)

    @classmethod
    def evaluate_outcome(
        cls,
        *,
        route_id: str,
        expected_fruit: float,
        observed_fruit: float,
        failure_class: str,
        proof_refs: tuple[str, ...] = (),
    ) -> LearningCandidate:
        if not 0.0 <= expected_fruit <= 1.0 or not 0.0 <= observed_fruit <= 1.0:
            raise ValueError("OUTCOME_FRUIT_OUT_OF_RANGE")
        delta = round(observed_fruit - expected_fruit, 9)
        return LearningCandidate(
            route_id=route_id,
            state="LEARNING_CANDIDATE_REVIEW_REQUIRED",
            claim_fruit_delta=delta,
            failure_policy=cls.classify_failure(failure_class),
            auto_promoted=False,
            proof_refs=proof_refs,
        )

