from evidenceops.jurisdiction_first_referral_integrity.jfrie import (
    AuthorityClass,
    CauseElement,
    Decision,
    ReferralInput,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v11 import (
    AuditSignals,
    evaluate_v11,
    release_allowed_v11,
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


def signals(**overrides):
    data = dict(
        originating_instrument_verified=True,
        dispute_date_basis="date warning was issued",
        closed_list_category_required=True,
        closed_list_category_explicit=True,
        remedy_matches_cause=True,
    )
    data.update(overrides)
    return AuditSignals(**data)


def test_v11_clean_release_passes():
    result = evaluate_v11(referral(), signals())
    assert result.decision == Decision.PASS
    assert release_allowed_v11(result)


def test_original_form_controls_over_derivative_summary():
    result = evaluate_v11(referral(), signals(
        derivative_summary_conflicts=("later report describes a different checkbox",),
    ))
    assert result.decision == Decision.PASS_WITH_LIMITATIONS
    assert not result.release_blocked


def test_unverified_original_with_conflicting_derivative_fails():
    result = evaluate_v11(referral(), signals(
        originating_instrument_verified=False,
        derivative_summary_conflicts=("later report conflicts with alleged original fields",),
    ))
    assert result.release_blocked
    assert not release_allowed_v11(result)


def test_administrative_acceptance_does_not_create_jurisdiction():
    result = evaluate_v11(referral(), signals(administrative_processing_used_as_jurisdiction=True))
    assert result.release_blocked
    assert result.decision == Decision.REFRAME


def test_closed_list_category_cannot_be_implicit():
    result = evaluate_v11(referral(), signals(closed_list_category_explicit=False))
    assert result.release_blocked
    assert result.decision == Decision.REFRAME


def test_dispute_date_requires_reasoned_basis():
    result = evaluate_v11(referral(), signals(dispute_date_basis=None))
    assert result.release_blocked


def test_direct_agreement_enforcement_requires_agreement_and_authority():
    result = evaluate_v11(referral(), signals(
        direct_agreement_enforcement=True,
        agreement_fact_refs=("SRC-AGREEMENT",),
        agreement_authority_refs=(),
    ))
    assert result.release_blocked
    assert result.decision == Decision.HOLD_FOR_AUTHORITY


def test_procedural_certificate_cannot_prove_merits():
    result = evaluate_v11(referral(), signals(certificate_or_ruling_used_as_merits_proof=True))
    assert result.release_blocked


def test_mixed_legal_lanes_need_separate_authority_mapping():
    r = referral(mixed_causes=("ULP", "DISCRIMINATION", "UNION_PROTECTION"))
    result = evaluate_v11(r, signals(mixed_lane_authority={"ULP": "statutory ULP provision"}))
    assert result.release_blocked
    assert result.decision == Decision.SEPARATE_CAUSES


def test_secondary_questionnaire_flag_does_not_replace_primary_type():
    result = evaluate_v11(referral(), signals(secondary_questionnaire_flags=("discrimination questionnaire marked yes",)))
    assert result.decision == Decision.PASS_WITH_LIMITATIONS
    assert not result.release_blocked


def test_remedy_must_match_cause_and_forum():
    result = evaluate_v11(referral(), signals(remedy_matches_cause=False))
    assert result.release_blocked
