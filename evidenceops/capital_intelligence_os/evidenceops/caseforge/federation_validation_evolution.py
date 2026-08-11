from __future__ import annotations

from typing import Mapping

from .federation_validation import FederationEvaluationContract


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _first_metric(contract: FederationEvaluationContract, names: tuple[str, ...], fallback: float) -> float:
    for name in names:
        if name in contract.metrics:
            return _clamp(contract.metrics[name])
    return _clamp(fallback)


def to_evolution_governor_metrics(
    contract: FederationEvaluationContract,
    *,
    reuse: float,
    owner_burden_reduction: float,
    cost_efficiency: float,
) -> Mapping[str, float]:
    """Map a validated Federation evaluation into the existing EvolutionGovernor metric contract.

    The three economic/operational values are explicit inputs because CASEFORGE must not
    manufacture cost, reuse or user-burden improvements from technical quality scores.
    """
    contract.validate()
    score = contract.score
    security_penalty = any(
        token in fingerprint
        for fingerprint in contract.failure_fingerprints
        for token in ("AUTHORITY", "CORRUPTION", "CROSS_CONTAMINATION", "LEAK")
    )
    metrics = {
        "factual_accuracy": _first_metric(
            contract,
            ("canonical_state_accuracy", "semantic_correctness", "state_integrity"),
            score,
        ),
        "proof_completeness": _first_metric(
            contract,
            ("provenance_fidelity", "provider_readback", "independent_readback"),
            score,
        ),
        "security": 0.0 if security_penalty else 1.0,
        "reversibility": _first_metric(
            contract,
            ("repair_reversibility", "stale_memory_rejection"),
            score,
        ),
        "completion_rate": _first_metric(
            contract,
            ("context_recovery", "recovery_completion", "state_validity"),
            score,
        ),
        "contradiction_detection": _first_metric(
            contract,
            ("contradiction_detection", "failure_classification"),
            score,
        ),
        "recovery": _first_metric(
            contract,
            ("recovery_completion", "unaffected_lane_continuity"),
            score,
        ),
        "reuse": _clamp(reuse),
        "owner_burden_reduction": _clamp(owner_burden_reduction),
        "cost_efficiency": _clamp(cost_efficiency),
    }
    return metrics


__all__ = ["to_evolution_governor_metrics"]
