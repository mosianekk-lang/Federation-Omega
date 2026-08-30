import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

from run_h2_preflight_canary import (  # noqa: E402
    SCENARIOS,
    canonical_digest,
    jain_index,
    mission_spec,
    scenario_task_count,
    tenant_for,
)
from run_h2_full_soak import percentile  # noqa: E402


class H2CanaryContractTests(unittest.TestCase):
    def test_full_soak_percentile_is_interpolated_and_fail_closed(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.50), 2.5)
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 1.0), 4.0)
        with self.assertRaisesRegex(ValueError, "PERCENTILE_INPUT_INVALID"):
            percentile([], 0.95)

    def test_exact_five_fault_boundaries_and_task_widths(self):
        self.assertEqual(len(SCENARIOS), 5)
        self.assertEqual(scenario_task_count("admission_commit"), 1)
        self.assertEqual(scenario_task_count("proof_completion"), 1)
        self.assertEqual(scenario_task_count("dispatch_wave_commit"), 2)
        self.assertEqual(scenario_task_count("transition_claim"), 2)
        self.assertEqual(scenario_task_count("partial_sidecar"), 2)

    def test_twenty_mission_tenant_mix_preserves_weighted_fairness(self):
        counts = {"tenant-a": 0, "tenant-b": 0, "tenant-c": 0}
        for index in range(20):
            tenant, _ = tenant_for(index)
            counts[tenant] += 1
        self.assertEqual(counts, {"tenant-a": 3, "tenant-b": 6, "tenant-c": 11})
        normalized = [counts["tenant-a"], counts["tenant-b"] / 2, counts["tenant-c"] / 4]
        self.assertGreaterEqual(jain_index(normalized), 0.995)

    def test_mission_contract_is_deterministic_and_idempotency_keys_unique(self):
        first = mission_spec("candidate", "partial_sidecar", 7)
        second = mission_spec("candidate", "partial_sidecar", 7)
        self.assertEqual(first, second)
        self.assertEqual(len(first[1]), 2)
        keys = {task.idempotency_key for task in first[1]}
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(first[1][0].input_digest, first[1][1].input_digest)

    def test_digest_and_jain_boundaries_fail_closed(self):
        self.assertEqual(canonical_digest({"b": 2, "a": 1}), canonical_digest({"a": 1, "b": 2}))
        self.assertTrue(math.isclose(jain_index([1, 1, 1]), 1.0))
        with self.assertRaises(ValueError):
            jain_index([1, -1])
        with self.assertRaises(ValueError):
            scenario_task_count("unknown")


if __name__ == "__main__":
    unittest.main()
