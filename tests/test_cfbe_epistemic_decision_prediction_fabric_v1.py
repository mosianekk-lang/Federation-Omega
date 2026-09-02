from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    ClaimKind,
    DecisionOption,
    DecisionState,
    EpistemicClaim,
    EvidenceCandidate,
    EvidenceClass,
    EvidenceRef,
    Prediction,
    PredictionOutcome,
    PredictorProfile,
    aggregate_uncertainty,
    decide,
    predictor_allocation_weight,
    rank_evidence_candidates,
    update_predictor,
)


class EDPFTests(unittest.TestCase):
    def evidence(self, evidence_id: str, source: str, supports: float = 0.8) -> EvidenceRef:
        return EvidenceRef(
            evidence_id=evidence_id,
            evidence_class=EvidenceClass.PRIMARY,
            source_fingerprint=source,
            freshness=1.0,
            reliability=0.9,
            supports=supports,
        )

    def claim(self, probability: float = 0.9, contradictions: tuple[str, ...] = ()) -> EpistemicClaim:
        return EpistemicClaim(
            claim_id="claim-1",
            kind=ClaimKind.HYPOTHESIS,
            statement="route A will close the mission faster",
            probability=probability,
            evidence_refs=(self.evidence("e1", "source-a"), self.evidence("e2", "source-b")),
            contradiction_refs=contradictions,
        )

    def option(self, option_id: str, *, success: float, value: float, external: bool = False) -> DecisionOption:
        return DecisionOption(
            option_id=option_id,
            expected_value=value,
            success_probability=success,
            reversibility=0.9,
            information_gain=0.6,
            cost=0.1,
            latency=0.2,
            owner_burden=0.1,
            risk=0.1,
            external_effect=external,
        )

    def test_independent_source_count_deduplicates_same_provenance(self) -> None:
        claim = EpistemicClaim(
            claim_id="c",
            kind=ClaimKind.FACT,
            statement="same-source model agreement is not independent evidence",
            probability=0.8,
            evidence_refs=(self.evidence("a", "shared"), self.evidence("b", "shared")),
        )
        self.assertEqual(claim.independent_source_count(), 1)

    def test_uncertainty_rises_for_mid_probability_contradiction_and_thin_sources(self) -> None:
        low = aggregate_uncertainty((self.claim(0.95),))
        thin = EpistemicClaim(
            claim_id="thin",
            kind=ClaimKind.INFERENCE,
            statement="uncertain",
            probability=0.5,
            evidence_refs=(self.evidence("e", "one"),),
            contradiction_refs=("x",),
        )
        high = aggregate_uncertainty((thin,))
        self.assertLess(low, high)
        self.assertGreaterEqual(high, 0.9)

    def test_information_value_prefers_decision_changing_low_cost_evidence(self) -> None:
        candidates = (
            EvidenceCandidate("cheap-decisive", ("c",), 0.8, 0.8, 0.1, 0.05, 0.8),
            EvidenceCandidate("expensive-weak", ("c",), 0.1, 0.2, 0.9, 0.5, 0.1),
        )
        ranked = rank_evidence_candidates(candidates)
        self.assertEqual(ranked[0][0], "cheap-decisive")
        self.assertGreater(ranked[0][1], ranked[1][1])

    def test_high_uncertainty_seeks_best_evidence_when_challenger_is_satisfied(self) -> None:
        uncertain = EpistemicClaim(
            claim_id="c-high",
            kind=ClaimKind.HYPOTHESIS,
            statement="uncertain route",
            probability=0.5,
            evidence_refs=(self.evidence("a", "s1"), self.evidence("b", "s2")),
        )
        receipt = decide(
            cycle_id="cycle-1",
            source_version="main@abc",
            claims=(uncertain,),
            options=(self.option("a", success=0.7, value=0.8), self.option("b", success=0.6, value=0.7)),
            evidence_candidates=(EvidenceCandidate("probe", ("c-high",), 0.8, 0.7, 0.1, 0.1, 0.7),),
            proposer_source_fingerprints=("gemini", "copilot"),
        )
        self.assertEqual(receipt.state, DecisionState.SEEK_EVIDENCE)
        self.assertEqual(receipt.next_evidence_candidate_id, "probe")
        self.assertIsNone(receipt.selected_option_id)

    def test_high_uncertainty_holds_without_independent_challenger(self) -> None:
        uncertain = EpistemicClaim(
            claim_id="c-high",
            kind=ClaimKind.HYPOTHESIS,
            statement="uncertain route",
            probability=0.5,
            evidence_refs=(self.evidence("a", "s1"), self.evidence("b", "s2")),
        )
        receipt = decide(
            cycle_id="cycle-2",
            source_version="main@abc",
            claims=(uncertain,),
            options=(self.option("a", success=0.8, value=0.8),),
            proposer_source_fingerprints=("same-proposer",),
        )
        self.assertEqual(receipt.state, DecisionState.HOLD)
        self.assertIn("INDEPENDENT_CHALLENGER_REQUIRED", receipt.reason_codes)

    def test_external_effect_always_requires_independent_challenger_and_never_grants_authority(self) -> None:
        receipt = decide(
            cycle_id="cycle-3",
            source_version="main@abc",
            claims=(self.claim(0.95),),
            options=(self.option("effect", success=0.95, value=0.9, external=True),),
            proposer_source_fingerprints=("prime", "scientist"),
        )
        self.assertTrue(receipt.independent_challenger_required)
        self.assertTrue(receipt.independent_challenger_satisfied)
        self.assertFalse(receipt.dispatch_authorized)
        self.assertFalse(receipt.external_effect_authorized)
        self.assertFalse(receipt.stable_self_promotion_allowed)

    def test_low_uncertainty_selects_highest_utility_advisory_option(self) -> None:
        receipt = decide(
            cycle_id="cycle-4",
            source_version="main@abc",
            claims=(self.claim(0.98),),
            options=(
                self.option("strong", success=0.9, value=0.9),
                self.option("weak", success=0.4, value=0.5),
            ),
            proposer_source_fingerprints=("prime", "scientist"),
        )
        self.assertEqual(receipt.state, DecisionState.DECIDE)
        self.assertEqual(receipt.selected_option_id, "strong")
        self.assertEqual(receipt.ranked_option_ids[0], "strong")
        self.assertEqual(len(receipt.receipt_sha256), 64)

    def test_prediction_outcome_updates_calibration(self) -> None:
        profile = PredictorProfile("gemini", "architecture")
        prediction = Prediction(
            prediction_id="p1",
            predictor_id="gemini",
            domain="architecture",
            event="candidate improves benchmark",
            probability=0.8,
            expected_value=0.2,
            expected_latency=0.2,
            expected_owner_burden=0.1,
        )
        outcome = PredictionOutcome(
            prediction_id="p1",
            occurred=True,
            realised_value=0.25,
            realised_latency=0.3,
            realised_owner_burden=0.1,
            proof_refs=("proof-1",),
        )
        updated = update_predictor(profile, prediction, outcome)
        self.assertEqual(updated.attempts, 1)
        self.assertEqual(updated.resolved_correct, 1)
        self.assertAlmostEqual(updated.brier_score, 0.04)
        self.assertAlmostEqual(updated.calibration_error, 0.2)
        self.assertGreater(updated.trust_weight, 0.7)

    def test_bad_prediction_lowers_trust_relative_to_good_prediction(self) -> None:
        base = PredictorProfile("p", "domain")
        good = update_predictor(
            base,
            Prediction("good", "p", "domain", "event", 0.9, 1.0, 0.1, 0.1),
            PredictionOutcome("good", True, 1.0, 0.1, 0.1),
        )
        bad = update_predictor(
            base,
            Prediction("bad", "p", "domain", "event", 0.9, 1.0, 0.1, 0.1),
            PredictionOutcome("bad", False, 0.0, 0.1, 0.1),
        )
        self.assertGreater(good.trust_weight, bad.trust_weight)

    def test_predictor_allocation_rewards_calibration_relevance_and_independence(self) -> None:
        trained = PredictorProfile("p", "architecture", attempts=10, brier_sum=0.5, absolute_error_sum=1.0, resolved_correct=9)
        strong = predictor_allocation_weight(
            trained,
            relevance=0.9,
            independence=0.9,
            expected_information_gain=0.8,
            cost=0.2,
            latency=0.2,
        )
        weak = predictor_allocation_weight(
            PredictorProfile("q", "architecture"),
            relevance=0.3,
            independence=0.2,
            expected_information_gain=0.2,
            cost=0.8,
            latency=0.8,
        )
        self.assertGreater(strong, weak)

    def test_invalid_ranges_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            self.evidence("bad", "s", supports=1.2).validate()
        with self.assertRaises(ValueError):
            DecisionOption("x", 1.0, 1.1, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0).validate()


if __name__ == "__main__":
    unittest.main()
