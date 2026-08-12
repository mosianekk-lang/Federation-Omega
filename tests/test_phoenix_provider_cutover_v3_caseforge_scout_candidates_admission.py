from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScoutCandidateAdmissionTests(unittest.TestCase):
    def test_scout_candidate_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_caseforge_candidate_registry.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(5, result.testsRun, evidence)
        self.assertIn("test_no_benchmark_means_no_promotion", evidence)
        self.assertIn("test_provider_claim_requires_readback_reference", evidence)

    def test_candidate_register_and_guard_are_present(self) -> None:
        self.assertTrue((ROOT / "evidenceops" / "caseforge" / "candidate_registry.py").is_file())
        self.assertTrue((ROOT / "evidenceops" / "caseforge" / "benchmarks" / "candidate_register_v1.json").is_file())


if __name__ == "__main__":
    unittest.main()
