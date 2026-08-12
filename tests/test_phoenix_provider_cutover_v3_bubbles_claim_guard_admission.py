from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BubblesClaimGuardAdmissionTests(unittest.TestCase):
    def test_claim_guard_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_bubbles_claim_guard.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(7, result.testsRun, evidence)
        self.assertIn("test_cios_can_claim_canary_ready_but_not_deployed", evidence)
        self.assertIn("test_caseforge_provider_quality_cannot_inherit_from_deterministic_benchmark", evidence)

    def test_crosswalk_and_guard_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "claim_proof_crosswalk.json").is_file())
        self.assertTrue((ROOT / "bubbles" / "claim_guard.py").is_file())


if __name__ == "__main__":
    unittest.main()
