from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArchitronBridgeCanaryAdmissionTests(unittest.TestCase):
    def test_bridge_semantic_canary_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_architron_local_semantic_canary.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(5, result.testsRun, evidence)
        self.assertIn("test_retryable_failure_recovers_without_duplicate_mutation", evidence)
        self.assertIn("test_wrong_target_readback_fails_semantically", evidence)

    def test_existing_provider_semantic_contract_is_preserved(self) -> None:
        self.assertTrue((ROOT / "ops" / "architron_semantic_contract.py").is_file())
        self.assertTrue((ROOT / "ops" / "architron_local_semantic_canary.py").is_file())


if __name__ == "__main__":
    unittest.main()
