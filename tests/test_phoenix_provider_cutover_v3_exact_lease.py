from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "provider_cutover_v3_1", ROOT / "phoenix" / "provider_cutover_v3_1.py"
)
assert SPEC and SPEC.loader
LEASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LEASE
SPEC.loader.exec_module(LEASE)


class ExactLeaseTests(unittest.TestCase):
    def test_parse_remote_main_sha(self):
        sha = "a" * 40
        self.assertEqual(
            sha,
            LEASE.parse_remote_main_sha(f"{sha}\trefs/heads/main\n"),
        )

    def test_parse_remote_main_absent(self):
        self.assertIsNone(LEASE.parse_remote_main_sha(""))

    def test_parse_remote_main_rejects_malformed_sha(self):
        with self.assertRaisesRegex(LEASE.V3.CutoverError, "malformed SHA"):
            LEASE.parse_remote_main_sha("bad\trefs/heads/main\n")

    def test_existing_main_uses_provider_bound_exact_lease(self):
        remote_sha = "b" * 40
        local_sha = "c" * 40
        calls: list[list[str]] = []
        original_run = LEASE.V3.run

        def fake_run(command, cwd, environment=None):
            calls.append(command)
            if command[:3] == ["git", "ls-remote", "--heads"]:
                return f"{remote_sha}\trefs/heads/main"
            if command == ["git", "rev-parse", "HEAD"]:
                return local_sha
            return ""

        LEASE.V3.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as directory:
                result = LEASE.git_push_exact_lease(
                    "secret-not-recorded",
                    "mosianekk-lang",
                    "Federation-Omega-Core",
                    Path(directory),
                    True,
                )
        finally:
            LEASE.V3.run = original_run

        self.assertEqual(local_sha, result)
        push = next(command for command in calls if command[:2] == ["git", "push"])
        self.assertIn(
            f"--force-with-lease=refs/heads/main:{remote_sha}",
            push,
        )
        self.assertNotIn("--force-with-lease", push)

    def test_empty_repository_push_has_no_force_lease(self):
        calls: list[list[str]] = []
        original_run = LEASE.V3.run

        def fake_run(command, cwd, environment=None):
            calls.append(command)
            if command[:3] == ["git", "ls-remote", "--heads"]:
                return ""
            if command == ["git", "rev-parse", "HEAD"]:
                return "d" * 40
            return ""

        LEASE.V3.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as directory:
                LEASE.git_push_exact_lease(
                    "secret-not-recorded",
                    "mosianekk-lang",
                    "Federation-Omega-Core",
                    Path(directory),
                    False,
                )
        finally:
            LEASE.V3.run = original_run

        push = next(command for command in calls if command[:2] == ["git", "push"])
        self.assertFalse(
            any(item.startswith("--force-with-lease") for item in push)
        )

    def test_existing_main_without_replace_fails_closed(self):
        original_run = LEASE.V3.run

        def fake_run(command, cwd, environment=None):
            if command[:3] == ["git", "ls-remote", "--heads"]:
                return f"{'e' * 40}\trefs/heads/main"
            return ""

        LEASE.V3.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(
                    LEASE.V3.CutoverError, "Refusing to replace existing main"
                ):
                    LEASE.git_push_exact_lease(
                        "secret-not-recorded",
                        "mosianekk-lang",
                        "Federation-Omega-Core",
                        Path(directory),
                        False,
                    )
        finally:
            LEASE.V3.run = original_run


if __name__ == "__main__":
    unittest.main()
