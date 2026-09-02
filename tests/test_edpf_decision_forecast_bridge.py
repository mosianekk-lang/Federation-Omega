import unittest
from dataclasses import replace

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    DecisionState,
    EpistemicDecisionReceipt,
    EvidenceCandidate,
)
from federation.living_state.edpf_decision_forecast_bridge import (
    BridgeState,
    DecisionForecastContext,
    ForecastOutcomeContract,
    compile_decision_forecast,
)

HEAD = "d78954342cc6b3bf1d3fa6cec151ec2b8a532b87"
SNAP = "sha256:decision-forecast-snapshot"


def evidence(candidate_id: str = "evidence-1", *, claim: str = "claim-1") -> EvidenceCandidate:
    return EvidenceCandidate(
        candidate_id=candidate_id,
        resolves_claim_ids=(claim,),
        decision_flip_probability=0.8,
        uncertainty_reduction=0.8,
        acquisition_cost=0.1,
        acquisition_risk=0.1,
        freshness_gain=0.8,
    )


def receipt(
    *,
    state: DecisionState = DecisionState.SEEK_EVIDENCE,
    next_id: str | None = "evidence-1",
    source_version: str = HEAD,
) -> EpistemicDecisionReceipt:
    return EpistemicDecisionReceipt(
        schema="SOVARA_EDPF_V1",
        cycle_id="cycle-1",
        source_version=source_version,
        claim_ids=("claim-1",),
        ranked_option_ids=("route-a", "route-b"),
        option_scores=(("route-a", 0.4), ("route-b", 0.39)),
        state=state,
        selected_option_id=None if state is DecisionState.SEEK_EVIDENCE else "route-a",
        next_evidence_candidate_id=next_id,
        uncertainty=0.8,
        independent_challenger_required=True,
        independent_challenger_satisfied=True,
        dispatch_authorized=False,
        external_effect_authorized=False,
        stable_self_promotion_allowed=False,
        reason_codes=("DECISION_SENSITIVE_UNCERTAINTY",),
        receipt_sha256="a" * 64,
    )


def context(*, source_head: str = HEAD) -> DecisionForecastContext:
    return DecisionForecastContext(
        mission_id="mission-1",
        system_source_head_sha=source_head,
        mission_snapshot_digest=SNAP,
        domain="runtime",
        created_at="2026-09-02T13:05:00+00:00",
        matter_scope="GLOBAL",
        sensitivity="PUBLIC_SAFE",
        context={"route_class": "read-only"},
    )


def contract(*, candidate_id: str = "evidence-1", observability: float = 0.9) -> ForecastOutcomeContract:
    return ForecastOutcomeContract(
        evidence_candidate_id=candidate_id,
        event="Airlock completes successfully",
        outcome_criterion="provider-native workflow conclusion equals success",
        prediction_deadline_at="2026-09-02T13:10:00+00:00",
        outcome_not_before_at="2026-09-02T13:11:00+00:00",
        outcome_deadline_at="2026-09-02T14:00:00+00:00",
        outcome_observability=observability,
        evidence_refs=("evidence:pre-outcome",),
        observability_basis_refs=("proof:workflow-readback-contract",),
        context={"workflow": "Federation Omega Airlock"},
    )


class DecisionForecastBridgeTests(unittest.TestCase):
    def test_seek_evidence_compiles_exact_canonical_candidate(self) -> None:
        item = evidence()
        result = compile_decision_forecast(
            receipt=receipt(),
            evidence_candidates=(item,),
            outcome_contracts=(contract(),),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.FORECAST_QUESTION_READY)
        self.assertEqual(result.selected_evidence_candidate_id, item.candidate_id)
        self.assertEqual(result.opportunity_set.selected_count, 1)
        opportunity = result.opportunity_set.opportunities[0]
        self.assertEqual(opportunity.score, item.information_value())
        self.assertEqual(opportunity.question.event, "Airlock completes successfully")
        self.assertEqual(opportunity.question.context["edpf_next_evidence_candidate_id"], item.candidate_id)

    def test_non_seek_evidence_decision_holds(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(state=DecisionState.DECIDE, next_id=None),
            evidence_candidates=(evidence(),),
            outcome_contracts=(contract(),),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.HOLD)
        self.assertEqual(result.reason_codes, ("DECISION_NOT_SEEKING_EVIDENCE",))

    def test_source_epoch_mismatch_holds(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(source_version="b" * 40),
            evidence_candidates=(evidence(),),
            outcome_contracts=(contract(),),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.HOLD)
        self.assertEqual(result.reason_codes, ("SOURCE_EPOCH_MISMATCH",))

    def test_missing_canonical_candidate_holds(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(),
            evidence_candidates=(evidence("other"),),
            outcome_contracts=(contract(),),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.HOLD)
        self.assertEqual(result.reason_codes, ("CANONICAL_EVIDENCE_CANDIDATE_NOT_SUPPLIED",))

    def test_claim_binding_mismatch_holds(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(),
            evidence_candidates=(evidence(claim="claim-other"),),
            outcome_contracts=(contract(),),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.HOLD)
        self.assertEqual(result.reason_codes, ("EVIDENCE_CANDIDATE_DECISION_CLAIM_BINDING_MISMATCH",))

    def test_missing_measurable_outcome_contract_holds(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(),
            evidence_candidates=(evidence(),),
            outcome_contracts=(),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.HOLD)
        self.assertEqual(result.reason_codes, ("MEASURABLE_OUTCOME_CONTRACT_REQUIRED",))

    def test_low_outcome_observability_holds_via_forecast_compiler(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(),
            evidence_candidates=(evidence(),),
            outcome_contracts=(contract(observability=0.2),),
            context=context(),
        )
        self.assertEqual(result.state, BridgeState.HOLD)
        self.assertEqual(result.reason_codes, ("OUTCOME_OBSERVABILITY_BELOW_FLOOR",))

    def test_observability_must_have_evidence_basis(self) -> None:
        bad = replace(contract(), observability_basis_refs=())
        with self.assertRaisesRegex(ValueError, "OBSERVABILITY_BASIS_REQUIRED"):
            compile_decision_forecast(
                receipt=receipt(),
                evidence_candidates=(evidence(),),
                outcome_contracts=(bad,),
                context=context(),
            )

    def test_bridge_never_generates_probability_or_authority(self) -> None:
        result = compile_decision_forecast(
            receipt=receipt(),
            evidence_candidates=(evidence(),),
            outcome_contracts=(contract(),),
            context=context(),
        )
        self.assertFalse(result.forecast_probability_generated)
        self.assertFalse(result.provider_call_authorized)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.external_effect_authorized)
        self.assertFalse(result.live_predictor_weight_change_authorized)
        self.assertFalse(result.stable_self_promotion_allowed)
        self.assertFalse(hasattr(result.opportunity_set.opportunities[0].question, "probability"))

    def test_duplicate_candidates_and_contracts_fail_closed(self) -> None:
        item = evidence()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EVIDENCE_CANDIDATE_ID"):
            compile_decision_forecast(
                receipt=receipt(),
                evidence_candidates=(item, item),
                outcome_contracts=(contract(),),
                context=context(),
            )
        c = contract()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OUTCOME_CONTRACT_ID"):
            compile_decision_forecast(
                receipt=receipt(),
                evidence_candidates=(item,),
                outcome_contracts=(c, c),
                context=context(),
            )


if __name__ == "__main__":
    unittest.main()
