from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .benchmark_engine import Dimension, EVIDENCE_FACTORS, leadership_state, weighted_score


PROFILE_KEY = "CFBE-FORMATION-RECONCILIATION-V2-001"
FRONTIER_THRESHOLD = 85.0


@dataclass(frozen=True)
class DimensionProof:
    dimension_id: str
    evidence_state: str
    freshness_factor: float = 1.0
    independent_readback: bool = False


@dataclass(frozen=True)
class ReconciliationV2Report:
    profile_key: str
    raw_architecture: float
    proof_adjusted: float
    leadership: str
    provider_live: bool
    independently_replicated: bool
    model_checked: bool
    policy_runtime_verified: bool
    trace_backend_verified: bool
    signed_attestation_verified: bool
    repeated_operational_cycles: int
    gap_dimensions: tuple[str, ...]


_BASE_DIMENSIONS = (
    ("desired_state_reconciliation", "Continuous desired-vs-observed reconciliation", 13.0, 5.0),
    ("stale_state_fencing", "Exact provider snapshot and candidate-head fencing", 12.0, 5.0),
    ("durable_replay", "Durable hash-chained replay/checkpoint semantics", 11.0, 4.5),
    ("adaptive_topology", "Adaptive deterministic/single/parallel/hybrid topology", 10.0, 4.5),
    ("proof_directed_parallelism", "Proof-directed scheduling and shared-state serialization", 10.0, 4.7),
    ("formal_safety", "Formal constitutional state-machine model", 9.0, 4.0),
    ("policy_as_code", "Declarative default-deny authority and admission policy", 8.0, 4.2),
    ("causal_observability", "Cross-surface causal trace propagation", 8.0, 4.0),
    ("attested_provenance", "in-toto/SLSA-shaped attestable provenance", 7.0, 4.0),
    ("evaluator_evolution", "Evaluator-driven Pareto challenger evolution", 7.0, 4.6),
    ("owner_burden", "Automated failure preemption, replay and minimal-delta recovery", 5.0, 4.6),
)

_SPECIAL_PROOF_REQUIREMENTS = {
    "formal_safety": "model_checked",
    "policy_as_code": "policy_runtime_verified",
    "causal_observability": "trace_backend_verified",
    "attested_provenance": "signed_attestation_verified",
}


def _proof_map(proofs: Iterable[DimensionProof]) -> Mapping[str, DimensionProof]:
    mapped: dict[str, DimensionProof] = {}
    for proof in proofs:
        if proof.dimension_id in mapped:
            raise ValueError(f"duplicate dimension proof: {proof.dimension_id}")
        if proof.evidence_state not in EVIDENCE_FACTORS:
            raise ValueError(f"unknown evidence state: {proof.evidence_state}")
        if not 0.0 <= float(proof.freshness_factor) <= 1.0:
            raise ValueError("freshness_factor must be in [0,1]")
        mapped[proof.dimension_id] = proof
    return mapped


def compile_dimensions(
    proofs: Iterable[DimensionProof] = (),
    *,
    default_state: str = "CONTROL_PLANE_OR_SOURCE_ONLY",
    model_checked: bool = False,
    policy_runtime_verified: bool = False,
    trace_backend_verified: bool = False,
    signed_attestation_verified: bool = False,
    repeated_operational_cycles: int = 0,
) -> list[Dimension]:
    if default_state not in EVIDENCE_FACTORS:
        raise ValueError("unknown default evidence state")
    proof_by_dimension = _proof_map(proofs)
    flags = {
        "model_checked": bool(model_checked),
        "policy_runtime_verified": bool(policy_runtime_verified),
        "trace_backend_verified": bool(trace_backend_verified),
        "signed_attestation_verified": bool(signed_attestation_verified),
    }
    dimensions: list[Dimension] = []
    for dimension_id, name, weight, raw_score in _BASE_DIMENSIONS:
        proof = proof_by_dimension.get(dimension_id)
        evidence_state = proof.evidence_state if proof else default_state
        freshness = proof.freshness_factor if proof else 1.0
        requirement = _SPECIAL_PROOF_REQUIREMENTS.get(dimension_id)
        if requirement and not flags[requirement]:
            # A source artifact is not equivalent to model-check/runtime/signing proof.
            evidence_state = "PLANNED_OR_CLAIMED"
        if repeated_operational_cycles >= 3 and dimension_id in {
            "desired_state_reconciliation",
            "stale_state_fencing",
            "durable_replay",
            "adaptive_topology",
            "proof_directed_parallelism",
            "owner_burden",
        }:
            if EVIDENCE_FACTORS[evidence_state] < EVIDENCE_FACTORS["OPERATIONAL_SCOPED_REPEATED"]:
                evidence_state = "OPERATIONAL_SCOPED_REPEATED"
        dimensions.append(
            Dimension(
                dimension_id=dimension_id,
                name=name,
                weight=weight,
                raw_score=raw_score,
                evidence_factor=EVIDENCE_FACTORS[evidence_state],
                freshness_factor=freshness,
            )
        )
    return dimensions


def evaluate(
    proofs: Iterable[DimensionProof] = (),
    *,
    default_state: str = "CONTROL_PLANE_OR_SOURCE_ONLY",
    model_checked: bool = False,
    policy_runtime_verified: bool = False,
    trace_backend_verified: bool = False,
    signed_attestation_verified: bool = False,
    repeated_operational_cycles: int = 0,
    provider_live: bool = False,
    independently_replicated: bool = False,
    no_critical_regression: bool = True,
) -> ReconciliationV2Report:
    dimensions = compile_dimensions(
        proofs,
        default_state=default_state,
        model_checked=model_checked,
        policy_runtime_verified=policy_runtime_verified,
        trace_backend_verified=trace_backend_verified,
        signed_attestation_verified=signed_attestation_verified,
        repeated_operational_cycles=repeated_operational_cycles,
    )
    score = weighted_score(dimensions)
    leadership = leadership_state(
        score.proof_adjusted,
        FRONTIER_THRESHOLD,
        provider_live=provider_live,
        independently_replicated=independently_replicated,
        no_critical_regression=no_critical_regression,
        externally_distinguishable_advantage=False,
    )
    gap_dimensions = tuple(
        dimension.dimension_id
        for dimension in dimensions
        if dimension.effective_percent < FRONTIER_THRESHOLD
    )
    return ReconciliationV2Report(
        profile_key=PROFILE_KEY,
        raw_architecture=score.raw_architecture,
        proof_adjusted=score.proof_adjusted,
        leadership=leadership,
        provider_live=provider_live,
        independently_replicated=independently_replicated,
        model_checked=model_checked,
        policy_runtime_verified=policy_runtime_verified,
        trace_backend_verified=trace_backend_verified,
        signed_attestation_verified=signed_attestation_verified,
        repeated_operational_cycles=max(0, int(repeated_operational_cycles)),
        gap_dimensions=gap_dimensions,
    )


__all__ = [
    "DimensionProof",
    "FRONTIER_THRESHOLD",
    "PROFILE_KEY",
    "ReconciliationV2Report",
    "compile_dimensions",
    "evaluate",
]
