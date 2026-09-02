import unittest
from dataclasses import replace

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import EvidenceCandidate
from federation.living_state.edpf_forecast_opportunity import (
    SCORE_BASIS,
    ForecastSignal,
    compile_forecast_opportunities,
)

HEAD = "55166f0a05befa1d0947cdf12662fd741b251a0f"
SNAP = "sha256:mission-snapshot-001"


def candidate(
    candidate_id: str,
    *,
    flip: float = 0.8,
    uncertainty_reduction: float = 0.8,
    cost: float = 0.1,
    risk: float = 0.1,
    freshness: float = 0.8,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        candidate_id=candidate_id,
        resolves_claim_ids=("claim-runtime",),
        decision_flip_probability=flip,
        uncertainty_reduction=uncertainty_reduction,
        acquisition_cost=cost,
        acquisition_risk=risk,
        freshness_gain=freshness,
    )


def signal(
    signal_id: str,
    *,
    event: str | None = None,
    evidence_candidate: EvidenceCandidate | None = None,
    observability: float = 0.9,
) -> ForecastSignal:
    event_text = event or f"event-{signal_id} occurs"
    return ForecastSignal(
        signal_id=signal_id,
        mission_id="mission-edpf-forecast",
        system_source_head_sha=HEAD,
        mission_snapshot_digest=SNAP,
        domain="runtime",
        event=event_text,
        outcome_criterion=f"provider receipt for {event_text} exists",
        created_at="2026-09-02T12:00:00+00:00",
        prediction_deadline_at="2026-09-02T12:10:00+00:00",
        outcome_not_before_at="2026-09-02T12:11:00+00:00",
        outcome_deadline_at="2026-09-02T13:00:00+00:00",
        evidence_candidate=evidence_candidate or candidate(f"candidate-{signal_id}"),
        outcome_observability=observability,
        evidence_refs=("evidence:pre-outcome",),
        context={"route": "read-only"},
        matter_scope="GLOBAL",
        sensitivity="PUBLIC_SAFE",
    )


class ForecastOpportunityCompilerTests(unittest.TestCase):
    def test_ranks_by_canonical_edpf_information_value(self) -> None:
        high = signal("high", evidence_candidate=candidate("candidate-high"))
        low = signal(
            "low",
            evidence_candidate=candidate(
                "candidate-low",
                flip=0.5,
                uncertainty_reduction=0.5,
                cost=0.1,
                risk=0.1,
                freshness=0.5,
            ),
        )
        result = compile_forecast_opportunities(
            (low, high),
            max_questions=1,
            min_information_value=0.0,
        )
        self.assertEqual(result.selected_count, 1)
        self.assertEqual(result.opportunities[0].signal_id, "high")
        self.assertEqual(result.opportunities[0].score, high.evidence_candidate.information_value())
        self.assertEqual(result.opportunities[0].score_basis, SCORE_BASIS)
        self.assertIn("QUESTION_BUDGET_EXHAUSTED", result.held[0].reason_codes)

    def test_collapses_semantic_duplicates_using_canonical_strength(self) -> None:
        weak = signal(
            "weak",
            event="same-event",
            evidence_candidate=candidate(
                "candidate-weak",
                flip=0.4,
                uncertainty_reduction=0.4,
                cost=0.2,
                risk=0.2,
                freshness=0.4,
            ),
        )
        strong = signal("strong", event="same-event", evidence_candidate=candidate("candidate-strong"))
        weak = replace(weak, outcome_criterion="same criterion")
        strong = replace(strong, outcome_criterion="same criterion")
        result = compile_forecast_opportunities(
            (weak, strong),
            max_questions=2,
            min_information_value=-1.0,
        )
        self.assertEqual(result.unique_candidate_count, 1)
        self.assertEqual(result.opportunities[0].signal_id, "strong")
        self.assertTrue(
            any(item.signal_id == "weak" and "SEMANTIC_DUPLICATE" in item.reason_codes for item in result.held)
        )

    def test_below_canonical_information_floor_is_held(self) -> None:
        low = signal(
            "low",
            evidence_candidate=candidate(
                "candidate-low",
                flip=0.1,
                uncertainty_reduction=0.1,
                cost=0.9,
                risk=0.9,
                freshness=0.1,
            ),
        )
        result = compile_forecast_opportunities((low,), min_information_value=0.05)
        self.assertEqual(result.selected_count, 0)
        self.assertEqual(result.held[0].reason_codes, ("BELOW_CANONICAL_INFORMATION_VALUE_FLOOR",))

    def test_low_outcome_observability_is_held_even_when_information_value_is_high(self) -> None:
        result = compile_forecast_opportunities(
            (signal("opaque", observability=0.2),),
            min_information_value=0.0,
            min_outcome_observability=0.5,
        )
        self.assertEqual(result.selected_count, 0)
        self.assertEqual(result.held[0].reason_codes, ("OUTCOME_OBSERVABILITY_BELOW_FLOOR",))

    def test_reuses_prediction_question_temporal_validation(self) -> None:
        bad = replace(
            signal("bad"),
            prediction_deadline_at="2026-09-02T12:20:00+00:00",
            outcome_not_before_at="2026-09-02T12:10:00+00:00",
        )
        with self.assertRaisesRegex(ValueError, "TEMPORAL_CONTRACT_INVALID"):
            compile_forecast_opportunities((bad,))

    def test_compiler_has_no_local_information_value_model_or_event_probability(self) -> None:
        source = signal("safe")
        result = compile_forecast_opportunities((source,))
        self.assertEqual(result.score_basis, SCORE_BASIS)
        self.assertFalse(result.local_information_value_model_present)
        self.assertFalse(result.opportunity_scores_are_forecast_probabilities)
        self.assertFalse(result.provider_call_authorized)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.external_effect_authorized)
        self.assertFalse(result.live_predictor_weight_change_authorized)
        self.assertFalse(result.stable_self_promotion_allowed)
        question = result.opportunities[0].question
        self.assertFalse(hasattr(question, "probability"))
        self.assertFalse(question.context["information_value_is_event_probability"])
        self.assertEqual(question.context["edpf_canonical_information_value"], source.evidence_candidate.information_value())

    def test_duplicate_signal_ids_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SIGNAL_ID"):
            compile_forecast_opportunities((signal("dup"), signal("dup", evidence_candidate=candidate("candidate-dup-2"))))

    def test_duplicate_evidence_candidate_ids_fail_closed(self) -> None:
        shared = candidate("shared-candidate")
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EVIDENCE_CANDIDATE_ID"):
            compile_forecast_opportunities((signal("one", evidence_candidate=shared), signal("two", evidence_candidate=shared)))


if __name__ == "__main__":
    unittest.main()
