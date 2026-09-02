from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.edpf_shadow_prediction_court_v1 import (
    EvidenceMode,
    ShadowPredictionPair,
    evaluate_shadow_prediction_court,
)
from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    Prediction,
    PredictionOutcome,
)

SHA = "a" * 40


def make_pair(index: int, *, mode: EvidenceMode = EvidenceMode.REAL_MISSION, source: str | None = None) -> ShadowPredictionPair:
    occurred = index % 2 == 0
    predictor = ("GEMINI", "COPILOT", "BCO_PRIME")[index % 3]
    probability = 0.90 if occurred else 0.10
    prediction_id = f"pred-{index}"
    pre_ref = f"pre-{index}"
    outcome_ref = f"outcome-{index}"
    prediction = Prediction(
        prediction_id=prediction_id,
        predictor_id=predictor,
        domain="architecture" if index % 2 == 0 else "source_defect",
        event=f"event-{index}",
        probability=probability,
        expected_value=0.8 if occurred else 0.2,
        expected_latency=0.2,
        expected_owner_burden=0.1,
        evidence_refs=(pre_ref,),
    )
    outcome = PredictionOutcome(
        prediction_id=prediction_id,
        occurred=occurred,
        realised_value=0.82 if occurred else 0.18,
        realised_latency=0.22,
        realised_owner_burden=0.12,
        proof_refs=(outcome_ref,),
    )
    return ShadowPredictionPair(
        pair_id=f"pair-{index}",
        mission_id=f"mission-{index // 3}",
        source_head_sha=SHA,
        predictor_source_fingerprint=source or ("model-family-a" if index % 2 == 0 else "model-family-b"),
        prediction_cutoff_epoch=1_000 + index * 10,
        outcome_observed_epoch=1_005 + index * 10,
        prediction=prediction,
        outcome=outcome,
        pre_outcome_evidence_refs=(pre_ref,),
        outcome_proof_refs=(outcome_ref,),
        evidence_mode=mode,
    )


class ShadowPredictionCourtTests(unittest.TestCase):
    def test_real_chronological_cohort_scores_positive_without_live_promotion(self) -> None:
        receipt = evaluate_shadow_prediction_court(tuple(make_pair(i) for i in range(30)), holdout_size=10)
        self.assertEqual(receipt.decision, "REAL_SHADOW_CALIBRATION_POSITIVE")
        self.assertGreaterEqual(receipt.holdout_brier_gain, 0.01)
        self.assertEqual(receipt.predictor_count, 3)
        self.assertEqual(receipt.independent_source_count, 2)
        self.assertFalse(receipt.live_predictor_weights_changed)
        self.assertFalse(receipt.live_predictor_weight_change_authorized)
        self.assertFalse(receipt.dispatch_authorized)
        self.assertFalse(receipt.external_effect_authorized)
        self.assertFalse(receipt.stable_self_promotion_allowed)
        self.assertFalse(receipt.owner_action_required)

    def test_synthetic_cohort_never_empirically_promotes(self) -> None:
        receipt = evaluate_shadow_prediction_court(
            tuple(make_pair(i, mode=EvidenceMode.SYNTHETIC_TEST) for i in range(30)),
            holdout_size=10,
        )
        self.assertEqual(receipt.decision, "SOURCE_COURT_READY_AWAITING_REAL_COHORT")
        self.assertIn("REAL_MISSION_EVIDENCE_REQUIRED_FOR_EMPIRICAL_PROMOTION", receipt.blockers)

    def test_temporal_leakage_fails_closed(self) -> None:
        pair = make_pair(0)
        leaked = ShadowPredictionPair(
            **{**pair.__dict__, "outcome_observed_epoch": pair.prediction_cutoff_epoch}
        )
        with self.assertRaisesRegex(ValueError, "TEMPORAL_LEAKAGE"):
            leaked.validate()

    def test_outcome_proof_cannot_be_prediction_evidence(self) -> None:
        pair = make_pair(1)
        leaked = ShadowPredictionPair(
            pair_id=pair.pair_id,
            mission_id=pair.mission_id,
            source_head_sha=pair.source_head_sha,
            predictor_source_fingerprint=pair.predictor_source_fingerprint,
            prediction_cutoff_epoch=pair.prediction_cutoff_epoch,
            outcome_observed_epoch=pair.outcome_observed_epoch,
            prediction=pair.prediction,
            outcome=pair.outcome,
            pre_outcome_evidence_refs=pair.pre_outcome_evidence_refs + pair.outcome_proof_refs,
            outcome_proof_refs=pair.outcome_proof_refs,
            evidence_mode=pair.evidence_mode,
        )
        with self.assertRaisesRegex(ValueError, "OUTCOME_PROOF_LEAKED"):
            leaked.validate()

    def test_low_predictor_diversity_is_held(self) -> None:
        pairs = []
        for i in range(30):
            pair = make_pair(i, source="single-source")
            prediction = Prediction(
                prediction_id=pair.prediction.prediction_id,
                predictor_id="ONLY_ONE",
                domain=pair.prediction.domain,
                event=pair.prediction.event,
                probability=pair.prediction.probability,
                expected_value=pair.prediction.expected_value,
                expected_latency=pair.prediction.expected_latency,
                expected_owner_burden=pair.prediction.expected_owner_burden,
                evidence_refs=pair.prediction.evidence_refs,
            )
            pairs.append(
                ShadowPredictionPair(
                    pair_id=pair.pair_id,
                    mission_id=pair.mission_id,
                    source_head_sha=pair.source_head_sha,
                    predictor_source_fingerprint="single-source",
                    prediction_cutoff_epoch=pair.prediction_cutoff_epoch,
                    outcome_observed_epoch=pair.outcome_observed_epoch,
                    prediction=prediction,
                    outcome=pair.outcome,
                    pre_outcome_evidence_refs=pair.pre_outcome_evidence_refs,
                    outcome_proof_refs=pair.outcome_proof_refs,
                    evidence_mode=pair.evidence_mode,
                )
            )
        receipt = evaluate_shadow_prediction_court(tuple(pairs), holdout_size=10)
        self.assertEqual(receipt.decision, "REAL_SHADOW_CALIBRATION_NEGATIVE_OR_INSUFFICIENT")
        self.assertIn("MINIMUM_PREDICTOR_DIVERSITY_REQUIRED", receipt.blockers)
        self.assertIn("MINIMUM_INDEPENDENT_SOURCE_DIVERSITY_REQUIRED", receipt.blockers)

    def test_mixed_evidence_modes_fail_closed(self) -> None:
        pairs = [make_pair(i) for i in range(29)]
        pairs.append(make_pair(29, mode=EvidenceMode.SYNTHETIC_TEST))
        with self.assertRaisesRegex(ValueError, "EVIDENCE_MODE_MIXED"):
            evaluate_shadow_prediction_court(tuple(pairs), holdout_size=10)


if __name__ == "__main__":
    unittest.main()
