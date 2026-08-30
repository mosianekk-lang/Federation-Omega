from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
RG_ROOT = ROOT / "realityguard_v0.4.0"
RG_SRC = RG_ROOT / "src"


class RealityGuardV050PackageSurfaceTests(unittest.TestCase):
    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(RG_SRC)
        return env

    def test_nested_realityguard_suite_is_green(self):
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=RG_ROOT,
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=180,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + "\n" + proc.stderr)

    def test_health_reports_v050_and_execution_guard_surface(self):
        proc = subprocess.run(
            [sys.executable, "-m", "realityguard.cli", "health"],
            cwd=RG_ROOT,
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual("0.5.0", payload["version"])
        self.assertEqual("TESTED_LOCAL_ADAPTER_REQUIRED", payload["execution_guard"])
        self.assertFalse(payload["external_bindings"])

    def test_synthetic_inline_binary_fixture_fails_closed(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "realityguard.cli",
                "execution-preflight",
                "--input",
                "examples/gmail_attachment_failure_execution_guard.json",
            ],
            cwd=RG_ROOT,
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(7, proc.returncode, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual("BLOCK_UNSAFE_BINARY_TRANSPORT", payload["decision"])
        self.assertFalse(payload["dispatch_authorized"])

    def test_synthetic_file_reference_fixture_is_admitted_without_dispatch(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "realityguard.cli",
                "execution-preflight",
                "--input",
                "examples/gmail_attachment_repaired_execution_guard.json",
            ],
            cwd=RG_ROOT,
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual("ALLOW_DISPATCH", payload["decision"])
        self.assertTrue(payload["dispatch_authorized"])
        self.assertEqual("ADAPTER_REQUIRED", payload["provider_binding"])
        self.assertFalse(payload["target_runtime_binding_proven"])

    def test_package_metadata_matches_public_api_version(self):
        pyproject = (RG_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.5.0"', pyproject)
        init_text = (RG_SRC / "realityguard" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.5.0"', init_text)


if __name__ == "__main__":
    unittest.main()
