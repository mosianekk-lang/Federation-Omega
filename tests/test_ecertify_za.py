import unittest
from evidenceops.ecertify_za.identity_receipt import IdentityDecision,IdentityReceiptGate,ProviderVerificationReceipt
from evidenceops.ecertify_za.legal import CertificationRouteEngine
from evidenceops.ecertify_za.ledger import HashChainLedger
from evidenceops.ecertify_za.models import AssuranceLane
from evidenceops.ecertify_za.service import ECertifyService

def receipt(**kw):
    base=dict(provider="approved-idp",transaction_id="tx1",verification_passed=True,live_presence_check_passed=True,trusted_reference_match_passed=True,document_check_passed=True,device_attestation_passed=True,provider_risk_level="LOW",policy_version="v1",issued_at="2026-08-07T10:00:00Z",signature_verified=True,raw_sensitive_media_received_by_evidenceops=False)
    base.update(kw); return ProviderVerificationReceipt(**base)

class ReceiptTests(unittest.TestCase):
    def test_good_receipt_passes(self): self.assertEqual(IdentityReceiptGate().assess(receipt(),True).decision,IdentityDecision.VERIFIED)
    def test_signature_failure_human_review(self): self.assertEqual(IdentityReceiptGate().assess(receipt(signature_verified=False),True).decision,IdentityDecision.HUMAN_REVIEW_REQUIRED)
    def test_sensitive_media_boundary(self): self.assertEqual(IdentityReceiptGate().assess(receipt(raw_sensitive_media_received_by_evidenceops=True),True).decision,IdentityDecision.HUMAN_REVIEW_REQUIRED)
    def test_no_consent_fallback(self): self.assertEqual(IdentityReceiptGate().assess(receipt(),False).decision,IdentityDecision.NON_BIOMETRIC_FALLBACK)
    def test_provider_risk_steps_up(self): self.assertEqual(IdentityReceiptGate().assess(receipt(provider_risk_level="HIGH"),True).decision,IdentityDecision.STEP_UP_REQUIRED)
    def test_failed_live_presence_steps_up(self): self.assertEqual(IdentityReceiptGate().assess(receipt(live_presence_check_passed=False),True).decision,IdentityDecision.STEP_UP_REQUIRED)
    def test_failed_trusted_reference_steps_up(self): self.assertEqual(IdentityReceiptGate().assess(receipt(trusted_reference_match_passed=False),True).decision,IdentityDecision.STEP_UP_REQUIRED)
    def test_failed_device_attestation_steps_up(self): self.assertEqual(IdentityReceiptGate().assess(receipt(device_attestation_passed=False),True).decision,IdentityDecision.STEP_UP_REQUIRED)

class LegalTests(unittest.TestCase):
    def test_certifier_gate(self):
        x=CertificationRouteEngine().route("certified copy"); self.assertEqual(x.lane,AssuranceLane.CERTIFIED_COPY); self.assertTrue(x.commissioner_required); self.assertNotEqual(x.final_label,"CERTIFIED_COPY")
    def test_affidavit_presence_default(self): self.assertTrue(CertificationRouteEngine().route("affidavit").physical_presence_default)
    def test_acceptance_lane(self): self.assertEqual(CertificationRouteEngine().route("certified copy",True).lane,AssuranceLane.INSTITUTION_ACCEPTED)

class LedgerTests(unittest.TestCase):
    def test_hash_chain(self):
        l=HashChainLedger(); l.append("A",{"x":1}); l.append("B",{"x":2}); self.assertTrue(l.verify()); l.close()

class ServiceTests(unittest.TestCase):
    def test_certified_record_remains_commissioner_gated(self):
        s=ECertifyService(); ident=s.assess_identity(receipt(),True); rec=s.create_verification_record(document_bytes=b"hello",requested_status="certified copy",identity_assessment=ident); self.assertEqual(rec.status,"COMMISSIONER_EVENT_REQUIRED"); self.assertEqual(len(rec.document_sha256),64); self.assertTrue(s.ledger.verify())

if __name__=="__main__": unittest.main()
