from __future__ import annotations

import unittest

from evidenceops.caseforge.candidate_registry import CandidateRegistry


class ScoutCandidateRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CandidateRegistry.load()

    def test_all_candidates_begin_as_hypotheses(self) -> None:
        self.assertEqual(5, len(self.registry.candidates))
        self.assertTrue(all(c["state"] == "HYPOTHESIS" for c in self.registry.candidates.values()))
        self.assertTrue(all(not c["provider_performance_verified"] for c in self.registry.candidates.values()))

    def test_no_benchmark_means_no_promotion(self) -> None:
        decision = self.registry.promotion_decision("CF-CAND-001")
        self.assertFalse(decision["promoted"])
        self.assertEqual("PULSE_BENCHMARK_REQUIRED", decision["reason"])

    def test_wrong_benchmark_does_not_promote(self) -> None:
        decision = self.registry.promotion_decision(
            "CF-CAND-001",
            benchmark_receipt={"benchmark_id": "WRONG", "fatal_failure_count": 0, "execution_state": "DETERMINISTIC_TEST_ONLY"},
        )
        self.assertFalse(decision["promoted"])

    def test_clean_deterministic_benchmark_promotes_only_to_benchmarked_candidate(self) -> None:
        decision = self.registry.promotion_decision(
            "CF-CAND-001",
            benchmark_receipt={"benchmark_id": "PULSE-BASELINE-V1", "fatal_failure_count": 0, "execution_state": "DETERMINISTIC_TEST_ONLY"},
        )
        self.assertTrue(decision["promoted"])
        self.assertEqual("BENCHMARKED_CANDIDATE", decision["state"])
        self.assertFalse(decision["provider_performance_verified"])

    def test_provider_claim_requires_readback_reference(self) -> None:
        receipt = {"benchmark_id": "PULSE-BASELINE-V1", "fatal_failure_count": 0, "execution_state": "PROVIDER_VERIFIED"}
        blocked = self.registry.promotion_decision("CF-CAND-001", benchmark_receipt=receipt)
        self.assertFalse(blocked["promoted"])
        allowed = self.registry.promotion_decision(
            "CF-CAND-001", benchmark_receipt=receipt, provider_readback_ref="provider://receipt/verified"
        )
        self.assertTrue(allowed["provider_performance_verified"])


if __name__ == "__main__":
    unittest.main()
