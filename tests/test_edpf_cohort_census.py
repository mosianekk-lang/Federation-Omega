from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import copy
import unittest

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import Prediction, PredictionOutcome
from federation.living_state.edpf_cohort_census import census_prospective_cohorts
from federation.living_state.edpf_prediction_adapter import (
    ProspectiveOutcomeRecord,
    ProspectivePredictionRecord,
    record_prospective_prediction,
    resolve_prospective_prediction,
)
from federation.living_state.model import LivingWorldModel
from federation.living_state.types import ProofMaturity

HEAD_A = "a" * 40
HEAD_B = "b" * 40
PREDICTORS = ("GEMINI", "COPILOT", "BCO_PRIME")
DOMAINS = ("architecture", "source_defect", "provider_state")
FAMILIES = ("family-a", "family-b")
BASE = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)


def add_pair(
    model: LivingWorldModel,
    index: int,
    *,
    source_head: str = HEAD_A,
    matter_scope: str = "GLOBAL",
    resolve: bool = True,
) -> None:
    predictor = PREDICTORS[index % len(PREDICTORS)]
    domain = DOMAINS[index % len(DOMAINS)]
    family = FAMILIES[index % len(FAMILIES)]
    occurred = index % 2 == 0
    prediction_id = f"prediction-{source_head[0]}-{matter_scope}-{index}"
    prediction_at = BASE + timedelta(minutes=index * 10)
    outcome_at = prediction_at + timedelta(minutes=5)
    prediction = Prediction(
        prediction_id=prediction_id,
        predictor_id=predictor,
        domain=domain,
        event=f"event-{index}",
        probability=0.8 if occurred else 0.2,
        expected_value=0.7 if occurred else 0.3,
        expected_latency=0.2,
        expected_owner_burden=0.1,
        evidence_refs=(f"evidence:pre:{prediction_id}",),
    )
    record_prospective_prediction(
        model,
        ProspectivePredictionRecord(
            mission_id=f"mission-{index}",
            system_source_head_sha=source_head,
            mission_snapshot_digest=f"snapshot:{index}",
            predictor_source_fingerprint=family,
            predictor_version=f"{predictor.lower()}-v1",
            observed_at=prediction_at.isoformat(),
            prediction_proof_ref=f"proof:prediction:{prediction_id}",
            prediction=prediction,
            matter_scope=matter_scope,
        ),
    )
    if not resolve:
        return
    resolve_prospective_prediction(
        model,
        ProspectiveOutcomeRecord(
            prediction_id=prediction_id,
            observed_at=outcome_at.isoformat(),
            outcome_source_ref=f"runtime:{prediction_id}",
            proof_maturity=ProofMaturity.RUNTIME_READBACK,
            outcome=PredictionOutcome(
                prediction_id=prediction_id,
                occurred=occurred,
                realised_value=0.75 if occurred else 0.25,
                realised_latency=0.2,
                realised_owner_burden=0.1,
                proof_refs=(f"proof:outcome:{prediction_id}",),
            ),
            matter_scope=matter_scope,
        ),
    )


class EdpfCohortCensusTests(unittest.TestCase):
    def test_empty_journal_is_zero_state_not_fake_evidence(self) -> None:
        receipt = census_prospective_cohorts(())
        self.assertEqual(receipt.cohort_count, 0)
        self.assertEqual(receipt.total_open, 0)
        self.assertEqual(receipt.total_resolved, 0)
        self.assertEqual(receipt.count_ready_cohorts, 0)
        self.assertFalse(receipt.empirical_calibration_evaluated)
        self.assertFalse(receipt.empirical_calibration_proven)

    def test_open_prediction_counts_but_never_satisfies_real_pair_floor(self) -> None:
        model = LivingWorldModel()
        add_pair(model, 0, resolve=False)
        receipt = census_prospective_cohorts(model.export_event_log())
        cohort = receipt.cohorts[0]
        self.assertEqual(cohort.open_count, 1)
        self.assertEqual(cohort.resolved_count, 0)
        self.assertEqual(cohort.additional_resolutions_needed, 30)
        self.assertFalse(cohort.count_ready_for_shadow_court)
        self.assertIn("MINIMUM_REAL_SHADOW_PAIR_COHORT_REQUIRED", cohort.blockers)

    def test_thirty_resolved_diverse_pairs_are_count_ready_only(self) -> None:
        model = LivingWorldModel()
        for index in range(30):
            add_pair(model, index)
        receipt = census_prospective_cohorts(model.export_event_log())
        self.assertEqual(receipt.cohort_count, 1)
        self.assertEqual(receipt.total_resolved, 30)
        self.assertEqual(receipt.count_ready_cohorts, 1)
        cohort = receipt.cohorts[0]
        self.assertTrue(cohort.count_ready_for_shadow_court)
        self.assertEqual(cohort.predictor_count, 3)
        self.assertEqual(cohort.independent_source_count, 2)
        self.assertEqual(cohort.domain_count, 3)
        self.assertEqual(cohort.possible_holdout_count, 10)
        self.assertEqual(cohort.additional_resolutions_needed, 0)
        self.assertFalse(receipt.empirical_calibration_evaluated)
        self.assertFalse(receipt.empirical_calibration_proven)
        self.assertFalse(receipt.live_predictor_weight_change_authorized)
        self.assertFalse(receipt.dispatch_authorized)
        self.assertFalse(receipt.external_effect_authorized)

    def test_source_epoch_change_creates_separate_cohorts(self) -> None:
        model = LivingWorldModel()
        for index in range(15):
            add_pair(model, index, source_head=HEAD_A)
        for index in range(15, 30):
            add_pair(model, index, source_head=HEAD_B)
        receipt = census_prospective_cohorts(model.export_event_log())
        self.assertEqual(receipt.cohort_count, 2)
        self.assertEqual({cohort.source_head_sha for cohort in receipt.cohorts}, {HEAD_A, HEAD_B})
        self.assertEqual(receipt.count_ready_cohorts, 0)
        self.assertTrue(all(cohort.resolved_count == 15 for cohort in receipt.cohorts))

    def test_matter_wall_creates_separate_cohorts(self) -> None:
        model = LivingWorldModel()
        for index in range(15):
            add_pair(model, index, matter_scope="MATTER-A")
        for index in range(15, 30):
            add_pair(model, index, matter_scope="MATTER-B")
        receipt = census_prospective_cohorts(model.export_event_log())
        self.assertEqual(receipt.cohort_count, 2)
        self.assertEqual({cohort.matter_scope for cohort in receipt.cohorts}, {"MATTER-A", "MATTER-B"})
        self.assertEqual(receipt.count_ready_cohorts, 0)

    def test_post_cutoff_prediction_mutation_fails_closed(self) -> None:
        model = LivingWorldModel()
        add_pair(model, 0)
        events = copy.deepcopy(list(model.export_event_log()))
        resolved = events[-1]
        resolved["payload"]["node"]["payload"]["prediction"]["event"] = "mutated-after-cutoff"
        with self.assertRaisesRegex(ValueError, "PREDICTION_MUTATED_AFTER_CUTOFF"):
            census_prospective_cohorts(events)


if __name__ == "__main__":
    unittest.main()
