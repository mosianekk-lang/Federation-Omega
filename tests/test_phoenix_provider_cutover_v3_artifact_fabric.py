from __future__ import annotations

from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from federation_artifact_fabric_v3 import (
    ArtifactGateway, ArtifactLedger, ArtifactReconciler, ArtifactRequest,
    HMACReceiptSigner, GenesisImporter, LegacyArtifactRecord,
    IdempotencyCollision, InjectedCrash, InMemoryProjection, InMemoryStorage,
    InvalidTransition, RetentionClass, ScanViolation, SensitivityClass,
    TransactionState, merkle_root, scan_artifact, sha256_bytes,
)

KEY = b"federation-artifact-fabric-v3-test-key-material-0001"


def request(*, name="report.md", content=b"# Verified artifact\n", media_type="text/markdown", version="1.0.0", destination_alias="PRIVATE_DRIVE_CANONICAL", metadata=None, retention=RetentionClass.CANONICAL):
    return ArtifactRequest(
        artifact_name=name, content=content, media_type=media_type,
        workstream="FAF3-TEST", version=version, destination_alias=destination_alias,
        retention_class=retention, sensitivity=SensitivityClass.PRIVATE,
        source_ref="test:fixture", metadata=metadata or {},
    )


def gateway(*, max_attempts=5):
    ledger = ArtifactLedger(); storage = InMemoryStorage(); projection = InMemoryProjection(); signer = HMACReceiptSigner(KEY)
    service = ArtifactGateway(ledger=ledger, storage=storage, projection=projection, signer=signer, max_attempts=max_attempts)
    return service, ledger, storage, projection, signer


class SecurityTests(unittest.TestCase):
    def test_plain_text_passes(self):
        report = scan_artifact(request()); self.assertTrue(report.passed); self.assertEqual(report.sha256, sha256_bytes(b"# Verified artifact\n"))
    def test_secret_token_is_rejected(self):
        synthetic = b"token = '" + b"sk-" + b"proj-" + (b"A" * 32) + b"'"
        with self.assertRaises(ScanViolation): scan_artifact(request(content=synthetic))
    def test_secret_metadata_field_is_rejected(self):
        with self.assertRaises(ScanViolation): scan_artifact(request(metadata={"api_key": "not-even-needed"}))
    def test_secret_reference_metadata_is_allowed(self): self.assertTrue(scan_artifact(request(metadata={"api_key_ref": "OPENROUTER_KEY_ALIAS"})).passed)
    def test_hidden_reasoning_marker_is_rejected(self):
        with self.assertRaises(ScanViolation): scan_artifact(request(content=b"hidden_reasoning: do not publish"))
    def test_raw_provider_id_destination_is_rejected(self):
        with self.assertRaises(ScanViolation): scan_artifact(request(destination_alias="1vLgKS8EhMKrjuFo6tsKVzI-LFtVyel8L"))
    def test_mime_extension_mismatch_is_rejected(self):
        with self.assertRaises(ScanViolation): scan_artifact(request(name="report.pdf", media_type="text/plain"))
    def test_fake_pdf_is_rejected(self):
        with self.assertRaises(ScanViolation): scan_artifact(request(name="report.pdf", media_type="application/pdf", content=b"not pdf"))
    def test_macro_format_is_rejected(self):
        with self.assertRaises(ScanViolation): scan_artifact(request(name="report.docm", media_type="application/octet-stream"))
    def test_zip_traversal_is_rejected(self):
        buffer=io.BytesIO();
        with zipfile.ZipFile(buffer,"w") as archive: archive.writestr("../escape.txt","bad")
        with self.assertRaises(ScanViolation): scan_artifact(request(name="bad.zip",media_type="application/zip",content=buffer.getvalue()))
    def test_zip_bomb_ratio_is_rejected(self):
        buffer=io.BytesIO();
        with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_DEFLATED) as archive: archive.writestr("zeros.bin",b"0"*(2*1024*1024))
        with self.assertRaises(ScanViolation): scan_artifact(request(name="bomb.zip",media_type="application/zip",content=buffer.getvalue()))
    def test_duplicate_archive_entry_is_rejected(self):
        buffer=io.BytesIO();
        with zipfile.ZipFile(buffer,"w") as archive: archive.writestr("a.txt","one"); archive.writestr("A.TXT","two")
        with self.assertRaises(ScanViolation): scan_artifact(request(name="dup.zip",media_type="application/zip",content=buffer.getvalue()))


