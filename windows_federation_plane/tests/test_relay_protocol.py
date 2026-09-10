from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from federation_windows_plane.relay_protocol import SovereignRelay, sign_request


NOW = datetime(2026, 9, 10, 19, 30, 0, tzinfo=timezone.utc)


def task(task_id: str = "task-1", *, task_type: str = "health", effect: str = "READ_ONLY"):
    return {
        "schema": "FEDERATION-WINDOWS-TASK-V1",
        "task_id": task_id,
        "correlation_id": "corr-1",
        "issued_by": "FUSE/FDOF",
        "task_type": task_type,
        "issued_at": "2026-09-10T19:30:00Z",
        "expires_at": "2026-09-10T19:35:00Z",
        "parameters": {},
        "effect": effect,
    }


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def receipt(
    task_id: str = "task-1", *, correlation_id: str = "corr-1", task_type: str = "health"
):
    task_body = task(task_id=task_id, task_type=task_type)
    task_body["correlation_id"] = correlation_id
    result = {"status": "healthy"}
    return {
        "schema": "FEDERATION-WINDOWS-RECEIPT-V1",
        "task_id": task_id,
        "correlation_id": correlation_id,
        "task_type": task_type,
        "state": "COMPLETED_VERIFIED_LOCAL",
        "started_at": "2026-09-10T19:30:01Z",
        "completed_at": "2026-09-10T19:30:02Z",
        "runner": {"os": "Windows", "hostname_sha256": "0" * 64},
        "task": task_body,
        "result": result,
        "task_sha256": _digest(task_body),
        "result_sha256": _digest(result),
        "effect": "READ_ONLY",
        "truth_boundary": "Test semantic receipt only.",
    }


