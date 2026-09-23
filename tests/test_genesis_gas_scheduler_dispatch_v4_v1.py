from __future__ import annotations

import json
import pathlib
import re
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=(ROOT/"fuse_genesis"/"gas_scheduler_dispatch_v4.js").read_text(encoding="utf-8")

class GenesisGasThinDispatchV1Tests(unittest.TestCase):
    def test_01_google_apps_script_only_scheduler_identity(self):
        self.assertIn("schedulerId: 'GOOGLE_APPS_SCRIPT'",SRC)
    def test_02_no_gmail_business_logic(self):
        self.assertNotIn("GmailApp",SRC)
        self.assertNotIn("runFederationConnectorKernelV5",SRC)
    def test_03_no_urlfetch_business_execution(self):
        self.assertNotIn("UrlFetchApp",SRC)
    def test_04_no_full_prompt_payload(self):
        self.assertNotRegex(SRC,r"\bprompt\b")
    def test_05_payload_reference_only(self):
        self.assertIn("payloadRef",SRC)
        self.assertIn("payload_sha256",SRC)
    def test_06_private_key_from_script_properties(self):
        self.assertIn("PropertiesService.getScriptProperties()",SRC)
        self.assertIn("FUSE_GNS4_RSA_PRIVATE_KEY_PEM",SRC)
    def test_07_rsa_sha256_signature(self):
        self.assertIn("Utilities.computeRsaSha256Signature",SRC)
        self.assertIn("signature_algorithm: 'RSA_SHA256'",SRC)
    def test_08_canonical_signing_payload(self):
        self.assertIn("fuseGns4Canon_(signingPayload)",SRC)
        self.assertIn("Object.keys(value).sort()",SRC)
    def test_09_source_epoch_is_hash_bound(self):
        self.assertIn("SOURCE_EPOCH_SHA256_INVALID",SRC)
        self.assertIn("source_epoch_digest: sourceEpoch",SRC)
    def test_10_payload_hash_is_required(self):
        self.assertIn("PAYLOAD_SHA256_INVALID",SRC)
    def test_11_idempotency_is_period_payload_epoch_bound(self):
        for token in ("task.taskId","periodKey","task.payloadSha256","sourceEpoch"):
            self.assertIn(token,SRC)
    def test_12_stable_dispatch_id_from_idempotency(self):
        self.assertIn("GNS4D-' + idempotencyKey.slice(0, 40)",SRC)
    def test_13_effect_class_allowlist(self):
        for value in ("A0_READ_ONLY","A1_INTERNAL","A2_EXACT_PREAUTHORIZED"):
            self.assertIn(value,SRC)
    def test_14_provider_trigger_uid_required(self):
        self.assertIn("PROVIDER_TRIGGER_UID_REQUIRED",SRC)
    def test_15_queue_status_is_not_semantic_completion(self):
        self.assertIn("SIGNED_DISPATCH_QUEUED",SRC)
        self.assertNotIn("TASK_COMPLETE",SRC)
        self.assertNotIn("SEMANTIC_SUCCESS",SRC)
    def test_16_cycle_receipt_denies_business_execution(self):
        self.assertIn("semanticTaskExecutionPerformed: false",SRC)
        self.assertIn("externalBusinessLogicPerformed: false",SRC)
    def test_17_lock_is_bounded_to_tick(self):
        self.assertIn("LockService.getScriptLock()",SRC)
        self.assertIn("lock.releaseLock()",SRC)
    def test_18_dispatch_readback_required(self):
        self.assertIn("DISPATCH_OUTBOX_READBACK_MISMATCH",SRC)
    def test_19_idempotent_period_collision_suppressed(self):
        self.assertIn("IDEMPOTENT_PERIOD_ALREADY_QUEUED",SRC)
    def test_20_scheduler_max_work_is_bounded(self):
        self.assertIn("maxDispatchesPerTick: 12",SRC)
    def test_21_ttl_is_bounded(self):
        self.assertIn("ttl < 30 || ttl > 3600",SRC)
    def test_22_mission_id_is_required(self):
        self.assertIn("MISSION_ID_REQUIRED",SRC)
    def test_23_signature_private_key_not_sheet_column(self):
        append_block=SRC.split("function fuseGns4AppendDispatch_",1)[1].split("function fuseGns4AppendReceipt_",1)[0]
        self.assertNotIn("privateKey",append_block)
    def test_24_scheduler_receipt_is_explicitly_nonsemantic(self):
        self.assertIn("SCHEDULER_ONLY_NO_TASK_EXECUTION",SRC)
    def test_25_due_logic_is_separate_from_execution(self):
        self.assertIn("function fuseGns4Due_",SRC)
        self.assertNotIn("ExecuteCcma",SRC)
        self.assertNotIn("ExecuteDffe",SRC)
    def test_26_minimal_envelope_fields_present(self):
        fields=("dispatch_id","task_id","idempotency_key","mission_id","scheduler_id",
                "source_epoch_digest","payload_sha256","authority_ref","provider_event_id",
                "issued_at","expires_at","effect_class","signature_key_id",
                "signature_algorithm","signature_b64")
        for f in fields:self.assertIn(f,SRC)
    def test_27_signing_payload_excludes_signature_fields(self):
        block=SRC.split("var signingPayload = {",1)[1].split("};",1)[0]
        self.assertNotIn("signature_b64",block)
        self.assertNotIn("signature_key_id",block)
    def test_28_private_key_never_serialized(self):
        self.assertNotIn("JSON.stringify(privateKey)",SRC)
    def test_29_outbox_contains_payload_ref_not_payload_body(self):
        block=SRC.split("sheet.appendRow([",1)[1].split("]);",1)[0]
        self.assertIn("task.payloadRef",block)
        self.assertNotIn("task.payload,",block)
    def test_30_no_http_transport_success_shortcut(self):
        self.assertNotRegex(SRC,r"getResponseCode|HTTP_?200|responseCode")

if __name__=="__main__":
    unittest.main(verbosity=2)
