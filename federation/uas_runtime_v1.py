from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from math import sqrt
from typing import Iterable, Mapping, Sequence

from federation.mission_ir import MissionIR


_SCHEMA = "UAS-RUNTIME-EVALUATION-V1"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return max(0.0, min(1.0, numerator / denominator))


def _ordered_subsequence(expected: Sequence[str], actual: Sequence[str]) -> bool:
    if not expected:
        return True
    cursor = 0
    for item in actual:
        if item == expected[cursor]:
            cursor += 1
            if cursor == len(expected):
                return True
    return False


def wilson_lower_bound(successes: int, trials: int, z: float = 1.96) -> float:
    """Conservative lower confidence bound for bounded promotion decisions."""
    if trials <= 0:
        return 0.0
    successes = max(0, min(int(successes), int(trials)))
    p = successes / trials
    z2 = z * z
    numerator = (
        p
        + z2 / (2 * trials)
        - z * sqrt((p * (1.0 - p) / trials) + z2 / (4 * trials * trials))
    )
    denominator = 1.0 + z2 / trials
    return max(0.0, min(1.0, numerator / denominator))


@dataclass(frozen=True, slots=True)
class EvaluationEvidence:
    outcome_ok: bool
    proof_axes: tuple[str, ...] = ()
    expected_tool_sequence: tuple[str, ...] = ()
    actual_tool_sequence: tuple[str, ...] = ()
    critical_failures: tuple[str, ...] = ()
    security_violations: tuple[str, ...] = ()
    regression_failures: tuple[str, ...] = ()
    owner_interventions: int = 0
    cost_microunits: int | None = None
    latency_ms: int | None = None
    value_observations: Mapping[str, float] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UASEvaluation:
    mission_id: str
    state: str
    score: float
    threshold: float
    dimensions: Mapping[str, float]
    hard_blockers: tuple[str, ...]
    missing_proof_axes: tuple[str, ...]
    evaluation_sha256: str