class LedgerTests(unittest.TestCase):
    def test_idempotency_key_is_deterministic(self):
        req=request(); digest=sha256_bytes(req.content); self.assertEqual(ArtifactLedger.idempotency_key(req,digest),ArtifactLedger.idempotency_key(req,digest))
    def test_idempotency_collision_fails_closed(self):
        ledger=ArtifactLedger(); req=request(); digest=sha256_bytes(req.content); ledger.get_or_create(req,content_sha256=digest,size_bytes=len(req.content))
        with self.assertRaises(IdempotencyCollision): ledger.get_or_create(replace(req,media_type="application/octet-stream"),content_sha256=digest,size_bytes=len(req.content))
    def test_illegal_transition_is_rejected(self):
        ledger=ArtifactLedger(); req=request(); tx,_=ledger.get_or_create(req,content_sha256=sha256_bytes(req.content),size_bytes=len(req.content))
        with self.assertRaises(InvalidTransition): ledger.transition(tx["transaction_id"],TransactionState.DELIVERED,event_type="BYPASS")
    def test_generation_fence_rejects_stale_writer(self):
        ledger=ArtifactLedger(); req=request(); tx,_=ledger.get_or_create(req,content_sha256=sha256_bytes(req.content),size_bytes=len(req.content)); ledger.transition(tx["transaction_id"],TransactionState.QUARANTINED,event_type="STEP",expected_generation=1)
        with self.assertRaises(InvalidTransition): ledger.transition(tx["transaction_id"],TransactionState.VALIDATED,event_type="STALE",expected_generation=1)
    def test_event_chain_detects_tampering(self):
        service,ledger,*_=gateway(); self.assertEqual(service.deliver(request()).state,TransactionState.DELIVERED); self.assertTrue(ledger.verify_event_chain()); ledger.tamper_event_for_test(1,'{"tampered":true}'); self.assertFalse(ledger.verify_event_chain())
    def test_sqlite_ledger_survives_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"fabric.sqlite3"); ledger=ArtifactLedger(path); req=request(); tx,_=ledger.get_or_create(req,content_sha256=sha256_bytes(req.content),size_bytes=len(req.content)); transaction_id=tx["transaction_id"]; ledger.close(); reopened=ArtifactLedger(path); self.assertEqual(reopened.get(transaction_id)["artifact_name"],req.artifact_name); self.assertTrue(reopened.verify_event_chain())
    def test_merkle_root_is_order_independent(self): self.assertEqual(merkle_root(["0"*64,"1"*64]),merkle_root(["1"*64,"0"*64]))


class GatewayTests(unittest.TestCase):
    def test_full_delivery_transaction(self):
        service,ledger,storage,projection,_=gateway(); outcome=service.deliver(request()); self.assertEqual(outcome.state,TransactionState.DELIVERED); self.assertFalse(outcome.reused_existing); self.assertEqual(storage.put_calls,1); self.assertEqual(projection.commit_calls,1); self.assertTrue(ledger.verify_event_chain()); self.assertIn("signature",outcome.receipt)
    def test_duplicate_retry_reuses_one_provider_object(self):
        service,_,storage,projection,_=gateway(); first=service.deliver(request()); second=service.deliver(request()); self.assertEqual(first.transaction_id,second.transaction_id); self.assertTrue(second.reused_existing); self.assertEqual(storage.put_calls,1); self.assertEqual(projection.commit_calls,1)
    def test_crash_after_provider_write_resumes_without_duplicate(self):
        service,ledger,storage,*_=gateway();
        with self.assertRaises(InjectedCrash): service.deliver(request(),crash_after=TransactionState.DRIVE_WRITTEN)
        self.assertEqual(storage.put_calls,1); self.assertEqual(service.deliver(request()).state,TransactionState.DELIVERED); self.assertEqual(storage.put_calls,1); self.assertTrue(ledger.verify_event_chain())
    def test_temporary_storage_failure_holds_and_resumes(self):
        service,_,storage,*_=gateway(); storage.fail_put_times=1; self.assertEqual(service.deliver(request()).state,TransactionState.HOLD); self.assertEqual(service.deliver(request()).state,TransactionState.DELIVERED)
    def test_repeated_temporary_failure_dead_letters(self):
        service,_,storage,*_=gateway(max_attempts=2); storage.fail_put_times=5; self.assertEqual(service.deliver(request()).state,TransactionState.HOLD); self.assertEqual(service.deliver(request()).state,TransactionState.DEAD_LETTER); self.assertEqual(service.deliver(request()).state,TransactionState.DEAD_LETTER)
    def test_security_hold_does_not_auto_retry(self):
        service,_,storage,*_=gateway(); unsafe=request(content=b"password=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"); self.assertEqual(service.deliver(unsafe).state,TransactionState.HOLD); self.assertEqual(service.deliver(unsafe).state,TransactionState.HOLD); self.assertEqual(storage.put_calls,0)
    def test_shared_provider_readback_fails_and_rolls_back(self):
        service,_,storage,*_=gateway();
        with self.assertRaises(InjectedCrash): service.deliver(request(),crash_after=TransactionState.DRIVE_WRITTEN)
        object_id=next(iter(storage.bytes_by_id)); storage.readback_overrides[object_id]={"shared":True}; self.assertEqual(service.deliver(request()).state,TransactionState.FAILED); self.assertEqual(storage.delete_calls,1)
    def test_hash_mismatch_fails_and_rolls_back(self):
        service,_,storage,*_=gateway();
        with self.assertRaises(InjectedCrash): service.deliver(request(),crash_after=TransactionState.DRIVE_WRITTEN)
        object_id=next(iter(storage.bytes_by_id)); storage.readback_overrides[object_id]={"sha256":"f"*64}; self.assertEqual(service.deliver(request()).state,TransactionState.FAILED); self.assertEqual(storage.delete_calls,1)
    def test_projection_outage_holds_and_resumes(self):
        service,_,storage,projection,_=gateway(); projection.fail_commit_times=1; self.assertEqual(service.deliver(request()).state,TransactionState.HOLD); self.assertEqual(service.deliver(request()).state,TransactionState.DELIVERED); self.assertEqual(storage.put_calls,1); self.assertEqual(projection.commit_calls,2)
    def test_receipt_signature_detects_tampering(self):
        service,_,_,_,signer=gateway(); outcome=service.deliver(request()); transaction=service.ledger.get(outcome.transaction_id); signed_payload=dict(transaction["receipt"]); signed_payload.pop("signature",None); signed_payload.pop("receipt_sha256",None)
        from federation_artifact_fabric_v3.model import SignatureEnvelope
        envelope=SignatureEnvelope(**transaction["signature"]); self.assertTrue(signer.verify(signed_payload,envelope)); signed_payload["size_bytes"]+=1; self.assertFalse(signer.verify(signed_payload,envelope))
    def test_all_retention_classes_can_be_recorded(self):
        for index,retention in enumerate(RetentionClass):
            service,*_=gateway(); outcome=service.deliver(request(name=f"r{index}.txt",media_type="text/plain",content=b"safe",retention=retention)); self.assertEqual(outcome.state,TransactionState.DELIVERED); self.assertEqual(outcome.receipt["retention_class"],retention.value)
    def test_gateway_has_no_email_send_surface(self):
        service,*_=gateway(); self.assertFalse(hasattr(service,"send_email")); self.assertFalse(hasattr(service.storage,"send_continuity_email"))


