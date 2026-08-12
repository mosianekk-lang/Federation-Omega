from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ShowcaseAdmissionTests(unittest.TestCase):
    def test_showcase_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_bubbles_showcase.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(6, result.testsRun, evidence)
        self.assertIn("test_architron_is_now_local_runtime_verified_not_provider_verified", evidence)
        self.assertIn("test_k10_remains_execution_pending", evidence)
        self.assertIn("test_provider_overclaim_is_blocked", evidence)

    def test_showcase_source_and_crosswalk_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "showcase.py").is_file())
        self.assertTrue((ROOT / "bubbles" / "claim_proof_crosswalk.json").is_file())


if __name__ == "__main__":
    unittest.main()
