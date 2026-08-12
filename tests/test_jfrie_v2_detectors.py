from __future__ import annotations

import unittest

from evidenceops.jurisdiction_first_referral_integrity.jfrie import AuthorityClass, CauseElement, ReferralInput
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2 import ClaimRecord, ClaimStatus, IntegrityGraph, JfrieV2Core, ProvenanceClass, ReleaseRequest, SourceRecord
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_detectors import EvidencePacket, FindingSeverity, JfrieV2Assurance, JfrieV2DetectorEngine, PostReleaseMonitor, PostReleaseState, SourceVersionObservation


def referral() -> ReferralInput:
    return ReferralInput(
        instrument="LRA section 188A inquiry by arbitrator", forum="CCMA",
        cause_of_action="inquiry by arbitrator under LRA section 188A",
        cause_authority_ref="LRA s188A", cause_authority_class=AuthorityClass.STATUTE,
        specific_act_or_omission="initiated the prescribed inquiry procedure",
        dispute_date="2026-08-01", filing_date="2026-08-02",
        filing_period_rule="current verified forum rule", maturity_basis="prescribed trigger has arisen",
        elements=(CauseElement("prescribed inquiry trigger", ("FACT-1",), "LRA s188A"),),
        remedy="conduct the inquiry within statutory/forum competence", remedy_authority_ref="LRA s188A",
        narrative="Bounded source-controlled referral narrative.", source_refs=("SRC-1",),
        form_category="inquiry by arbitrator",
    )


def make_claim(claim_id: str, source_ids: tuple[str, ...], *, text: str | None = None, dependencies: tuple[str, ...] = (), origin_type: ProvenanceClass = ProvenanceClass.PRIMARY_EVIDENCE) -> ClaimRecord:
    text = text or f"Exact proposition {claim_id}"
    return ClaimRecord(
        claim_id=claim_id, exact_text=text, normalized_text=text.lower(), matter_id="MAT-1", workstream_id="WS-1",
        origin_type=origin_type, origin_reference=source_ids[0], source_ids=source_ids,
        evidence_status=ClaimStatus.VERIFIED, authority_status="VERIFIED",
        created_at="2026-08-12T00:00:00Z", last_verified_at="2026-08-12T00:00:00Z",
        dependency_ids=dependencies, legal_category="LRA s188A inquiry", authority_ref="LRA s188A",
    )


