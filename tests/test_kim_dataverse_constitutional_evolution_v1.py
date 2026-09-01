from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_constitutional_evolution_v1 import (
    AmendmentState,
    CapabilityFitness,
    CapabilityMarketAction,
    ConstitutionalAmendment,
    capability_market,
    evaluate_amendment,
)


class KimDataverseConstitutionalEvolutionTests(unittest.TestCase):
    def test_safe_reversible_amendment_can_only_reach_shadow_candidate(self) -> None:
        decision = evaluate_amendment(
            ConstitutionalAmendment(
                amendment_id="better-routing",
                changes_owner_authority=False,
                changes_external_effect_policy=False,
                changes_proof_floor=False,
                changes_owner_intent=False,
                reversible=True,
                historical_replay_passed=True,
                adversarial_passed=True,
                rollback_verified=True,
                shadow_observed=False,
                independent_proof_refs=("proof:a", "proof:b"),
                measured_gain=0.1,
            )
        )
        self.assertEqual(AmendmentState.SHADOW_CANDIDATE, decision.state)
        self.assertTrue(decision.eligible_for_shadow)
        self.assertFalse(decision.self_promoted)

    def test_authority_change_requires_owner_review_even_with_all_other_proof(self) -> None:
        decision = evaluate_amendment(
            ConstitutionalAmendment(
                amendment_id="authority-expansion",
                changes_owner_authority=True,
                changes_external_effect_policy=False,
                changes_proof_floor=False,
                changes_owner_intent=False,
                reversible=True,
                historical_replay_passed=True,
                adversarial_passed=True,
                rollback_verified=True,
                shadow_observed=True,
                independent_proof_refs=("proof:a",),
                measured_gain=1.0,
            )
        )
        self.assertEqual(AmendmentState.OWNER_REVIEW_REQUIRED, decision.state)
        self.assertTrue(decision.owner_review_required)
        self.assertFalse(decision.self_promoted)

    def test_proof_floor_change_can_never_self_promote(self) -> None:
        decision = evaluate_amendment(
            ConstitutionalAmendment(
                amendment_id="weaken-proof",
                changes_owner_authority=False,
                changes_external_effect_policy=False,
                changes_proof_floor=True,
                changes_owner_intent=False,
                reversible=True,
                historical_replay_passed=True,
                adversarial_passed=True,
                rollback_verified=True,
                shadow_observed=True,
                independent_proof_refs=("proof:a",),
                measured_gain=2.0,
            )
        )
        self.assertTrue(decision.owner_review_required)
        self.assertIn("PROOF_FLOOR_CHANGE_REQUIRES_OWNER_REVIEW", decision.reasons)

    def test_missing_rollback_or_independent_proof_holds(self) -> None:
        decision = evaluate_amendment(
            ConstitutionalAmendment(
                amendment_id="unsafe-candidate",
                changes_owner_authority=False,
                changes_external_effect_policy=False,
                changes_proof_floor=False,
                changes_owner_intent=False,
                reversible=True,
                historical_replay_passed=True,
                adversarial_passed=True,
                rollback_verified=False,
                shadow_observed=False,
                independent_proof_refs=(),
                measured_gain=0.5,
            )
        )
        self.assertEqual(AmendmentState.HELD, decision.state)
        self.assertIn("ROLLBACK_REQUIRED", decision.reasons)
        self.assertIn("INDEPENDENT_PROOF_REQUIRED", decision.reasons)

    def test_high_overlap_capability_goes_to_merge_review_not_auto_merge(self) -> None:
        decisions = capability_market(
            (
                CapabilityFitness("a", 0.9, 0.9, 0.9, 8, 2, 2, overlap_score=0.95),
            )
        )
        self.assertEqual(CapabilityMarketAction.MERGE_REVIEW, decisions[0].action)
        self.assertFalse(decisions[0].destructive_action_authorized)

    def test_unused_low_fitness_capability_goes_to_retire_review_only(self) -> None:
        decisions = capability_market(
            (
                CapabilityFitness("old", 0.1, 0.1, 0.1, 0, 30, 90, overlap_score=0.0),
            )
        )
        self.assertEqual(CapabilityMarketAction.RETIRE_REVIEW, decisions[0].action)
        self.assertFalse(decisions[0].destructive_action_authorized)

    def test_strong_reused_capability_is_retained(self) -> None:
        decisions = capability_market(
            (
                CapabilityFitness("strong", 0.95, 0.95, 0.95, 20, 1, 1),
            )
        )
        self.assertEqual(CapabilityMarketAction.RETAIN, decisions[0].action)

    def test_capability_market_is_deterministic_and_rejects_duplicate_ids(self) -> None:
        item = CapabilityFitness("cap", 0.7, 0.8, 0.9, 3, 5, 10)
        self.assertEqual(capability_market((item,)), capability_market((item,)))
        with self.assertRaises(ValueError):
            capability_market((item, item))


if __name__ == "__main__":
    unittest.main()
