from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PrismDemoAdmissionTests(unittest.TestCase):
    def test_prism_demo_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_bubbles_demo_journey_guard.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(5, result.testsRun, evidence)
        self.assertIn("test_k10_cannot_claim_render_before_real_export_proofs", evidence)
        self.assertIn("test_ipep_search_result_requires_provenance_fields", evidence)

    def test_demo_contract_and_guard_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "demo_journeys.json").is_file())
        self.assertTrue((ROOT / "bubbles" / "demo_journey_guard.py").is_file())


if __name__ == "__main__":
    unittest.main()
