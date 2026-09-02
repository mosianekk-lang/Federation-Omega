from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import Prediction, PredictionOutcome
from federation.living_state.edpf_prediction_adapter import (
    ProspectiveOutcomeRecord,
    ProspectivePredictionRecord,
    record_prospective_prediction,
    resolve_prospective_prediction,
)
from federation.living_state.edpf_predictor_projection import (
    EvidenceState,
    MissionPredictorFit,
    PredictorDefinition,
    project_empirical_profiles,
    project_request_candidates,
)
from federation.living_state.model import LivingWorldModel
from federation.living_state.types import ProofMaturity

HEAD_A = "a" * 40
HEAD_B = "b" * 40
BASE = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)


def definition(*, version: str = "predictor-v1", provider_backed: bool = False) -> PredictorDefinition:
    return PredictorDefinition(
        predictor_id="PREDICTOR_A",
        source_fingerprint="family-a",
        predictor_version=version,
        provider_backed=provider_backed,
        supported_domains=("architecture",),
    )


def fit() -> MissionPredictorFit:
    return MissionPredictorFit(
        predictor_id="PREDICTOR_A",
        domain="architecture",
        relevance=0.8,
        independence=0.9,
        expected_information_gain=0.7,
        cost=0.2,
        latency=0.2,
    )


def add_resolved(
    model: LivingWorldModel,
    index: int,
    *,
    head: str = HEAD_A,
    matter: str = "GLOBAL",
    version: str = "predictor-v1",
    correct: bool = True,
) -> None:
    prediction_id = f"prediction-{head[0]}-{matter}-{version}-{index}"
    occurred = index % 2 == 0
    probability = (0.9 if occurred else 0.1) if correct else (0.1 if occurred else 0.9)
    predicted_at = BASE + timedelta(minutes=index * 10)
    observed_at = predicted_at + timedelta(minutes=5)
    prediction = Prediction(
        prediction_id=prediction_id,
        predictor_id="PREDICTOR_A",
        domain="architecture",
        event=f"event-{index}",
        probability=probability,
        expected_value=0.8 if occurred else 0.2,
        expected_latency=0.2,
        expected_owner_burden=0.1,
        evidence_refs=(f"evidence:pre:{prediction_id}",),
    )
    record_prospective_prediction(
        model,
        ProspectivePredictionRecord(
            mission_id=f"mission-{index}",
            system_source_head_sha=head,
            mission_snapshot_digest=f"snapshot:{index}",
            predictor_source_fingerprint="family-a",
            predictor_version=version,
            observed_at=predicted_at.isoformat(),
            prediction_proof_ref=f"proof:prediction:{prediction_id}",
            prediction=prediction,
            matter_scope=matter,
        ),
    )
    resolve_prospective_prediction(
        model,
        ProspectiveOutcomeRecord(
            prediction_id=prediction_id,
            observed_at=observed_at.isoformat(),
            outcome_source_ref=f"runtime:{prediction_id}",
            proof_maturity=ProofMaturity.RUNTIME_READBACK,
            outcome=PredictionOutcome(
                prediction_id=prediction_id,
                occurred=occurred,
                realised_value=0.82 if occurred else 0.18,
                realised_latency=0.2,
                realised_owner_burden=0.1,
                proof_refs=(f"proof:outcome:{prediction_id}",),
            ),
            matter_scope=matter,
        ),
    )


