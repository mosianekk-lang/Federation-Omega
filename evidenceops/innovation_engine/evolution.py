from __future__ import annotations

from typing import Mapping

from .evolution_common import AUTHORITY_CEILING, EvolutionDecision, clamp_metric, digest
from .evolution_storage import AlgorithmLedgerStorageMixin
from .evolution_candidates import AlgorithmLedgerCandidateMixin


class AlgorithmLedger(AlgorithmLedgerStorageMixin, AlgorithmLedgerCandidateMixin):
    """Durable hash-linked algorithm configuration and evaluation ledger."""


class EvolutionGovernor:
    algorithm_id = "ALG-EOPS-EVG-001"
    name = "EvidenceOps Evolution Governor"

    default_weights: Mapping[str, float] = {
        "factual_accuracy": 0.18,
        "proof_completeness": 0.18,
        "security": 0.14,
        "reversibility": 0.12,
        "completion_rate": 0.10,
        "contradiction_detection": 0.08,
        "recovery": 0.08,
        "reuse": 0.05,
        "owner_burden_reduction": 0.05,
        "cost_efficiency": 0.02,
    }
    hard_metrics = ("factual_accuracy", "proof_completeness", "security", "reversibility")

    def __init__(self, ledger: AlgorithmLedger, *, minimum_gain: float = 0.02, weights: Mapping[str, float] | None = None) -> None:
        self.ledger = ledger
        self.minimum_gain = float(minimum_gain)
        self.weights = dict(weights or self.default_weights)
        if not self.weights or sum(self.weights.values()) <= 0:
            raise ValueError("evolution weights must have a positive total")

    def _score(self, metrics: Mapping[str, float]) -> float:
        clean = {key: clamp_metric(value) for key, value in metrics.items()}
        total_weight = sum(self.weights.values())
        return sum(self.weights[key] * clean.get(key, 0.0) for key in self.weights) / total_weight

    def evaluate_and_maybe_promote(self, *, candidate_id: str, candidate_metrics: Mapping[str, float], promote: bool = True) -> EvolutionDecision:
        candidate = self.ledger.candidate(candidate_id)
        active = self.ledger.active_version(candidate["algorithm_id"])
        if active["version"] != candidate["baseline_version"]:
            raise ValueError("candidate baseline is stale; rebase or reject before evaluation")
        baseline_metrics = {key: clamp_metric(value) for key, value in active["metrics"].items()}
        clean_candidate = {key: clamp_metric(value) for key, value in candidate_metrics.items()}
        missing_metrics = sorted(set(self.weights) - set(clean_candidate))
        reasons: list[str] = []
        if missing_metrics:
            reasons.append("MISSING_EVALUATION_METRICS:" + ",".join(missing_metrics))
        hard_regressions = tuple(metric for metric in self.hard_metrics if clean_candidate.get(metric, 0.0) < baseline_metrics.get(metric, 0.0))
        baseline_score = self._score(baseline_metrics)
        candidate_score = self._score(clean_candidate)
        gain = candidate_score - baseline_score
        if hard_regressions:
            reasons.append("HARD_REGRESSION:" + ",".join(hard_regressions))
        if gain < self.minimum_gain:
            reasons.append(f"GAIN_BELOW_THRESHOLD:{gain:.6f}<{self.minimum_gain:.6f}")
        decision = "ACCEPT" if not reasons else "REJECT"
        self.ledger.record_evaluation(candidate_id=candidate_id, baseline_metrics=baseline_metrics, candidate_metrics=clean_candidate, decision=decision, reasons=reasons, hard_regressions=hard_regressions, baseline_score=baseline_score, candidate_score=candidate_score, gain=gain)
        promoted = False
        if decision == "ACCEPT" and promote:
            self.ledger.promote(candidate_id, clean_candidate)
            promoted = True
        body = {
            "algorithm_id": candidate["algorithm_id"], "candidate_id": candidate_id,
            "decision": decision, "baseline_version": candidate["baseline_version"],
            "candidate_version": candidate["candidate_version"],
            "baseline_score": round(baseline_score, 8), "candidate_score": round(candidate_score, 8),
            "gain": round(gain, 8), "hard_regressions": list(hard_regressions),
            "reasons": reasons, "promoted": promoted,
            "rollback_version": candidate["rollback_version"],
            "authority_ceiling": AUTHORITY_CEILING, "external_effect": False,
        }
        return EvolutionDecision(
            algorithm_id=candidate["algorithm_id"], candidate_id=candidate_id,
            decision=decision, baseline_version=candidate["baseline_version"],
            candidate_version=candidate["candidate_version"],
            baseline_score=round(baseline_score, 8), candidate_score=round(candidate_score, 8),
            gain=round(gain, 8), hard_regressions=hard_regressions,
            reasons=tuple(reasons), promoted=promoted,
            rollback_version=candidate["rollback_version"], receipt_sha256=digest(body),
        )


__all__ = ["AlgorithmLedger", "EvolutionDecision", "EvolutionGovernor"]
