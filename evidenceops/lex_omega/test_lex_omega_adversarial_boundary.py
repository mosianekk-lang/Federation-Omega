from datetime import date

from evidenceops.lex_omega.lex_omega import (
    AuthorityLifecycle,
    AuthorityRecord,
    AuthorityState,
    AuthoritySupportClaim,
    LegalProposition,
    LegalPropositionLedger,
    PropositionState,
)


def test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding():
    text = "unfair labour practice referrals are made within 90 days"
    record = AuthorityRecord(
        authority_id="AUTH-1",
        citation="Current authority",
        source_ref="primary://authority",
        verified_on=date(2026, 8, 14),
        later_treatment_checked=True,
        state=AuthorityState.CURRENT_VERIFIED,
        supported_claims=(
            AuthoritySupportClaim(
                "ulp-period",
                text,
                "unrelated://different-source#not-independently-verified",
            ),
        ),
    )
    ledger = LegalPropositionLedger(authorities={"AUTH-1": record})
    proposition = LegalProposition(
        text,
        ("AUTH-1",),
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key="ulp-period",
    )
    proposition_id = ledger.add_proposition(proposition)

    assert ledger.proposition_authority_state(
        proposition_id,
        date(2026, 8, 14),
    ) != AuthorityState.CURRENT_VERIFIED


def test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof():
    text = "a proposed section is current law"
    record = AuthorityRecord(
        authority_id="AUTH-PROPOSED",
        citation="Proposed Amendments to Labour Relations Act",
        source_ref="official://proposed-amendments",
        verified_on=date(2026, 8, 14),
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
    ledger = LegalPropositionLedger(authorities={"AUTH-PROPOSED": record})
    proposition = LegalProposition(
        text,
        ("AUTH-PROPOSED",),
        proposition_state=PropositionState.VERIFIED_LAW,
        support_key="proposed-rule",
    )
    proposition_id = ledger.add_proposition(proposition)

    assert ledger.proposition_authority_state(
        proposition_id,
        date(2026, 8, 14),
    ) != AuthorityState.CURRENT_VERIFIED
