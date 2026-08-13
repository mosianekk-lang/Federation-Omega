from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_autonomous_controller import (
    ActivationKind,
    AutonomousMaturityDominanceController,
    AutonomousRegressionPlanner,
    CapabilityFormationEngine,
    EvolutionGovernorBridge,
    REQUIRED_ATTESTATION_CONTROLS,
    RuntimeAttestation,
    WeaknessSignal,
)
from evidenceops.caseforge.federation_capability_twin import CapabilityTwin, ReadbackState, RuntimeState, SemanticState
from evidenceops.caseforge.federation_evolution_program import EvolutionStage
from evidenceops.caseforge.federation_evolution_runtime import FailureMemoryEntry, MissionExecutionState
from evidenceops.caseforge.federation_maturity_proof import MaturityProofEnvelope, StrictMaturity


def source_twin(system_id: str = "KAIO") -> CapabilityTwin:
    return CapabilityTwin(
        system_id=system_id,
        source_ref=f"REGISTRY:{system_id}",
        observed_at="2026-08-11T23:50:00+02:00",
        source_exists=True,
        canonical_readback=True,
        authority_ceiling="A1_INTERNAL",
        semantic_state=SemanticState.DECLARED_CONTRACT,
        readback_state=ReadbackState.SOURCE_READBACK,
        runtime_state=RuntimeState.SOURCE_ONLY,
        proof_ref=f"RCP:{system_id}",
    )


def provider_twin(system_id: str = "KIM_DATAVERSE") -> CapabilityTwin:
    return CapabilityTwin(
        system_id=system_id,
        source_ref=f"REGISTRY:{system_id}",
        observed_at="2026-08-11T23:50:00+02:00",
        source_exists=True,
        canonical_readback=True,
        authority_ceiling="A1_INTERNAL",
        semantic_state=SemanticState.PROVIDER_SEMANTIC_VERIFIED,
        readback_state=ReadbackState.PROVIDER_READBACK,
        runtime_state=RuntimeState.PROVIDER_VERIFIED,
        proof_ref=f"RCP:{system_id}",
        provider_readback_ref=f"PROVIDER:{system_id}",
    )


class RuntimeAttestationTests(unittest.TestCase):
    def attestation(self, **overrides) -> RuntimeAttestation:
        payload = dict(
            invocation_id="INV-1",
            system_id="CHATBRIDGE",
            activation_kind=ActivationKind.NEW_CHAT,
            observed_at="2026-08-12T00:01:00+02:00",
            current_main_sha="a" * 40,
            startup_block="NCB-003",
            loaded_controls=REQUIRED_ATTESTATION_CONTROLS,
            private_readback_ref="KDV-RCP",
            source_readback_ref="GITHUB-RCP",
            capability_twin_ref="TWIN:CHATBRIDGE",
        )
        payload.update(overrides)
        return RuntimeAttestation(**payload)

    def test_current_chat_does_not_preprove_cross_chat_stage16(self) -> None:
        self.assertFalse(self.attestation(activation_kind=ActivationKind.CURRENT_CHAT).qualifies_stage16)

    def test_new_chat_with_all_controls_can_prove_stage16_for_that_invocation(self) -> None:
        self.assertTrue(self.attestation().qualifies_stage16)

    def test_missing_control_fails_stage16(self) -> None:
        attestation = self.attestation(loaded_controls=REQUIRED_ATTESTATION_CONTROLS[:-1])
        self.assertFalse(attestation.qualifies_stage16)
        self.assertEqual(("ROUTE_AND_FAILURE_MEMORY",), attestation.missing_controls)

    def test_restored_chat_requires_restore_receipt(self) -> None:
        self.assertFalse(self.attestation(activation_kind=ActivationKind.RESTORED_CHAT).qualifies_stage16)
        self.assertTrue(
            self.attestation(
                activation_kind=ActivationKind.RESTORED_CHAT,
                mission_restore_ref="RESTORE-RCP",
            ).qualifies_stage16
        )

    def test_lower_authority_ceiling_can_attest_without_inheritance(self) -> None:
        self.assertTrue(
            self.attestation(
                system_id="VERITAS",
                authority_ceiling="A0",
                capability_twin_ref="TWIN:VERITAS:A0",
            ).qualifies_stage16
        )

    def test_unknown_or_higher_authority_ceiling_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot expand authority"):
            self.attestation(authority_ceiling="A2_PROVIDER").validate()


