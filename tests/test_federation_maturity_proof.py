from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_evolution_program import EvolutionStage
from evidenceops.caseforge.federation_maturity_proof import (
    MaturityProofEnvelope,
    StrictMaturity,
    StrictMaturityGate,
)


class StrictMaturityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = StrictMaturityGate()

    def test_stage_count_alone_cannot_claim_deterministic_maturity(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.SUCCESS_ROUTE_MEMORY,
            proof=MaturityProofEnvelope(),
        )
        self.assertEqual(StrictMaturity.FOUNDATION_ACTIVE, decision.maturity)
        self.assertIn("DETERMINISTIC_TEST_PROOF_REQUIRED", decision.blocked_by)

    def test_stage_twelve_needs_explicit_shadow_validation(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.NEGATIVE_PROOF_ENGINE,
            proof=MaturityProofEnvelope(deterministic_test_ref="R-DET"),
        )
        self.assertEqual(StrictMaturity.DETERMINISTIC_TESTED, decision.maturity)
        self.assertIn("SHADOW_VALIDATION_REQUIRED", decision.blocked_by)

    def test_stage_fourteen_needs_adversarial_validation(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.MISSION_CONTINUATION_KERNEL,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
            ),
        )
        self.assertEqual(StrictMaturity.SHADOW_VALIDATED, decision.maturity)
        self.assertIn("ADVERSARIAL_VALIDATION_REQUIRED", decision.blocked_by)

    def test_stage_fifteen_needs_canary(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.EXECUTABLE_WORK_ZERO_ENGINE,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
                adversarial_validation_ref="R-ADV",
            ),
        )
        self.assertEqual(StrictMaturity.ADVERSARIALLY_VALIDATED, decision.maturity)
        self.assertIn("CANARY_VALIDATION_REQUIRED", decision.blocked_by)

    def test_stage_sixteen_needs_limited_workflow_attestation(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.CROSS_CHAT_RUNTIME_ATTESTATION,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
                adversarial_validation_ref="R-ADV",
                canary_validation_ref="R-CANARY",
            ),
        )
        self.assertEqual(StrictMaturity.CANARY_VALIDATED, decision.maturity)
        self.assertIn("LIMITED_WORKFLOW_RUNTIME_ATTESTATION_REQUIRED", decision.blocked_by)

    def test_stage_eighteen_needs_cross_domain_and_regression(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.EVOLUTION_GOVERNOR,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
                adversarial_validation_ref="R-ADV",
                canary_validation_ref="R-CANARY",
                limited_workflow_ref="R-LIMITED",
            ),
        )
        self.assertEqual(StrictMaturity.LIMITED_WORKFLOW_VERIFIED, decision.maturity)
        self.assertIn("CROSS_DOMAIN_PROOF_REQUIRED", decision.blocked_by)
        self.assertIn("REGRESSION_PROOF_REQUIRED", decision.blocked_by)

    def test_critical_failure_vetoes_high_maturity(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
                adversarial_validation_ref="R-ADV",
                canary_validation_ref="R-CANARY",
                limited_workflow_ref="R-LIMITED",
                cross_domain_ref="R-CROSS",
                operational_readback_ref="R-OPS",
                provider_readback_ref="R-PROVIDER",
                regression_ref="R-REG",
                rollback_ref="R-ROLL",
                critical_failures=("WRONG_FORUM",),
            ),
        )
        self.assertEqual(StrictMaturity.FOUNDATION_ACTIVE, decision.maturity)
        self.assertFalse(decision.dominance_candidate)
        self.assertIn("CRITICAL_FAILURE_PRESENT", decision.blocked_by)

    def test_stage_twenty_without_provider_readback_is_not_dominance(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
                adversarial_validation_ref="R-ADV",
                canary_validation_ref="R-CANARY",
                limited_workflow_ref="R-LIMITED",
                cross_domain_ref="R-CROSS",
                operational_readback_ref="R-OPS",
                regression_ref="R-REG",
                rollback_ref="R-ROLL",
            ),
        )
        self.assertEqual(StrictMaturity.OPERATIONAL_VERIFIED, decision.maturity)
        self.assertFalse(decision.dominance_candidate)
        self.assertIn("PROVIDER_READBACK_REQUIRED_FOR_DOMINANCE", decision.blocked_by)

    def test_full_independent_proof_can_reach_dominance_candidate(self) -> None:
        decision = self.gate.classify(
            completed_through=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            proof=MaturityProofEnvelope(
                deterministic_test_ref="R-DET",
                shadow_validation_ref="R-SHADOW",
                adversarial_validation_ref="R-ADV",
                canary_validation_ref="R-CANARY",
                limited_workflow_ref="R-LIMITED",
                cross_domain_ref="R-CROSS",
                operational_readback_ref="R-OPS",
                provider_readback_ref="R-PROVIDER",
                regression_ref="R-REG",
                rollback_ref="R-ROLL",
            ),
        )
        self.assertEqual(StrictMaturity.ADAPTIVE_DOMINANCE_CANDIDATE, decision.maturity)
        self.assertTrue(decision.dominance_candidate)
        self.assertEqual((), decision.blocked_by)


if __name__ == "__main__":
    unittest.main()
