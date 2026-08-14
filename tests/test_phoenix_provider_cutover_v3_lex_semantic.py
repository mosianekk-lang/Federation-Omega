from datetime import date
import unittest

from evidenceops.lex_omega.lex_omega import (
    AuthorityRecord,
    AuthorityState,
    AuthoritySupportClaim,
    LegalProposition,
    LegalPropositionLedger,
    PropositionState,
)


class LexSemanticAuthorityBindingTests(unittest.TestCase):
    def setUp(self):
        self.today = date.today()

    def authority(self, authority_id, support_key, canonical_text):
        return AuthorityRecord(
            authority_id=authority_id,
            citation="Current official authority",
            source_ref="official://authority",
            verified_on=self.today,
            later_treatment_checked=True,
            state=AuthorityState.CURRENT_VERIFIED,
            supported_claims=(
                AuthoritySupportClaim(
                    support_key=support_key,
                    canonical_text=canonical_text,
                    source_pinpoint="official://authority#pinpoint",
                ),
            ),
        )

    def proposition(self, text, authority_id, support_key):
        return LegalProposition(
            text=text,
            authority_ids=(authority_id,),
            proposition_state=PropositionState.VERIFIED_LAW,
            support_key=support_key,
        )

    def test_correct_ulp_period_binding_passes(self):
        canonical = "Unfair labour practice referrals are made within 90 days"
        ledger = LegalPropositionLedger()
        ledger.add_authority(self.authority("CCMA-ULP", "ulp-referral-period", canonical))
        pid = ledger.add_proposition(self.proposition(canonical, "CCMA-ULP", "ulp-referral-period"))
        self.assertEqual(ledger.proposition_authority_state(pid, self.today), AuthorityState.CURRENT_VERIFIED)

    def test_false_30_day_ulp_mutation_is_rejected(self):
        canonical = "Unfair labour practice referrals are made within 90 days"
        ledger = LegalPropositionLedger()
        ledger.add_authority(self.authority("CCMA-ULP", "ulp-referral-period", canonical))
        pid = ledger.add_proposition(
            self.proposition(
                "Unfair labour practice referrals are made within 30 days",
                "CCMA-ULP",
                "ulp-referral-period",
            )
        )
        self.assertEqual(
            ledger.proposition_authority_state(pid, self.today),
            AuthorityState.SEMANTIC_SUPPORT_MISSING,
        )

    def test_false_protected_disclosure_forum_mutation_is_rejected(self):
        canonical = (
            "A protected-disclosure occupational-detriment unfair labour practice is "
            "adjudicated by the Labour Court after conciliation"
        )
        ledger = LegalPropositionLedger()
        ledger.add_authority(self.authority("CCMA-PDA", "pda-forum", canonical))
        pid = ledger.add_proposition(
            self.proposition(
                "A protected-disclosure occupational-detriment unfair labour practice is "
                "arbitrated by the CCMA after conciliation",
                "CCMA-PDA",
                "pda-forum",
            )
        )
        self.assertEqual(
            ledger.proposition_authority_state(pid, self.today),
            AuthorityState.SEMANTIC_SUPPORT_MISSING,
        )

    def test_missing_support_key_is_rejected(self):
        canonical = "A current legal proposition"
        ledger = LegalPropositionLedger()
        ledger.add_authority(self.authority("AUTH", "rule", canonical))
        pid = ledger.add_proposition(
            LegalProposition(
                text=canonical,
                authority_ids=("AUTH",),
                proposition_state=PropositionState.VERIFIED_LAW,
            )
        )
        self.assertEqual(
            ledger.proposition_authority_state(pid, self.today),
            AuthorityState.SEMANTIC_SUPPORT_MISSING,
        )

    def test_support_key_without_matching_registered_claim_is_rejected(self):
        canonical = "A current legal proposition"
        ledger = LegalPropositionLedger()
        ledger.add_authority(self.authority("AUTH", "rule-a", canonical))
        pid = ledger.add_proposition(self.proposition(canonical, "AUTH", "rule-b"))
        self.assertEqual(
            ledger.proposition_authority_state(pid, self.today),
            AuthorityState.SEMANTIC_SUPPORT_MISSING,
        )


if __name__ == "__main__":
    unittest.main()
