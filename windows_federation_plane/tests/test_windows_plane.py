from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from federation_windows_plane import TaskEnvelope, WindowsPlane
from federation_windows_plane.models import verify_receipt_mapping


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


class WindowsPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = datetime.now(timezone.utc)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def task(self, kind="health", parameters=None, **changes):
        raw = {
            "schema":"FEDERATION-WINDOWS-TASK-V1", "task_id":"task-1",
            "correlation_id":"corr-1", "issued_by":"FUSE/FDOF", "task_type":kind,
            "issued_at":iso(self.now - timedelta(seconds=1)),
            "expires_at":iso(self.now + timedelta(minutes=5)),
            "parameters":parameters or {}, "effect":"READ_ONLY",
        }
        raw.update(changes)
        return TaskEnvelope.from_mapping(raw)

    def heavy_parameters(self, **changes):
        params = {
            "bytes_per_round": 1024 * 1024,
            "rounds": 2,
            "requested_workers": 4,
            "requested_memory_mb": 256,
            "max_seconds": 30,
            "seed_hex": "ab" * 32,
        }
        params.update(changes)
        return params

    def test_health_receipt_is_hash_bound(self):
        task = self.task()
        receipt = WindowsPlane(self.root, require_windows=False).execute(task)
        expected = hashlib.sha256(json.dumps(receipt.result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(receipt.result_sha256, expected)
        expected_task = hashlib.sha256(json.dumps(task.__dict__, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(receipt.task_sha256, expected_task)
        self.assertEqual(receipt.task, task.__dict__)
        self.assertFalse(receipt.result["arbitrary_command_execution"])

    def test_receipt_verifier_rejects_hash_tampering(self):
        receipt = WindowsPlane(self.root, require_windows=False).execute(self.task()).to_dict()
        receipt["runner"] = dict(receipt["runner"], os="Windows", github_actions=True, source_sha="a" * 40)
        verify_receipt_mapping(receipt, expected_source_sha="a" * 40)
        receipt["result"] = dict(receipt["result"], status="tampered")
        with self.assertRaisesRegex(ValueError, "RESULT_HASH_MISMATCH"):
            verify_receipt_mapping(receipt, expected_source_sha="a" * 40)

    def test_receipt_verifier_rejects_wrong_source(self):
        receipt = WindowsPlane(self.root, require_windows=False).execute(self.task()).to_dict()
        receipt["runner"] = dict(receipt["runner"], os="Windows", github_actions=True, source_sha="a" * 40)
        with self.assertRaisesRegex(ValueError, "EXACT_SOURCE_SHA_MISMATCH"):
            verify_receipt_mapping(receipt, expected_source_sha="b" * 40)

    def test_inventory_is_privacy_minimized(self):
        result = WindowsPlane(self.root, require_windows=False).execute(self.task("inventory")).result
        self.assertFalse(result["workspace_path_disclosed"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_hash_is_bounded_to_workspace(self):
        target = self.root / "sample.txt"
        target.write_text("federation", encoding="utf-8")
        result = WindowsPlane(self.root, require_windows=False).execute(
            self.task("hash_workspace_file", {"relative_path":"sample.txt"})
        ).result
        self.assertEqual(result["relative_path"], "sample.txt")
        self.assertEqual(result["sha256"], hashlib.sha256(b"federation").hexdigest())

    def test_heavy_sha256_is_deterministic_and_governed(self):
        plane = WindowsPlane(self.root, require_windows=False)
        first = plane.execute(self.task("heavy_sha256", self.heavy_parameters())).result
        second = plane.execute(self.task("heavy_sha256", self.heavy_parameters())).result
        self.assertEqual(first["final_sha256"], second["final_sha256"])
        self.assertEqual(first["total_bytes"], 2 * 1024 * 1024)
        self.assertEqual(first["rounds"], 2)
        self.assertTrue(first["resource_governor_bound"])
        self.assertTrue(first["generated_in_memory"])
        self.assertFalse(first["filesystem_used"])
        self.assertFalse(first["network_used"])
        self.assertFalse(first["shell_process_used"])
        self.assertFalse(first["gpu_used"])
        self.assertGreater(first["granted_workers"], 0)
        self.assertLessEqual(first["granted_workers"], first["requested_workers"])

    def test_heavy_sha256_rejects_extra_or_malformed_parameters(self):
        with self.assertRaisesRegex(ValueError, "HEAVY_SHA256_REQUIRES_EXACT_PARAMETERS"):
            WindowsPlane(self.root, require_windows=False).execute(
                self.task("heavy_sha256", self.heavy_parameters(extra=1))
            )
        with self.assertRaisesRegex(ValueError, "HEAVY_SHA256_BYTES_PER_ROUND_TYPE_INVALID"):
            WindowsPlane(self.root, require_windows=False).execute(
                self.task("heavy_sha256", self.heavy_parameters(bytes_per_round="1048576"))
            )

    def test_heavy_sha256_rejects_total_byte_overflow(self):
        with self.assertRaisesRegex(ValueError, "HEAVY_SHA256_TOTAL_BYTES_LIMIT_EXCEEDED"):
            WindowsPlane(self.root, require_windows=False).execute(
                self.task("heavy_sha256", self.heavy_parameters(bytes_per_round=64 * 1024 * 1024, rounds=33))
            )

    def test_path_escape_is_denied(self):
        with self.assertRaisesRegex(ValueError, "PATH_ESCAPE_DENIED"):
            WindowsPlane(self.root, require_windows=False).execute(
                self.task("hash_workspace_file", {"relative_path":"../outside.txt"})
            )

    def test_absolute_path_is_denied(self):
        with self.assertRaisesRegex(ValueError, "ABSOLUTE_PATH_DENIED"):
            WindowsPlane(self.root, require_windows=False).execute(
                self.task("hash_workspace_file", {"relative_path":str(self.root / "x")})
            )

    def test_unknown_task_is_denied(self):
        with self.assertRaisesRegex(ValueError, "TASK_TYPE_NOT_ALLOWLISTED"):
            self.task("shell").validate(now=self.now)

    def test_non_read_only_effect_is_denied(self):
        with self.assertRaisesRegex(ValueError, "EFFECT_NOT_AUTHORIZED"):
            self.task(effect="MUTATING").validate(now=self.now)

    def test_untrusted_issuer_is_denied(self):
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_TASK_ISSUER"):
            self.task(issued_by="unknown").validate(now=self.now)

    def test_expired_task_is_denied(self):
        with self.assertRaisesRegex(ValueError, "TASK_EXPIRED"):
            self.task(
                issued_at=iso(self.now - timedelta(minutes=2)),
                expires_at=iso(self.now - timedelta(seconds=2)),
            ).validate(now=self.now)

    def test_long_ttl_is_denied(self):
        with self.assertRaisesRegex(ValueError, "TASK_TTL_EXCEEDS_900_SECONDS"):
            self.task(expires_at=iso(self.now + timedelta(hours=1))).validate(now=self.now)

    def test_unknown_fields_are_denied(self):
        raw = self.task().__dict__ | {"command":"whoami"}
        with self.assertRaisesRegex(ValueError, "UNKNOWN_ENVELOPE_FIELDS"):
            TaskEnvelope.from_mapping(raw)


if __name__ == "__main__":
    unittest.main()
