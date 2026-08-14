from datetime import date, timedelta

import pytest

from evidenceops.lex_omega.lex_omega import (
    AuthorityRecord,
    AuthorityState,
    AuthoritySupportClaim,
    ClaimLawEvidenceTriangle,
    CounselRole,
    CounselSubmission,
    IndependentCounselPanel,
    LegalProposition,
    LegalPropositionLedger,
    LexOmegaCouncil,
    MaturityLevel,
    MaturityTracker,
    OutcomeClass,
    OutcomeLearningEvent,
    PropositionState,
    ReleaseState,
    TriangleState,
)


def current_authority(authority_id="AUTH-1", text="material proposition", support_key="material"):
    return AuthorityRecord(
        authority_id=authority_id,
        citation="Test Authority",
        source_ref="primary://authority",
        verified_on=date.today(),
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        revalidation_days=30,
        supported_claims=(AuthoritySupportClaim(support_key, text, "primary://authority#pinpoint"),),
    )


def verified_proposition(text="material proposition", authority_ids=("AUTH-1",), support_key="material"):
    return LegalProposition(
        text,
        authority_ids,
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key=support_key,
    )


def counsel(conclusion="supported"):
    return [
        CounselSubmission(CounselRole.PRIMARY_ANALYST, conclusion),
        CounselSubmission(CounselRole.EMPLOYER_RED_TEAM, conclusion),
        CounselSubmission(CounselRole.NEUTRAL_DECISION_MAKER, conclusion),
    ]


def test_legal_proposition_id_is_stable_across_whitespace_and_authority_order():
    p1 = LegalProposition("  This   is LAW ", ("B", "A"), matter_id="M1", legal_route="ULP", support_key="rule")
    p2 = LegalProposition("this is law", ("A", "B"), matter_id="M1", legal_route="ULP", support_key="rule")
    assert p1.proposition_id == p2.proposition_id


def test_support_key_changes_proposition_identity():
    p1 = LegalProposition("this is law", ("A",), support_key="rule-a")
    p2 = LegalProposition("this is law", ("A",), support_key="rule-b")
    assert p1.proposition_id != p2.proposition_id


def test_authority_revalidation_expires_without_rewriting_history():
    record = AuthorityRecord(
        authority_id="A",
        citation="Authority",
        source_ref="primary://a",
        verified_on=date.today() - timedelta(days=31),
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        revalidation_days=30,
    )
    assert record.status_on(date.today()) == AuthorityState.RECHECK_REQUIRED


def test_authority_later_treatment_check_is_required():
    record = AuthorityRecord(
        authority_id="A",
        citation="Authority",
        source_ref="primary://a",
        verified_on=date.today(),
        later_treatment_checked=False,
        state=AuthorityState.CURRENT_VERIFIED,
    )
    assert record.status_on(date.today()) == AuthorityState.RECHECK_REQUIRED


def test_claim_law_evidence_triangle_closes_only_with_all_three_sides():
    closed = ClaimLawEvidenceTriangle("E1", "LP-1", "CL-1", ("SRC-1",))
    missing = ClaimLawEvidenceTriangle("E2", "LP-2", "CL-2", ())
    assert closed.state == TriangleState.CLOSED
    assert missing.state == TriangleState.MISSING_EVIDENCE


def test_independent_counsel_panel_is_sealed_until_all_roles_submit():
    panel = IndependentCounselPanel()
    panel.submit(CounselSubmission(CounselRole.PRIMARY_ANALYST, "A"))
    panel.submit(CounselSubmission(CounselRole.EMPLOYER_RED_TEAM, "B"))
    with pytest.raises(ValueError):
        panel.integrate()
    panel.submit(CounselSubmission(CounselRole.NEUTRAL_DECISION_MAKER, "C"))
    integrated = panel.integrate()
    assert len(integrated) == 3


def test_outcome_learning_does_not_convert_success_into_doctrine():
    event = OutcomeLearningEvent("argument succeeded", strategy_succeeded=True)
    assert event.classification == OutcomeClass.STRATEGIC_SUCCESS
    assert event.may_auto_promote_doctrine is False


def test_outcome_learning_distinguishes_evidence_failure():
    event = OutcomeLearningEvent("proof failed", proof_deficiency=True)
    assert event.classification == OutcomeClass.EVIDENCE_FAILURE


def test_maturity_promotion_requires_proof_and_is_sequential():
    tracker = MaturityTracker()
    with pytest.raises(ValueError):
        tracker.promote(MaturityLevel.SHADOW_VALIDATED, ["proof"])
    with pytest.raises(ValueError):
        tracker.promote(MaturityLevel.DETERMINISTIC_TESTED, [])
    tracker.promote(MaturityLevel.DETERMINISTIC_TESTED, ["TEST-001"])
    assert tracker.level == MaturityLevel.DETERMINISTIC_TESTED