class RelayProtocolTests(unittest.TestCase):
    def setUp(self):
        self.relay = SovereignRelay(enrollment_ttl_seconds=300, request_skew_seconds=60, lease_ttl_seconds=120)
        grant = self.relay.issue_enrollment(now=NOW)
        self.grant = grant
        self.credential = self.relay.enroll(
            enrollment_id=grant.enrollment_id,
            enrollment_token=grant.enrollment_token,
            device_label="kim-windows-baseline",
            now=NOW,
        )

    def test_enrollment_is_single_use(self):
        with self.assertRaisesRegex(ValueError, "ENROLLMENT_ALREADY_USED"):
            self.relay.enroll(
                enrollment_id=self.grant.enrollment_id,
                enrollment_token=self.grant.enrollment_token,
                device_label="kim-windows-baseline",
                now=NOW,
            )

    def test_expired_enrollment_is_rejected(self):
        relay = SovereignRelay(enrollment_ttl_seconds=30)
        grant = relay.issue_enrollment(now=NOW)
        with self.assertRaisesRegex(ValueError, "ENROLLMENT_EXPIRED"):
            relay.enroll(
                enrollment_id=grant.enrollment_id,
                enrollment_token=grant.enrollment_token,
                device_label="late-device",
                now=NOW + timedelta(seconds=31),
            )

    def test_bad_enrollment_token_is_rejected_without_consuming_grant(self):
        relay = SovereignRelay()
        grant = relay.issue_enrollment(now=NOW)
        with self.assertRaisesRegex(ValueError, "ENROLLMENT_TOKEN_INVALID"):
            relay.enroll(
                enrollment_id=grant.enrollment_id,
                enrollment_token="x" * 43,
                device_label="device-a",
                now=NOW,
            )
        credential = relay.enroll(
            enrollment_id=grant.enrollment_id,
            enrollment_token=grant.enrollment_token,
            device_label="device-a",
            now=NOW,
        )
        self.assertTrue(credential.device_id.startswith("dev_"))

    def _signed(self, *, nonce="nonce-1", body=b"", timestamp="2026-09-10T19:30:00Z"):
        sig = sign_request(
            self.credential.device_secret,
            method="POST",
            path="/agent/poll",
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
        return sig

    def test_valid_device_request_is_accepted(self):
        self.relay.verify_device_request(
            device_id=self.credential.device_id,
            method="POST",
            path="/agent/poll",
            timestamp="2026-09-10T19:30:00Z",
            nonce="nonce-1",
            signature=self._signed(),
            body=b"",
            now=NOW,
        )

    def test_replay_is_rejected(self):
        sig = self._signed()
        kwargs = dict(
            device_id=self.credential.device_id,
            method="POST",
            path="/agent/poll",
            timestamp="2026-09-10T19:30:00Z",
            nonce="nonce-1",
            signature=sig,
            body=b"",
            now=NOW,
        )
        self.relay.verify_device_request(**kwargs)
        with self.assertRaisesRegex(ValueError, "REPLAY_DETECTED"):
            self.relay.verify_device_request(**kwargs)

    def test_stale_signature_is_rejected(self):
        stamp = "2026-09-10T19:28:00Z"
        sig = self._signed(timestamp=stamp)
        with self.assertRaisesRegex(ValueError, "REQUEST_TIMESTAMP_OUTSIDE_WINDOW"):
            self.relay.verify_device_request(
                device_id=self.credential.device_id,
                method="POST",
                path="/agent/poll",
                timestamp=stamp,
                nonce="nonce-old",
                signature=sig,
                body=b"",
                now=NOW,
            )

    def test_non_z_request_timestamp_is_rejected(self):
        stamp = "2026-09-10T19:30:00+00:00"
        sig = self._signed(timestamp=stamp)
        with self.assertRaisesRegex(ValueError, "REQUEST_TIMESTAMP_INVALID"):
            self.relay.verify_device_request(
                device_id=self.credential.device_id,
                method="POST",
                path="/agent/poll",
                timestamp=stamp,
                nonce="nonce-offset",
                signature=sig,
                body=b"",
                now=NOW,
            )

    def test_tampered_body_is_rejected(self):
        sig = self._signed(body=b'{"a":1}')
        with self.assertRaisesRegex(ValueError, "REQUEST_SIGNATURE_INVALID"):
            self.relay.verify_device_request(
                device_id=self.credential.device_id,
                method="POST",
                path="/agent/poll",
                timestamp="2026-09-10T19:30:00Z",
                nonce="nonce-body",
                signature=sig,
                body=b'{"a":2}',
                now=NOW,
            )

    def test_only_read_only_allowlisted_tasks_can_enter_queue(self):
        with self.assertRaisesRegex(ValueError, "TASK_TYPE_NOT_ALLOWLISTED"):
            self.relay.submit_task(device_id=self.credential.device_id, task=task(task_type="shell"))
        with self.assertRaisesRegex(ValueError, "TASK_EFFECT_NOT_AUTHORIZED"):
            self.relay.submit_task(device_id=self.credential.device_id, task=task(effect="WRITE"))

    def test_expired_and_unknown_field_tasks_are_rejected(self):
        expired = task()
        expired["issued_at"] = "2026-09-10T19:20:00Z"
        expired["expires_at"] = "2026-09-10T19:25:00Z"
        with self.assertRaisesRegex(ValueError, "TASK_EXPIRED"):
            self.relay.submit_task(device_id=self.credential.device_id, task=expired, now=NOW)
        unknown = task()
        unknown["shell"] = "whoami"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_TASK_FIELDS"):
            self.relay.submit_task(device_id=self.credential.device_id, task=unknown, now=NOW)

    def test_receipt_hash_tamper_is_rejected(self):
        self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW)
        _, lease = self.relay.poll(device_id=self.credential.device_id, now=NOW)
        forged = receipt()
        forged["result"]["status"] = "forged"
        with self.assertRaisesRegex(ValueError, "RESULT_HASH_MISMATCH"):
            self.relay.complete(
                device_id=self.credential.device_id,
                task_id="task-1",
                lease_token=lease.lease_token,
                receipt=forged,
                now=NOW,
            )

    def test_idempotent_same_task_submission_and_collision_rejection(self):
        task_id = self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW)
        self.assertEqual(task_id, self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW))
        changed = task()
        changed["correlation_id"] = "corr-2"
        with self.assertRaisesRegex(ValueError, "TASK_ID_COLLISION"):
            self.relay.submit_task(device_id=self.credential.device_id, task=changed, now=NOW)

    def test_poll_leases_and_expired_lease_can_be_reissued(self):
        self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW)
        first = self.relay.poll(device_id=self.credential.device_id, now=NOW)
        self.assertIsNotNone(first)
        self.assertIsNone(self.relay.poll(device_id=self.credential.device_id, now=NOW + timedelta(seconds=30)))
        second = self.relay.poll(device_id=self.credential.device_id, now=NOW + timedelta(seconds=121))
        self.assertIsNotNone(second)
        self.assertNotEqual(first[1].lease_token, second[1].lease_token)

    def test_foreign_device_cannot_poll_targeted_task(self):
        grant = self.relay.issue_enrollment(now=NOW)
        other = self.relay.enroll(
            enrollment_id=grant.enrollment_id,
            enrollment_token=grant.enrollment_token,
            device_label="other-device",
            now=NOW,
        )
        self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW)
        self.assertIsNone(self.relay.poll(device_id=other.device_id, now=NOW))

    def test_completion_requires_live_exact_lease_and_matching_receipt(self):
        self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW)
        leased_task, lease = self.relay.poll(device_id=self.credential.device_id, now=NOW)
        with self.assertRaisesRegex(ValueError, "LEASE_TOKEN_INVALID"):
            self.relay.complete(
                device_id=self.credential.device_id,
                task_id="task-1",
                lease_token="wrong-token",
                receipt=receipt(),
                now=NOW,
            )
        with self.assertRaisesRegex(ValueError, "RECEIPT_CORRELATION_MISMATCH"):
            self.relay.complete(
                device_id=self.credential.device_id,
                task_id="task-1",
                lease_token=lease.lease_token,
                receipt=receipt(correlation_id="other"),
                now=NOW,
            )
        stored = self.relay.complete(
            device_id=self.credential.device_id,
            task_id="task-1",
            lease_token=lease.lease_token,
            receipt=receipt(),
            now=NOW,
        )
        self.assertEqual(stored["state"], "COMPLETED_VERIFIED_LOCAL")
        status = self.relay.status("task-1")
        self.assertTrue(status["completed"])
        self.assertEqual(len(status["receipt_sha256"]), 64)

    def test_exact_completed_receipt_is_idempotent(self):
        self.relay.submit_task(device_id=self.credential.device_id, task=task(), now=NOW)
        _, lease = self.relay.poll(device_id=self.credential.device_id, now=NOW)
        expected = receipt()
        first = self.relay.complete(
            device_id=self.credential.device_id,
            task_id="task-1",
            lease_token=lease.lease_token,
            receipt=expected,
            now=NOW,
        )
        second = self.relay.complete(
            device_id=self.credential.device_id,
            task_id="task-1",
            lease_token="does-not-matter-after-exact-completion",
            receipt=expected,
            now=NOW,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
