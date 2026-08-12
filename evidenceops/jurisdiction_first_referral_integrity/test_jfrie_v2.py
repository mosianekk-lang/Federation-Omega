from evidenceops.jurisdiction_first_referral_integrity.jfrie import (
    AuthorityClass,
    CauseElement,
    LegalLabel,
    ReferralInput,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v11 import AuditSignals
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2 import (
    HashScope,
    V2Decision,
    V2ExecutionContext,
    V2Signals,
    evaluate_v2,
    release_allowed_v2,
)


def referral(**overrides):
    data = dict(
        instrument="Statutory referral form",
        forum="Statutory labour forum",
        cause_of_action="unfair labour practice: disciplinary action short of dismissal",
        cause_authority_ref="statutory closed-list provision",
        cause_authority_class=AuthorityClass.STATUTE,
        specific_act_or_omission="issued a written warning",
        dispute_date="2026-04-22",
        filing_date="2026-05-13",
        filing_period_rule="statutory filing period",
        maturity_basis="warning already issued",
        elements=(
            CauseElement("disciplinary action short of dismissal", ("SRC-1",), "statutory closed-list provision"),
            CauseElement("unfairness", ("SRC-2",), "statutory closed-list provision"),
        ),
        remedy="removal of warning and competent relief",
        remedy_authority_ref="statutory remedy provision",
        narrative="A written warning is challenged as unfair.",
        source_refs=("SRC-1", "SRC-2"),
        form_category="unfair labour practice",
    )
    data.update(overrides)
    return ReferralInput(**data)


def audit(**overrides):
    data = dict(
        originating_instrument_verified=True,
        dispute_date_basis="date warning was issued",
        closed_list_category_required=True,
        closed_list_category_explicit=True,
        remedy_matches_cause=True,
    )
    data.update(overrides)
    return AuditSignals(**data)


def execution(**overrides):
    data = dict(
        object_id="OBJ-TEST-001",
        source_ids=("SRC-1", "SRC-2"),
        executed_at="2026-08-12T02:00:00+02:00",
        node_version_current=True,
        node_readback_complete=True,
        self_tests_pass=True,
        independent_second_pass_state="NOT_REQUIRED",
    )
    data.update(overrides)
    return V2ExecutionContext(**data)


def run(signals=None, *, r=None, a=None, e=None):
    return evaluate_v2(r or referral(), a or audit(), signals or V2Signals(), e or execution())


def test_clean_foundation_release_passes_and_emits_receipts():
    result = run()
    assert result.decision == V2Decision.PASS
    assert release_allowed_v2(result)
    assert result.receipts
    assert all(receipt.object_id == "OBJ-TEST-001" for receipt in result.receipts)
    assert all(receipt.source_ids for receipt in result.receipts)
    assert result.evidence_note["executable_v2_parity"] == "FOUNDATION_ONLY_NOT_FULL_PARITY"


def test_t001_ai_term_cannot_become_jurisdictional_category():
    r = referral(labels=(
        LegalLabel(
            "protective referral",
            AuthorityClass.AI_TERM,
            used_as_jurisdictional_category=True,
        ),
    ))
    result = run(r=r)
    assert result.release_blocked
    assert result.decision == V2Decision.REFRAME


def test_t002_repeated_derivative_support_collapses_to_independent_count():
    result = run(V2Signals(apparent_support_count=10, independent_source_count=1))
    assert "C007_DERIVATIVE_SOURCE_DETECTION" in result.detector_hits
    assert result.decision == V2Decision.PASS_WITH_LIMITATIONS
    assert release_allowed_v2(result)


def test_t003_later_dispute_date_drift_blocks_release():
    result = run(V2Signals(
        originating_dispute_date="2026-04-22",
        derivative_dispute_date="2026-05-01",
    ))
    assert "D003_DATE_DRIFT" in result.detector_hits
    assert result.decision == V2Decision.REFRAME
    assert result.release_blocked


def test_t004_transmission_does_not_prove_knowledge():
    result = run(V2Signals(
        communication_sent=True,
        knowledge_claim_material=True,
        reading_or_knowledge_proven=False,
    ))
    assert "D005_TRANSMISSION_TO_KNOWLEDGE" in result.detector_hits
    assert result.decision == V2Decision.HOLD_FOR_SOURCE


def test_t005_silence_does_not_prove_agreement():
    result = run(V2Signals(silence_treated_as_agreement=True))
    assert "D006_SILENCE_TO_AGREEMENT" in result.detector_hits
    assert result.decision == V2Decision.REFRAME


def test_t006_excluded_matter_cannot_reappear_from_copied_history():
    result = run(V2Signals(excluded_matter_reintroduced=True))
    assert "D016_EXCLUDED_MATTER_RESURRECTION" in result.detector_hits
    assert result.decision == V2Decision.QUARANTINED


def test_t007_primary_source_invalidation_quarantines_pre_release_claim():
    result = run(V2Signals(primary_source_invalidates_material_claim=True))
    assert "C075_AUTOMATIC_DOWNGRADE" in result.detector_hits
    assert result.decision == V2Decision.QUARANTINED


def test_t008_stale_or_unread_node_requires_resync():
    result = run(e=execution(node_readback_complete=False))
    assert "D017_STALE_NODE" in result.detector_hits
    assert result.decision == V2Decision.RESYNC_REQUIRED


def test_t009_missing_referenced_attachment_holds_for_source():
    result = run(V2Signals(referenced_attachment_count=2, verified_attachment_count=1))
    assert "D013_MISSING_ATTACHMENT" in result.detector_hits
    assert result.decision == V2Decision.HOLD_FOR_SOURCE


def test_t010_quarantined_claim_reappearing_by_family_is_blocked():
    result = run(V2Signals(quarantined_claim_reappears=True))
    assert "D019_QUARANTINED_REUSE" in result.detector_hits
    assert result.decision == V2Decision.QUARANTINED


def test_t011_generated_detector_cannot_self_promote_without_shadow_and_fp_gate():
    held = run(V2Signals(generated_detector_candidate=True))
    assert "C098_AUTOMATED_CAPABILITY_PROMOTION_HELD" in held.detector_hits
    assert not held.detector_promotion_allowed
    assert held.decision == V2Decision.PASS_WITH_LIMITATIONS

    passed = run(V2Signals(
        generated_detector_candidate=True,
        detector_shadow_passed=True,
        detector_false_positive_rate_acceptable=True,
    ))
    assert passed.detector_promotion_allowed


def test_t012_invalidated_source_after_release_requires_recall():
    result = run(V2Signals(
        primary_source_invalidates_material_claim=True,
        release_previously_occurred=True,
    ))
    assert result.decision == V2Decision.RECALL_REQUIRED
    assert result.release_blocked


def test_ea07_hash_must_have_explicit_scope():
    result = run(V2Signals(hash_present=True, hash_scope=None))
    assert "EA07_UNSCOPED_HASH" in result.detector_hits
    assert result.decision == V2Decision.HOLD_FOR_SOURCE

    scoped = run(V2Signals(hash_present=True, hash_scope=HashScope.ACQUISITION_BYTES))
    assert "EA07_UNSCOPED_HASH" not in scoped.detector_hits


def test_ea08_role_is_not_authority():
    result = run(V2Signals(
        material_authority_claim=True,
        role_and_authority_separately_sourced=False,
    ))
    assert "EA08_ROLE_AUTHORITY_CONFLATION" in result.detector_hits
    assert result.decision == V2Decision.HOLD_FOR_AUTHORITY


def test_v11_hard_release_veto_is_preserved():
    result = run(a=audit(administrative_processing_used_as_jurisdiction=True))
    assert result.base.release_blocked
    assert result.release_blocked
    assert result.decision == V2Decision.REFRAME


def test_external_effect_and_authority_expansion_are_rejected():
    try:
        run(e=execution(external_effect=True))
    except ValueError as exc:
        assert "cannot expand authority" in str(exc)
    else:
        raise AssertionError("external-effect execution context should be rejected")

    try:
        run(e=execution(authority_ceiling="A2"))
    except ValueError as exc:
        assert "cannot expand authority" in str(exc)
    else:
        raise AssertionError("authority expansion should be rejected")
