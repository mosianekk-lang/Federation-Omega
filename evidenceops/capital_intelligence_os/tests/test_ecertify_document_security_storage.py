import unittest
from evidenceops.ecertify_za.document_intake import DocumentIntakePolicy,IntakeDecision
from evidenceops.ecertify_za.document_security import DocumentSecurityDecision,DocumentSecurityGate,DocumentSecurityScanReceipt
from evidenceops.ecertify_za.identity_receipt import IdentityDecision,IdentityReceiptAssessment
from evidenceops.ecertify_za.service import ECertifyService
from evidenceops.ecertify_za.storage_assurance import SecureDocumentAssessment,StorageAssuranceDecision,StorageAssuranceGate,StorageCommitReceipt

NOW=1700000000
PDF=b"%PDF-1.7\nsecure-test"

def scan(sha,**kw):
    base=dict(scanner_id="scanner-1",document_sha256=sha,malware_verdict="CLEAN",dlp_verdict="PASS",content_validation_verdict="PASS",scanner_policy_version="scan-v1",issued_at=NOW,evidence_ref="SCAN-RCP-001")
    base.update(kw);return DocumentSecurityScanReceipt(**base)

def storage(sha,**kw):
    base=dict(object_id="gs://private-bucket/object-1",object_version="7",document_sha256=sha,encryption_evidence_ref="KMS-RCP-001",storage_evidence_ref="STORAGE-READBACK-001",retention_policy_ref="RETENTION-POLICY-001",deletion_due_at=NOW+86400,private_access_only=True)
    base.update(kw);return StorageCommitReceipt(**base)

class DocumentSecurityTests(unittest.TestCase):
    def setUp(self):self.intake=DocumentIntakePolicy().assess(PDF,"application/pdf")
    def test_clean_scan_passes(self):self.assertEqual(DocumentSecurityGate().assess(self.intake,scan(self.intake.sha256),NOW).decision,DocumentSecurityDecision.VERIFIED)
    def test_hash_mismatch_rejects(self):self.assertEqual(DocumentSecurityGate().assess(self.intake,scan("b"*64),NOW).decision,DocumentSecurityDecision.REJECT)
    def test_malware_rejects(self):self.assertEqual(DocumentSecurityGate().assess(self.intake,scan(self.intake.sha256,malware_verdict="MALICIOUS"),NOW).decision,DocumentSecurityDecision.REJECT)
    def test_dlp_or_placeholder_evidence_holds(self):
        self.assertEqual(DocumentSecurityGate().assess(self.intake,scan(self.intake.sha256,dlp_verdict="REVIEW"),NOW).decision,DocumentSecurityDecision.HOLD)
        self.assertEqual(DocumentSecurityGate().assess(self.intake,scan(self.intake.sha256,evidence_ref="PENDING-SCAN"),NOW).decision,DocumentSecurityDecision.HOLD)

class StorageAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.intake=DocumentIntakePolicy().assess(PDF,"application/pdf")
        self.security=DocumentSecurityGate().assess(self.intake,scan(self.intake.sha256),NOW)
    def test_private_encrypted_storage_passes(self):self.assertEqual(StorageAssuranceGate().assess(self.security,storage(self.intake.sha256)).decision,StorageAssuranceDecision.VERIFIED)
    def test_public_or_unverified_storage_holds(self):
        self.assertEqual(StorageAssuranceGate().assess(self.security,storage(self.intake.sha256,private_access_only=False)).decision,StorageAssuranceDecision.HOLD)
        self.assertEqual(StorageAssuranceGate().assess(self.security,storage(self.intake.sha256,encryption_evidence_ref="UNVERIFIED")).decision,StorageAssuranceDecision.HOLD)
    def test_hash_mismatch_holds(self):self.assertEqual(StorageAssuranceGate().assess(self.security,storage("b"*64)).decision,StorageAssuranceDecision.HOLD)

class ProductionServiceDocumentTests(unittest.TestCase):
    def identity(self):return IdentityReceiptAssessment(IdentityDecision.VERIFIED,("ok",),"identity-digest","tx")
    def secure(self):
        intake=DocumentIntakePolicy().assess(PDF,"application/pdf");sec=DocumentSecurityGate().assess(intake,scan(intake.sha256),NOW);return StorageAssuranceGate().assess(sec,storage(intake.sha256))
    def test_production_rejects_raw_bytes_shortcut(self):
        service=ECertifyService(production_mode=True)
        with self.assertRaisesRegex(RuntimeError,"PRODUCTION_DOCUMENT_SECURITY_EVIDENCE_REQUIRED"):service.create_verification_record(document_bytes=PDF,requested_status="copy",identity_assessment=self.identity())
        service.close()
    def test_production_accepts_verified_secure_document(self):
        service=ECertifyService(production_mode=True);record=service.create_verification_record_from_secure_document(secure_document=self.secure(),requested_status="copy",identity_assessment=self.identity())
        self.assertEqual(record.metadata["document_pipeline"],"SECURITY_AND_STORAGE_VERIFIED");self.assertEqual(record.document_sha256,self.secure().document_sha256);service.close()
    def test_unverified_secure_document_is_rejected(self):
        service=ECertifyService(production_mode=True);bad=SecureDocumentAssessment(StorageAssuranceDecision.HOLD,"a"*64,"obj",("bad",),"digest")
        with self.assertRaisesRegex(RuntimeError,"SECURE_DOCUMENT_STORAGE_NOT_VERIFIED"):service.create_verification_record_from_secure_document(secure_document=bad,requested_status="copy",identity_assessment=self.identity())
        service.close()

if __name__=="__main__":unittest.main()
