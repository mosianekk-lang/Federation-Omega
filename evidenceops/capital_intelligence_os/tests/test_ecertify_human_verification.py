import base64,hashlib,hmac,unittest
from datetime import datetime,timezone
from evidenceops.ecertify_za.device_trust import DeviceAttestationReceipt,DeviceDecision,DeviceTrustPolicy
from evidenceops.ecertify_za.human_verification import HumanVerificationDecision,HumanVerificationOrchestrator
from evidenceops.ecertify_za.identity_receipt import IdentityReceiptGate
from evidenceops.ecertify_za.replay import SQLiteReplayGuard
from evidenceops.ecertify_za.smileid_adapter import SmileIDConfig,SmileIDProviderAdapter

NOW=1700000000;PARTNER="085";KEY=b"smile-secret"

def timestamp():return datetime.fromtimestamp(NOW,timezone.utc).isoformat().replace("+00:00","Z")
def callback():
    ts=timestamp();sig=base64.b64encode(hmac.new(KEY,(ts+PARTNER+"sid_request").encode(),hashlib.sha256).digest()).decode()
    return {"Actions":{"Liveness_Check":"Passed","Human_Review_Liveness_Check":"Passed","Verify_ID_Number":"Verified","Selfie_To_ID_Authority_Compare":"Completed","Verify_Document":"Not Applicable"},"PartnerParams":{"job_id":"EOZA-HV-1","job_type":1,"user_id":"EOZA-U-1"},"SmileJobID":"000099","ResultCode":"1210","ResultText":"Enroll User","timestamp":ts,"signature":sig}
def device(**kw):
    base=dict(platform="android",app_instance_id="app-1",device_key_id="hardware-key-1",attestation_verified=True,hardware_backed_key=True,app_integrity_passed=True,device_integrity_passed=True,nonce_verified=True,issued_at=NOW,risk_signals=())
    base.update(kw);return DeviceAttestationReceipt(**base)

class LayeredHumanVerificationTests(unittest.TestCase):
    def setUp(self):
        self.replay=SQLiteReplayGuard();self.adapter=SmileIDProviderAdapter(SmileIDConfig(PARTNER,KEY),self.replay)
    def tearDown(self):self.replay.close()
    def test_identity_plus_trusted_device_is_verified(self):
        identity=IdentityReceiptGate().assess(self.adapter.authenticate_callback(callback(),NOW),True)
        dev=DeviceTrustPolicy().assess(device(),now=NOW)
        self.assertEqual(dev.decision,DeviceDecision.TRUSTED)
        self.assertEqual(HumanVerificationOrchestrator().assess(identity,dev).decision,HumanVerificationDecision.VERIFIED)
    def test_identity_success_does_not_inherit_new_device_trust(self):
        identity=IdentityReceiptGate().assess(self.adapter.authenticate_callback(callback(),NOW),True)
        dev=DeviceTrustPolicy().assess(device(),new_device=True,now=NOW)
        self.assertEqual(HumanVerificationOrchestrator().assess(identity,dev).decision,HumanVerificationDecision.STEP_UP_REQUIRED)
    def test_identity_success_does_not_cure_device_integrity_failure(self):
        identity=IdentityReceiptGate().assess(self.adapter.authenticate_callback(callback(),NOW),True)
        dev=DeviceTrustPolicy().assess(device(device_integrity_passed=False),now=NOW)
        self.assertEqual(HumanVerificationOrchestrator().assess(identity,dev).decision,HumanVerificationDecision.HUMAN_REVIEW_REQUIRED)

if __name__=="__main__":unittest.main()