class UASRuntimeEvaluator:
    """Executable minimum UAS court for runtime promotion and mission closure.

    This evaluator does not grant authority or certify a provider by itself. It
    converts runtime evidence into a repeatable, machine-readable decision and
    fails closed on proof, security, regression, cost or critical-failure gaps.
    """

    version = "1.0.0"

    def __init__(self, *, threshold: float = 0.90) -> None:
        if not 0.0 < float(threshold) <= 1.0:
            raise ValueError("UAS_THRESHOLD_INVALID")
        self.threshold = float(threshold)

    def evaluate(self, mission: MissionIR, evidence: EvaluationEvidence) -> UASEvaluation:
        mission = mission.normalized()
        mission.validate()

        required_proof = set(mission.proof_requirements)
        observed_proof = {str(item).strip() for item in evidence.proof_axes if str(item).strip()}
        missing_proof = tuple(sorted(required_proof - observed_proof))

        trajectory_ok = _ordered_subsequence(
            tuple(evidence.expected_tool_sequence),
            tuple(evidence.actual_tool_sequence),
        )

        cost_evidence_required = mission.max_cost_microunits is not None
        latency_evidence_required = mission.latency_target_ms is not None
        cost_evidence_present = evidence.cost_microunits is not None
        latency_evidence_present = evidence.latency_ms is not None

        cost_ok = (
            not cost_evidence_required
            or (
                cost_evidence_present
                and int(evidence.cost_microunits) <= int(mission.max_cost_microunits)
            )
        )
        latency_ok = (
            not latency_evidence_required
            or (
                latency_evidence_present
                and int(evidence.latency_ms) <= int(mission.latency_target_ms)
            )
        )

        owner_burden_score = 1.0 / (1.0 + max(0, int(evidence.owner_interventions)))
        proof_score = _ratio(len(required_proof) - len(missing_proof), len(required_proof))

        dimensions = {
            "outcome": 1.0 if evidence.outcome_ok else 0.0,
            "proof": proof_score,
            "trajectory": 1.0 if trajectory_ok else 0.0,
            "security": 1.0 if not evidence.security_violations else 0.0,
            "regression": 1.0 if not evidence.regression_failures else 0.0,
            "cost": 1.0 if cost_ok else 0.0,
            "latency": 1.0 if latency_ok else 0.0,
            "owner_burden": owner_burden_score,
        }

        weights = {
            "outcome": 0.22,
            "proof": 0.20,
            "trajectory": 0.10,
            "security": 0.16,
            "regression": 0.12,
            "cost": 0.07,
            "latency": 0.05,
            "owner_burden": 0.08,
        }
        score = round(sum(dimensions[key] * weights[key] for key in weights), 6)

        blockers: list[str] = []
        if not evidence.outcome_ok:
            blockers.append("OUTCOME_NOT_PROVEN")
        if missing_proof:
            blockers.append("REQUIRED_PROOF_MISSING")
        if evidence.critical_failures:
            blockers.append("CRITICAL_FAILURE_PRESENT")
        if evidence.security_violations:
            blockers.append("SECURITY_VIOLATION_PRESENT")
        if evidence.regression_failures:
            blockers.append("REGRESSION_FAILURE_PRESENT")
        if cost_evidence_required and not cost_evidence_present:
            blockers.append("COST_EVIDENCE_MISSING")
        elif not cost_ok:
            blockers.append("COST_CEILING_EXCEEDED")
        if latency_evidence_required and not latency_evidence_present:
            blockers.append("LATENCY_EVIDENCE_MISSING")
        elif not latency_ok:
            blockers.append("LATENCY_TARGET_EXCEEDED")
        if not trajectory_ok:
            blockers.append("EXPECTED_TOOL_TRAJECTORY_NOT_OBSERVED")

        state = "PASS" if not blockers and score >= self.threshold else "HOLD"
        body = {
            "schema": _SCHEMA,
            "version": self.version,
            "mission_id": mission.mission_id,
            "state": state,
            "score": score,
            "threshold": self.threshold,
            "dimensions": dimensions,
            "hard_blockers": sorted(blockers),
            "missing_proof_axes": list(missing_proof),
            "evidence": asdict(evidence),
            "truth_boundary": {
                "authority_granted": False,
                "provider_certified": False,
                "market_superiority_proven": False,
                "evaluation_is_scope_bound": True,
            },
        }
        return UASEvaluation(
            mission_id=mission.mission_id,
            state=state,
            score=score,
            threshold=self.threshold,
            dimensions=dimensions,
            hard_blockers=tuple(sorted(blockers)),
            missing_proof_axes=missing_proof,
            evaluation_sha256=_digest(body),
        )

    def promotion_decision(
        self,
        *,
        successes: int,
        trials: int,
        minimum_lower_bound: float,
        critical_failures: Iterable[str] = (),
        proof_violations: Iterable[str] = (),
        owner_burden_regression: bool = False,
        cost_regression: bool = False,
        latency_regression: bool = False,
    ) -> dict[str, object]:
        lower = wilson_lower_bound(successes, trials)
        blockers: list[str] = []
        if lower < float(minimum_lower_bound):
            blockers.append("CONFIDENCE_BOUND_BELOW_THRESHOLD")
        if tuple(critical_failures):
            blockers.append("CRITICAL_FAILURE_PRESENT")
        if tuple(proof_violations):
            blockers.append("PROOF_VIOLATION_PRESENT")
        if owner_burden_regression:
            blockers.append("OWNER_BURDEN_REGRESSION")
        if cost_regression:
            blockers.append("COST_REGRESSION")
        if latency_regression:
            blockers.append("LATENCY_REGRESSION")
        body = {
            "schema": "UAS-PROMOTION-DECISION-V1",
            "successes": int(successes),
            "trials": int(trials),
            "wilson_lower_bound": round(lower, 6),
            "minimum_lower_bound": float(minimum_lower_bound),
            "state": "PROMOTE" if not blockers else "HOLD",
            "blockers": sorted(blockers),
        }
        body["receipt_sha256"] = _digest(body)
        return body
