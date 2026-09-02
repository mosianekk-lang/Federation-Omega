import unittest

from federation.living_state.edpf_forecast_opportunity import (
    ForecastSignal,
    compile_forecast_opportunities,
)

HEAD = "01b987a642ab3b87b2bd515429857b4dd74958f2"
SNAP = "sha256:mission-snapshot-001"


def signal(
    signal_id: str,
    *,
    event: str | None = None,
    uncertainty: float = 0.8,
    flip: float = 0.8,
    impact: float = 0.8,
    observability: float = 0.9,
    cost: float = 0.1,
    burden: float = 0.1,
) -> ForecastSignal:
    return ForecastSignal(
        signal_id=signal_id,
        mission_id="mission-edpf-forecast",
        system_source_head_sha=HEAD,
        mission_snapshot_digest=SNAP,
        domain="runtime",
        event=event or f"event-{signal_id} occurs",
        outcome_criterion=f"provider receipt for {event or signal_id} exists",
        created_at="2026-09-02T12:00:00+00:00",
        prediction_deadline_at="2026-09-02T12:10:00+00:00",
        outcome_not_before_at="2026-09-02T12:11:00+00:00",
        outcome_deadline_at="2026-09-02T13:00:00+00:00",
        uncertainty=uncertainty,
        decision_flip_probability=flip,
        decision_impact=impact,
        observability=observability,
        acquisition_cost=cost,
        owner_burden=burden,
        evidence_refs=("evidence:pre-outcome",),
        context={"route": "read-only"},
        matter_scope="GLOBAL",
        sensitivity="PUBLIC_SAFE",
    )


class ForecastOpportunityCompilerTests(unittest.TestCase):
    def test_ranks_high_information_signal_first(self) -> None:
        high = signal("high")
        low = signal("low", uncertainty=0.3, flip=0.2, impact=0.2, observability=0.5, cost=0.4, burden=0.4)
        result = compile_forecast_opportunities((low, high), max_questions=1, min_score=0.1)
        self.assertEqual(result.selected_count, 1)
        self.assertEqual(result.opportunities[0].signal_id, "high")
        self.assertIn("QUESTION_BUDGET_EXHAUSTED", result.held[0].reason_codes)

    def test_collapses_semantic_duplicates(self) -> None:
        weak = signal("weak", event="same-event", uncertainty=0.4, flip=0.4, impact=0.4)
        strong = signal("strong", event="same-event", uncertainty=0.9, flip=0.9, impact=0.9)
        # Match the outcome criterion as well so the semantic keys are identical.
        weak = ForecastSignal(**{**weak.__dict__, "outcome_criterion": "same criterion"}) if hasattr(weak, "__dict__") else ForecastSignal(
            signal_id=weak.signal_id, mission_id=weak.mission_id, system_source_head_sha=weak.system_source_head_sha,
            mission_snapshot_digest=weak.mission_snapshot_digest, domain=weak.domain, event=weak.event,
            outcome_criterion="same criterion", created_at=weak.created_at, prediction_deadline_at=weak.prediction_deadline_at,
            outcome_not_before_at=weak.outcome_not_before_at, outcome_deadline_at=weak.outcome_deadline_at,
            uncertainty=weak.uncertainty, decision_flip_probability=weak.decision_flip_probability,
            decision_impact=weak.decision_impact, observability=weak.observability, acquisition_cost=weak.acquisition_cost,
            owner_burden=weak.owner_burden, evidence_refs=weak.evidence_refs, context=weak.context,
            matter_scope=weak.matter_scope, sensitivity=weak.sensitivity)
        strong = ForecastSignal(
            signal_id=strong.signal_id, mission_id=strong.mission_id, system_source_head_sha=strong.system_source_head_sha,
            mission_snapshot_digest=strong.mission_snapshot_digest, domain=strong.domain, event=strong.event,
            outcome_criterion="same criterion", created_at=strong.created_at, prediction_deadline_at=strong.prediction_deadline_at,
            outcome_not_before_at=strong.outcome_not_before_at, outcome_deadline_at=strong.outcome_deadline_at,
            uncertainty=strong.uncertainty, decision_flip_probability=strong.decision_flip_probability,
            decision_impact=strong.decision_impact, observability=strong.observability, acquisition_cost=strong.acquisition_cost,
            owner_burden=strong.owner_burden, evidence_refs=strong.evidence_refs, context=strong.context,
            matter_scope=strong.matter_scope, sensitivity=strong.sensitivity)
        result = compile_forecast_opportunities((weak, strong), max_questions=2, min_score=0.0)
        self.assertEqual(result.unique_candidate_count, 1)
        self.assertEqual(result.opportunities[0].signal_id, "strong")
        self.assertTrue(any(item.signal_id == "weak" and "SEMANTIC_DUPLICATE" in item.reason_codes for item in result.held))

    def test_below_floor_is_held(self) -> None:
        result = compile_forecast_opportunities(
            (signal("low", uncertainty=0.1, flip=0.1, impact=0.1, observability=0.1, cost=0.5, burden=0.5),),
            min_score=0.2,
        )
        self.assertEqual(result.selected_count, 0)
        self.assertEqual(result.held[0].reason_codes, ("BELOW_INFORMATION_VALUE_FLOOR",))

    def test_reuses_prediction_question_temporal_validation(self) -> None:
        bad = signal("bad")
        bad = ForecastSignal(
            signal_id=bad.signal_id, mission_id=bad.mission_id, system_source_head_sha=bad.system_source_head_sha,
            mission_snapshot_digest=bad.mission_snapshot_digest, domain=bad.domain, event=bad.event,
            outcome_criterion=bad.outcome_criterion, created_at=bad.created_at,
            prediction_deadline_at="2026-09-02T12:20:00+00:00",
            outcome_not_before_at="2026-09-02T12:10:00+00:00", outcome_deadline_at=bad.outcome_deadline_at,
            uncertainty=bad.uncertainty, decision_flip_probability=bad.decision_flip_probability,
            decision_impact=bad.decision_impact, observability=bad.observability, acquisition_cost=bad.acquisition_cost,
            owner_burden=bad.owner_burden, evidence_refs=bad.evidence_refs, context=bad.context,
            matter_scope=bad.matter_scope, sensitivity=bad.sensitivity)
        with self.assertRaisesRegex(ValueError, "TEMPORAL_CONTRACT_INVALID"):
            compile_forecast_opportunities((bad,))

    def test_compiler_never_authorizes_or_invents_probability(self) -> None:
        result = compile_forecast_opportunities((signal("safe"),))
        self.assertFalse(result.opportunity_scores_are_forecast_probabilities)
        self.assertFalse(result.provider_call_authorized)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.external_effect_authorized)
        self.assertFalse(result.live_predictor_weight_change_authorized)
        self.assertFalse(result.stable_self_promotion_allowed)
        question = result.opportunities[0].question
        self.assertFalse(hasattr(question, "probability"))

    def test_duplicate_signal_ids_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SIGNAL_ID"):
            compile_forecast_opportunities((signal("dup"), signal("dup")))


if __name__ == "__main__":
    unittest.main()
