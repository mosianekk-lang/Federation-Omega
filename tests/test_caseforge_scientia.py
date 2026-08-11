from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidenceops.caseforge import (
    Capability,
    EpistemicState,
    Hypothesis,
    ScientiaKernel,
    ScientificObservation,
    SurfaceState,
    build_innovation_frontier,
    evaluate_benchmark,
    evaluate_candidate_promotion,
    select_minimum_sufficient_capabilities,
    select_next_case,
    to_evolution_metrics,
)
from evidenceops.innovation_engine.evolution import EvolutionGovernor


ROOT = Path(__file__).resolve().parents[1]
BLIND = ROOT / "evidenceops" / "caseforge" / "benchmarks" / "CF-UTILITY-ZA-001.blind.json"


def full_scores(value: float = 0.9) -> dict[str, float]:
    return {
        "legal_route": value,
        "evidence_integrity": value,
        "authority_quality": value,
        "fact_chronology": value,
        "contradiction_reasoning": value,
        "adversarial_resilience": value,
        "remedy_procedure": value,
        "uncertainty_calibration": value,
        "traceability": value,
    }


def test_scientia_requires_competing_falsifiable_hypotheses() -> None:
    kernel = ScientiaKernel()
    observations = [
        ScientificObservation("O1", "supply remains off", EpistemicState.USER_SUPPLIED)
    ]
    with pytest.raises(ValueError, match="competing hypotheses"):
        kernel.validate_case_design(
            observations=observations,
            hypotheses=[Hypothesis("H1", "payment enforcement", ("written condition",), ("technical-only reason",))],
        )

    result = kernel.validate_case_design(
        observations=observations,
        hypotheses=[
            Hypothesis("H1", "payment enforcement", ("written condition",), ("technical-only reason",)),
            Hypothesis("H2", "technical constraint", ("engineering report",), ("safe energisation approved",)),
        ],
    )
    assert result["status"] == "SCIENTIFIC_DESIGN_VALID"
    assert result["external_effect"] is False


def test_blind_pack_has_no_control_answer_leak() -> None:
    kernel = ScientiaKernel()
    blind = json.loads(BLIND.read_text(encoding="utf-8"))
    assert len(kernel.assert_blind_pack(blind)) == 64
    contaminated = {"case": blind, "answer_key": {"winner": "party-a"}}
    with pytest.raises(ValueError, match="leakage"):
        kernel.assert_blind_pack(contaminated)


def test_benchmark_fatal_failure_overrides_high_score() -> None:
    evaluation = evaluate_benchmark(full_scores(1.0), fatal_events=["FABRICATED_AUTHORITY"])
    assert evaluation.score == 1.0
    assert evaluation.decision == "FAIL_FATAL"
    assert evaluation.fatal_failures == ("FABRICATED_AUTHORITY",)


def test_candidate_promotion_requires_replication_red_team_and_rollback() -> None:
    rejected = evaluate_candidate_promotion(
        original_failure_repaired=True,
        fatal_regressions=(),
        supported_case_count=3,
        mutation_passed=True,
        red_team_passed=True,
        current_law_verified=True,
        rollback_available=False,
        independently_replicated=True,
        global_regression_passed=True,
    )
    assert rejected.decision == "REJECT"
    assert "ROLLBACK_NOT_AVAILABLE" in rejected.reasons

    accepted = evaluate_candidate_promotion(
        original_failure_repaired=True,
        fatal_regressions=(),
        supported_case_count=3,
        mutation_passed=True,
        red_team_passed=True,
        current_law_verified=True,
        rollback_available=True,
        independently_replicated=True,
        global_regression_passed=True,
    )
    assert accepted.decision == "ACCEPT"
    assert accepted.promotion_state == "SHADOW_VALIDATED"


def test_weakness_driven_selector_prefers_high_information_case() -> None:
    cases = [
        {
            "case_id": "STRONG-DOMAIN",
            "weakness_score": 0.1,
            "legal_materiality": 0.8,
            "failure_recurrence": 0.1,
            "domain_undercoverage": 0.1,
            "authority_change_risk": 0.1,
            "real_world_frequency": 0.8,
        },
        {
            "case_id": "WEAK-DOMAIN",
            "weakness_score": 1.0,
            "legal_materiality": 0.8,
            "failure_recurrence": 0.8,
            "domain_undercoverage": 1.0,
            "authority_change_risk": 0.5,
            "real_world_frequency": 0.7,
        },
    ]
    assert select_next_case(cases)["case_id"] == "WEAK-DOMAIN"


def test_federation_broker_uses_verified_capabilities_and_opens_ao_cra_gap() -> None:
    capabilities = [
        Capability(
            "JFRIE",
            frozenset({"evidence_integrity", "release_gate"}),
            SurfaceState.RUNTIME_ADAPTER_AVAILABLE,
        ),
        Capability(
            "LEX-OMEGA",
            frozenset({"legal_authority", "red_team"}),
            SurfaceState.RUNTIME_ADAPTER_AVAILABLE,
        ),
        Capability(
            "AI-STUDIO",
            frozenset({"model_diversity"}),
            SurfaceState.SUBSCRIPTION_KNOWN,
        ),
    ]
    plan = select_minimum_sufficient_capabilities(
        {"evidence_integrity", "legal_authority", "model_diversity"}, capabilities
    )
    assert set(plan.selected) == {"JFRIE", "LEX-OMEGA"}
    assert plan.unresolved_roles == ("model_diversity",)
    assert plan.ao_cra_builds == ("AO-CRA:model_diversity",)


def test_innovation_frontier_is_mandatory_and_complete() -> None:
    frontier = build_innovation_frontier(
        strongest_verified_reuse="reuse existing EvolutionGovernor",
        strongest_incremental_improvement="add scientific benchmark adapter",
        strongest_materially_different_solution="independent blind replication",
        highest_information_reversible_experiment="run utility benchmark in shadow mode",
    )
    assert frontier["verified_reuse"].startswith("reuse")
    with pytest.raises(ValueError, match="incomplete"):
        build_innovation_frontier(
            strongest_verified_reuse="reuse",
            strongest_incremental_improvement="",
            strongest_materially_different_solution="different",
            highest_information_reversible_experiment="experiment",
        )


def test_caseforge_metrics_bind_to_existing_evolution_governor_contract() -> None:
    scores = full_scores(0.9)
    evaluation = evaluate_benchmark(scores)
    metrics = to_evolution_metrics(evaluation, scores)
    assert set(metrics) == set(EvolutionGovernor.default_weights)
    assert all(0.0 <= value <= 1.0 for value in metrics.values())
