from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_source_identity",
    ROOT / "phoenix" / "build_exports.py",
)
assert SPEC and SPEC.loader
EXPORTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORTS
SPEC.loader.exec_module(EXPORTS)


class PhoenixSourceIdentityTests(unittest.TestCase):
    @staticmethod
    def initialise_repository(root: Path) -> str:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "phoenix@example.invalid"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Phoenix Test"],
            cwd=root,
            check=True,
        )
        (root / "source.txt").write_text("verified\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

    def test_checked_out_head_outranks_conflicting_github_event_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout_head = self.initialise_repository(root)
            with mock.patch.dict(os.environ, {"GITHUB_SHA": "f" * 40}):
                self.assertEqual(checkout_head, EXPORTS.source_sha(root))

    def test_github_sha_is_only_a_validated_fallback_without_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fallback = "a" * 40
            with mock.patch.dict(os.environ, {"GITHUB_SHA": fallback}):
                self.assertEqual(fallback, EXPORTS.source_sha(root))

    def test_unresolved_or_malformed_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.dict(os.environ, {"GITHUB_SHA": "not-a-sha"}):
                self.assertEqual("UNRESOLVED", EXPORTS.source_sha(root))


if __name__ == "__main__":
    unittest.main()