class JfrieV2DetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph=IntegrityGraph(); self.graph.register_source(SourceRecord("SRC-1",ProvenanceClass.PRIMARY_EVIDENCE,authenticated=True)); self.graph.register_claim(make_claim("CLM-1",("SRC-1",))); self.graph.mark_release_eligible("CLM-1",timestamp="2026-08-12T00:10:00Z")
        self.core=JfrieV2Core(self.graph); self.detector=JfrieV2DetectorEngine(); self.assurance=JfrieV2Assurance(self.core,self.detector)
    def request(self, claim_ids=("CLM-1",)) -> ReleaseRequest:
        return ReleaseRequest(referral(),tuple(claim_ids),{"truthgrid":True,"lex":True,"caseforge":True},True,True,"provider-readback","snapshot-ref")
    def test_clean_detector_report_allows_clean_core_release(self)->None:
        report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z"); self.assertEqual((),report.findings)
        d=self.assurance.evaluate_release(self.request(),report); self.assertTrue(d.allowed); self.assertEqual((),d.blockers)
    def test_semantic_duplicate_is_review_not_auto_truth_and_blocks_until_resolved(self)->None:
        self.graph.register_claim(make_claim("CLM-2",("SRC-1",),text="Exact proposition CLM-1")); self.graph.mark_release_eligible("CLM-2",timestamp="2026-08-12T00:11:00Z")
        report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z"); reviews=[f for f in report.reviews if f.code=="SEMANTIC_DUPLICATE_EXACT"]
        self.assertEqual(1,len(reviews)); self.assertEqual(FindingSeverity.REVIEW,reviews[0].severity)
        held=self.assurance.evaluate_release(self.request(),report); self.assertFalse(held.allowed); self.assertTrue(any(x.startswith("DETECTOR_REVIEW_UNRESOLVED") for x in held.blockers))
        cleared=self.assurance.evaluate_release(self.request(),report,accepted_review_finding_ids=(reviews[0].finding_id,)); self.assertTrue(cleared.allowed)
    def test_dependency_cycle_is_hard_block(self)->None:
        graph=IntegrityGraph(); graph.register_source(SourceRecord("SRC-1",ProvenanceClass.PRIMARY_EVIDENCE,authenticated=True)); graph.register_claim(make_claim("A",("SRC-1",),dependencies=("B",))); graph.register_claim(make_claim("B",("SRC-1",),dependencies=("A",)))
        report=self.detector.scan(graph,generated_at="2026-08-12T00:20:00Z"); self.assertTrue(any(f.code=="CLAIM_DEPENDENCY_CYCLE" and f.severity is FindingSeverity.BLOCK for f in report.findings))
    def test_copy_carriers_are_reviewed_as_non_independent(self)->None:
        self.graph.register_source(SourceRecord("SRC-COPY",ProvenanceClass.DERIVATIVE_SUMMARY,parent_source_id="SRC-1")); self.graph.register_claim(make_claim("CLM-COPY",("SRC-1","SRC-COPY"))); self.graph.mark_release_eligible("CLM-COPY",timestamp="2026-08-12T00:12:00Z")
        report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z"); self.assertTrue(any(f.code=="COPY_CORROBORATION_INFLATION_RISK" for f in report.reviews))
    def test_release_eligible_derivative_only_support_is_hard_block(self)->None:
        graph=IntegrityGraph(); graph.register_source(SourceRecord("DER-1",ProvenanceClass.DERIVATIVE_SUMMARY)); graph.register_claim(make_claim("CLM-D",("DER-1",),origin_type=ProvenanceClass.DERIVATIVE_SUMMARY)); graph.mark_release_eligible("CLM-D",timestamp="2026-08-12T00:12:00Z")
        report=self.detector.scan(graph,generated_at="2026-08-12T00:20:00Z"); self.assertTrue(any(f.code=="RELEASE_ELIGIBLE_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT" and f.severity is FindingSeverity.BLOCK for f in report.findings))
    def test_required_packet_missing_member_is_hard_block(self)->None:
        packet=EvidencePacket("PKT-1",("notice","attachment","proof"),("notice","attachment"),True); report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z",packets=(packet,))
        self.assertTrue(any(f.code=="REQUIRED_EVIDENCE_PACKET_INCOMPLETE" and "proof" in f.object_ids for f in report.blocking))
    def test_source_version_collision_blocks_and_multi_version_requires_review(self)->None:
        observations=(SourceVersionObservation("FORM-719","v1","sha-a","2026-08-12T00:00:00Z"),SourceVersionObservation("FORM-719","v1","sha-b","2026-08-12T00:01:00Z"),SourceVersionObservation("FORM-719","v2","sha-c","2026-08-12T00:02:00Z"))
        report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z",observations=observations)
        self.assertTrue(any(f.code=="SOURCE_VERSION_FINGERPRINT_CONFLICT" for f in report.blocking)); self.assertTrue(any(f.code=="MULTIPLE_AUTHORITATIVE_VERSIONS_REQUIRE_SUPERSESSION" for f in report.reviews))
    def test_stale_detector_report_blocks_release(self)->None:
        report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z")
        self.graph.revise_claim("CLM-1",new_text="Corrected proposition",new_normalized_text="corrected proposition",new_status=ClaimStatus.VERIFIED,actor="JFRIE",reason="fresh source",timestamp="2026-08-12T00:21:00Z")
        held=self.assurance.evaluate_release(self.request(),report); self.assertFalse(held.allowed); self.assertIn("DETECTOR_REPORT_STALE",held.blockers)
    def test_post_release_snapshot_ignores_unrelated_change_but_recalls_released_claim_drift(self)->None:
        report=self.detector.scan(self.graph,generated_at="2026-08-12T00:20:00Z"); decision=self.assurance.evaluate_release(self.request(),report); self.assertTrue(decision.allowed)
        monitor=PostReleaseMonitor(self.detector); snapshot=monitor.capture(decision=decision,graph=self.graph,release_id="REL-1",matter_id="MAT-1",snapshot_ref="snap-001",captured_at="2026-08-12T00:22:00Z")
        stable=monitor.compare(snapshot,self.graph); self.assertEqual(PostReleaseState.STABLE,stable.state); self.assertFalse(stable.recall_required)
        self.graph.register_source(SourceRecord("SRC-U",ProvenanceClass.PRIMARY_EVIDENCE,authenticated=True)); unrelated=make_claim("CLM-U",("SRC-U",)); unrelated=ClaimRecord(**{**unrelated.__dict__,"matter_id":"MAT-U"}); self.graph.register_claim(unrelated)
        still_stable=monitor.compare(snapshot,self.graph); self.assertEqual(PostReleaseState.STABLE,still_stable.state)
        self.graph.revise_claim("CLM-1",new_text="Post-release corrected proposition",new_normalized_text="post release corrected proposition",new_status=ClaimStatus.VERIFIED_WITH_LIMITATION,actor="JFRIE",reason="new contrary source",timestamp="2026-08-12T00:23:00Z")
        recall=monitor.compare(snapshot,self.graph); self.assertEqual(PostReleaseState.RECALL_REQUIRED,recall.state); self.assertTrue(recall.recall_required); self.assertEqual(("CLM-1",),recall.changed_claim_ids)

if __name__=="__main__": unittest.main()
