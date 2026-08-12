from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ipep" / "audio_evidence_v4"
TEST_PATH = PACKAGE / "tests" / "test_resilience.py"


class IPEPPatchResilienceAdmissionTests(unittest.TestCase):
    def test_patch_fault_suite_executes(self) -> None:
        sys.path.insert(0, str(PACKAGE))
        try:
            spec = importlib.util.spec_from_file_location("ipep_patch_resilience_tests", TEST_PATH)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader if spec else None)
            module = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(module)
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            evidence = stream.getvalue()
            self.assertTrue(result.wasSuccessful(), evidence)
            self.assertEqual(4, result.testsRun, evidence)
            self.assertIn("test_tampered_custody_chain_is_detected", evidence)
            self.assertIn("test_missing_index_fails_closed_without_rebuilding_silently", evidence)
        finally:
            if sys.path and sys.path[0] == str(PACKAGE):
                sys.path.pop(0)

    def test_resilience_probe_source_is_present(self) -> None:
        self.assertTrue((PACKAGE / "evidenceops_audio_v4" / "resilience.py").is_file())


if __name__ == "__main__":
    unittest.main()
