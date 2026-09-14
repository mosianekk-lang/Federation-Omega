from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from federation_windows_plane.tunnel_service import (
    execute_read_only_task,
    stdio_command,
    validate_profile,
    validate_tunnel_id,
)


class TunnelServiceTests(unittest.TestCase):
    def test_tunnel_and_profile_identifiers_are_bounded(self):
        self.assertEqual(validate_tunnel_id("tunnel_0123456789abcdef0123456789abcdef"), "tunnel_0123456789abcdef0123456789abcdef")
        self.assertEqual(validate_profile("fuse-windows"), "fuse-windows")
        for invalid in ("", "tunnel_short", "$(whoami)", "fuse windows", "../profile"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    (validate_tunnel_id if invalid.startswith("tunnel") or invalid == "" else validate_profile)(invalid)

    def test_stdio_command_is_argument_quoted(self):
        command = stdio_command(r"C:\Program Files\Python\python.exe", r"C:\FUSE Workspace")
        self.assertIn('"C:\\Program Files\\Python\\python.exe"', command)
        self.assertIn('"C:\\FUSE Workspace"', command)
        self.assertNotIn("powershell", command.lower())

    def test_health_receipt_is_read_only_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = execute_read_only_task(Path(tmp), "health", require_windows=False)
        self.assertEqual(receipt["effect"], "READ_ONLY")
        self.assertFalse(receipt["result"]["arbitrary_command_execution"])
        self.assertEqual(len(receipt["task_sha256"]), 64)
        self.assertEqual(len(receipt["result_sha256"]), 64)

    def test_hash_tool_stays_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("fuse", encoding="utf-8")
            receipt = execute_read_only_task(root, "hash_workspace_file", relative_path="a.txt", require_windows=False)
            self.assertEqual(receipt["result"]["sha256"], hashlib.sha256(b"fuse").hexdigest())
            with self.assertRaisesRegex(ValueError, "PATH_ESCAPE_DENIED"):
                execute_read_only_task(root, "hash_workspace_file", relative_path="../a.txt", require_windows=False)

    def test_no_arbitrary_task_route_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "TASK_TYPE_NOT_ALLOWLISTED"):
                execute_read_only_task(Path(tmp), "shell", require_windows=False)


if __name__ == "__main__":
    unittest.main()
