import unittest
from evidenceops.ecertify_za.android_play_integrity import PlayIntegrityConfig,PlayIntegrityVerdictAdapter
from evidenceops.ecertify_za.apple_app_attest import AppleAppAttestAdapter,AppleAppAttestConfig,AppleVerifiedAssertion
from evidenceops.ecertify_za.device_trust import DeviceDecision,DeviceTrustPolicy

NOW=1700000000
NOW_MS=NOW*1000

def android_payload(labels=None,request_hash="hash-1"):
    return {"requestDetails":{"requestPackageName":"za.evidenceops.ecertify","requestHash":request_hash,"timestampMillis":str(NOW_MS)},"appIntegrity":{"appRecognitionVerdict":"PLAY_RECOGNIZED","packageName":"za.evidenceops.ecertify"},"deviceIntegrity":{"deviceRecognitionVerdict":labels or ["MEETS_DEVICE_INTEGRITY","MEETS_STRONG_INTEGRITY"]}}

class PlayIntegrityTests(unittest.TestCase):
    def setUp(self):self.adapter=PlayIntegrityVerdictAdapter(PlayIntegrityConfig("za.evidenceops.ecertify"));self.policy=DeviceTrustPolicy()
    def test_strong_integrity_can_trust_known_device(self):
        receipt=self.adapter.assess(android_payload(),expected_request_hash="hash-1",app_instance_id="app1",provider_evidence_ref="GOOGLE-PI-RCP-001",high_risk=True,now_millis=NOW_MS)
        self.assertTrue(receipt.strong_platform_integrity);self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.TRUSTED)
    def test_request_hash_mismatch_fails(self):
        receipt=self.adapter.assess(android_payload(),expected_request_hash="different",app_instance_id="app1",provider_evidence_ref="GOOGLE-PI-RCP-001",now_millis=NOW_MS)
        self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.HUMAN_REVIEW_REQUIRED)
    def test_high_risk_requires_strong_integrity(self):
        receipt=self.adapter.assess(android_payload(["MEETS_DEVICE_INTEGRITY"]),expected_request_hash="hash-1",app_instance_id="app1",provider_evidence_ref="GOOGLE-PI-RCP-001",high_risk=True,now_millis=NOW_MS)
        self.assertNotEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.TRUSTED)
    def test_placeholder_provider_evidence_fails(self):
        receipt=self.adapter.assess(android_payload(),expected_request_hash="hash-1",app_instance_id="app1",provider_evidence_ref="UNVERIFIED",now_millis=NOW_MS)
        self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.HUMAN_REVIEW_REQUIRED)
    def test_new_device_still_steps_up_even_with_strong_integrity(self):
        receipt=self.adapter.assess(android_payload(),expected_request_hash="hash-1",app_instance_id="app1",provider_evidence_ref="GOOGLE-PI-RCP-001",high_risk=True,now_millis=NOW_MS)
        self.assertEqual(self.policy.assess(receipt,new_device=True,now=NOW).decision,DeviceDecision.STEP_UP_REQUIRED)

class AppleAppAttestTests(unittest.TestCase):
    def setUp(self):self.adapter=AppleAppAttestAdapter(AppleAppAttestConfig("TEAM.za.evidenceops.ecertify"));self.policy=DeviceTrustPolicy()
    def result(self,**kw):
        base=dict(app_id="TEAM.za.evidenceops.ecertify",app_instance_id="ios-app-1",key_id="apple-key-1",environment="production",challenge="challenge-1",assertion_counter=5,validation_category=4,bundle_version="1.0",issued_at=NOW,provider_evidence_ref="APPLE-ATTEST-RCP-001")
        base.update(kw);return AppleVerifiedAssertion(**base)
    def test_verified_assertion_trusts_known_device(self):
        receipt=self.adapter.assess(self.result(),expected_challenge="challenge-1",previous_counter=4)
        self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.TRUSTED)
    def test_challenge_mismatch_fails(self):
        receipt=self.adapter.assess(self.result(),expected_challenge="wrong",previous_counter=4)
        self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.HUMAN_REVIEW_REQUIRED)
    def test_non_monotonic_counter_fails(self):
        receipt=self.adapter.assess(self.result(assertion_counter=4),expected_challenge="challenge-1",previous_counter=4)
        self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.HUMAN_REVIEW_REQUIRED)
    def test_development_or_placeholder_evidence_fails_production_config(self):
        receipt=self.adapter.assess(self.result(environment="development",provider_evidence_ref="TEST-APPLE"),expected_challenge="challenge-1",previous_counter=4)
        self.assertEqual(self.policy.assess(receipt,now=NOW).decision,DeviceDecision.HUMAN_REVIEW_REQUIRED)

if __name__=="__main__":unittest.main()