class EdpfPredictorProjectionTests(unittest.TestCase):
    def test_unseen_predictor_gets_neutral_profile_not_invented_competence(self) -> None:
        projected = project_request_candidates(
            events=(),
            definitions=(definition(),),
            fits=(fit(),),
            system_source_head_sha=HEAD_A,
            matter_scope="GLOBAL",
            domain="architecture",
        )
        self.assertEqual(len(projected), 1)
        item = projected[0]
        self.assertTrue(item.neutral_fallback_used)
        self.assertEqual(item.evidence.evidence_state, EvidenceState.NEUTRAL_UNSEEN)
        self.assertEqual(item.evidence.resolved_samples, 0)
        self.assertEqual(item.evidence.empirical_trust_weight, 0.5)
        self.assertEqual(item.candidate.profile.attempts, 0)
        self.assertFalse(item.dispatch_authorized)
        self.assertFalse(item.external_effect_authorized)

    def test_resolved_prospective_pairs_build_existing_predictor_profile_math(self) -> None:
        model = LivingWorldModel()
        for index in range(5):
            add_resolved(model, index)
        profiles = project_empirical_profiles(model.export_event_log(), (definition(),))
        self.assertEqual(len(profiles), 1)
        profile = profiles[0]
        self.assertEqual(profile.resolved_samples, 5)
        self.assertEqual(profile.evidence_state, EvidenceState.THIN_PROSPECTIVE)
        self.assertGreater(profile.empirical_accuracy, 0.9)
        self.assertLess(profile.empirical_brier_score, 0.05)
        self.assertGreater(profile.empirical_trust_weight, 0.5)
        self.assertFalse(profile.calibration_positive_proven)
        self.assertFalse(profile.owner_value_proven)
        self.assertFalse(profile.live_weight_change_authorized)

    def test_source_epoch_change_resets_candidate_to_neutral(self) -> None:
        model = LivingWorldModel()
        for index in range(5):
            add_resolved(model, index, head=HEAD_A)
        projected = project_request_candidates(
            events=model.export_event_log(),
            definitions=(definition(),),
            fits=(fit(),),
            system_source_head_sha=HEAD_B,
            matter_scope="GLOBAL",
            domain="architecture",
        )
        self.assertTrue(projected[0].neutral_fallback_used)
        self.assertEqual(projected[0].candidate.profile.attempts, 0)
        self.assertEqual(projected[0].candidate.profile.trust_weight, 0.5)

    def test_matter_scope_change_resets_candidate_to_neutral(self) -> None:
        model = LivingWorldModel()
        for index in range(5):
            add_resolved(model, index, matter="MATTER-A")
        projected = project_request_candidates(
            events=model.export_event_log(),
            definitions=(definition(),),
            fits=(fit(),),
            system_source_head_sha=HEAD_A,
            matter_scope="MATTER-B",
            domain="architecture",
        )
        self.assertTrue(projected[0].neutral_fallback_used)
        self.assertEqual(projected[0].candidate.profile.attempts, 0)

    def test_predictor_version_change_does_not_inherit_old_version_trust(self) -> None:
        model = LivingWorldModel()
        for index in range(5):
            add_resolved(model, index, version="predictor-v1")
        projected = project_request_candidates(
            events=model.export_event_log(),
            definitions=(definition(version="predictor-v2"),),
            fits=(fit(),),
            system_source_head_sha=HEAD_A,
            matter_scope="GLOBAL",
            domain="architecture",
        )
        self.assertTrue(projected[0].neutral_fallback_used)
        self.assertEqual(projected[0].evidence.predictor_version, "predictor-v2")
        self.assertEqual(projected[0].candidate.profile.attempts, 0)

    def test_thirty_samples_mean_count_eligible_not_calibration_proven(self) -> None:
        model = LivingWorldModel()
        for index in range(30):
            add_resolved(model, index)
        profiles = project_empirical_profiles(model.export_event_log(), (definition(),))
        profile = profiles[0]
        self.assertEqual(profile.evidence_state, EvidenceState.SHADOW_COUNT_ELIGIBLE)
        self.assertEqual(profile.resolved_samples, 30)
        self.assertFalse(profile.calibration_positive_proven)
        self.assertFalse(profile.owner_value_proven)
        self.assertFalse(profile.live_weight_change_authorized)

    def test_bad_historical_predictions_reduce_empirical_trust(self) -> None:
        model = LivingWorldModel()
        for index in range(20):
            add_resolved(model, index, correct=False)
        projected = project_request_candidates(
            events=model.export_event_log(),
            definitions=(definition(),),
            fits=(fit(),),
            system_source_head_sha=HEAD_A,
            matter_scope="GLOBAL",
            domain="architecture",
        )
        self.assertFalse(projected[0].neutral_fallback_used)
        self.assertLess(projected[0].evidence.empirical_trust_weight, 0.5)
        self.assertLess(projected[0].candidate.profile.trust_weight, 0.5)

    def test_missing_mission_fit_does_not_fabricate_fit_scores(self) -> None:
        projected = project_request_candidates(
            events=(),
            definitions=(definition(),),
            fits=(),
            system_source_head_sha=HEAD_A,
            matter_scope="GLOBAL",
            domain="architecture",
        )
        self.assertEqual(projected, ())

    def test_duplicate_definition_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "DUPLICATE_DEFINITION"):
            project_empirical_profiles((), (definition(), definition()))


if __name__ == "__main__":
    unittest.main()