class MigrationTests(unittest.TestCase):
    def record(self, **changes):
        values=dict(artifact_name="legacy.md",content_sha256="a"*64,size_bytes=42,media_type="text/markdown",object_id="DRIVE-LEGACY-1",parent_alias="PRIVATE_DRIVE_CANONICAL",workstream="LEGACY-V2",version="2.0",evidence_ref="receipt:v2:1"); values.update(changes); return LegacyArtifactRecord(**values)
    def test_verified_private_v2_record_migrates_without_provider_replay(self):
        ledger=ArtifactLedger(); transaction=GenesisImporter(ledger=ledger,signer=HMACReceiptSigner(KEY)).import_record(self.record()); self.assertEqual(transaction["state"],TransactionState.DELIVERED); self.assertFalse(transaction["provider_object"]["created_new"]); self.assertTrue(ledger.verify_event_chain())
    def test_shared_v2_record_is_rejected(self):
        with self.assertRaises(ValueError): GenesisImporter(ledger=ArtifactLedger(),signer=HMACReceiptSigner(KEY)).import_record(self.record(shared=True))
    def test_unverified_v2_record_is_rejected(self):
        with self.assertRaises(ValueError): GenesisImporter(ledger=ArtifactLedger(),signer=HMACReceiptSigner(KEY)).import_record(self.record(readback_verified=False))


class ReconciliationTests(unittest.TestCase):
    def test_clean_delivery_has_no_drift(self):
        service,ledger,storage,projection,_=gateway(); service.deliver(request()); self.assertEqual(ArtifactReconciler(ledger=ledger,storage=storage,projection=projection).inspect(),[])
    def test_sharing_drift_is_detected(self):
        service,ledger,storage,projection,_=gateway(); outcome=service.deliver(request()); object_id=ledger.get(outcome.transaction_id)["provider_object"]["object_id"]; storage.readback_overrides[object_id]={"shared":True}; findings=ArtifactReconciler(ledger=ledger,storage=storage,projection=projection).inspect(); self.assertIn("SHARING_DRIFT",{item.code for item in findings})
    def test_hash_drift_is_detected(self):
        service,ledger,storage,projection,_=gateway(); outcome=service.deliver(request()); object_id=ledger.get(outcome.transaction_id)["provider_object"]["object_id"]; storage.readback_overrides[object_id]={"sha256":"a"*64}; findings=ArtifactReconciler(ledger=ledger,storage=storage,projection=projection).inspect(); self.assertIn("HASH_DRIFT",{item.code for item in findings})
    def test_missing_projection_is_repaired_only_after_provider_proof(self):
        service,ledger,storage,projection,_=gateway(); outcome=service.deliver(request()); projection.rows.pop(outcome.transaction_id); reconciler=ArtifactReconciler(ledger=ledger,storage=storage,projection=projection); self.assertIn("PROJECTION_MISSING",{item.code for item in reconciler.inspect()}); self.assertTrue(reconciler.repair_projection(outcome.transaction_id)); self.assertEqual(reconciler.inspect(),[])


if __name__ == "__main__": unittest.main()
