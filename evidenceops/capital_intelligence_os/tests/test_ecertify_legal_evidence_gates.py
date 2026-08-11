import unittest
from evidenceops.ecertify_za.commissioner_authority import CommissionerAuthorityDecision,CommissionerAuthorityGate,CommissionerAuthorityRecord
from evidenceops.ecertify_za.identity_receipt import IdentityDecision,IdentityReceiptAssessment
from evidenceops.ecertify_za.legal import CertificationRouteEngine
from evidenceops.ecertify_za.legal_completion import CommissionerEvent,CommissionerEventType,LegalCompletionDecision,LegalCompletionGate
from evidenceops.ecertify_za.models import AssuranceLane
from evidenceops.ecertify_za.recipient_acceptance import RecipientAcceptanceDecision,RecipientAcceptanceGate,RecipientAcceptanceRule
from evidenceops.ecertify_za.service import ECertifyService

NOW=1700000000
DOC_HASH="a"*64

def recipient_rule(**kw):
    base=dict(rule_id="RULE-1",recipient_id="university-1",use_case="admission",document_type="qualification",accepted_lanes=(AssuranceLane.INSTITUTION_ACCEPTED,),authority_evidence_ref="AGR-RECIPIENT-2026-001",effective_from=NOW-100,expires_at=NOW+1000,last_verified_at=NOW)
    base.update(kw);return RecipientAcceptanceRule(**base)

def authority(**kw):
    base=dict(commissioner_id="COM-1",designation_type="EX_OFFICIO",identity_evidence_ref="IDV-COM-1",authority_source_ref="GAZETTE-COM-1",current_capacity_evidence_ref="EMPLOYMENT-CAPACITY-COM-1",valid_from=NOW-1000,valid_to=NOW+1000,authority_checked_at=NOW)
    base.update(kw);return CommissionerAuthorityRecord(**base)

class RecipientAcceptanceTests(unittest.TestCase):
    def test_exact_current_rule_passes(self):
        a=RecipientAcceptanceGate().assess(recipient_rule(),recipient_id="university-1",use_case="admission",document_type="qualification",now=NOW)
        self.assertEqual(a.decision,RecipientAcceptanceDecision.VERIFIED)
    def test_placeholder_agreement_is_held(self):
        a=RecipientAcceptanceGate().assess(recipient_rule(authority_evidence_ref="DRAFT-AGREEMENT"),recipient_id="university-1",use_case="admission",document_type="qualification",now=NOW)
        self.assertEqual(a.decision,RecipientAcceptanceDecision.HOLD)
    def test_mismatched_use_case_cannot_create_lane5(self):
        a=RecipientAcceptanceGate().assess(recipient_rule(),recipient_id="university-1",use_case="employment",document_type="qualification",now=NOW)
        self.assertEqual(CertificationRouteEngine().route("certified copy",a).lane,AssuranceLane.REQUIREMENT_VERIFICATION)
    def test_stale_rule_is_held(self):
        a=RecipientAcceptanceGate(max_rule_age_seconds=100).assess(recipient_rule(last_verified_at=NOW-1000),recipient_id="university-1",use_case="admission",document_type="qualification",now=NOW)
        self.assertEqual(a.decision,RecipientAcceptanceDecision.HOLD)

class CommissionerAuthorityTests(unittest.TestCase):
    def test_current_ex_officio_authority_passes(self):self.assertEqual(CommissionerAuthorityGate().assess(authority(),NOW).decision,CommissionerAuthorityDecision.VERIFIED)
    def test_ex_officio_without_current_capacity_is_held(self):self.assertEqual(CommissionerAuthorityGate().assess(authority(current_capacity_evidence_ref="UNVERIFIED"),NOW).decision,CommissionerAuthorityDecision.HOLD)
    def test_stale_authority_is_held(self):self.assertEqual(CommissionerAuthorityGate(max_authority_age_seconds=100).assess(authority(authority_checked_at=NOW-1000),NOW).decision,CommissionerAuthorityDecision.HOLD)

