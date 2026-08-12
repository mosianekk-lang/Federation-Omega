from __future__ import annotations

import importlib.util
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOCUSED_TEST = "test_caseforge_openai_provider_adapter.py"
FOCUSED_TEST_PATH = ROOT / "tests" / FOCUSED_TEST

SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_caseforge_openai_admission",
    ROOT / "phoenix" / "build_exports.py",
)
assert SPEC and SPEC.loader
EXPORTS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EXPORTS
SPEC.loader.exec_module(EXPORTS)


class CaseForgeOpenAIAdmissionTests(unittest.TestCase):
    """Make focused CASEFORGE provider-adapter evidence visible in Airlock logs."""

    def test_focused_provider_adapter_suite_executes(self) -> None:
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
        self.assertIn(
            "test_provider_execution_receipt_does_not_self_certify_readback",
            evidence,
        )
        self.assertIn(
            "test_unverified_model_version_cannot_promote_provider_state",
            evidence,
        )
        self.assertIn(
            "test_provider_storage_requires_public_synthetic_classification",
            evidence,
        )
        self.assertIn(
            "test_stored_response_and_model_resource_readback_can_verify_provider",
            evidence,
        )
        self.assertIn(
            "test_stored_readback_rejects_configuration_mismatch",
            evidence,
        )
        self.assertIn(
            "test_stored_readback_rejects_model_resource_mismatch",
            evidence,
        )
        self.assertIn(
            "test_stored_readback_requires_provider_stored_execution",
            evidence,
        )
        self.assertIn("Ran 13 tests", evidence)
        self.assertIn("OK", evidence)

    def test_focused_provider_adapter_suite_is_present_in_core_export(self) -> None:
        self.assertTrue(FOCUSED_TEST_PATH.is_file())
        with tempfile.TemporaryDirectory(prefix="caseforge-openai-admission-") as temporary:
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
