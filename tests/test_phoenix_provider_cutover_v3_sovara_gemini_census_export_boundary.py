from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "phoenix" / "export_policy.json"
EXPORTS_PATH = ROOT / "phoenix" / "build_exports.py"

SPEC = importlib.util.spec_from_file_location("phoenix_build_exports_census_boundary", EXPORTS_PATH)
assert SPEC and SPEC.loader
EXPORTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORTS
SPEC.loader.exec_module(EXPORTS)

SOURCE_CONTROL_TESTS = (
    "tests/test_sovara_admin_actas_census.py",
    "tests/test_sovara_privileged_control_runtime_census.py",
)


class SovaraGeminiCensusExportBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_census_source_control_tests_execute_in_repository(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_sovara_*census.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        output = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, output)
        self.assertIn("test_active_request_is_read_only_g0", output)
        self.assertIn("test_probe_is_read_only_and_current_request_remains_g0", output)
        self.assertIn("Ran 11 tests", output)
        self.assertIn("OK", output)

    def test_census_tests_are_explicitly_repository_only_in_core_export(self) -> None:
        excluded = set(self.policy["core"]["excluded_test_globs"])
        for path in SOURCE_CONTROL_TESTS:
            self.assertIn(path, excluded)
            self.assertTrue(EXPORTS.is_migration_control_test(path, self.policy))

    def test_export_boundary_does_not_change_provider_authority(self) -> None:
        self.assertEqual(self.policy["version"], "1.0.21")
        self.assertEqual(self.policy["invariants"]["core_workflow_count"], 0)
        self.assertEqual(self.policy["invariants"]["core_migration_control_test_count"], 0)
        request = json.loads(
            (ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(request["mode"], "G0_READ_ONLY_VERIFY")
        self.assertTrue(request["admin_actas_census_scope"]["read_only"])
        self.assertTrue(request["privileged_control_runtime_scope"]["read_only"])
        self.assertFalse(request["provider_mutation_allowed"])
        self.assertFalse(request["model_inference_allowed"])
        self.assertFalse(request["external_communication_allowed"])


if __name__ == "__main__":
    unittest.main()
