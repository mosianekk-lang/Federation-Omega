import hashlib,hmac,json,unittest
from datetime import datetime,timezone
from pathlib import Path
from evidenceops.ecertify_za.identity_receipt import IdentityDecision,IdentityReceiptGate
from evidenceops.ecertify_za.legal import CertificationRouteEngine
from evidenceops.ecertify_za.ledger import HashChainLedger
from evidenceops.ecertify_za.models import AssuranceLane
from evidenceops.ecertify_za.provider_adapter import ProviderCapabilities,ProviderNotProductionQualified,require_production_provider
from evidenceops.ecertify_za.receipt_auth import HMACReceiptAuthenticator,ReceiptEnvelope,ReplayStore
from evidenceops.ecertify_za.replay import PostgresReplayGuard,ProductionReplayGuardRequired,SQLiteReplayGuard,require_distributed_replay
from evidenceops.ecertify_za.service import ECertifyService
from evidenceops.ecertify_za.verification_registry import PublicVerification,SQLiteVerificationRegistry

NOW=1700000000

def payload(now=NOW,**kw):
    base={"transaction_id":"tx-1","issued_at":datetime.fromtimestamp(now,timezone.utc).isoformat(),"verification_passed":True,"live_presence_check_passed":True,"trusted_reference_match_passed":True,"document_check_passed":True,"device_attestation_passed":True,"provider_risk_level":"LOW","policy_version":"v1","raw_sensitive_media_received_by_evidenceops":False}
    base.update(kw);return base

