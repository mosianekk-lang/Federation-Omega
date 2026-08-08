import unittest
from dataclasses import replace
from pathlib import Path
from evidenceops.ecertify_za.launch_now import LaunchNowEngine,LaunchRoute
from evidenceops.ecertify_za.zero_possession import ZeroPossessionReceiptService
from evidenceops.ecertify_za.commissioner_dispatch import CommissionerCandidate,CommissionerDispatchEngine,DispatchDecision,DispatchRequest

class LaunchNowTests(unittest.TestCase):
    def setUp(self):self.engine=LaunchNowEngine()
    def test_digital_original_launches_without_idv_contract(self):
        result=self.engine.route("digital original")
        self.assertTrue(result.launchable_without_idv_contract)
        self.assertEqual(result.route,LaunchRoute.SELF_SERVICE_INTEGRITY)
        self.assertNotIn("CERTIFIED",result.public_label)
    def test_source_verified_original_can_upgrade_without_statutory_certification(self):
        result=self.engine.route("digital original",issuer_or_source_verified=True)
        self.assertEqual(result.route,LaunchRoute.SELF_SERVICE_VERIFIED_ORIGINAL)
        self.assertEqual(result.public_label,"VERIFIED_DIGITAL_ORIGINAL")
    def test_certified_copy_becomes_platform_dispatch_not_user_search(self):
        result=self.engine.route("certified copy")
        self.assertEqual(result.route,LaunchRoute.ASSISTED_CERTIFICATION_DISPATCH)
        self.assertTrue(result.commissioner_required)
        self.assertNotEqual(result.public_label,"CERTIFIED_COPY")
        self.assertIn("platform finds and assigns",result.citizen_experience.lower())
    def test_affidavit_keeps_physical_presence_default(self):
        result=self.engine.route("affidavit")
        self.assertEqual(result.route,LaunchRoute.ASSISTED_AFFIDAVIT_DISPATCH)
        self.assertTrue(result.physical_presence_default)

class ZeroPossessionTests(unittest.TestCase):
    def setUp(self):self.service=ZeroPossessionReceiptService(b"x"*32,key_id="k1")
    def test_receipt_is_signed_without_document_bytes(self):
        receipt=self.service.issue(document_sha256="a"*64,client_nonce="0123456789abcdef",now=1700000000)
        self.assertTrue(self.service.verify(receipt))
        self.assertEqual(receipt.public_label,"EVIDENCEOPS_DOCUMENT_INTEGRITY_RECEIPT")
    def test_tampered_hash_fails_verification(self):
        receipt=self.service.issue(document_sha256="a"*64,client_nonce="0123456789abcdef",now=1700000000)
        self.assertFalse(self.service.verify(replace(receipt,document_sha256="b"*64)))
    def test_invalid_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"DOCUMENT_SHA256_INVALID"):
            self.service.issue(document_sha256="bad",client_nonce="0123456789abcdef")

class DispatchTests(unittest.TestCase):
    def test_nearest_verified_candidate_is_assigned(self):
        engine=CommissionerDispatchEngine();req=DispatchRequest("EOZA-1","certified_copy","Mbombela","LOC-1")
        candidates=[
            CommissionerCandidate("C2","Two",True,True,("certified_copy",),"Mbombela",True,True,8.0,100),
            CommissionerCandidate("C1","One",True,True,("certified_copy",),"Mbombela",True,True,3.0,70),
        ]
        result=engine.dispatch(req,candidates)
        self.assertEqual(result.decision,DispatchDecision.ASSIGNED);self.assertEqual(result.commissioner_id,"C1")
    def test_no_supply_creates_platform_supply_expansion_not_user_task(self):
        engine=CommissionerDispatchEngine();req=DispatchRequest("EOZA-2","affidavit","Nelspruit","LOC-2")
        result=engine.dispatch(req,[])
        self.assertEqual(result.decision,DispatchDecision.SUPPLY_EXPANSION_REQUIRED)
        self.assertIn("you do not need to find one",result.citizen_message.lower())

class HttpContractTests(unittest.TestCase):
    def test_launch_mode_does_not_require_idv_provider(self):
        text=Path("evidenceops/ecertify_za/http_app.py").read_text()
        self.assertIn('mode=="full_assurance"',text)
        self.assertIn('/v1/launch/route',text)
        self.assertIn('/v1/integrity/receipt/issue',text)
        self.assertIn('zero_possession_endpoint_rejects_document_bytes',text)

if __name__=="__main__":unittest.main()
