from __future__ import annotations

from dataclasses import replace
import unittest

from benchmarking.cfbe_omega.edpf_shadow_prediction_court_v1 import EvidenceMode
from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    Prediction,
    PredictionOutcome,
)
from federation.living_state.edpf_prediction_adapter import (
    OPEN_STATE,
    RESOLVED_TRUE_STATE,
    ProspectiveOutcomeRecord,
    ProspectivePredictionRecord,
    compile_real_shadow_pairs,
    record_prospective_prediction,
    resolve_prospective_prediction,
)
from federation.living_state.model import LivingWorldModel
from federation.living_state.types import NodeKind, ProofMaturity

SOURCE_HEAD = "a" * 40


def prediction_record(*, prediction_id: str = "pred-1", observed_at: str = "2026-09-02T10:00:00+00:00") -> ProspectivePredictionRecord:
    return ProspectivePredictionRecord(
        mission_id="mission-1",
        system_source_head_sha=SOURCE_HEAD,
        mission_snapshot_digest="snapshot:mission-1:v1",
        predictor_source_fingerprint="gemini-family:2.5",
        predictor_version="gemini-2.5-flash",
        observed_at=observed_at,
        prediction_proof_ref="receipt:prediction:1",
        prediction=Prediction(
            prediction_id=prediction_id,
            predictor_id="GEMINI",
            domain="architecture",
            event="route-a-will-close",
            probability=0.80,
            expected_value=0.70,
            expected_latency=0.25,
            expected_owner_burden=0.10,
            evidence_refs=("evidence:pre:1", "evidence:pre:2"),
        ),
    )


def outcome_record(*, prediction_id: str = "pred-1", observed_at: str = "2026-09-02T11:00:00+00:00") -> ProspectiveOutcomeRecord:
    return ProspectiveOutcomeRecord(
        prediction_id=prediction_id,
        observed_at=observed_at,
        outcome_source_ref="runtime:mission-1",
        proof_maturity=ProofMaturity.RUNTIME_READBACK,
        outcome=PredictionOutcome(
            prediction_id=prediction_id,
            occurred=True,
            realised_value=0.75,
            realised_latency=0.20,
            realised_owner_burden=0.05,
            proof_refs=("proof:outcome:1", "proof:outcome:2"),
        ),
    )


