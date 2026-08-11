import base64,hashlib,hmac,unittest
from datetime import datetime,timezone
from evidenceops.ecertify_za.identity_receipt import IdentityDecision,IdentityReceiptGate
from evidenceops.ecertify_za.provider_adapter import ProviderNotProductionQualified,require_production_provider
from evidenceops.ecertify_za.replay import SQLiteReplayGuard
from evidenceops.ecertify_za.smileid_adapter import SmileIDConfig,SmileIDProviderAdapter

NOW=1700000000
KEY=b"smile-secret"
PARTNER="085"

def ts(epoch=NOW):return datetime.fromtimestamp(epoch,timezone.utc).isoformat().replace("+00:00","Z")
def signature(timestamp):
    material=(timestamp+PARTNER+"sid_request").encode()
    return base64.b64encode(hmac.new(KEY,material,hashlib.sha256).digest()).decode()
def callback(**kw):
    timestamp=kw.pop("timestamp",ts())
    value={
        "Actions":{
            "Liveness_Check":"Passed",
            "Human_Review_Liveness_Check":"Passed",
            "Verify_ID_Number":"Verified",
            "Selfie_To_ID_Authority_Compare":"Completed",
            "Verify_Document":"Not Applicable",
        },
        "PartnerParams":{"job_id":"EOZA-JOB-1","job_type":1,"user_id":"EOZA-USER-1"},
        "SmileJobID":"0000056574",
        "ResultCode":"1210",
        "ResultText":"Enroll User",
        "Source":"WebAPI",
        "timestamp":timestamp,
        "signature":signature(timestamp),
    }
    value.update(kw);return value

class SmileIDAdapterTests(unittest.TestCase):
    def setUp(self):
        self.replay=SQLiteReplayGuard()
        self.adapter=SmileIDProviderAdapter(SmileIDConfig(PARTNER,KEY),self.replay)
    def tearDown(self):self.replay.close()
    def test_valid_biometric_kyc_callback_normalises_to_verified_identity(self):
        authenticated=self.adapter.authenticate_callback(callback(),NOW)
        assessment=IdentityReceiptGate().assess(authenticated,True)
        self.assertEqual(assessment.decision,IdentityDecision.VERIFIED)
        self.assertTrue(authenticated.payload["live_presence_check_passed"])
        self.assertTrue(authenticated.payload["trusted_reference_match_passed"])
    def test_invalid_signature_rejected(self):
        value=callback();value["signature"]="invalid"
        with self.assertRaisesRegex(ValueError,"SMILE_CALLBACK_SIGNATURE_INVALID"):self.adapter.authenticate_callback(value,NOW)
    def test_expired_callback_rejected(self):
        old=ts(NOW-1000);value=callback(timestamp=old);value["signature"]=signature(old)
        with self.assertRaisesRegex(ValueError,"SMILE_CALLBACK_EXPIRED"):self.adapter.authenticate_callback(value,NOW)
    def test_replay_rejected(self):
        value=callback();self.adapter.authenticate_callback(value,NOW)
        with self.assertRaisesRegex(ValueError,"SMILE_CALLBACK_REPLAY_DETECTED"):self.adapter.authenticate_callback(value,NOW)
    def test_liveness_failure_steps_up(self):
        value=callback();value["Actions"]["Liveness_Check"]="Failed";value["Actions"]["Human_Review_Liveness_Check"]="Failed"
        authenticated=self.adapter.authenticate_callback(value,NOW)
        self.assertEqual(IdentityReceiptGate().assess(authenticated,True).decision,IdentityDecision.STEP_UP_REQUIRED)
    def test_authority_compare_failure_steps_up(self):
        value=callback();value["Actions"]["Selfie_To_ID_Authority_Compare"]="Under Review"
        authenticated=self.adapter.authenticate_callback(value,NOW)
        self.assertEqual(IdentityReceiptGate().assess(authenticated,True).decision,IdentityDecision.STEP_UP_REQUIRED)
    def test_image_links_trigger_sensitive_media_boundary(self):
        value=callback(ImageLinks={"selfie_image":"https://example.invalid/private"})
        authenticated=self.adapter.authenticate_callback(value,NOW)
        self.assertTrue(authenticated.payload["raw_sensitive_media_received_by_evidenceops"])
        self.assertEqual(IdentityReceiptGate().assess(authenticated,True).decision,IdentityDecision.HUMAN_REVIEW_REQUIRED)
    def test_provider_cannot_be_marked_production_without_native_evidence(self):
        with self.assertRaises(ProviderNotProductionQualified):require_production_provider(self.adapter)

if __name__=="__main__":unittest.main()
