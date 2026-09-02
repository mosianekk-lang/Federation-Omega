from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from federation.living_state.edpf_cohort_census import census_prospective_cohorts
from federation.living_state.edpf_prediction_adapter import (
    OPEN_STATE,
    RESOLVED_TRUE_STATE,
    compile_real_shadow_pairs,
)
from federation.living_state.ingress import (
    EDPF_OUTCOME_EVENT,
    EDPF_PREDICTION_EVENT,
    IngressEnvelope,
    LivingStateIngress,
)
from federation.living_state.store import LivingStateStore
from federation.living_state.types import NodeKind, ProofMaturity

SOURCE_HEAD = "a" * 40


def prediction_envelope(*, event_id: str = "evt:prediction:1") -> IngressEnvelope:
    return IngressEnvelope(
        event_id=event_id,
        event_class=EDPF_PREDICTION_EVENT,
        source_ref="predictor:GEMINI",
        observed_at="2026-09-02T10:00:00+00:00",
        proof_ref="receipt:prediction:1",
        proof_maturity=ProofMaturity.SOURCE_READBACK,
        object_id="prediction:1",
        object_kind=NodeKind.EXPERIMENT.value,
        state=OPEN_STATE,
        payload={
            "mission_id": "mission:1",
            "system_source_head_sha": SOURCE_HEAD,
            "mission_snapshot_digest": "snapshot:mission:1:v1",
            "predictor_source_fingerprint": "gemini-family:2.5",
            "predictor_version": "gemini-2.5-flash",
            "predictor_id": "GEMINI",
            "domain": "architecture",
            "event": "candidate-route-closes",
            "probability": 0.80,
            "expected_value": 0.70,
            "expected_latency": 0.20,
            "expected_owner_burden": 0.10,
            "evidence_refs": ("evidence:pre:1",),
        },
    )


def outcome_envelope(*, event_id: str = "evt:outcome:1") -> IngressEnvelope:
    return IngressEnvelope(
        event_id=event_id,
        event_class=EDPF_OUTCOME_EVENT,
        source_ref="runtime:mission:1",
        observed_at="2026-09-02T11:00:00+00:00",
        proof_ref="receipt:outcome:1",
        proof_maturity=ProofMaturity.RUNTIME_READBACK,
        object_id="prediction:1",
        object_kind=NodeKind.EXPERIMENT.value,
        state=RESOLVED_TRUE_STATE,
        payload={
            "occurred": True,
            "realised_value": 0.75,
            "realised_latency": 0.18,
            "realised_owner_burden": 0.08,
            "proof_refs": ("proof:outcome:1",),
        },
    )


class EdpfLivingStateIngressBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = LivingStateStore(Path(self.temp.name) / "living.sqlite3")
        self.ingress = LivingStateIngress(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_prediction_is_transactionally_persisted_and_semantically_read_back(self) -> None:
        receipt = self.ingress.ingest(prediction_envelope())
        self.assertEqual(receipt.disposition, "APPLIED")
        self.assertTrue(receipt.readback_verified)
        self.assertEqual(receipt.external_effects, 0)
        model = self.store.restore()
        node = next(iter(model.current_nodes().values()))
        self.assertEqual(node.state, OPEN_STATE)
        self.assertEqual(node.payload["prediction"]["probability"], 0.80)
        self.assertEqual(node.provenance.confidence, 1.0)
        self.assertEqual(model.external_effects, 0)

    def test_same_ingress_event_is_idempotent(self) -> None:
        envelope = prediction_envelope()
        first = self.ingress.ingest(envelope)
        second = self.ingress.ingest(envelope)
        self.assertEqual(first.disposition, "APPLIED")
        self.assertEqual(second.disposition, "DUPLICATE_IDEMPOTENT")
        self.assertEqual(self.store.restore().event_count, 1)

    def test_later_outcome_resolves_same_prediction_and_compiles_real_pair(self) -> None:
        self.ingress.ingest(prediction_envelope())
        receipt = self.ingress.ingest(outcome_envelope())
        self.assertTrue(receipt.readback_verified)
        model = self.store.restore()
        node = next(iter(model.current_nodes().values()))
        self.assertEqual(node.state, RESOLVED_TRUE_STATE)
        self.assertAlmostEqual(node.payload["resolution"]["brier_score"], 0.04)
        pairs = compile_real_shadow_pairs(model.export_event_log())
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].prediction.predictor_id, "GEMINI")
        self.assertEqual(pairs[0].source_head_sha, SOURCE_HEAD)
        self.assertLess(pairs[0].prediction_cutoff_epoch, pairs[0].outcome_observed_epoch)
        census = census_prospective_cohorts(model.export_event_log())
        self.assertEqual(census.total_resolved, 1)
        self.assertFalse(census.cohorts[0].count_ready_for_shadow_court)
        self.assertFalse(census.empirical_calibration_proven)

    def test_prediction_requires_explicit_probability_payload(self) -> None:
        envelope = prediction_envelope()
        payload = dict(envelope.payload)
        del payload["probability"]
        broken = IngressEnvelope(**{**envelope.__dict__, "payload": payload})
        with self.assertRaisesRegex(ValueError, "EDPF_PREDICTION_PAYLOAD_REQUIRED"):
            self.ingress.ingest(broken)

    def test_prediction_requires_source_readback_or_stronger_proof(self) -> None:
        envelope = prediction_envelope()
        weak = IngressEnvelope(**{**envelope.__dict__, "proof_maturity": ProofMaturity.DECLARED})
        with self.assertRaisesRegex(ValueError, "prediction ingress proof maturity too weak"):
            self.ingress.ingest(weak)
        self.assertEqual(self.store.restore().event_count, 0)

    def test_prediction_state_and_kind_must_match_edpf_contract(self) -> None:
        envelope = prediction_envelope()
        with self.assertRaisesRegex(ValueError, "prediction ingress state mismatch"):
            self.ingress.ingest(IngressEnvelope(**{**envelope.__dict__, "state": "READY"}))
        with self.assertRaisesRegex(ValueError, "requires EXPERIMENT"):
            self.ingress.ingest(IngressEnvelope(**{**envelope.__dict__, "object_kind": NodeKind.MISSION.value}))

    def test_outcome_boolean_and_state_must_agree(self) -> None:
        self.ingress.ingest(prediction_envelope())
        envelope = outcome_envelope()
        payload = dict(envelope.payload)
        payload["occurred"] = False
        mismatch = IngressEnvelope(**{**envelope.__dict__, "payload": payload})
        with self.assertRaisesRegex(ValueError, "outcome ingress state mismatch"):
            self.ingress.ingest(mismatch)

    def test_outcome_cannot_arrive_before_prediction(self) -> None:
        with self.assertRaisesRegex(ValueError, "OPEN_PREDICTION_REQUIRED"):
            self.ingress.ingest(outcome_envelope())


if __name__ == "__main__":
    unittest.main()