def envelope(secret=b"secret",now=NOW,provider="approved-idp",key_id="k1",**kw):
    p=payload(now,**kw);canonical=json.dumps(p,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode();sig=hmac.new(secret,canonical,hashlib.sha256).hexdigest();return ReceiptEnvelope(provider,p,sig,key_id)

class ReceiptAuthTests(unittest.TestCase):
    def setUp(self):self.a=HMACReceiptAuthenticator({"approved-idp":b"secret"},{"approved-idp":{"k1"}},300,ReplayStore())
    def tearDown(self):self.a.replay_store.close()
    def test_valid_signature_and_gate(self):self.assertEqual(IdentityReceiptGate().assess(self.a.verify(envelope(),NOW),True).decision,IdentityDecision.VERIFIED)
    def test_bad_signature_rejected(self):
        e=envelope();bad=ReceiptEnvelope(e.provider,e.payload,"00"*32,e.key_id)
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

class ReplayBoundaryTests(unittest.TestCase):
    def test_sqlite_fails_production_gate(self):
        g=SQLiteReplayGuard()
        with self.assertRaises(ProductionReplayGuardRequired):require_distributed_replay(g)
        g.close()
    def test_postgres_contract_is_distributed(self):
        class Cursor:
            def execute(self,*args):self.row=("tx",)
            def fetchone(self):return self.row
        class Conn:
            def cursor(self):return Cursor()
            def commit(self):pass
            def rollback(self):pass
            def close(self):pass
        g=PostgresReplayGuard(lambda:Conn());require_distributed_replay(g);self.assertTrue(g.claim("p","t"))

class ProviderGateTests(unittest.TestCase):
    def test_requires_provider_native_production_evidence(self):
        class Adapter:
            capabilities=ProviderCapabilities("p",True,True,True,True,True,True,False,"")
            def authenticate(self,e):raise NotImplementedError
            def health(self):return {}
        with self.assertRaises(ProviderNotProductionQualified):require_production_provider(Adapter())
    def test_semantic_placeholder_never_counts_as_provider_proof(self):
        for ref in ("UNBOUND_PROVIDER_READBACK","PENDING_CONTRACT","REFERENCE_ONLY","TEST_RECEIPT","MOCK_PROOF","UNVERIFIED","PLACEHOLDER","TODO","TBD","N/A"):
            class Adapter:
                capabilities=ProviderCapabilities("p",True,True,True,True,True,True,False,ref)
                def authenticate(self,e):raise NotImplementedError
                def health(self):return {}
            with self.subTest(ref=ref),self.assertRaises(ProviderNotProductionQualified):require_production_provider(Adapter())
    def test_concrete_provider_evidence_reference_can_pass_gate(self):
        class Adapter:
            capabilities=ProviderCapabilities("p",True,True,True,True,True,True,False,"RCP-IDP-PROD-20260807-001")
            def authenticate(self,e):raise NotImplementedError
            def health(self):return {}
        require_production_provider(Adapter())
    def test_rejects_raw_biometric_media_boundary(self):
        class Adapter:
            capabilities=ProviderCapabilities("p",True,True,True,True,True,True,True,"RCP-IDP-PROD-20260807-001")
            def authenticate(self,e):raise NotImplementedError
            def health(self):return {}
        with self.assertRaises(ProviderNotProductionQualified):require_production_provider(Adapter())

class LegalTests(unittest.TestCase):
    def test_certifier_gate(self):
        x=CertificationRouteEngine().route("certified copy");self.assertEqual(x.lane,AssuranceLane.CERTIFIED_COPY);self.assertTrue(x.commissioner_required);self.assertNotEqual(x.final_label,"CERTIFIED_COPY")
    def test_affidavit_presence_default(self):self.assertTrue(CertificationRouteEngine().route("affidavit").physical_presence_default)
    def test_acceptance_lane(self):self.assertEqual(CertificationRouteEngine().route("certified copy",True).lane,AssuranceLane.INSTITUTION_ACCEPTED)

class PublicVerificationTests(unittest.TestCase):
    def test_public_record_contains_minimum_fields(self):
        r=SQLiteVerificationRegistry();item=PublicVerification("EOZA-ABC123","VALID","SOURCE_MATCHED_COPY","a"*64,NOW,NOW+60);r.publish(item);got=r.get("EOZA-ABC123",NOW);self.assertEqual(got,item);self.assertNotIn("identity",got.__dict__);r.close()
    def test_expiry(self):
        r=SQLiteVerificationRegistry();r.publish(PublicVerification("EOZA-ABC123","VALID","SOURCE_MATCHED_COPY","a"*64,NOW,NOW+1));self.assertEqual(r.get("EOZA-ABC123",NOW+2).status,"EXPIRED");r.close()

class LedgerTests(unittest.TestCase):
    def test_hash_chain(self):
        l=HashChainLedger();l.append("A",{"x":1});l.append("B",{"x":2});self.assertTrue(l.verify());l.close()

class ServiceTests(unittest.TestCase):
    def test_certified_record_remains_commissioner_gated(self):
        auth=HMACReceiptAuthenticator({"approved-idp":b"secret"},{"approved-idp":{"k1"}},300,ReplayStore());s=ECertifyService(authenticator=auth);ident=s.assess_identity(auth.verify(envelope(),NOW),True);rec=s.create_verification_record(document_bytes=b"hello",requested_status="certified copy",identity_assessment=ident);self.assertEqual(rec.status,"COMMISSIONER_EVENT_REQUIRED");self.assertEqual(len(rec.document_sha256),64);self.assertTrue(s.ledger.verify());s.close()
    def test_service_context_manager_closes_resources(self):
        auth=HMACReceiptAuthenticator({"approved-idp":b"secret"},{"approved-idp":{"k1"}},300,ReplayStore())
        with ECertifyService(authenticator=auth) as service:self.assertFalse(service._closed)
        self.assertTrue(service._closed)

class DeploymentSafetyTests(unittest.TestCase):
    def test_canary_bundle_is_isolated_and_zero_traffic(self):
        text=Path("evidenceops/ecertify_za/deployment/deploy_cloud_run_canary.sh").read_text()
        self.assertIn("evidenceops-ecertify-za-private",text);self.assertIn("evidenceops-ecertify-za-public",text);self.assertIn("--no-traffic",text);self.assertIn("--no-allow-unauthenticated",text);self.assertIn("Refusing reserved service target",text)

if __name__=="__main__":unittest.main()
