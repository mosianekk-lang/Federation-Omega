from datetime import date, timedelta

from evidenceops.lex_omega.lex_omega import (
    AuthorityLifecycle,
    AuthorityRecord,
    AuthorityState,
    AuthoritySupportClaim,
    LegalProposition,
    LegalPropositionLedger,
    PropositionState,
)


ON_DATE = date(2026, 8, 14)
TEXT_90 = "unfair labour practice referrals are made within 90 days"


def _current_record(
    authority_id="AUTH-1",
    *,
    text=TEXT_90,
    support_key="ulp-period",
    source_ref="primary://authority",
    pinpoint="primary://authority#pinpoint",
):
    return AuthorityRecord(
        authority_id=authority_id,
        citation="Current authority",
        source_ref=source_ref,
        verified_on=ON_DATE,
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        lifecycle=AuthorityLifecycle.IN_FORCE,
        supported_claims=(AuthoritySupportClaim(support_key, text, pinpoint),),
    )


def _state(record, *, text=TEXT_90, support_key="ulp-period", authority_ids=None):
    ledger = LegalPropositionLedger(authorities={record.authority_id: record})
    ids = authority_ids or (record.authority_id,)
    proposition = LegalProposition(
        text,
        ids,
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key=support_key,
    )
    return ledger.proposition_authority_state(ledger.add_proposition(proposition), ON_DATE)


def test_support_key_substitution_fails_closed():
    assert _state(_current_record(), support_key="different-rule") == AuthorityState.SEMANTIC_SUPPORT_MISSING


def test_proposition_text_mutation_fails_closed():
    assert _state(
        _current_record(),
        text="unfair labour practice referrals are made within 30 days",
    ) == AuthorityState.SEMANTIC_SUPPORT_MISSING


def test_missing_source_pinpoint_is_rejected_at_construction():
    try:
        AuthoritySupportClaim("ulp-period", TEXT_90, "")
    except ValueError:
        return
    raise AssertionError("blank source pinpoint must fail closed")


def test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding():
    record = _current_record(
        pinpoint="unrelated://different-source#not-independently-verified",
    )
    assert _state(record) == AuthorityState.SEMANTIC_SUPPORT_MISSING


def test_stale_authority_fails_closed():
    record = AuthorityRecord(
        authority_id="AUTH-STALE",
        citation="Stale authority",
        source_ref="primary://stale",
        verified_on=ON_DATE - timedelta(days=31),
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        revalidation_days=30,
        lifecycle=AuthorityLifecycle.IN_FORCE,
        supported_claims=(AuthoritySupportClaim("ulp-period", TEXT_90, "primary://stale#pin"),),
    )
    assert _state(record) == AuthorityState.RECHECK_REQUIRED


def test_superseded_authority_fails_closed():
    record = AuthorityRecord(
        authority_id="AUTH-SUPERSEDED",
        citation="Superseded authority",
        source_ref="primary://superseded",
        verified_on=ON_DATE,
        later_treatment_checked=True,
        state=AuthorityState.SUPERSEDED,
        lifecycle=AuthorityLifecycle.IN_FORCE,
        supported_claims=(AuthoritySupportClaim("ulp-period", TEXT_90, "primary://superseded#pin"),),
    )
    assert _state(record) == AuthorityState.SUPERSEDED


def test_future_effective_authority_fails_closed():
    record = AuthorityRecord(
        authority_id="AUTH-FUTURE",
        citation="Future authority",
        source_ref="primary://future",
        verified_on=ON_DATE,
        effective_from=ON_DATE + timedelta(days=1),
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        lifecycle=AuthorityLifecycle.IN_FORCE,
        supported_claims=(AuthoritySupportClaim("ulp-period", TEXT_90, "primary://future#pin"),),
    )
    assert _state(record) == AuthorityState.RECHECK_REQUIRED


def test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof():
    text = "a proposed section is current law"
    record = AuthorityRecord(
        authority_id="AUTH-PROPOSED",
        citation="Proposed Amendments to Labour Relations Act",
        source_ref="official://proposed-amendments",
        verified_on=ON_DATE,
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        lifecycle=AuthorityLifecycle.PROPOSED,
        supported_claims=(
            AuthoritySupportClaim(
                "proposed-rule",
                text,
                "official://proposed-amendments#proposal",
            ),
        ),
    )
    assert _state(record, text=text, support_key="proposed-rule") == AuthorityState.NOT_IN_FORCE


def test_multi_authority_partial_support_fails_closed():
    first = _current_record("AUTH-A", source_ref="primary://a", pinpoint="primary://a#pin")
    second = AuthorityRecord(
        authority_id="AUTH-B",
        citation="Second current authority",
        source_ref="primary://b",
        verified_on=ON_DATE,
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        lifecycle=AuthorityLifecycle.IN_FORCE,
        supported_claims=(),
    )
    ledger = LegalPropositionLedger(authorities={"AUTH-A": first, "AUTH-B": second})
    proposition = LegalProposition(
        TEXT_90,
        ("AUTH-A", "AUTH-B"),
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key="ulp-period",
    )
    assert ledger.proposition_authority_state(
        ledger.add_proposition(proposition),
        ON_DATE,
    ) == AuthorityState.SEMANTIC_SUPPORT_MISSING
