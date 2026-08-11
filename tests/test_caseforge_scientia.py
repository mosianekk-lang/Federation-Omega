from __future__ import annotations

import json
import unittest
from pathlib import Path

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


class CaseForgeScientiaTests(unittest.TestCase):
    def test_scientia_requires_competing_falsifiable_hypotheses(self) -> None:
        kernel = ScientiaKernel()
        observations = [
            ScientificObservation("O1", "supply remains off", EpistemicState.USER_SUPPLIED)
        ]
        with self.assertRaisesRegex(ValueError, "competing hypotheses"):
            kernel.validate_case_design(
                observations=observations,
                hypotheses=[
                    Hypothesis(
                        "H1",
                        "payment enforcement",
                        ("written condition",),
                        ("technical-only reason",),
                    )
                ],
            )

        result = kernel.validate_case_design(
            observations=observations,
            hypotheses=[
                Hypothesis(
                    "H1",
                    "payment enforcement",
                    ("written condition",),
                    ("technical-only reason",),
                ),
                Hypothesis(
                    "H2",
                    "technical constraint",
                    ("engineering report",),
                    ("safe energisation approved",),
                ),
            ],
        )
        self.assertEqual("SCIENTIFIC_DESIGN_VALID", result["status"])
        self.assertFalse(result["external_effect"])

    def test_blind_pack_has_no_control_answer_leak(self) -> None:
        kernel = ScientiaKernel()
        blind = json.loads(BLIND.read_text(encoding="utf-8"))
        self.assertEqual(64, len(kernel.assert_blind_pack(blind)))
        contaminated = {"case": blind, "answer_key": {"winner": "party-a"}}
        with self.assertRaisesRegex(ValueError, "leakage"):
            kernel.assert_blind_pack(contaminated)

    def test_benchmark_fatal_failure_overrides_high_score(self) -> None:
        evaluation = evaluate_benchmark(
            full_scores(1.0), fatal_events=["FABRICATED_AUTHORITY"]
        )
        self.assertEqual(1.0, evaluation.score)
        self.assertEqual("FAIL_FATAL", evaluation.decision)
        self.assertEqual(("FABRICATED_AUTHORITY",), evaluation.fatal_failures)

    def test_candidate_promotion_requires_replication_red_team_and_rollback(self) -> None:
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
        self.assertEqual("REJECT", rejected.decision)
        self.assertIn("ROLLBACK_NOT_AVAILABLE", rejected.reasons)

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
        self.assertEqual("ACCEPT", accepted.decision)
        self.assertEqual("SHADOW_VALIDATED", accepted.promotion_state)

    def test_weakness_driven_selector_prefers_high_information_case(self) -> None:
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
        self.assertEqual("WEAK-DOMAIN", select_next_case(cases)["case_id"])

    def test_federation_broker_uses_verified_capabilities_and_opens_ao_cra_gap(self) -> None:
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
            {"evidence_integrity", "legal_authority", "model_diversity"},
            capabilities,
        )
        self.assertEqual({"JFRIE", "LEX-OMEGA"}, set(plan.selected))
        self.assertEqual(("model_diversity",), plan.unresolved_roles)
        self.assertEqual(("AO-CRA:model_diversity",), plan.ao_cra_builds)

    def test_innovation_frontier_is_mandatory_and_complete(self) -> None:
        frontier = build_innovation_frontier(
            strongest_verified_reuse="reuse existing EvolutionGovernor",
            strongest_incremental_improvement="add scientific benchmark adapter",
            strongest_materially_different_solution="independent blind replication",
            highest_information_reversible_experiment="run utility benchmark in shadow mode",
        )
        self.assertTrue(frontier["verified_reuse"].startswith("reuse"))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            build_innovation_frontier(
                strongest_verified_reuse="reuse",
                strongest_incremental_improvement="",
                strongest_materially_different_solution="different",
                highest_information_reversible_experiment="experiment",
            )

    def test_caseforge_metrics_bind_to_existing_evolution_governor_contract(self) -> None:
        scores = full_scores(0.9)
        evaluation = evaluate_benchmark(scores)
        metrics = to_evolution_metrics(evaluation, scores)
        self.assertEqual(set(EvolutionGovernor.default_weights), set(metrics))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in metrics.values()))


if __name__ == "__main__":
    unittest.main()
