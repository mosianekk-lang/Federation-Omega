from evidenceops.caseforge.capability_decision import (
    CapabilityDecisionRequest,
    CapabilityScope,
    CapabilityState,
    GateDecision,
    TerminalClaim,
)
from evidenceops.caseforge.scientia import EpistemicState, Hypothesis, ScientificObservation
from evidenceops.truthgrid.vnext import CompletionVector

from evidenceops.lex_omega.alignment import EvidenceOpsLegalAlignmentGate, MainlineMaturityStage
from evidenceops.lex_omega.lex_omega import MaturityLevel, ReleaseState


def completion(*, external_gaps: int = 0, contradictions: int = 0, writer: bool = True) -> CompletionVector:
    return CompletionVector(
        accessible_corpus_exhausted=True,
        material_sources_processed=True,
        executable_internal_gap_count=0,
        external_production_gap_count=external_gaps,
        material_contradiction_count=contradictions,
        adversarial_review_passed=True,
        live_writer_enforcement_passed=writer,
        regression_passed=True,
        dashboard_live_generated=True,
    )


def scientific_inputs():
    observations = (
        ScientificObservation("O1", "record exists", EpistemicState.VERIFIED_FACT, ("SRC-1",)),
    )
    hypotheses = (
        Hypothesis("H1", "route A", ("P1",), ("F1",)),
        Hypothesis("H2", "route B", ("P2",), ("F2",)),
    )
    return observations, hypotheses


def test_jfrie_remains_fail_closed_after_alignment():
    result = EvidenceOpsLegalAlignmentGate().evaluate(jfrie_status="HOLD_FOR_AUTHORITY")
    assert result.legal_release_state is ReleaseState.DO_NOT_FILE
    assert "JFRIE_FAIL_CLOSED" in result.reason_codes


def test_truthgrid_not_ready_holds_for_source():
    result = EvidenceOpsLegalAlignmentGate().evaluate(
        jfrie_status="PASS",
        truthgrid_completion=completion(contradictions=1),
        require_truthgrid=True,
    )
    assert result.legal_release_state is ReleaseState.HOLD_FOR_SOURCE
    assert result.truthgrid_readiness == "NOT_READY"


def test_truthgrid_external_production_gap_is_conditional_not_complete():
    result = EvidenceOpsLegalAlignmentGate().evaluate(
        jfrie_status="PASS",
        truthgrid_completion=completion(external_gaps=1),
        require_truthgrid=True,
    )
    assert result.legal_release_state is ReleaseState.PASS_WITH_LIMITATIONS
    assert result.truthgrid_readiness == "CONDITIONAL"
    assert result.evolution_promotion_allowed is False


def test_scientia_requires_competing_falsifiable_hypotheses():
    observations = (
        ScientificObservation("O1", "record exists", EpistemicState.VERIFIED_FACT, ("SRC-1",)),
    )
    result = EvidenceOpsLegalAlignmentGate().evaluate(
        jfrie_status="PASS",
        observations=observations,
        hypotheses=(Hypothesis("H1", "only theory", ("P1",), ("F1",)),),
        require_scientia=True,
    )
    assert result.legal_release_state is ReleaseState.LEGAL_RESEARCH_REQUIRED
    assert result.scientia_status == "SCIENTIFIC_DESIGN_INVALID"


def test_scientia_and_truthgrid_can_pass_together():
    observations, hypotheses = scientific_inputs()
    result = EvidenceOpsLegalAlignmentGate().evaluate(
        jfrie_status="PASS",
        truthgrid_completion=completion(),
        require_truthgrid=True,
        observations=observations,
        hypotheses=hypotheses,
        require_scientia=True,
    )
    assert result.legal_release_state is ReleaseState.PASS
    assert result.truthgrid_readiness == "READY"
    assert result.scientia_status == "SCIENTIFIC_DESIGN_VALID"
    assert result.evolution_promotion_allowed is True


def test_capability_done_claim_is_denied_without_objective_complete_and_readback():
    request = CapabilityDecisionRequest(
        objective="align legal stack",
        claim=TerminalClaim.DONE,
        scope=CapabilityScope.USER_CANONICAL_SYSTEM,
        state=CapabilityState.ROUTE_EXECUTED,
        internal_executable_dependencies=1,
    )
    result = EvidenceOpsLegalAlignmentGate().evaluate(
        jfrie_status="PASS",
        capability_request=request,
    )
    assert result.terminal_claim_allowed is False
    assert result.capability_decision is not None
    assert result.capability_decision.decision is GateDecision.DENY_TERMINAL_CLAIM


def test_provider_blind_claim_requires_provider_native_readback():
    observations, hypotheses = scientific_inputs()
    result = EvidenceOpsLegalAlignmentGate().evaluate(
        jfrie_status="PASS",
        truthgrid_completion=completion(),
        require_truthgrid=True,
        observations=observations,
        hypotheses=hypotheses,
        require_scientia=True,
        require_provider_blind=True,
        blind_execution_state="DETERMINISTIC_TEST_ONLY",
    )
    assert result.evolution_promotion_allowed is False
    assert result.blind_validation_state == "PROVIDER_BLIND_READBACK_REQUIRED"


def test_legacy_maturity_maps_without_silent_promotion():
    gate = EvidenceOpsLegalAlignmentGate()
    assert gate.map_legacy_maturity(MaturityLevel.DESIGN_ONLY) is MainlineMaturityStage.DESIGNED
    assert gate.map_legacy_maturity(MaturityLevel.WORKFLOW_VERIFIED) is MainlineMaturityStage.LIMITED_WORKFLOW_VERIFIED
