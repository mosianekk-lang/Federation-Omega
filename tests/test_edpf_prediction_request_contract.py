from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import PredictorProfile
from federation.living_state.edpf_prediction_adapter import OPEN_STATE
from federation.living_state.edpf_prediction_request import (
    PROBABILITY_BASIS,
    PredictionQuestion,
    PredictionResponseEnvelope,
    PredictorCandidate,
    RequestState,
    compile_prediction_request_set,
    response_to_ingress_envelope,
)
from federation.living_state.ingress import EDPF_PREDICTION_EVENT, LivingStateIngress
from federation.living_state.store import LivingStateStore
from federation.living_state.types import ProofMaturity

HEAD = "a" * 40


def question(**overrides) -> PredictionQuestion:
    values = dict(
        request_id="request:1",
        mission_id="mission:1",
        system_source_head_sha=HEAD,
        mission_snapshot_digest="snapshot:mission:1:v1",
        domain="architecture",
        event="candidate-route-closes",
        outcome_criterion="The admitted candidate reaches its defined verified closure state.",
        created_at="2026-09-02T10:00:00+00:00",
        prediction_deadline_at="2026-09-02T10:10:00+00:00",
        outcome_not_before_at="2026-09-02T10:20:00+00:00",
        outcome_deadline_at="2026-09-03T10:20:00+00:00",
        evidence_refs=("evidence:1",),
        context={"route_count": 2},
    )
    values.update(overrides)
    return PredictionQuestion(**values)


def candidate(
    predictor_id: str,
    source: str,
    *,
    attempts: int = 20,
    correct: int = 16,
    brier_sum: float = 2.0,
    absolute_error_sum: float = 4.0,
    relevance: float = 0.8,
    provider_backed: bool = False,
) -> PredictorCandidate:
    return PredictorCandidate(
        predictor_id=predictor_id,
        source_fingerprint=source,
        predictor_version=f"{predictor_id.lower()}-v1",
        profile=PredictorProfile(
            predictor_id=predictor_id,
            domain="architecture",
            attempts=attempts,
            brier_sum=brier_sum,
            absolute_error_sum=absolute_error_sum,
            resolved_correct=correct,
        ),
        relevance=relevance,
        independence=0.9,
        expected_information_gain=0.8,
        cost=0.2,
        latency=0.2,
        provider_backed=provider_backed,
    )


def response(packet, *, proof_maturity: ProofMaturity | None = None, **overrides) -> PredictionResponseEnvelope:
    values = dict(
        response_id="response:1",
        request_id=packet.request_id,
        packet_id=packet.packet_id,
        request_receipt_sha256=packet.receipt_sha256,
        predictor_id=packet.predictor_id,
        predictor_source_fingerprint=packet.predictor_source_fingerprint,
        predictor_version=packet.predictor_version,
        observed_at="2026-09-02T10:05:00+00:00",
        probability=0.78,
        expected_value=0.70,
        expected_latency=0.20,
        expected_owner_burden=0.10,
        evidence_refs=("evidence:response:1",),
        proof_ref="proof:prediction-response:1",
        proof_maturity=proof_maturity or (ProofMaturity.PROVIDER_READBACK if packet.provider_backed else ProofMaturity.SOURCE_READBACK),
        probability_basis=PROBABILITY_BASIS,
    )
    values.update(overrides)
    return PredictionResponseEnvelope(**values)