class LegalCompletionTests(unittest.TestCase):
    def setUp(self):self.auth=CommissionerAuthorityGate().assess(authority(),NOW);self.gate=LegalCompletionGate()
    def event(self,kind=CommissionerEventType.CERTIFY_COPY,**kw):
        base=dict(event_id="EV-1",transaction_id="EOZA-ABC123",commissioner_id="COM-1",event_type=kind,document_sha256=DOC_HASH,event_timestamp=NOW,event_evidence_ref="EVENT-EVIDENCE-1",conflict_clearance_ref="CONFLICT-CLEAR-1",original_inspected=True,physical_presence=False,deponent_signed_in_presence=False)
        base.update(kw);return CommissionerEvent(**base)
    def test_certified_copy_released_only_after_original_inspection(self):
        route=CertificationRouteEngine().route("certified copy")
        good=self.gate.assess(route,self.auth,self.event(),expected_document_sha256=DOC_HASH,expected_transaction_id="EOZA-ABC123",now=NOW)
        bad=self.gate.assess(route,self.auth,self.event(original_inspected=False),expected_document_sha256=DOC_HASH,expected_transaction_id="EOZA-ABC123",now=NOW)
        self.assertEqual(good.decision,LegalCompletionDecision.VERIFIED);self.assertEqual(good.final_label,"CERTIFIED_COPY");self.assertEqual(bad.decision,LegalCompletionDecision.HOLD)
    def test_transaction_or_hash_mismatch_blocks_completion(self):
        route=CertificationRouteEngine().route("certified copy")
        a=self.gate.assess(route,self.auth,self.event(transaction_id="OTHER"),expected_document_sha256=DOC_HASH,expected_transaction_id="EOZA-ABC123",now=NOW)
        b=self.gate.assess(route,self.auth,self.event(document_sha256="b"*64),expected_document_sha256=DOC_HASH,expected_transaction_id="EOZA-ABC123",now=NOW)
        self.assertEqual(a.decision,LegalCompletionDecision.HOLD);self.assertEqual(b.decision,LegalCompletionDecision.HOLD)
    def test_affidavit_requires_presence_and_signature_in_presence(self):
        route=CertificationRouteEngine().route("affidavit")
        good=self.gate.assess(route,self.auth,self.event(CommissionerEventType.COMMISSION_AFFIDAVIT,original_inspected=False,physical_presence=True,deponent_signed_in_presence=True),expected_document_sha256=DOC_HASH,expected_transaction_id="EOZA-ABC123",now=NOW)
        remote=self.gate.assess(route,self.auth,self.event(CommissionerEventType.COMMISSION_AFFIDAVIT,original_inspected=False,physical_presence=False,deponent_signed_in_presence=True),expected_document_sha256=DOC_HASH,expected_transaction_id="EOZA-ABC123",now=NOW)
        self.assertEqual(good.final_label,"COMMISSIONED_AFFIDAVIT");self.assertEqual(good.decision,LegalCompletionDecision.VERIFIED);self.assertEqual(remote.decision,LegalCompletionDecision.HOLD)
    def test_service_only_changes_label_after_verified_event(self):
        identity=IdentityReceiptAssessment(IdentityDecision.VERIFIED,("ok",),"identity-digest","tx")
        service=ECertifyService();record=service.create_verification_record(document_bytes=b"hello",requested_status="certified copy",identity_assessment=identity)
        good_event=self.event(transaction_id=record.verification_code,document_sha256=record.document_sha256)
        completed=service.complete_legal_event(record,self.auth,good_event,now=NOW)
        blocked=service.complete_legal_event(record,self.auth,self.event(transaction_id="wrong",document_sha256=record.document_sha256),now=NOW)
        self.assertEqual(completed.legal_label,"CERTIFIED_COPY");self.assertEqual(completed.status,"LEGAL_EVENT_VERIFIED");self.assertEqual(blocked.legal_label,"CERTIFICATION_REQUIRED");service.close()

if __name__=="__main__":unittest.main()
