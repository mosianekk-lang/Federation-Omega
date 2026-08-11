import pytest

from evidenceops.truthgrid.falsification import AttributionFirewallError, Hypothesis, validate_personal_attribution
from evidenceops.truthgrid.truthstate import EvidenceSignal, Proposition, assess
from evidenceops.truthgrid.vnext import ClosureCandidate, CompletionVector, DecisionReadiness, TruthGridVNext, TruthState


def test_external_production_does_not_equal_internal_work():
    vector = CompletionVector(True, True, 0, 3, 0, True, True, True, True)
    assert vector.internal_complete()
    assert vector.evidence_availability() == "PRODUCTION_REQUIRED"
    assert vector.decision_readiness() == DecisionReadiness.CONDITIONAL


def test_internal_gap_blocks_completion():
    vector = CompletionVector(True, True, 1, 0, 0, True, True, True, True)
    assert not vector.internal_complete()


def test_closure_optimizer_prefers_material_recoverable_action():
    high = ClosureCandidate("A", 1, 5, 0.9, 1, 4, 1)
    low = ClosureCandidate("B", 0.5, 1, 0.3, 1, 1, 2)
    assert TruthGridVNext.rank_closure((low, high))[0].action_id == "A"


def test_external_blocker_scores_zero():
    blocked = ClosureCandidate("A", 1, 10, 1, 1, 10, 1, external_blocker=True)
    assert blocked.score() == 0


def test_account_activity_cannot_be_personally_attributed_without_identity_evidence():
    with pytest.raises(AttributionFirewallError, match="PERSONAL_ACTOR"):
        validate_personal_attribution(observed_subject="user account system activity", asserted_personal_actor="Kim")


def test_organisational_service_does_not_prove_personal_duty():
    with pytest.raises(AttributionFirewallError, match="PERSONAL_DUTY"):
        validate_personal_attribution(observed_subject="ICT service objective", asserted_personal_actor="Kim", actor_identity_source_ids=("SRC-ID",))


def test_falsification_requires_adverse_counterfactual_and_exhaustion():
    h = Hypothesis("H1", "theory", ("instruction", "date"), ("instruction", "date"), True, True, True)
    assert h.ready


def test_production_required_truthstate():
    result = assess(Proposition("P1", external_production_required=("appointment_instrument",), search_exhausted=True))
    assert result.state == TruthState.PRODUCTION_REQUIRED
    assert result.readiness == DecisionReadiness.NOT_READY


def test_confidence_ceiling_caps_derivative_summary():
    result = assess(Proposition("P1", evidence=(EvidenceSignal("S1", "DERIVATIVE_SUMMARY", True, 1.0, 1.0),)))
    assert result.ceiling == 0.75
    assert result.confidence <= 0.75


def test_strong_adverse_evidence_can_contradict():
    result = assess(Proposition("P1", evidence=(EvidenceSignal("S1", "PROVIDER_NATIVE_ORIGINAL", False, 1.0, 1.0),)))
    assert result.state == TruthState.CONTRADICTED
