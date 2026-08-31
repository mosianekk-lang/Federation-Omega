import unittest

from federation.bubbles_autonomy_value_cohort import (
    AutonomyValuePolicy,
    BubblesAutonomyValueCourt,
    MissionValueObservation,
)


class BubblesAutonomyValueCourtTests(unittest.TestCase):
    def _obs(
        self,
        pair_id: str,
        variant: str,
        *,
        accepted: bool = True,
        intervention: float = 30.0,
        clarifications: int = 1,
        corrections: int = 0,
        cycle: float = 120.0,
        task_signature: str | None = None,
        oracle_id: str = "oracle-v1",
        evidence_class: str = "OBSERVED_REAL_MISSION",
        proof_refs: tuple[str, ...] | None = None,
    ) -> MissionValueObservation:
        return MissionValueObservation(
            pair_id=pair_id,
            variant=variant,
            task_signature=task_signature or f"task-{pair_id}",
            oracle_id=oracle_id,
            accepted=accepted,
            cycle_time_seconds=cycle,
            owner_intervention_seconds=intervention,
            clarification_count=clarifications,
            correction_count=corrections,
            observed_at="2026-08-31T20:00:00+02:00",
            proof_refs=proof_refs or (f"proof:{pair_id}:{variant}",),
            evidence_class=evidence_class,
        )

    def _good_pairs(self, count: int = 3):
        records = []
        for index in range(count):
            pair_id = f"pair-{index}"
            records.append(
                self._obs(
                    pair_id,
                    "BASELINE",
                    intervention=45.0,
                    clarifications=2,
                    corrections=1,
                    cycle=150.0,
                )
            )
            records.append(
                self._obs(
                    pair_id,
                    "BUBBLES",
                    intervention=15.0,
                    clarifications=1,
                    corrections=0,
                    cycle=120.0,
                )
            )
        return records

    def test_missing_proof_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "COHORT_PROOF_REFS_REQUIRED"):
            self._obs("p1", "BASELINE", proof_refs=()).validate()

    def test_incomplete_pair_is_held(self):
        result = BubblesAutonomyValueCourt().evaluate(
            [self._obs("p1", "BASELINE")],
            policy=AutonomyValuePolicy(min_pairs=1),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertEqual(result.state, "HELD_INCOMPLETE_COMPARABILITY")
        self.assertIn("INCOMPLETE_BASELINE_CANDIDATE_PAIR", result.blockers)

    def test_duplicate_variant_is_held(self):
        records = [
            self._obs("p1", "BASELINE"),
            self._obs("p1", "BASELINE", intervention=20.0),
            self._obs("p1", "BUBBLES", intervention=10.0),
        ]
        result = BubblesAutonomyValueCourt().evaluate(
            records,
            policy=AutonomyValuePolicy(min_pairs=1),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertIn("DUPLICATE_PAIR_VARIANT", result.blockers)

    def test_task_identity_mismatch_is_held(self):
        records = [
            self._obs("p1", "BASELINE", task_signature="task-a"),
            self._obs("p1", "BUBBLES", task_signature="task-b", intervention=10.0),
        ]
        result = BubblesAutonomyValueCourt().evaluate(
            records,
            policy=AutonomyValuePolicy(min_pairs=1),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertIn("TASK_SIGNATURE_MISMATCH", result.blockers)

    def test_minimum_pair_count_is_enforced(self):
        result = BubblesAutonomyValueCourt().evaluate(
            self._good_pairs(2),
            policy=AutonomyValuePolicy(min_pairs=3),
        )
        self.assertEqual(result.state, "HELD_INCOMPLETE_EMPIRICAL_COHORT")
        self.assertIn("MINIMUM_OBSERVED_PAIR_COUNT_NOT_MET", result.blockers)

    def test_accepted_outcome_regression_blocks_value_candidate(self):
        records = self._good_pairs(3)
        records[-1] = self._obs(
            "pair-2",
            "BUBBLES",
            accepted=False,
            intervention=10.0,
            clarifications=0,
            corrections=0,
            cycle=90.0,
        )
        result = BubblesAutonomyValueCourt().evaluate(
            records,
            policy=AutonomyValuePolicy(min_pairs=3, min_candidate_acceptance_rate=0.5),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertEqual(result.state, "HELD_ACCEPTED_OUTCOME_REGRESSION")
        self.assertIn("ACCEPTED_OUTCOME_QUALITY_REGRESSION", result.blockers)

    def test_pair_level_burden_regression_cannot_hide_in_aggregate(self):
        records = self._good_pairs(3)
        records[-1] = self._obs(
            "pair-2",
            "BUBBLES",
            intervention=60.0,
            clarifications=3,
            corrections=2,
            cycle=100.0,
        )
        result = BubblesAutonomyValueCourt().evaluate(
            records,
            policy=AutonomyValuePolicy(min_pairs=3),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertIn("PAIR_LEVEL_OWNER_BURDEN_REGRESSION", result.blockers)
        self.assertEqual(result.burden_regression_pair_ids, ("pair-2",))

    def test_positive_creator_time_and_non_regression_yield_value_candidate(self):
        result = BubblesAutonomyValueCourt().evaluate(
            self._good_pairs(3),
            policy=AutonomyValuePolicy(min_pairs=3),
        )
        self.assertTrue(result.promotion_eligible)
        self.assertEqual(result.state, "AUTONOMY_VALUE_CANDIDATE")
        self.assertEqual(result.pair_count, 3)
        self.assertEqual(result.creator_time_recovered_seconds, 90.0)
        self.assertEqual(result.median_owner_intervention_delta_seconds, 30.0)
        self.assertEqual(result.median_clarification_delta, 1.0)
        self.assertEqual(result.median_correction_delta, 1.0)
        self.assertEqual(result.median_cycle_time_delta_seconds, 30.0)
        self.assertFalse(result.provider_effect_authorized)
        self.assertFalse(result.external_effect_authorized)

    def test_non_real_evidence_class_cannot_promote(self):
        records = self._good_pairs(2)
        records[0] = self._obs(
            "pair-0",
            "BASELINE",
            intervention=45.0,
            clarifications=2,
            corrections=1,
            cycle=150.0,
            evidence_class="SYNTHETIC_FIXTURE",
        )
        result = BubblesAutonomyValueCourt().evaluate(
            records,
            policy=AutonomyValuePolicy(min_pairs=2),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertEqual(result.state, "DETERMINISTIC_COHORT_LOGIC_ONLY")
        self.assertFalse(result.all_observations_real_mission_class)

    def test_optional_cycle_time_regression_gate(self):
        records = self._good_pairs(2)
        records[1] = self._obs(
            "pair-0",
            "BUBBLES",
            intervention=10.0,
            clarifications=0,
            corrections=0,
            cycle=220.0,
        )
        result = BubblesAutonomyValueCourt().evaluate(
            records,
            policy=AutonomyValuePolicy(
                min_pairs=2,
                max_median_cycle_time_regression_ratio=0.05,
            ),
        )
        self.assertFalse(result.promotion_eligible)
        self.assertIn("MEDIAN_CYCLE_TIME_REGRESSION", result.blockers)

    def test_receipt_is_deterministic_for_same_cohort(self):
        court = BubblesAutonomyValueCourt()
        policy = AutonomyValuePolicy(min_pairs=3)
        first = court.evaluate(self._good_pairs(3), policy=policy)
        second = court.evaluate(self._good_pairs(3), policy=policy)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)


if __name__ == "__main__":
    unittest.main()