class EdpfLivingStatePredictionAdapterTests(unittest.TestCase):
    def test_prediction_is_existing_living_state_experiment_with_zero_effects(self) -> None:
        model = LivingWorldModel()
        event = record_prospective_prediction(model, prediction_record())
        self.assertEqual(event.event_type, "NODE_OBSERVED")
        self.assertEqual(model.event_count, 1)
        self.assertEqual(model.external_effects, 0)
        node = next(iter(model.current_nodes().values()))
        self.assertEqual(node.kind, NodeKind.EXPERIMENT)
        self.assertEqual(node.state, OPEN_STATE)
        self.assertTrue(node.payload["prospective_capture"])
        self.assertEqual(node.payload["mission_snapshot_digest"], "snapshot:mission-1:v1")
        self.assertFalse(node.external_effect)

    def test_duplicate_prediction_cutoff_fails_closed(self) -> None:
        model = LivingWorldModel()
        record = prediction_record()
        record_prospective_prediction(model, record)
        with self.assertRaisesRegex(ValueError, "ALREADY_RECORDED"):
            record_prospective_prediction(model, record)

    def test_resolution_requires_later_time_and_separate_proof(self) -> None:
        model = LivingWorldModel()
        record_prospective_prediction(model, prediction_record())
        with self.assertRaisesRegex(ValueError, "TEMPORAL_LEAKAGE"):
            resolve_prospective_prediction(model, outcome_record(observed_at="2026-09-02T09:59:00+00:00"))

        leaked = outcome_record()
        leaked = replace(
            leaked,
            outcome=replace(leaked.outcome, proof_refs=("evidence:pre:1",)),
        )
        with self.assertRaisesRegex(ValueError, "OUTCOME_PROOF_LEAKED"):
            resolve_prospective_prediction(model, leaked)

    def test_declared_outcome_proof_is_too_weak(self) -> None:
        weak = replace(outcome_record(), proof_maturity=ProofMaturity.DECLARED)
        with self.assertRaisesRegex(ValueError, "OUTCOME_PROOF_TOO_WEAK"):
            weak.validate()

    def test_resolution_scores_prediction_without_route_weight_or_provider_effect(self) -> None:
        model = LivingWorldModel()
        record_prospective_prediction(model, prediction_record())
        resolve_prospective_prediction(model, outcome_record())
        node = next(iter(model.current_nodes().values()))
        self.assertEqual(node.state, RESOLVED_TRUE_STATE)
        resolution = node.payload["resolution"]
        self.assertAlmostEqual(resolution["brier_score"], 0.04)
        self.assertAlmostEqual(resolution["absolute_probability_error"], 0.20)
        self.assertAlmostEqual(resolution["absolute_value_error"], 0.05)
        self.assertEqual(model.external_effects, 0)
        self.assertEqual(model.event_count, 2)

    def test_event_journal_replays_semantically_after_prediction_resolution(self) -> None:
        model = LivingWorldModel()
        record_prospective_prediction(model, prediction_record())
        resolve_prospective_prediction(model, outcome_record())
        events = model.export_event_log()
        replayed = LivingWorldModel.replay(events)
        self.assertTrue(replayed.verify_event_chain())
        self.assertEqual(replayed.event_head_digest, model.event_head_digest)
        self.assertEqual(next(iter(replayed.current_nodes().values())).state, RESOLVED_TRUE_STATE)

    def test_compiler_emits_real_shadow_pair_only_after_resolution(self) -> None:
        model = LivingWorldModel()
        record_prospective_prediction(model, prediction_record())
        self.assertEqual(compile_real_shadow_pairs(model.export_event_log()), ())
        resolve_prospective_prediction(model, outcome_record())
        pairs = compile_real_shadow_pairs(model.export_event_log())
        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(pair.evidence_mode, EvidenceMode.REAL_MISSION)
        self.assertEqual(pair.source_head_sha, SOURCE_HEAD)
        self.assertEqual(pair.prediction.predictor_id, "GEMINI")
        self.assertLess(pair.prediction_cutoff_epoch, pair.outcome_observed_epoch)
        self.assertTrue(set(pair.pre_outcome_evidence_refs).isdisjoint(pair.outcome_proof_refs))

    def test_multiple_mission_snapshots_share_one_fixed_predictor_source_head(self) -> None:
        model = LivingWorldModel()
        first = prediction_record(prediction_id="pred-1", observed_at="2026-09-02T10:00:00+00:00")
        second = replace(
            prediction_record(prediction_id="pred-2", observed_at="2026-09-02T10:05:00+00:00"),
            mission_id="mission-2",
            mission_snapshot_digest="snapshot:mission-2:v9",
            prediction_proof_ref="receipt:prediction:2",
        )
        record_prospective_prediction(model, first)
        record_prospective_prediction(model, second)
        resolve_prospective_prediction(model, outcome_record(prediction_id="pred-1", observed_at="2026-09-02T11:00:00+00:00"))
        second_outcome = replace(
            outcome_record(prediction_id="pred-2", observed_at="2026-09-02T11:05:00+00:00"),
            outcome_source_ref="runtime:mission-2",
            outcome=replace(outcome_record(prediction_id="pred-2").outcome, prediction_id="pred-2", proof_refs=("proof:outcome:3",)),
        )
        resolve_prospective_prediction(model, second_outcome)
        pairs = compile_real_shadow_pairs(model.export_event_log())
        self.assertEqual(len(pairs), 2)
        self.assertEqual({pair.source_head_sha for pair in pairs}, {SOURCE_HEAD})
        self.assertEqual({pair.mission_id for pair in pairs}, {"mission-1", "mission-2"})


if __name__ == "__main__":
    unittest.main()
