from __future__ import annotations

import unittest

from evidenceops.jurisdiction_first_referral_integrity.jfrie import (
    AuthorityClass,
    CauseElement,
    LegalLabel,
    ReferralInput,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2 import (
    ClaimRecord,
    ClaimStatus,
    ContaminationState,
    IntegrityGraph,
    JfrieV2Core,
    ProvenanceClass,
    ReleaseRequest,
    ReleaseState,
    SourceRecord,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_assurance import (
    AssuranceContext,
    AssuranceSignals,
    HashScope,
    JfrieV2Assurance,
)


def valid_referral(**overrides) -> ReferralInput:
    data = dict(
        instrument="LRA section 188A inquiry by arbitrator",
        forum="CCMA",
        cause_of_action="inquiry by arbitrator under LRA section 188A",
        cause_authority_ref="LRA s188A",
        cause_authority_class=AuthorityClass.STATUTE,
        specific_act_or_omission="initiated the prescribed inquiry procedure",
        dispute_date="2026-08-01",
        filing_date="2026-08-02",
        filing_period_rule="current verified forum rule",
        maturity_basis="prescribed trigger has arisen",
        elements=(CauseElement("prescribed inquiry trigger", ("FACT-1",), "LRA s188A"),),
        remedy="conduct the inquiry within statutory/forum competence",
        remedy_authority_ref="LRA s188A",
        narrative="Bounded source-controlled referral narrative.",
        source_refs=("SRC-PRIMARY-1",),
        form_category="inquiry by arbitrator",
    )
    data.update(overrides)
    return ReferralInput(**data)


def claim() -> ClaimRecord:
    return ClaimRecord(
        claim_id="CLM-1",
        exact_text="The prescribed inquiry trigger has arisen.",
        normalized_text="prescribed inquiry trigger has arisen",
        matter_id="MAT-188A",
        workstream_id="WS-JFRIE",
        origin_type=ProvenanceClass.PRIMARY_EVIDENCE,
        origin_reference="SRC-PRIMARY-1",
        source_ids=("SRC-PRIMARY-1",),
        evidence_status=ClaimStatus.VERIFIED,
        authority_status="VERIFIED",
        created_at="2026-08-12T00:00:00Z",
        last_verified_at="2026-08-12T00:00:00Z",
        contamination_state=ContaminationState.CLEAN,
        release_eligibility=False,
        legal_category="LRA s188A inquiry",
        authority_ref="LRA s188A",
    )


class JfrieV2AssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        graph = IntegrityGraph()
        graph.register_source(SourceRecord(
            source_id="SRC-PRIMARY-1",
            provenance_class=ProvenanceClass.PRIMARY_EVIDENCE,
            authenticated=True,
        ))
        graph.register_claim(claim())
        graph.mark_release_eligible("CLM-1", timestamp="2026-08-12T00:30:00Z")
        self.engine = JfrieV2Assurance(JfrieV2Core(graph))

    def request(self, referral: ReferralInput | None = None) -> ReleaseRequest:
        return ReleaseRequest(
            referral or valid_referral(),
            ("CLM-1",),
            {"truthgrid": True, "lex": True, "caseforge": True},
            True,
            True,
            "provider-readback-001",
            "snapshot-revision-sha256-001",
        )

    @staticmethod
    def context(**overrides) -> AssuranceContext:
        data = dict(
            object_id="OBJ-JFRIE-ASSURANCE-001",
            source_ids=("SRC-PRIMARY-1",),
            executed_at="2026-08-12T02:00:00+02:00",
            node_version_current=True,
        )
        data.update(overrides)
        return AssuranceContext(**data)

    def evaluate(self, signals: AssuranceSignals | None = None, *, referral=None, context=None):
        return self.engine.evaluate(
            self.request(referral),
            signals or AssuranceSignals(),
            context or self.context(),
        )

    def test_clean_assurance_cannot_expand_core_and_emits_receipts(self) -> None:
        result = self.evaluate()
        self.assertTrue(result.core.allowed)
        self.assertTrue(result.allowed)
        self.assertEqual(ReleaseState.RELEASE_CLEARED, result.state)
        self.assertTrue(result.receipts)
        self.assertTrue(all(item.source_ids for item in result.receipts))

    def test_t001_v1_ai_term_laundering_veto_remains_absolute(self) -> None:
        referral = valid_referral(labels=(
            LegalLabel("protective referral", AuthorityClass.AI_TERM, used_as_jurisdictional_category=True),
        ))
        result = self.evaluate(referral=referral)
        self.assertFalse(result.core.allowed)
        self.assertFalse(result.allowed)
        self.assertIn("V1_REFERRAL_GATE_NOT_RELEASABLE", result.blockers)

    def test_t003_date_drift_blocks_an_otherwise_clean_core_release(self) -> None:
        result = self.evaluate(AssuranceSignals(
            originating_dispute_date="2026-08-01",
            derivative_dispute_date="2026-08-04",
        ))
        self.assertTrue(result.core.allowed)
        self.assertFalse(result.allowed)
        self.assertIn("D003_DATE_DRIFT", result.detector_hits)

    def test_t004_transmission_is_not_knowledge(self) -> None:
        result = self.evaluate(AssuranceSignals(
            communication_sent=True,
            knowledge_claim_material=True,
            reading_or_knowledge_proven=False,
        ))
        self.assertIn("D005_TRANSMISSION_TO_KNOWLEDGE", result.detector_hits)
        self.assertFalse(result.allowed)

    def test_t005_silence_is_not_agreement(self) -> None:
        result = self.evaluate(AssuranceSignals(silence_treated_as_agreement=True))
        self.assertIn("D006_SILENCE_TO_AGREEMENT", result.detector_hits)
        self.assertFalse(result.allowed)

    def test_t008_stale_node_version_blocks_even_with_core_readback(self) -> None:
        result = self.evaluate(context=self.context(node_version_current=False))
        self.assertTrue(result.core.allowed)
        self.assertIn("D017_STALE_NODE", result.detector_hits)
        self.assertFalse(result.allowed)

    def test_t009_missing_attachment_is_exact_id_blocker(self) -> None:
        result = self.evaluate(AssuranceSignals(
            referenced_attachment_ids=("ATT-1", "ATT-2"),
            verified_attachment_ids=("ATT-1",),
        ))
        self.assertIn("D013_MISSING_ATTACHMENT", result.detector_hits)
        self.assertIn("D013_MISSING_ATTACHMENT:ATT-2", result.blockers)
        self.assertFalse(result.allowed)

    def test_ea07_unscoped_hash_is_blocked(self) -> None:
        blocked = self.evaluate(AssuranceSignals(hash_present=True))
        self.assertIn("EA07_UNSCOPED_HASH", blocked.detector_hits)
        self.assertFalse(blocked.allowed)

        scoped = self.evaluate(AssuranceSignals(
            hash_present=True,
            hash_scope=HashScope.ACQUISITION_BYTES,
        ))
        self.assertNotIn("EA07_UNSCOPED_HASH", scoped.detector_hits)
        self.assertTrue(scoped.allowed)

    def test_ea08_role_is_not_authority(self) -> None:
        result = self.evaluate(AssuranceSignals(
            material_authority_claim=True,
            role_and_authority_separately_sourced=False,
        ))
        self.assertIn("EA08_ROLE_AUTHORITY_CONFLATION", result.detector_hits)
        self.assertFalse(result.allowed)

    def test_t011_generated_detector_remains_shadow_only_until_both_gates_pass(self) -> None:
        held = self.evaluate(AssuranceSignals(generated_detector_candidate=True))
        self.assertTrue(held.allowed)
        self.assertFalse(held.detector_promotion_allowed)
        self.assertIn("C098_AUTOMATED_CAPABILITY_PROMOTION_HELD", held.detector_hits)

        promoted = self.evaluate(AssuranceSignals(
            generated_detector_candidate=True,
            detector_shadow_passed=True,
            detector_false_positive_rate_acceptable=True,
        ))
        self.assertTrue(promoted.allowed)
        self.assertTrue(promoted.detector_promotion_allowed)

    def test_existing_core_blockers_can_never_be_cleared_by_assurance(self) -> None:
        bad = valid_referral(cause_authority_ref=None)
        result = self.evaluate(referral=bad)
        self.assertFalse(result.core.allowed)
        self.assertFalse(result.allowed)
        self.assertIn("V1_REFERRAL_GATE_NOT_RELEASABLE", result.blockers)

    def test_external_effect_or_authority_expansion_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot expand authority"):
            self.evaluate(context=self.context(external_effect=True))
        with self.assertRaisesRegex(ValueError, "cannot expand authority"):
            self.evaluate(context=self.context(authority_ceiling="A2"))


if __name__ == "__main__":
    unittest.main()
