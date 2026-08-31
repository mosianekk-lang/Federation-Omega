import unittest

from evidenceops.caseforge.observable_burden_court_v1 import (
    OBSERVABLE_BURDEN_MODE,
    evaluate_observable_burden_court,
)


HEAD = "4cf122608413c5cc00ba1d36feb0d5f21b011a7b"


def good_pair(index: int, **overrides):
    item = {
        "pair_id": f"pair-{index}",
        "mission_class": "GENERAL_AUTOMATION",
        "task_signature": f"task-{index}",
        "oracle_id": "oracle-v1",
        "source_head_sha": HEAD,
        "evidence_mode": OBSERVABLE_BURDEN_MODE,
        "baseline_owner_interventions": 3,
        "candidate_owner_interventions": 1,
        "baseline_clarification_count": 2,
        "candidate_clarification_count": 1,
        "baseline_correction_count": 1,
        "candidate_correction_count": 0,
        "baseline_verified_output_ratio": 0.95,
        "candidate_verified_output_ratio": 0.95,
        "baseline_elapsed_seconds": 120.0,
        "candidate_elapsed_seconds": 90.0,
        "independent_readback": True,
        "proof_refs": [f"provider:{index}:a", f"provider:{index}:b"],
    }
    item.update(overrides)
    return item


class ObservableBurdenCourtTests(unittest.TestCase):
    def test_ten_clean_pairs_yield_burden_candidate_but_not_owner_value(self):
        result = evaluate_observable_burden_court(
            candidate_id="BUBBLES",
            source_head_sha=HEAD,
            observations=[good_pair(i) for i in range(10)],
        )
        self.assertTrue(result.observable_burden_reduction_candidate)
        self.assertEqual(result.pair_count, 10)
        self.assertFalse(result.owner_minutes_proven)
        self.assertFalse(result.owner_value_proven)
        self.assertFalse(result.stable_promotion_authorized)
        self.assertFalse(result.provider_effect_authorized)
        self.assertEqual(result.blockers, ())

    def test_minimum_pair_count_is_blocking(self):
        result = evaluate_observable_burden_court(
            candidate_id="BUBBLES",
            source_head_sha=HEAD,
            observations=[good_pair(i) for i in range(9)],
        )
        self.assertFalse(result.observable_burden_reduction_candidate)
        self.assertIn("OBSERVABLE_BURDEN_MINIMUM_PAIRS_REQUIRED", result.blockers)

    def test_quality_regression_blocks(self):
        records = [good_pair(i) for i in range(10)]
        records[4] = good_pair(4, candidate_verified_output_ratio=0.80)
        result = evaluate_observable_burden_court(
            candidate_id="BUBBLES", source_head_sha=HEAD, observations=records
        )
        self.assertFalse(result.observable_burden_reduction_candidate)
        self.assertIn("OBSERVABLE_BURDEN_OUTPUT_RATIO_REGRESSION", result.blockers)

    def test_count_or_latency_regression_blocks(self):
        for field, value, blocker in (
            ("candidate_owner_interventions", 4, "OBSERVABLE_BURDEN_INTERVENTION_REGRESSION"),
            ("candidate_clarification_count", 3, "OBSERVABLE_BURDEN_CLARIFICATION_REGRESSION"),
            ("candidate_correction_count", 2, "OBSERVABLE_BURDEN_CORRECTION_REGRESSION"),
            ("candidate_elapsed_seconds", 121.0, "OBSERVABLE_BURDEN_LATENCY_REGRESSION"),
        ):
            records = [good_pair(i) for i in range(10)]
            records[0] = good_pair(0, **{field: value})
            result = evaluate_observable_burden_court(
                candidate_id="BUBBLES", source_head_sha=HEAD, observations=records
            )
            self.assertIn(blocker, result.blockers)

    def test_same_burden_everywhere_is_not_reduction(self):
        records = [
            good_pair(
                i,
                candidate_owner_interventions=3,
                candidate_clarification_count=2,
                candidate_correction_count=1,
                candidate_elapsed_seconds=120.0,
            )
            for i in range(10)
        ]
        result = evaluate_observable_burden_court(
            candidate_id="BUBBLES", source_head_sha=HEAD, observations=records
        )
        self.assertFalse(result.observable_burden_reduction_candidate)
        self.assertIn("OBSERVABLE_BURDEN_STRICT_IMPROVEMENT_REQUIRED", result.blockers)

    def test_source_head_and_readback_are_proof_gates(self):
        records = [good_pair(i) for i in range(10)]
        records[0] = good_pair(0, source_head_sha="0" * 40, independent_readback=False)
        result = evaluate_observable_burden_court(
            candidate_id="BUBBLES", source_head_sha=HEAD, observations=records
        )
        self.assertIn("OBSERVABLE_BURDEN_SOURCE_HEAD_MISMATCH", result.blockers)
        self.assertIn("OBSERVABLE_BURDEN_INDEPENDENT_READBACK_REQUIRED", result.blockers)

    def test_duplicate_pair_ids_block(self):
        records = [good_pair(i) for i in range(10)]
        records[9] = good_pair(8)
        result = evaluate_observable_burden_court(
            candidate_id="BUBBLES", source_head_sha=HEAD, observations=records
        )
        self.assertIn("OBSERVABLE_BURDEN_PAIR_IDS_MUST_BE_UNIQUE", result.blockers)


if __name__ == "__main__":
    unittest.main()
