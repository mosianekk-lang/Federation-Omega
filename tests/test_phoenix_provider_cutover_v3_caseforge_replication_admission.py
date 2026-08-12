from __future__ import annotations

import importlib.util
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOCUSED_TEST = "test_caseforge_independent_replication.py"
FOCUSED_TEST_PATH = ROOT / "tests" / FOCUSED_TEST

SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_caseforge_replication_admission",
    ROOT / "phoenix" / "build_exports.py",
)
assert SPEC and SPEC.loader
EXPORTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORTS
SPEC.loader.exec_module(EXPORTS)


class CaseForgeReplicationAdmissionTests(unittest.TestCase):
    def test_focused_independent_replication_suite_executes(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                FOCUSED_TEST,
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        evidence = process.stdout + process.stderr
        self.assertEqual(0, process.returncode, evidence)
        self.assertIn("test_cross_provider_replication_is_materially_independent", evidence)
        self.assertIn("test_same_provider_different_model_and_route_is_independent", evidence)
        self.assertIn("test_same_provider_model_route_is_not_independent", evidence)
        self.assertIn("test_blind_input_mismatch_vetoes_replication", evidence)
        self.assertIn("test_provider_unverified_run_is_rejected", evidence)
        self.assertIn("test_external_effect_run_is_rejected", evidence)
        self.assertIn("Ran 7 tests", evidence)
        self.assertIn("OK", evidence)

    def test_replication_suite_is_present_in_core_export(self) -> None:
        self.assertTrue(FOCUSED_TEST_PATH.is_file())
        with tempfile.TemporaryDirectory(prefix="caseforge-replication-admission-") as temporary:
            output = Path(temporary) / "output"
            receipt = EXPORTS.build(
                ROOT,
                output,
                ROOT / "phoenix" / "export_policy.json",
            )
            self.assertEqual("VERIFIED", receipt["status"])
            with tarfile.open(output / "Federation-Omega-Core.tar.gz", "r:gz") as archive:
                names = set(archive.getnames())
        self.assertIn(f"tests/{FOCUSED_TEST}", names)


if __name__ == "__main__":
    unittest.main()
