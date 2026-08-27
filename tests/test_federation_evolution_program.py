from __future__ import annotations

import unittest

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from evidenceops.caseforge.federation_evolution_program import (
    ALL_STAGES,
    EvolutionMaturity,
    EvolutionStage,
    FederationEvolutionOrchestrator,
    SYSTEM_PROFILES,
    StageEvidence,
    StrategyMode,
    SystemEvolutionProfile,
    SystemEvolutionState,
)


class FederationEvolutionProgramTests(unittest.TestCase):
    def test_all_registered_systems_preserve_twenty_stage_spine(self) -> None:
        self.assertGreaterEqual(len(SYSTEM_PROFILES), 20)
        for profile in SYSTEM_PROFILES.values():
            self.assertEqual(20, len(profile.mandatory_stages), profile.system_id)
            self.assertEqual(ALL_STAGES, profile.mandatory_stages, profile.system_id)
            self.assertFalse(profile.external_effect_default)

    def test_specialized_path_cannot_skip_common_stages(self) -> None:
        with self.assertRaisesRegex(ValueError, "may not weaken or skip"):
            SystemEvolutionProfile(
                system_id="WEAK",
                canonical_name="Weak",
                family="test",
                optimization_objective="test",
                strategy_mode=StrategyMode.SPECIALIZED,
                specialized_algorithms=("custom",),
                vetoes=(),
                mandatory_stages=ALL_STAGES[:-1],
            ).validate()

    def test_lower_system_authority_ceiling_is_allowed_without_inheritance(self) -> None:
        profile = SystemEvolutionProfile(
            system_id="VERITAS",
            canonical_name="Veritas-Ω",
            family="TRUTH_ASSURANCE",
            optimization_objective="test",
            strategy_mode=StrategyMode.SPECIALIZED,
            specialized_algorithms=("FALSIFICATION",),
            vetoes=("INFERENCE_AS_FACT",),
            authority_ceiling="A0",
        ).validate()
        self.assertEqual("A0", profile.authority_ceiling)
        self.assertEqual("A0", SYSTEM_PROFILES["VERITAS"].authority_ceiling)

    def test_higher_or_unknown_system_authority_ceiling_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported authority ceiling"):
            SystemEvolutionProfile(
                system_id="VERITAS",
                canonical_name="Veritas-Ω",
                family="TRUTH_ASSURANCE",
                optimization_objective="test",
                strategy_mode=StrategyMode.SPECIALIZED,
                specialized_algorithms=("FALSIFICATION",),
                vetoes=("INFERENCE_AS_FACT",),
                authority_ceiling="A2_PROVIDER",
            ).validate()

    def test_next_stage_is_first_unproven_stage(self) -> None:
        state = SystemEvolutionState(
            system_id="TRUTHGRID",
            evidence=(
                StageEvidence(EvolutionStage.OBJECTIVE_COMPILER, True, "R1", 1.0),
                StageEvidence(EvolutionStage.CAPABILITY_DIGITAL_TWIN, True, "R2", 1.0),
            ),
        )
        decision = FederationEvolutionOrchestrator().evaluate(state)
        self.assertEqual(EvolutionStage.CAPABILITY_DEPENDENCY_GRAPH, decision.next_stage)
        self.assertEqual(EvolutionMaturity.FOUNDATION_ACTIVE, decision.maturity)
        self.assertTrue(any("APPLY_SPECIALIZED" in action for action in decision.automatic_next_actions))

    def test_stage_pass_requires_proof(self) -> None:
        with self.assertRaisesRegex(ValueError, "proof_ref"):
            StageEvidence(EvolutionStage.OBJECTIVE_COMPILER, True).validate()

    def test_late_evolution_requires_regression_and_rollback(self) -> None:
        with self.assertRaisesRegex(ValueError, "regression"):
            StageEvidence(
                EvolutionStage.AUTONOMOUS_REGRESSION_LAB,
                True,
                proof_ref="R17",
                score=1.0,
            ).validate()
        with self.assertRaisesRegex(ValueError, "rollback"):
            StageEvidence(
                EvolutionStage.CAPABILITY_FORMATION_ENGINE,
                True,
                proof_ref="R19",
                score=1.0,
                regression_passed=True,
            ).validate()

    def test_external_effect_cannot_be_smuggled_into_internal_evolution(self) -> None:
        with self.assertRaisesRegex(ValueError, "external effects"):
            StageEvidence(
                EvolutionStage.SELF_HEALING_ROUTE_ENGINE,
                True,
                proof_ref="R7",
                score=1.0,
                external_effect=True,
            ).validate()

    def test_twenty_stage_completion_without_final_provider_proof_is_not_dominance(self) -> None:
        evidence = []
        for stage in ALL_STAGES:
            evidence.append(
                StageEvidence(
                    stage=stage,
                    passed=True,
                    proof_ref=f"R{stage.value}",
                    score=1.0,
                    regression_passed=stage < EvolutionStage.AUTONOMOUS_REGRESSION_LAB or True,
                    rollback_available=stage < EvolutionStage.CAPABILITY_FORMATION_ENGINE or True,
                    provider_readback=False,
                )
            )
        decision = FederationEvolutionOrchestrator().evaluate(
            SystemEvolutionState(system_id="CASEFORGE", evidence=tuple(evidence))
        )
        self.assertEqual(EvolutionMaturity.ADAPTIVE_DOMINANCE_CANDIDATE, decision.maturity)
        self.assertFalse(decision.dominance_candidate)
        self.assertIn("ALL_STAGES_PRESENT_BUT_DOMINANCE_PROOF_INSUFFICIENT", decision.reason_codes)

    def test_dominance_candidate_requires_all_stages_regression_rollback_and_provider_readback(self) -> None:
        evidence = []
        for stage in ALL_STAGES:
            evidence.append(
                StageEvidence(
                    stage=stage,
                    passed=True,
                    proof_ref=f"R{stage.value}",
                    score=0.95,
                    regression_passed=stage >= EvolutionStage.AUTONOMOUS_REGRESSION_LAB,
                    rollback_available=stage >= EvolutionStage.CAPABILITY_FORMATION_ENGINE,
                    provider_readback=stage == EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
                )
            )
        decision = FederationEvolutionOrchestrator().evaluate(
            SystemEvolutionState(system_id="FEDERATION_OMEGA", evidence=tuple(evidence))
        )
        self.assertTrue(decision.dominance_candidate)
        self.assertIsNone(decision.next_stage)

    def test_critical_failure_vetoes_dominance_even_when_stages_pass(self) -> None:
        evidence = []
        for stage in ALL_STAGES:
            evidence.append(
                StageEvidence(
                    stage=stage,
                    passed=True,
                    proof_ref=f"R{stage.value}",
                    score=1.0,
                    regression_passed=stage >= EvolutionStage.AUTONOMOUS_REGRESSION_LAB,
                    rollback_available=stage >= EvolutionStage.CAPABILITY_FORMATION_ENGINE,
                    provider_readback=stage == EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
                )
            )
        decision = FederationEvolutionOrchestrator().evaluate(
            SystemEvolutionState(
                system_id="JFRIE",
                evidence=tuple(evidence),
                critical_failures=("WRONG_FORUM_REGRESSION",),
            )
        )
        self.assertFalse(decision.dominance_candidate)
        self.assertIn("CRITICAL_FAILURE_PRESENT", decision.reason_codes)
        self.assertTrue(any(action.startswith("REPAIR_CRITICAL") for action in decision.automatic_next_actions))

    def test_federation_rollup_keeps_external_dependencies_bounded(self) -> None:
        rollup = FederationEvolutionOrchestrator().federation_rollup(
            [
                SystemEvolutionState(
                    system_id="MODISA",
                    open_external_dependencies=("PROVIDER_SCHEDULER_PROOF",),
                ),
                SystemEvolutionState(system_id="KAIO"),
            ]
        )
        self.assertFalse(rollup["external_effect"])
        actions = rollup["next_actions"]["MODISA"]
        self.assertIn("DISPOSITION_EXTERNAL:PROVIDER_SCHEDULER_PROOF", actions)

    def test_failure_win_v2_source_bridge_opens_repair_without_self_promotion(self) -> None:
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FW-AIRLOCK-1",
                    event_type=FailureEventType.FAILURE,
                    system_id="FEDERATION_OMEGA",
                    objective="recover material failure",
                    claim="route should produce semantic completion",
                    observed_fruit="failure",
                    desired_outcome="proved recovery",
                    failure_code="FIXTURE_FAILURE",
                )
            )
        )
        self.assertEqual(FailureWinState.REPAIR_CYCLE_OPEN, result.state)
        self.assertFalse(result.proof_graph.complete)
        self.assertTrue(result.next_falsification_test)

    def test_failure_win_v2_rejects_speed_gain_that_dilutes_quality(self) -> None:
        incumbent = PerformanceVector(quality=5, reliability=5, proof=5, speed=1)
        faster_but_worse = PerformanceVector(quality=4, reliability=5, proof=5, speed=20)
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FW-AIRLOCK-2",
                    event_type=FailureEventType.REGRESSION,
                    system_id="FEDERATION_OMEGA",
                    objective="preserve quality while improving recovery",
                    claim="candidate is better",
                    observed_fruit="quality regressed",
                    desired_outcome="non-diluting improvement",
                    failure_code="QUALITY_REGRESSION",
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="fast-worse",
                        route_type="REROUTE",
                        performance=faster_but_worse,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                    ),
                ),
            )
        )
        self.assertFalse(result.vector_gate_passed)
        self.assertIn("quality", result.protected_regressions)


if __name__ == "__main__":
    unittest.main()
