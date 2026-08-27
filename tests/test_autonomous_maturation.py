from __future__ import annotations

import unittest

from evidenceops.caseforge.autonomous_maturation import (
    AutonomousMaturationController,
    MaturationAction,
    MaturationCandidate,
    MaturationGap,
    OwnerBoundary,
    SelfSustainingEvidence,
)
from evidenceops.caseforge.federation_evolution_program import (
    EvolutionStage,
    SystemEvolutionState,
)


class AutonomousMaturationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = AutonomousMaturationController()
        self.state = SystemEvolutionState(system_id="SUPERIOR_LOGIC")
        self.gap = MaturationGap(
            gap_id="GAP-OWNER-BURDEN",
            system_id="SUPERIOR_LOGIC",
            stage=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            description="Remove routine owner intervention from bounded maturation cycles.",
            mission_value_gain=0.9,
            failure_recurrence_reduction=0.8,
            owner_burden_reduction=1.0,
            proof_strength_gain=0.8,
            resilience_gain=0.8,
            capability_reuse_gain=0.7,
            reversibility=1.0,
            cost=0.0,
            risk=0.1,
            evidence_refs=("test://maturation-gap",),
        )

    def test_ordinary_gap_stays_autonomous_and_emits_resumable_transaction(self) -> None:
        decision = self.controller.plan(
            self.state,
            (self.gap,),
            expected_state_epoch="epoch-41",
        )
        self.assertEqual(MaturationAction.AUTONOMOUS_INTERNAL_EXPERIMENT, decision.action)
        self.assertFalse(decision.owner_escalation_reasons)
        self.assertFalse(decision.external_effect)
        self.assertIsNotNone(decision.transaction)
        assert decision.transaction is not None
        self.assertEqual("epoch-41", decision.transaction.expected_state_epoch)
        self.assertEqual("READBACK_BEFORE_RETRY", decision.transaction.retry_rule)
        self.assertTrue(decision.transaction.idempotency_key.startswith("maturation:"))

    def test_no_gap_follows_existing_twenty_stage_spine(self) -> None:
        decision = self.controller.plan(self.state)
        self.assertEqual(MaturationAction.ADVANCE_EXISTING_STAGE, decision.action)
        self.assertEqual(EvolutionStage.OBJECTIVE_COMPILER, decision.evolution.next_stage)
        self.assertFalse(decision.owner_escalation_reasons)

    def test_owner_boundary_is_exception_only(self) -> None:
        decision = self.controller.plan(
            self.state,
            (self.gap,),
            boundary=OwnerBoundary(new_or_expanded_provider_authority=True),
        )
        self.assertEqual(MaturationAction.ESCALATE_OWNER, decision.action)
        self.assertIn("NEW_OR_EXPANDED_PROVIDER_AUTHORITY", decision.owner_escalation_reasons)
        self.assertIsNone(decision.transaction)

    def test_incomplete_candidate_continues_qualification_instead_of_burdening_owner(self) -> None:
        candidate = MaturationCandidate(
            candidate_id="CAND-1",
            gap_id=self.gap.gap_id,
            lineage_refs=("sha256:parent",),
            champion_anchor="sha256:champion",
            champion_score=0.70,
            candidate_score=0.85,
            rollback_ref="restore://candidate-1",
            independent_readback=False,
            no_regression=True,
            restore_test_passed=True,
            proof_refs=("test://candidate",),
        )
        decision = self.controller.plan(self.state, (self.gap,), candidate=candidate)
        self.assertEqual(MaturationAction.RUN_QUALIFICATION, decision.action)
        self.assertFalse(decision.owner_escalation_reasons)
        self.assertIn(
            "PROMOTION_PROOF_INCOMPLETE_CONTINUE_AUTONOMOUS_QUALIFICATION",
            decision.reason_codes,
        )

    def test_proven_reversible_challenger_can_promote_inside_a1(self) -> None:
        candidate = MaturationCandidate(
            candidate_id="CAND-2",
            gap_id=self.gap.gap_id,
            lineage_refs=("sha256:parent",),
            champion_anchor="sha256:champion",
            champion_score=0.70,
            candidate_score=0.86,
            rollback_ref="restore://candidate-2",
            independent_readback=True,
            no_regression=True,
            restore_test_passed=True,
            proof_refs=("proof://independent", "proof://rollback"),
        )
        decision = self.controller.plan(self.state, (self.gap,), candidate=candidate)
        self.assertEqual(MaturationAction.PROMOTE_REVERSIBLE_INTERNAL_CHAMPION, decision.action)
        self.assertFalse(decision.external_effect)
        self.assertFalse(decision.owner_escalation_reasons)

    def test_candidate_cannot_smuggle_external_effect_or_authority_expansion(self) -> None:
        candidate = MaturationCandidate(
            candidate_id="CAND-3",
            gap_id=self.gap.gap_id,
            lineage_refs=("sha256:parent",),
            champion_anchor="sha256:champion",
            champion_score=0.70,
            candidate_score=0.90,
            rollback_ref="restore://candidate-3",
            independent_readback=True,
            no_regression=True,
            restore_test_passed=True,
            proof_refs=("proof://independent",),
            creates_external_effect=True,
            expands_authority=True,
        )
        decision = self.controller.plan(self.state, (self.gap,), candidate=candidate)
        self.assertEqual(MaturationAction.ESCALATE_OWNER, decision.action)
        self.assertIn("IRREVERSIBLE_EXTERNAL_EFFECT", decision.owner_escalation_reasons)
        self.assertIn("NEW_OR_EXPANDED_PROVIDER_AUTHORITY", decision.owner_escalation_reasons)

    def test_priority_function_rewards_owner_burden_reduction_and_reversibility(self) -> None:
        lower = MaturationGap(
            gap_id="LOWER",
            system_id="SUPERIOR_LOGIC",
            stage=EvolutionStage.AUTONOMOUS_REGRESSION_LAB,
            description="Lower value gap",
            mission_value_gain=0.6,
            owner_burden_reduction=0.0,
            reversibility=0.5,
            risk=0.2,
        )
        ranked = self.controller.rank_gaps((lower, self.gap))
        self.assertEqual(self.gap.gap_id, ranked[0].gap_id)

    def test_transaction_identity_is_stable_and_epoch_sensitive(self) -> None:
        first = self.controller.compile_transaction(
            system_id="SUPERIOR_LOGIC",
            gap=self.gap,
            candidate=None,
            expected_state_epoch="epoch-1",
            checkpoint_state="TEST",
        )
        replay = self.controller.compile_transaction(
            system_id="SUPERIOR_LOGIC",
            gap=self.gap,
            candidate=None,
            expected_state_epoch="epoch-1",
            checkpoint_state="TEST",
        )
        stale = self.controller.compile_transaction(
            system_id="SUPERIOR_LOGIC",
            gap=self.gap,
            candidate=None,
            expected_state_epoch="epoch-2",
            checkpoint_state="TEST",
        )
        self.assertEqual(first, replay)
        self.assertNotEqual(first.transaction_id, stale.transaction_id)
        self.assertNotEqual(first.idempotency_key, stale.idempotency_key)

    def test_interrupted_tool_execution_requires_readback_before_retry(self) -> None:
        result = self.controller.reconcile_interrupted_execution(
            {
                "failure_type": "MESSAGE_DELIVERY_TIMEOUT",
                "tool_inflight": True,
                "tool_call_id": "provider-write-1",
                "active_directive": "AUTONOMOUS_MATURATION:SUPERIOR_LOGIC",
                "objective": "continue from last provider-verified checkpoint",
                "last_proven_state": "SOURCE_COMMIT_VERIFIED",
                "last_completed_action": "create source",
                "next_pending_action": "read provider state",
            }
        )
        self.assertTrue(result["tool_outcome_readback_required"])
        self.assertEqual("READBACK_BEFORE_RETRY", result["retry_rule"])

    def test_self_sustaining_requires_measured_low_owner_intervention(self) -> None:
        mature = SelfSustainingEvidence(
            persistent_monitoring=True,
            repeated_successful_maturity_cycles=20,
            automatic_gap_detection=True,
            automatic_repair_or_candidate_generation=True,
            independent_proof=True,
            verified_rollback=True,
            measurable_operational_value=True,
            cross_receiver_learning_with_compatibility_proof=True,
            no_unresolved_constitutional_drift=True,
            owner_interventions=1,
        )
        burdened = SelfSustainingEvidence(
            persistent_monitoring=True,
            repeated_successful_maturity_cycles=20,
            automatic_gap_detection=True,
            automatic_repair_or_candidate_generation=True,
            independent_proof=True,
            verified_rollback=True,
            measurable_operational_value=True,
            cross_receiver_learning_with_compatibility_proof=True,
            no_unresolved_constitutional_drift=True,
            owner_interventions=10,
        )
        self.assertTrue(mature.self_sustaining)
        self.assertFalse(burdened.self_sustaining)


if __name__ == "__main__":
    unittest.main()
