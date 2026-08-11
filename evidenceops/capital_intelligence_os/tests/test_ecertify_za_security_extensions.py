import unittest
from evidenceops.ecertify_za.device_trust import DeviceAttestationReceipt,DeviceDecision,DeviceTrustPolicy
from evidenceops.ecertify_za.document_intake import DocumentIntakePolicy,IntakeDecision

NOW=1700000000

class DeviceTrustTests(unittest.TestCase):
    def receipt(self,**kw):
        base=dict(platform="android",app_instance_id="app-1",device_key_id="key-1",attestation_verified=True,hardware_backed_key=True,app_integrity_passed=True,device_integrity_passed=True,nonce_verified=True,issued_at=NOW,risk_signals=())
        base.update(kw);return DeviceAttestationReceipt(**base)
    def test_trusted_known_device(self):self.assertEqual(DeviceTrustPolicy().assess(self.receipt(),now=NOW).decision,DeviceDecision.TRUSTED)
    def test_new_device_steps_up(self):self.assertEqual(DeviceTrustPolicy().assess(self.receipt(),new_device=True,now=NOW).decision,DeviceDecision.STEP_UP_REQUIRED)
    def test_recovery_steps_up(self):self.assertEqual(DeviceTrustPolicy().assess(self.receipt(),recovery_event=True,now=NOW).decision,DeviceDecision.STEP_UP_REQUIRED)
    def test_integrity_failure_requires_review(self):self.assertEqual(DeviceTrustPolicy().assess(self.receipt(device_integrity_passed=False),now=NOW).decision,DeviceDecision.HUMAN_REVIEW_REQUIRED)
    def test_attestation_expiry(self):self.assertEqual(DeviceTrustPolicy(max_age_seconds=60).assess(self.receipt(issued_at=NOW-1000),now=NOW).decision,DeviceDecision.STEP_UP_REQUIRED)

class DocumentIntakeTests(unittest.TestCase):
    def test_pdf_holds_for_security_scan(self):
        r=DocumentIntakePolicy().assess(b"%PDF-1.7\nexample","application/pdf");self.assertEqual(r.decision,IntakeDecision.HOLD_FOR_SCAN);self.assertEqual(len(r.sha256),64)
    def test_mime_mismatch_rejected(self):self.assertEqual(DocumentIntakePolicy().assess(b"%PDF-1.7\nexample","image/jpeg").decision,IntakeDecision.REJECT)
    def test_unknown_binary_rejected(self):self.assertEqual(DocumentIntakePolicy().assess(b"MZbinary").decision,IntakeDecision.REJECT)
    def test_empty_rejected(self):self.assertEqual(DocumentIntakePolicy().assess(b"").decision,IntakeDecision.REJECT)

if __name__=="__main__":unittest.main()