class AutonomousRegressionPlannerTests(unittest.TestCase):
    def test_failure_memory_becomes_deterministic_regression_contract(self) -> None:
        entry = FailureMemoryEntry("STALE_BASE_HEAD_REJECTED", "RECUT_CURRENT_MAIN", "PR334")
        case1 = AutonomousRegressionPlanner().from_failure(entry)
        case2 = AutonomousRegressionPlanner().from_failure(entry)
        self.assertEqual(case1.regression_id, case2.regression_id)
        self.assertIn("recut from current main", case1.expected_behavior)
        self.assertIn("weaken ancestry", case1.prohibited_behavior)

    def test_regression_suite_requires_failure_memory(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            AutonomousRegressionPlanner().build_suite(())


class EvolutionGovernorBridgeTests(unittest.TestCase):
    def full_metrics(self, value: float) -> dict[str, float]:
        return {name: value for name in EvolutionGovernorBridge.weights}

    def test_hard_regression_rejects_prepromotion(self) -> None:
        baseline = self.full_metrics(0.8)
        candidate = self.full_metrics(0.9)
        candidate["security"] = 0.7
        result = EvolutionGovernorBridge().evaluate(
            baseline_metrics=baseline,
            candidate_metrics=candidate,
            regression_passed=True,
            rollback_available=True,
        )
        self.assertEqual("REJECT_PREPROMOTION", result.decision)
        self.assertIn("security", result.hard_regressions)

    def test_good_candidate_is_forwarded_to_existing_governor_not_self_promoted(self) -> None:
        result = EvolutionGovernorBridge().evaluate(
            baseline_metrics=self.full_metrics(0.70),
            candidate_metrics=self.full_metrics(0.90),
            regression_passed=True,
            rollback_available=True,
        )
        self.assertEqual("FORWARD_TO_EXISTING_EVOLUTION_GOVERNOR", result.decision)
        self.assertEqual("CALL_EXISTING_EVOLUTION_GOVERNOR_WITH_HASH_LINKED_CANDIDATE", result.next_action)

    def test_rollback_and_regression_are_mandatory(self) -> None:
        result = EvolutionGovernorBridge().evaluate(
            baseline_metrics=self.full_metrics(0.70),
            candidate_metrics=self.full_metrics(0.90),
            regression_passed=False,
            rollback_available=False,
        )
        self.assertIn("REGRESSION_PROOF_REQUIRED", result.reasons)
        self.assertIn("ROLLBACK_REQUIRED", result.reasons)


class CapabilityFormationTests(unittest.TestCase):
    def test_source_only_twin_generates_governed_capability_build(self) -> None:
        engine = CapabilityFormationEngine()
        gap = engine.infer_gap(source_twin("KAIO"), required_role="PROVIDER_BOUND_MODEL_RUNTIME")
        self.assertIsNotNone(gap)
        plan = engine.plan(gap)
        self.assertTrue(plan.build_id.startswith("AO-CRA:CAPABILITY:KAIO:"))
        self.assertTrue(plan.rollback_required)
        self.assertTrue(plan.provider_effects_separately_authorized)
        self.assertFalse(plan.external_effect)

    def test_provider_verified_twin_does_not_invent_gap(self) -> None:
        self.assertIsNone(
            CapabilityFormationEngine().infer_gap(
                provider_twin(), required_role="TESTED_GOOGLE_SHEETS_PROVIDER_ROUTE"
            )
        )


class DominanceControllerTests(unittest.TestCase):
    def signal(self, system_id: str, seed: float) -> WeaknessSignal:
        return WeaknessSignal(system_id, seed, seed, seed, seed, seed, f"RCP:{system_id}")

    def full_proof(self, provider: bool) -> MaturityProofEnvelope:
        return MaturityProofEnvelope(
            deterministic_test_ref="R-DET",
            shadow_validation_ref="R-SHADOW",
            adversarial_validation_ref="R-ADV",
            canary_validation_ref="R-CANARY",
            limited_workflow_ref="R-LIMITED",
            cross_domain_ref="R-CROSS",
            operational_readback_ref="R-OPS",
            provider_readback_ref="R-PROVIDER" if provider else "",
            regression_ref="R-REG",
            rollback_ref="R-ROLL",
        )

    def test_controller_cannot_claim_dominance_without_provider_proof(self) -> None:
        decision = AutonomousMaturityDominanceController().decide(
            completed_through=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            maturity_proof=self.full_proof(False),
            weaknesses=(self.signal("TRUTHGRID", 0.8),),
            mission_state=MissionExecutionState("M-1", 0),
        )
        self.assertEqual(StrictMaturity.OPERATIONAL_VERIFIED, decision.strict_maturity.maturity)
        self.assertFalse(decision.dominance_claim_allowed)

    def test_controller_selects_highest_priority_weakness(self) -> None:
        chosen = AutonomousMaturityDominanceController().choose_weakness(
            (
                self.signal("KAIO", 0.4),
                self.signal("TRUTHGRID", 0.9),
                self.signal("MODISA", 0.7),
            )
        )
        self.assertEqual("TRUTHGRID", chosen.system_id)

    def test_existing_mission_work_takes_priority_over_new_experiment(self) -> None:
        decision = AutonomousMaturityDominanceController().decide(
            completed_through=EvolutionStage.EXECUTABLE_WORK_ZERO_ENGINE,
            maturity_proof=MaturityProofEnvelope(deterministic_test_ref="R-DET"),
            weaknesses=(self.signal("KAIO", 0.9),),
            mission_state=MissionExecutionState("M-2", 2),
        )
        self.assertEqual("CONTINUE_HIGHEST_VALUE_EXECUTABLE_INTERNAL_REPAIR", decision.next_action.action)

    def test_full_independent_proof_allows_candidate_label_only_through_strict_gate(self) -> None:
        decision = AutonomousMaturityDominanceController().decide(
            completed_through=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            maturity_proof=self.full_proof(True),
            weaknesses=(),
            mission_state=MissionExecutionState("M-3", 0),
        )
        self.assertTrue(decision.dominance_claim_allowed)
        self.assertEqual(StrictMaturity.ADAPTIVE_DOMINANCE_CANDIDATE, decision.strict_maturity.maturity)


if __name__ == "__main__":
    unittest.main()
