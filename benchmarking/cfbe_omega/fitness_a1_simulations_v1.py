from __future__ import annotations

"""Bounded A1 simulations for CFBE Federation Scientific Fitness Court.

These simulations produce deterministic internal evidence only. They do not invoke
providers, grant authority, deploy code, or prove owner value.
"""

from dataclasses import asdict, dataclass
from typing import Sequence

from benchmarking.cfbe_omega.scientific_capability_compiler_v2 import (
    CapabilityGrant,
    ExperimentCandidate,
    authorize_capability,
    canonical_hash,
    select_information_gain_experiment,
)

SCHEMA = "CFBE_FITNESS_A1_SIMULATIONS_V1"


@dataclass(frozen=True, slots=True)
class AuthorityCase:
    case_id: str
    required: CapabilityGrant
    safe: bool


@dataclass(frozen=True, slots=True)
class AuthoritySimulationReceipt:
    schema: str
    experiment_id: str
    case_count: int
    exact_model_true_positive: int
    exact_model_false_positive: int
    exact_model_precision: float
    broad_role_false_positive: int
    broad_role_precision: float
    provider_effect: bool
    receipt_sha256: str


def run_authority_precision_simulation() -> AuthoritySimulationReceipt:
    grants = (
        CapabilityGrant("read", "benchmark", "fitness-audit", ("read-only",)),
        CapabilityGrant("read", "kdv", "fitness-audit", ("read-only",)),
    )
    cases = (
        AuthorityCase("A1", CapabilityGrant("read", "benchmark", "fitness-audit", ("read-only",)), True),
        AuthorityCase("A2", CapabilityGrant("read", "kdv", "fitness-audit", ("read-only",)), True),
        AuthorityCase("A3", CapabilityGrant("write", "benchmark", "fitness-audit", ()), False),
        AuthorityCase("A4", CapabilityGrant("read", "provider-iam", "fitness-audit", ("read-only",)), False),
        AuthorityCase("A5", CapabilityGrant("write", "provider-iam", "fitness-audit", ()), False),
        AuthorityCase("A6", CapabilityGrant("read", "benchmark", "provider-hardening", ("read-only",)), False),
    )

    exact_allowed = [authorize_capability(case.required, grants).allowed for case in cases]
    exact_tp = sum(allowed and case.safe for allowed, case in zip(exact_allowed, cases))
    exact_fp = sum(allowed and not case.safe for allowed, case in zip(exact_allowed, cases))
    exact_precision = exact_tp / max(exact_tp + exact_fp, 1)

    # Deliberately weak baseline: a broad "fitness operator" role permits any read
    # and benchmark writes. This is a synthetic comparator, not a real provider role.
    broad_allowed = [case.required.operation == "read" or case.required.resource == "benchmark" for case in cases]
    broad_tp = sum(allowed and case.safe for allowed, case in zip(broad_allowed, cases))
    broad_fp = sum(allowed and not case.safe for allowed, case in zip(broad_allowed, cases))
    broad_precision = broad_tp / max(broad_tp + broad_fp, 1)

    payload = {
        "schema": SCHEMA,
        "experiment_id": "EXP-CFBE-FIT-009",
        "case_count": len(cases),
        "exact_model_true_positive": exact_tp,
        "exact_model_false_positive": exact_fp,
        "exact_model_precision": round(exact_precision, 6),
        "broad_role_false_positive": broad_fp,
        "broad_role_precision": round(broad_precision, 6),
        "provider_effect": False,
    }
    return AuthoritySimulationReceipt(**payload, receipt_sha256=canonical_hash(payload))


@dataclass(frozen=True, slots=True)
class SchedulingSimulationReceipt:
    schema: str
    experiment_id: str
    fifo_order: tuple[str, ...]
    information_gain_order: tuple[str, ...]
    fifo_cost_to_threshold: float
    information_gain_cost_to_threshold: float
    threshold_information_gain: float
    information_gain_route_better: bool
    provider_effect: bool
    receipt_sha256: str


def _ordered_by_information_gain(candidates: Sequence[ExperimentCandidate]) -> tuple[ExperimentCandidate, ...]:
    remaining = list(candidates)
    ordered: list[ExperimentCandidate] = []
    while remaining:
        selected = select_information_gain_experiment(tuple(remaining))
        ordered.append(selected)
        remaining = [item for item in remaining if item.experiment_id != selected.experiment_id]
    return tuple(ordered)


def _cost_to_gain(order: Sequence[ExperimentCandidate], threshold: float) -> float:
    gain = 0.0
    cost = 0.0
    for item in order:
        gain += item.information_gain
        cost += item.cost
        if gain >= threshold:
            return round(cost, 6)
    return round(cost, 6)


def run_information_gain_scheduling_simulation() -> SchedulingSimulationReceipt:
    candidates = (
        ExperimentCandidate("E1", 0.90, 0.65, 1.20, 0.05, 0.80),
        ExperimentCandidate("E2", 0.80, 0.25, 0.70, 0.03, 0.95),
        ExperimentCandidate("E3", 0.75, 0.45, 0.60, 0.02, 0.75),
        ExperimentCandidate("E4", 0.85, 0.20, 1.00, 0.04, 1.00),
    )
    ranked = _ordered_by_information_gain(candidates)
    threshold = 0.90
    fifo_cost = _cost_to_gain(candidates, threshold)
    ranked_cost = _cost_to_gain(ranked, threshold)
    payload = {
        "schema": SCHEMA,
        "experiment_id": "EXP-CFBE-FIT-010",
        "fifo_order": tuple(item.experiment_id for item in candidates),
        "information_gain_order": tuple(item.experiment_id for item in ranked),
        "fifo_cost_to_threshold": fifo_cost,
        "information_gain_cost_to_threshold": ranked_cost,
        "threshold_information_gain": threshold,
        "information_gain_route_better": ranked_cost < fifo_cost,
        "provider_effect": False,
    }
    return SchedulingSimulationReceipt(**payload, receipt_sha256=canonical_hash(payload))


def simulation_summary() -> dict[str, object]:
    return {
        "authority_precision": asdict(run_authority_precision_simulation()),
        "information_gain_scheduling": asdict(run_information_gain_scheduling_simulation()),
        "truth_boundary": {
            "simulation_is_not_owner_value_proof": True,
            "simulation_is_not_provider_runtime_proof": True,
            "provider_effect": False,
            "stable_promotion_authorized": False,
        },
    }


__all__ = [
    "AuthoritySimulationReceipt",
    "SchedulingSimulationReceipt",
    "run_authority_precision_simulation",
    "run_information_gain_scheduling_simulation",
    "simulation_summary",
]
