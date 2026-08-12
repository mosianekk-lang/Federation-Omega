from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PulseBenchmarkAdmissionTests(unittest.TestCase):
    def test_pulse_benchmark_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_caseforge_pulse_benchmark.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(5, result.testsRun, evidence)
        self.assertIn("test_false_maturity_promotion_is_fatal", evidence)
        self.assertIn("test_provider_verified_label_requires_readback_reference", evidence)

    def test_dataset_and_harness_are_present(self) -> None:
        self.assertTrue((ROOT / "evidenceops" / "caseforge" / "pulse_benchmark.py").is_file())
        self.assertTrue((ROOT / "evidenceops" / "caseforge" / "benchmarks" / "pulse_baseline_v1.json").is_file())


if __name__ == "__main__":
    unittest.main()