class EdpfPredictionRequestContractTests(unittest.TestCase):
    def test_request_selects_strong_candidates_with_independent_sources(self) -> None:
        candidates = (
            candidate("GEMINI", "family-google", provider_backed=True),
            candidate("COPILOT", "family-microsoft", correct=15, brier_sum=2.5),
            candidate("BCO_PRIME", "family-internal", correct=12, brier_sum=4.0),
        )
        result = compile_prediction_request_set(question(), candidates, max_predictors=2)
        self.assertEqual(result.state, RequestState.REQUEST_CONTRACT_READY)
        self.assertEqual(result.selected_count, 2)
        self.assertEqual(result.independent_source_count, 2)
        self.assertFalse(result.provider_call_authorized)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.external_effect_authorized)
        self.assertTrue(all(not packet.provider_call_authorized for packet in result.packets))

    def test_single_source_family_is_held_even_with_multiple_predictor_names(self) -> None:
        candidates = (
            candidate("GEMINI", "shared-family"),
            candidate("COPILOT", "shared-family"),
            candidate("BCO_PRIME", "shared-family"),
        )
        result = compile_prediction_request_set(question(), candidates, max_predictors=3)
        self.assertEqual(result.state, RequestState.HOLD_INDEPENDENT_SOURCE_DIVERSITY)
        self.assertEqual(result.independent_source_count, 1)
        self.assertIn("INDEPENDENT_PREDICTOR_SOURCE_DIVERSITY_REQUIRED", result.blockers)
        self.assertFalse(result.dispatch_authorized)

    def test_request_refuses_credential_like_context(self) -> None:
        with self.assertRaisesRegex(ValueError, "CREDENTIAL_LIKE_KEY"):
            question(context={"api_key": "fixture"}).validate()

    def test_request_temporal_contract_prevents_outcome_window_leakage(self) -> None:
        with self.assertRaisesRegex(ValueError, "TEMPORAL_CONTRACT_INVALID"):
            question(prediction_deadline_at="2026-09-02T10:30:00+00:00").validate()

    def test_response_must_attest_explicit_probability_not_score_transform(self) -> None:
        packet = compile_prediction_request_set(
            question(),
            (candidate("BCO_PRIME", "family-internal"), candidate("COPILOT", "family-microsoft")),
            max_predictors=2,
        ).packets[0]
        bad = response(packet, probability_basis="ROUTE_SCORE_NORMALIZED")
        with self.assertRaisesRegex(ValueError, "EXPLICIT_PROBABILITY_ATTESTATION_REQUIRED"):
            bad.validate(packet)
        self.assertIn("Do not transform policy-market robust scores", packet.request_text)

    def test_provider_backed_response_requires_provider_native_readback(self) -> None:
        request_set = compile_prediction_request_set(
            question(),
            (candidate("GEMINI", "family-google", provider_backed=True), candidate("BCO_PRIME", "family-internal")),
            max_predictors=2,
        )
        packet = next(item for item in request_set.packets if item.predictor_id == "GEMINI")
        self.assertTrue(packet.provider_backed)
        weak = response(packet, proof_maturity=ProofMaturity.SOURCE_READBACK)
        with self.assertRaisesRegex(ValueError, "PROVIDER_NATIVE_READBACK_REQUIRED"):
            weak.validate(packet)

    def test_response_is_bound_to_exact_request_receipt(self) -> None:
        packet = compile_prediction_request_set(
            question(),
            (candidate("BCO_PRIME", "family-internal"), candidate("COPILOT", "family-microsoft")),
            max_predictors=2,
        ).packets[0]
        bad = response(packet, request_receipt_sha256="sha256:" + "0" * 64)
        with self.assertRaisesRegex(ValueError, "REQUEST_RECEIPT_MISMATCH"):
            bad.validate(packet)

    def test_valid_response_converts_to_admitted_ingress_without_dispatching(self) -> None:
        request_set = compile_prediction_request_set(
            question(),
            (candidate("BCO_PRIME", "family-internal"), candidate("COPILOT", "family-microsoft")),
            max_predictors=2,
        )
        packet = next(item for item in request_set.packets if item.predictor_id == "BCO_PRIME")
        envelope = response_to_ingress_envelope(packet, response(packet))
        self.assertEqual(envelope.event_class, EDPF_PREDICTION_EVENT)
        self.assertEqual(envelope.state, OPEN_STATE)
        self.assertEqual(envelope.payload["probability"], 0.78)
        self.assertEqual(envelope.payload["system_source_head_sha"], HEAD)
        self.assertEqual(envelope.proof_maturity, ProofMaturity.SOURCE_READBACK)
        self.assertEqual(set(envelope.payload["evidence_refs"]), {"evidence:1", "evidence:response:1"})

        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td) / "living.sqlite3") as store:
                receipt = LivingStateIngress(store).ingest(envelope)
                self.assertTrue(receipt.readback_verified)
                model = store.restore()
                self.assertEqual(model.event_count, 1)
                self.assertEqual(model.external_effects, 0)

    def test_response_after_prediction_deadline_fails_closed(self) -> None:
        packet = compile_prediction_request_set(
            question(),
            (candidate("BCO_PRIME", "family-internal"), candidate("COPILOT", "family-microsoft")),
            max_predictors=2,
        ).packets[0]
        late = response(packet, observed_at="2026-09-02T10:11:00+00:00")
        with self.assertRaisesRegex(ValueError, "OUTSIDE_PREDICTION_WINDOW"):
            late.validate(packet)


if __name__ == "__main__":
    unittest.main()
