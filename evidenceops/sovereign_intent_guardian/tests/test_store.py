from __future__ import annotations

import hashlib
from dataclasses import replace
import sqlite3
import tempfile
import time
import unittest

from sovereign_intent_guardian.contracts import Verdict, canonical_json
from sovereign_intent_guardian.policy import evaluate
from sovereign_intent_guardian.store import (
    GuardianStore,
    IdempotencyConflict,
    LeaseRejected,
    StopLatched,
)
from sovereign_intent_guardian.contracts import ValidationError
from tests.helpers import audit_request, digest, resume_registry, trust, trusted_registry


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = f"{self.temp.name}/guardian.db"
        resumes, self.resume_hash = resume_registry()
        self.store = GuardianStore(
            self.path,
            trusted_attestations=trusted_registry(),
            trusted_resume_records=resumes,
        )
        self.store.initialize()
        self.base = time.time()

    def tearDown(self):
        self.temp.cleanup()

    def worker(self, worker="sig-worker", boot="boot-one"):
        self.store.register_worker(worker, boot, now=self.base)
        return worker, boot

    def result_for(self, request, advisory=False):
        count, ledger_hash = self.store.output_snapshot(request.mission_id, request.mission_version)
        return evaluate(
            request,
            delivered_output_count=count,
            output_ledger_hash=ledger_hash,
            output_ledger_verified=True,
            advisory_available=advisory,
            continuity_attestation_verified=self.store.verify_continuity(request),
        )

    def test_initialize_and_reopen_preserve_queue(self):
        task_id = self.store.enqueue(audit_request(), now=self.base)
        resumes, _ = resume_registry()
        reopened = GuardianStore(
            self.path, trusted_attestations=trusted_registry(), trusted_resume_records=resumes
        )
        reopened.initialize()
        self.assertEqual(task_id, reopened.task(task_id)["task_id"])
        self.assertEqual("DURABLE_FOUNDATION_IMPLEMENTED_NOT_DEPLOYED", reopened.health()["classification"])

    def test_idempotent_enqueue_and_conflict(self):
        first = self.store.enqueue(audit_request(), idempotency_key="same-key", now=self.base)
        second = self.store.enqueue(audit_request(), idempotency_key="same-key", now=self.base)
        self.assertEqual(first, second)
        with self.assertRaises(IdempotencyConflict):
            different = trust(
                self.store,
                audit_request(proposed_action={"description_hash": digest("different action")}),
            )
            self.store.enqueue(
                different,
                idempotency_key="same-key",
                now=self.base,
            )

    def test_secret_like_idempotency_values_are_rejected_before_persistence(self):
        for value in (
            "password: hunter2", "AKIAABCDEFGHIJKLMNOP", "password-hunter2-safe",
            "token-supersecretvalue",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValidationError, "SECRET_LIKE_IDEMPOTENCY"):
                    self.store.enqueue(audit_request(), idempotency_key=value, now=self.base)
        with self.assertRaisesRegex(ValidationError, "idempotency_key_invalid"):
            self.store.enqueue(audit_request(), idempotency_key="private free text", now=self.base)

    def test_secret_like_control_metadata_is_rejected_before_persistence(self):
        for occurrence_id, mission_id in (
            ("password:hunter2", "mission-1"),
            ("password-hunter2", "mission-1"),
            ("output-1", "api-key-supersecretvalue"),
            ("token-supersecretvalue", "mission-1"),
            ("output-1", "token-supersecretvalue"),
        ):
            with self.subTest(occurrence_id=occurrence_id, mission_id=mission_id):
                with self.assertRaisesRegex(ValidationError, "occurrence_id_invalid|mission_id_invalid"):
                    self.store.record_delivered_output(
                        occurrence_id=occurrence_id, mission_id=mission_id,
                        mission_version=2, payload_hash="2" * 64, now=self.base,
                    )
        for subject in (
            "api_key=supersecretvalue", "password-hunter2", "token-supersecretvalue"
        ):
            with self.subTest(subject=subject):
                with self.assertRaisesRegex(ValidationError, "stop_subject_invalid"):
                    self.store.set_stop(
                        scope="MISSION", subject=subject, mission_version=2,
                        reason_code="USER_STOP", now=self.base,
                    )
        for registry_id in ("password:hunter2", "token-supersecretvalue"):
            with self.subTest(registry_id=registry_id):
                with self.assertRaisesRegex(ValidationError, "trusted_attestation_registry_invalid"):
                    GuardianStore(
                        f"{self.temp.name}/invalid.db",
                        trusted_attestations={registry_id: "a" * 64},
                    )
        resume_record = {
            "scope": "MISSION", "subject": "token-supersecretvalue",
            "new_mission_version": 3, "expected_generation": 1,
        }
        resume_hash = hashlib.sha256(
            canonical_json(resume_record).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValidationError, "trusted_resume_registry_invalid"):
            GuardianStore(
                f"{self.temp.name}/invalid-resume.db",
                trusted_resume_records={resume_hash: resume_record},
            )
        for worker_id, boot_id, expected in (
            ("sk-abcdefghijklmnopqrstuvwx", "boot-one", "worker_id_invalid"),
            ("sig-worker", "sk-abcdefghijklmnopqrstuvwx", "boot_id_invalid"),
            ("password-hunter2", "boot-one", "worker_id_invalid"),
            ("sig-worker", "api-key-supersecretvalue", "boot_id_invalid"),
            ("token-supersecretvalue", "boot-one", "worker_id_invalid"),
            ("sig-worker", "token-supersecretvalue", "boot_id_invalid"),
        ):
            with self.subTest(worker_id=worker_id, boot_id=boot_id):
                with self.assertRaisesRegex(ValidationError, expected):
                    self.store.register_worker(worker_id, boot_id, now=self.base)
        with self.assertRaisesRegex(ValidationError, "reason_code_invalid"):
            self.store.set_stop(
                scope="MISSION", subject="mission-1", mission_version=2,
                reason_code="AKIAABCDEFGHIJKLMNOP", now=self.base,
            )
        for request in (
            audit_request(mission_id="token-supersecretvalue"),
            audit_request(requirement_ids=["token-supersecretvalue"]),
            audit_request(trusted_attestation_id="token-supersecretvalue"),
        ):
            with self.subTest(request=request):
                with self.assertRaisesRegex(ValidationError, "SECRET_LIKE_INPUT_REJECTED"):
                    self.store.enqueue(request, now=self.base)
        self.store.enqueue(audit_request(), now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        with self.assertRaisesRegex(ValidationError, "reason_code_invalid"):
            self.store.fail_task(
                lease, reason_code="AKIAABCDEFGHIJKLMNOP", transient=False, now=self.base
            )
        connection = sqlite3.connect(self.path)
        persisted = "\n".join(connection.iterdump())
        connection.close()
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", persisted)
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", persisted)
        self.assertNotIn("password-hunter2", persisted)
        self.assertNotIn("api-key-supersecretvalue", persisted)
        self.assertNotIn("token-supersecretvalue", persisted)

    def test_transient_retry_flag_must_be_boolean(self):
        self.store.enqueue(audit_request(), now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        with self.assertRaisesRegex(ValidationError, "transient_flag_invalid"):
            self.store.fail_task(
                lease, reason_code="PROVIDER_TIMEOUT", transient="false", now=self.base
            )
        self.assertEqual("PROCESSING", self.store.task(lease["task_id"])["state"])

    def test_untrusted_self_asserted_continuity_is_rejected(self):
        request = audit_request(source_readback_hash="9" * 64)
        with self.assertRaisesRegex(ValidationError, "CONTINUITY_ATTESTATION_UNTRUSTED"):
            self.store.enqueue(request, now=self.base)

    def test_safe_attestation_cannot_authorize_changed_action(self):
        changed = audit_request(proposed_action={"kind": "READ_ONLY_STATUS"})
        with self.assertRaisesRegex(ValidationError, "CONTINUITY_ATTESTATION_UNTRUSTED"):
            self.store.enqueue(changed, now=self.base)

    def test_worker_identity_cannot_claim_owner_identity(self):
        with self.assertRaisesRegex(ValidationError, "worker_id_invalid"):
            self.store.register_worker("owner-worker", "boot-one", now=self.base)

    def test_two_workers_cannot_claim_same_task(self):
        self.store.enqueue(audit_request(), now=self.base)
        self.worker("sig-worker-a", "boot-one")
        self.worker("sig-worker-b", "boot-two")
        first = self.store.claim_task("sig-worker-a", "boot-one", now=self.base)
        second = self.store.claim_task("sig-worker-b", "boot-two", now=self.base)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_expired_lease_takeover_fences_old_worker(self):
        request = audit_request()
        self.store.enqueue(request, now=self.base)
        self.worker("sig-worker-a", "boot-one")
        self.worker("sig-worker-b", "boot-two")
        old = self.store.claim_task("sig-worker-a", "boot-one", lease_seconds=15, now=self.base)
        new = self.store.claim_task("sig-worker-b", "boot-two", lease_seconds=15, now=self.base + 16)
        self.assertGreater(new["fence_generation"], old["fence_generation"])
        with self.assertRaises(LeaseRejected):
            self.store.complete_task(old, self.result_for(request), now=self.base + 16)

    def test_stop_before_claim_and_authority_bound_resume(self):
        task_id = self.store.enqueue(audit_request(), now=self.base)
        self.worker()
        generation = self.store.set_stop(
            scope="MISSION", subject="mission-1", mission_version=2,
            reason_code="USER_STOP", now=self.base,
        )
        self.assertIsNone(self.store.claim_task("sig-worker", "boot-one", now=self.base))
        with self.assertRaises(StopLatched):
            self.store.clear_stop(
                scope="MISSION", subject="mission-1", new_mission_version=2,
                expected_generation=generation, authority_record_hash=self.resume_hash, now=self.base,
            )
        new_generation = self.store.clear_stop(
            scope="MISSION", subject="mission-1", new_mission_version=3,
            expected_generation=generation, authority_record_hash=self.resume_hash, now=self.base,
        )
        self.assertEqual(generation + 1, new_generation)
        self.assertEqual("DEAD_LETTER", self.store.task(task_id)["state"])

    def test_stale_task_cannot_claim_after_newer_mission_resume(self):
        task_id = self.store.enqueue(audit_request(), now=self.base)
        self.worker()
        generation = self.store.set_stop(
            scope="MISSION", subject="mission-1", mission_version=2,
            reason_code="USER_STOP", now=self.base,
        )
        self.store.clear_stop(
            scope="MISSION", subject="mission-1", new_mission_version=3,
            expected_generation=generation, authority_record_hash=self.resume_hash, now=self.base + 1,
        )
        self.assertEqual("DEAD_LETTER", self.store.task(task_id)["state"])
        self.assertIsNone(self.store.claim_task("sig-worker", "boot-one", now=self.base + 1))

    def test_active_stop_blocks_newer_matching_task_until_clear(self):
        request_v3 = trust(self.store, audit_request(mission_version=3))
        self.store.set_stop(
            scope="MISSION", subject="mission-1", mission_version=2,
            reason_code="USER_STOP", now=self.base,
        )
        with self.assertRaisesRegex(StopLatched, "STOP_LATCHED"):
            self.store.enqueue(request_v3, now=self.base + 1)

    def test_resume_floor_rejects_stale_task_enqueued_after_clear(self):
        generation = self.store.set_stop(
            scope="MISSION", subject="mission-1", mission_version=2,
            reason_code="USER_STOP", now=self.base,
        )
        self.store.clear_stop(
            scope="MISSION", subject="mission-1", new_mission_version=3,
            expected_generation=generation, authority_record_hash=self.resume_hash,
            now=self.base + 1,
        )
        stale = trust(
            self.store,
            audit_request(proposed_action={"description_hash": digest("late stale task")}),
        )
        with self.assertRaisesRegex(ValidationError, "MISSION_VERSION_BELOW_FLOOR"):
            self.store.enqueue(stale, now=self.base + 2)

    def test_untrusted_resume_authority_is_rejected(self):
        generation = self.store.set_stop(
            scope="MISSION", subject="mission-1", mission_version=2,
            reason_code="USER_STOP", now=self.base,
        )
        with self.assertRaisesRegex(StopLatched, "TRUSTED_RESUME_AUTHORITY_REQUIRED"):
            self.store.clear_stop(
                scope="MISSION", subject="mission-1", new_mission_version=3,
                expected_generation=generation, authority_record_hash="9" * 64,
                now=self.base + 1,
            )

    def test_stop_after_lease_fences_completion(self):
        request = audit_request()
        task_id = self.store.enqueue(request, now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        self.store.set_stop(
            scope="GLOBAL", subject="all", mission_version=2,
            reason_code="URGENT_STOP", now=self.base + 1,
        )
        with self.assertRaises(LeaseRejected):
            self.store.complete_task(lease, self.result_for(request), now=self.base + 1)
        self.assertEqual("DEAD_LETTER", self.store.task(task_id)["state"])

    def test_output_delivery_replay_does_not_double_count(self):
        kwargs = dict(
            occurrence_id="output-1", mission_id="mission-1", mission_version=2,
            payload_hash=hashlib.sha256(b"synthetic").hexdigest(), now=self.base,
        )
        first = self.store.record_delivered_output(**kwargs)
        second = self.store.record_delivered_output(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(1, first[0])
        with self.assertRaises(IdempotencyConflict):
            self.store.record_delivered_output(**{**kwargs, "payload_hash": "e" * 64})

    def test_transient_retry_is_bounded_then_dead_letters(self):
        task_id = self.store.enqueue(audit_request(), max_attempts=3, now=self.base)
        self.worker()
        moments = [self.base, self.base + 5, self.base + 15]
        states = []
        for moment in moments:
            lease = self.store.claim_task("sig-worker", "boot-one", now=moment)
            states.append(self.store.fail_task(
                lease, reason_code="PROVIDER_TIMEOUT", transient=True, now=moment
            ))
        self.assertEqual(["RETRY", "RETRY", "DEAD_LETTER"], states)
        self.assertEqual("DEAD_LETTER", self.store.task(task_id)["state"])

    def test_permission_failure_never_retries_and_dead_letter_is_metadata_only(self):
        task_id = self.store.enqueue(audit_request(), now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        state = self.store.fail_task(
            lease, reason_code="AUTHORIZATION_FAILURE", transient=True, now=self.base
        )
        self.assertEqual("DEAD_LETTER", state)
        connection = sqlite3.connect(self.path)
        columns = [row[1] for row in connection.execute("PRAGMA table_info(sig_dead_letters)")]
        connection.close()
        self.assertNotIn("request_json", columns)

    def test_completion_and_semantic_readback(self):
        request = audit_request()
        task_id = self.store.enqueue(request, now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        result = self.result_for(request)
        self.store.complete_task(lease, result, now=self.base)
        receipt = self.store.semantic_readback(task_id)
        self.assertTrue(receipt["verified"])
        self.assertFalse(receipt["authorizes_action"])

    def test_forged_align_result_never_reaches_completed(self):
        request = trust(
            self.store,
            audit_request(proposed_action={"requested_effects": ["DELETE_RESOURCE"]}),
        )
        task_id = self.store.enqueue(request, now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        blocked = self.result_for(request)
        forged = replace(blocked, verdict=Verdict.ALIGN, reason_codes=())
        with self.assertRaisesRegex(LeaseRejected, "DETERMINISTIC_RESULT_MISMATCH"):
            self.store.complete_task(lease, forged, now=self.base)
        self.assertNotEqual("COMPLETED", self.store.task(task_id)["state"])

    def test_raw_advisory_body_cannot_reach_persistence(self):
        request = audit_request()
        task_id = self.store.enqueue(request, now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        unsafe = self.result_for(request)
        unsafe = replace(unsafe, advisory={"raw_body": "untrusted model prose"})
        with self.assertRaisesRegex(LeaseRejected, "ADVISORY_RECEIPT_INVALID"):
            self.store.complete_task(lease, unsafe, now=self.base)
        self.assertNotEqual("COMPLETED", self.store.task(task_id)["state"])

    def test_tampered_result_and_event_chain_are_detected(self):
        request = audit_request()
        task_id = self.store.enqueue(request, now=self.base)
        self.worker()
        lease = self.store.claim_task("sig-worker", "boot-one", now=self.base)
        self.store.complete_task(lease, self.result_for(request), now=self.base)
        connection = sqlite3.connect(self.path)
        connection.execute("UPDATE sig_events SET payload_json='{}' WHERE sequence=1")
        connection.commit()
        connection.close()
        self.assertFalse(self.store.verify_event_chain())
        self.assertFalse(self.store.semantic_readback(task_id)["verified"])
        self.assertFalse(self.store.health()["ok"])


if __name__ == "__main__":
    unittest.main()