def test_jfrie_veto_is_fail_closed():
    ledger = LegalPropositionLedger()
    council = LexOmegaCouncil(ledger)
    result = council.evaluate(
        on_date=date.today(),
        proposition_ids=(),
        triangles=(),
        counsel_submissions=(),
        outcome_events=(),
        jfrie_status="HOLD_FOR_AUTHORITY",
    )
    assert result.release_state == ReleaseState.DO_NOT_FILE


def test_stale_authority_holds_release_for_authority():
    ledger = LegalPropositionLedger()
    ledger.add_authority(
        AuthorityRecord(
            authority_id="A",
            citation="Authority",
            source_ref="primary://a",
            verified_on=date.today() - timedelta(days=60),
            later_treatment_checked=True,
            state=AuthorityState.CURRENT_VERIFIED,
            revalidation_days=30,
            supported_claims=(AuthoritySupportClaim("material", "material proposition", "primary://a#pin"),),
        )
    )
    proposition = verified_proposition(authority_ids=("A",))
    proposition_id = ledger.add_proposition(proposition)
    council = LexOmegaCouncil(ledger)
    result = council.evaluate(
        on_date=date.today(),
        proposition_ids=(proposition_id,),
        triangles=(ClaimLawEvidenceTriangle("E1", proposition_id, "CL-1", ("SRC-1",)),),
        counsel_submissions=counsel(),
        outcome_events=(),
        jfrie_status="PASS",
    )
    assert result.release_state == ReleaseState.HOLD_FOR_AUTHORITY


def test_missing_evidence_side_holds_release_for_source():
    ledger = LegalPropositionLedger()
    ledger.add_authority(current_authority())
    proposition_id = ledger.add_proposition(verified_proposition())
    council = LexOmegaCouncil(ledger)
    result = council.evaluate(
        on_date=date.today(),
        proposition_ids=(proposition_id,),
        triangles=(ClaimLawEvidenceTriangle("E1", proposition_id, "CL-1", ()),),
        counsel_submissions=counsel(),
        outcome_events=(),
        jfrie_status="PASS",
    )
    assert result.release_state == ReleaseState.HOLD_FOR_SOURCE


def test_counsel_disagreement_is_preserved_as_limitation():
    ledger = LegalPropositionLedger()
    ledger.add_authority(current_authority())
    proposition_id = ledger.add_proposition(verified_proposition())
    submissions = [
        CounselSubmission(CounselRole.PRIMARY_ANALYST, "route A"),
        CounselSubmission(CounselRole.EMPLOYER_RED_TEAM, "route fails"),
        CounselSubmission(CounselRole.NEUTRAL_DECISION_MAKER, "route A with limits"),
    ]
    council = LexOmegaCouncil(ledger)
    result = council.evaluate(
        on_date=date.today(),
        proposition_ids=(proposition_id,),
        triangles=(ClaimLawEvidenceTriangle("E1", proposition_id, "CL-1", ("SRC-1",)),),
        counsel_submissions=submissions,
        outcome_events=(),
        jfrie_status="PASS",
    )
    assert result.release_state == ReleaseState.PASS_WITH_LIMITATIONS
    assert len(result.counsel_conflicts) == 3


def test_verified_law_without_explicit_support_binding_fails_closed():
    ledger = LegalPropositionLedger()
    ledger.add_authority(current_authority())
    proposition = LegalProposition(
        "material proposition",
        ("AUTH-1",),
        proposition_state=PropositionState.VERIFIED_LAW,
    )
    proposition_id = ledger.add_proposition(proposition)
    assert ledger.proposition_authority_state(proposition_id, date.today()) == AuthorityState.SEMANTIC_SUPPORT_MISSING


def test_current_authority_with_false_mutation_fails_semantic_support():
    ledger = LegalPropositionLedger()
    ledger.add_authority(current_authority(text="unfair labour practice referrals are made within 90 days", support_key="ulp-period"))
    proposition = LegalProposition(
        "unfair labour practice referrals are made within 30 days",
        ("AUTH-1",),
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key="ulp-period",
    )
    proposition_id = ledger.add_proposition(proposition)
    assert ledger.proposition_authority_state(proposition_id, date.today()) == AuthorityState.SEMANTIC_SUPPORT_MISSING


def test_correct_bound_proposition_passes_semantic_support():
    text = "unfair labour practice referrals are made within 90 days"
    ledger = LegalPropositionLedger()
    ledger.add_authority(current_authority(text=text, support_key="ulp-period"))
    proposition = LegalProposition(
        text,
        ("AUTH-1",),
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key="ulp-period",
    )
    proposition_id = ledger.add_proposition(proposition)
    assert ledger.proposition_authority_state(proposition_id, date.today()) == AuthorityState.CURRENT_VERIFIED
