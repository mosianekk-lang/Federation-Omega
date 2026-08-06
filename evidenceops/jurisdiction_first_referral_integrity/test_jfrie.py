from evidenceops.jurisdiction_first_referral_integrity.jfrie import (
    AuthorityClass,
    CauseElement,
    Decision,
    LegalLabel,
    ReferralInput,
    evaluate,
    release_allowed,
)


def base_referral(**overrides):
    data = dict(
        instrument="LRA Form 7.11",
        forum="CCMA",
        cause_of_action="unfair labour practice: disciplinary action short of dismissal",
        cause_authority_ref="LRA s186(2)(b)",
        cause_authority_class=AuthorityClass.STATUTE,
        specific_act_or_omission="issued a written warning",
        dispute_date="2026-04-22",
        filing_date="2026-05-13",
        filing_period_rule="LRA s191(1)(b)(ii): 90 days",
        maturity_basis="written warning already issued",
        elements=(
            CauseElement("disciplinary action short of dismissal", ("SRC-WARNING",), "LRA s186(2)(b)"),
            CauseElement("unfairness", ("SRC-RESPONSE", "SRC-POLICY"), "LRA s186(2)(b)"),
        ),
        remedy="removal of the warning and competent just-and-equitable relief",
        remedy_authority_ref="LRA s193(4)",
        narrative="The employer issued a warning which the employee alleges was unfair.",
        labels=(),
        mixed_causes=(),
        source_refs=("SRC-WARNING", "SRC-RESPONSE", "SRC-POLICY"),
        form_category="unfair labour practice",
        separate_matter_controls=(),
    )
    data.update(overrides)
    return ReferralInput(**data)


def test_clean_referral_passes():
    result = evaluate(base_referral())
    assert result.decision == Decision.PASS
    assert release_allowed(result)
    assert result.cause_sentence


def test_ai_term_used_as_jurisdictional_category_fails_closed():
    result = evaluate(base_referral(labels=(
        LegalLabel(
            "protective referral",
            AuthorityClass.AI_TERM,
            used_as_jurisdictional_category=True,
        ),
    )))
    assert result.release_blocked
    assert result.decision == Decision.REFRAME
    assert not release_allowed(result)


def test_ai_term_may_be_quoted_historically_without_becoming_authority():
    result = evaluate(base_referral(labels=(
        LegalLabel(
            "protective referral",
            AuthorityClass.PARTY_LABEL,
            used_as_jurisdictional_category=False,
        ),
    )))
    assert not result.release_blocked
    assert "protective referral [PARTY_LABEL]" in result.semantic_laundering_flags


def test_missing_statutory_cause_blocks_release():
    result = evaluate(base_referral(
        cause_authority_ref=None,
        cause_authority_class=AuthorityClass.UNVERIFIED,
    ))
    assert result.release_blocked
    assert result.decision == Decision.LEGAL_RESEARCH_REQUIRED


def test_mixed_causes_force_separation_review():
    result = evaluate(base_referral(mixed_causes=("ULP", "PDA", "grievance")))
    assert result.decision == Decision.SEPARATE_CAUSES
    assert not result.release_blocked
