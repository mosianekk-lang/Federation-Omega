from __future__ import annotations

import tempfile
import time
import unittest

from sovereign_intent_guardian.policy import evaluate
from sovereign_intent_guardian.provider import AdvisoryReview
from sovereign_intent_guardian.store import GuardianStore, LeaseRejected
from sovereign_intent_guardian.worker import GuardianWorker
from tests.helpers import audit_request, trust, trusted_registry


class MaliciousCallable:
    def __init__(self):
        self.called = False

    def __call__(self, *args, **kwargs):
        self.called = True
        raise AssertionError("must never execute")


class WorkerAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = GuardianStore(
            f"{self.temp.name}/guardian.db", trusted_attestations=trusted_registry()
        )
        self.store.initialize()
        self.base = time.time()

    def tearDown(self):
        self.temp.cleanup()

    def run_worker(self, request, advisory_review=None):
        trust(self.store, request)
        task_id = self.store.enqueue(request, now=self.base)
        worker = GuardianWorker(
            self.store,
            worker_id="sig-worker",
            boot_id="boot-one",
            advisory_review=advisory_review,
        )
        worker.start(now=self.base)
        return task_id, worker.run_once(now=self.base)

    def test_deterministic_block_does_not_consume_advisory_receipt(self):
        receipt = AdvisoryReview("recording-provider", ("2" * 64,), "ALIGN")
        task_id, result = self.run_worker(
            audit_request(proposed_action={"requested_effects": ["SEND_COMMUNICATION"]}), receipt
        )
        self.assertEqual("BLOCK", result["verdict"])
        self.assertFalse(result["authorizes_action"])
        stored = self.store.task(task_id)["result_json"]
        self.assertIn('"provider_id":"not-consumed"', stored)

    def test_contract_and_advisory_payload_are_value_suppressed(self):
        request = audit_request()
        payload = request.advisory_payload()
        self.assertNotIn("latest_instruction", payload)
        self.assertNotIn("description", payload["action"])
        self.assertIn("latest_instruction_hash", request.to_dict())
        self.assertIn("description_hash", request.to_dict()["proposed_action"])

    def test_invalid_advisory_hash_is_terminal(self):
        receipt = AdvisoryReview("recording-provider", ("raw owner voice",), "ALIGN")
        task_id, result = self.run_worker(audit_request(), receipt)
        self.assertEqual("DEAD_LETTER", result["state"])
        self.assertEqual("ADVISORY_RECEIPT_HASH_INVALID", result["reason_code"])
        self.assertEqual("DEAD_LETTER", self.store.task(task_id)["state"])

    def test_callable_provider_object_is_rejected_without_execution(self):
        malicious = MaliciousCallable()
        task_id, result = self.run_worker(audit_request(), malicious)
        self.assertFalse(malicious.called)
        self.assertEqual("DEAD_LETTER", result["state"])
        self.assertEqual("ADVISORY_RECEIPT_SCHEMA_INVALID", result["reason_code"])
        self.assertEqual("DEAD_LETTER", self.store.task(task_id)["state"])

    def test_align_is_never_an_execution_permit(self):
        receipt = AdvisoryReview("recording-provider", (), "ALIGN")
        task_id, result = self.run_worker(audit_request(), receipt)
        self.assertEqual("ALIGN", result["verdict"])
        self.assertEqual("NONE", result["release_authority"])
        readback = self.store.semantic_readback(task_id)
        self.assertFalse(readback["authorizes_action"])
        self.assertFalse(readback["effect_performed"])

    def test_output_ledger_race_is_rejected_before_completion(self):
        request = audit_request()
        self.store.enqueue(request, now=self.base)
        self.store.register_worker("sig-worker", "boot-one", now=self.base)
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        count, ledger_hash = self.store.output_snapshot(request.mission_id, request.mission_version)
        result = evaluate(
            request,
            delivered_output_count=count,
            output_ledger_hash=ledger_hash,
            output_ledger_verified=True,
            advisory_available=False,
            continuity_attestation_verified=True,
        )
        self.store.record_delivered_output(
            occurrence_id="racing-output", mission_id=request.mission_id,
            mission_version=request.mission_version, payload_hash="2" * 64,
            now=self.base + 1,
        )
        with self.assertRaisesRegex(LeaseRejected, "OUTPUT_LEDGER_SNAPSHOT_MISMATCH"):
            self.store.complete_task(lease, result, now=self.base + 1)


if __name__ == "__main__":
    unittest.main()
