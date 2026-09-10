from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from federation_windows_plane import TaskEnvelope, WindowsPlane


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

    def test_health_receipt_is_hash_bound(self):
        receipt = WindowsPlane(self.root, require_windows=False).execute(self.task())
        expected = hashlib.sha256(json.dumps(receipt.result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(receipt.result_sha256, expected)
        self.assertEqual(len(receipt.task_sha256), 64)
        self.assertFalse(receipt.result["arbitrary_command_execution"])

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
