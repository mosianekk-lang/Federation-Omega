import hashlib,hmac,json,unittest
from datetime import datetime,timezone
from evidenceops.ecertify_za.identity_receipt import IdentityDecision,IdentityReceiptGate
from evidenceops.ecertify_za.legal import CertificationRouteEngine
from evidenceops.ecertify_za.ledger import HashChainLedger
from evidenceops.ecertify_za.models import AssuranceLane
from evidenceops.ecertify_za.receipt_auth import HMACReceiptAuthenticator,ReceiptEnvelope,ReplayStore
from evidenceops.ecertify_za.service import ECertifyService

NOW=1700000000

def payload(now=NOW,**kw):
    base={"transaction_id":"tx-1","issued_at":datetime.fromtimestamp(now,timezone.utc).isoformat(),"verification_passed":True,"live_presence_check_passed":True,"trusted_reference_match_passed":True,"document_check_passed":True,"device_attestation_passed":True,"provider_risk_level":"LOW","policy_version":"v1","raw_sensitive_media_received_by_evidenceops":False}
    base.update(kw);return base

def envelope(secret=b"secret",now=NOW,provider="approved-idp",key_id="k1",**kw):
    p=payload(now,**kw); canonical=json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode(); sig=hmac.new(secret,canonical,hashlib.sha256).hexdigest(); return ReceiptEnvelope(provider,p,sig,key_id)

class ReceiptAuthTests(unittest.TestCase):
    def setUp(self):self.a=HMACReceiptAuthenticator({"approved-idp":b"secret"},{"approved-idp":{"k1"}},300,ReplayStore())
    def tearDown(self):self.a.replay_store.close()
    def test_valid_signature_and_gate(self):self.assertEqual(IdentityReceiptGate().assess(self.a.verify(envelope(),NOW),True).decision,IdentityDecision.VERIFIED)
    def test_bad_signature_rejected(self):
        e=envelope(); bad=ReceiptEnvelope(e.provider,e.payload,"00"*32,e.key_id)
        with self.assertRaisesRegex(ValueError,"SIGNATURE_INVALID"):self.a.verify(bad,NOW)
    def test_unlisted_provider_rejected(self):
        with self.assertRaisesRegex(ValueError,"PROVIDER_NOT_ALLOWLISTED"):self.a.verify(envelope(provider="evil"),NOW)
    def test_wrong_key_id_rejected(self):
        with self.assertRaisesRegex(ValueError,"KEY_ID_NOT_ALLOWED"):self.a.verify(envelope(key_id="bad"),NOW)
    def test_expired_receipt_rejected(self):
        with self.assertRaisesRegex(ValueError,"RECEIPT_EXPIRED"):self.a.verify(envelope(now=NOW-1000),NOW)
    def test_replay_rejected(self):
        e=envelope();self.a.verify(e,NOW)
        with self.assertRaisesRegex(ValueError,"RECEIPT_REPLAY_DETECTED"):self.a.verify(e,NOW)
    def test_no_consent_fallback(self):self.assertEqual(IdentityReceiptGate().assess(self.a.verify(envelope(),NOW),False).decision,IdentityDecision.NON_BIOMETRIC_FALLBACK)
    def test_sensitive_media_boundary(self):self.assertEqual(IdentityReceiptGate().assess(self.a.verify(envelope(raw_sensitive_media_received_by_evidenceops=True),NOW),True).decision,IdentityDecision.HUMAN_REVIEW_REQUIRED)
    def test_failed_live_presence_steps_up(self):self.assertEqual(IdentityReceiptGate().assess(self.a.verify(envelope(live_presence_check_passed=False),NOW),True).decision,IdentityDecision.STEP_UP_REQUIRED)

class LegalTests(unittest.TestCase):
    def test_certifier_gate(self):
        x=CertificationRouteEngine().route("certified copy");self.assertEqual(x.lane,AssuranceLane.CERTIFIED_COPY);self.assertTrue(x.commissioner_required);self.assertNotEqual(x.final_label,"CERTIFIED_COPY")
    def test_affidavit_presence_default(self):self.assertTrue(CertificationRouteEngine().route("affidavit").physical_presence_default)
    def test_acceptance_lane(self):self.assertEqual(CertificationRouteEngine().route("certified copy",True).lane,AssuranceLane.INSTITUTION_ACCEPTED)

class LedgerTests(unittest.TestCase):
    def test_hash_chain(self):
        l=HashChainLedger();l.append("A",{"x":1});l.append("B",{"x":2});self.assertTrue(l.verify());l.close()

class ServiceTests(unittest.TestCase):
    def test_certified_record_remains_commissioner_gated(self):
        auth=HMACReceiptAuthenticator({"approved-idp":b"secret"},{"approved-idp":{"k1"}},300,ReplayStore());s=ECertifyService(authenticator=auth);ident=s.assess_identity(auth.verify(envelope(),NOW),True);rec=s.create_verification_record(document_bytes=b"hello",requested_status="certified copy",identity_assessment=ident);self.assertEqual(rec.status,"COMMISSIONER_EVENT_REQUIRED");self.assertEqual(len(rec.document_sha256),64);self.assertTrue(s.ledger.verify());auth.replay_store.close()

if __name__=="__main__":unittest.main()
