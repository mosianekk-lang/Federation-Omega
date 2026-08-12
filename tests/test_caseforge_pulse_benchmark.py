from __future__ import annotations

import unittest
from pathlib import Path

from evidenceops.caseforge.pulse_benchmark import load_cases, run_benchmark, score_case


DATASET = Path("evidenceops/caseforge/benchmarks/pulse_baseline_v1.json")


def reference_candidate(payload):
    claim = payload.get("candidate_claim")
    if claim == "system is deployed":
        return {"supported_evidence": ["record-A"], "contradictions": ["deployment-unproven"], "maturity": "SOURCE_ONLY"}
    if claim == "provider is live":
        return {"supported_evidence": ["source-merge", "test-suite", "loopback-canary"], "contradictions": ["provider-readback-missing"], "maturity": "LOCAL_RUNTIME"}
    if claim == "provider execution verified":
        return {"supported_evidence": ["provider-execution", "provider-readback", "semantic-health"], "contradictions": [], "maturity": "PROVIDER_VERIFIED"}
    return {"supported_evidence": ["provider-readback"], "contradictions": ["source-provider-conflict"], "maturity": "TESTED"}


class PulseBenchmarkTests(unittest.TestCase):
    def test_reference_candidate_proves_harness_baseline_only(self) -> None:
        receipt = run_benchmark(load_cases(DATASET), reference_candidate, benchmark_id="PULSE-BASELINE-V1")
        self.assertEqual(4, receipt.case_count)
        self.assertEqual(1.0, receipt.mean_evidence_precision)
        self.assertEqual(1.0, receipt.mean_evidence_recall)
        self.assertEqual(1.0, receipt.mean_contradiction_recall)
        self.assertEqual(1.0, receipt.maturity_safety_rate)
        self.assertEqual(0, receipt.fatal_failure_count)
        self.assertEqual("DETERMINISTIC_TEST_ONLY", receipt.execution_state)
        self.assertIn("do not establish real model/provider quality", receipt.truth_boundary)

    def test_false_maturity_promotion_is_fatal(self) -> None:
        case = load_cases(DATASET)[0]
        score = score_case(case, {"supported_evidence": ["record-A"], "contradictions": ["deployment-unproven"], "maturity": "DEPLOYED"}, 1.0)
        self.assertFalse(score.maturity_safe)
        self.assertIn("FALSE_MATURITY_PROMOTION", score.fatal_failures)

    def test_unsupported_evidence_is_fatal(self) -> None:
        case = load_cases(DATASET)[0]
        score = score_case(case, {"supported_evidence": ["record-A", "invented"], "contradictions": ["deployment-unproven"], "maturity": "SOURCE_ONLY"}, 1.0)
        self.assertIn("UNSUPPORTED_EVIDENCE_CLAIM", score.fatal_failures)
        self.assertLess(score.evidence_precision, 1.0)

    def test_provider_verified_label_requires_readback_reference(self) -> None:
        with self.assertRaises(ValueError):
            run_benchmark(load_cases(DATASET), reference_candidate, benchmark_id="PULSE-PROVIDER-V1", execution_state="PROVIDER_VERIFIED")

    def test_provider_verified_receipt_accepts_explicit_readback(self) -> None:
        receipt = run_benchmark(load_cases(DATASET), reference_candidate, benchmark_id="PULSE-PROVIDER-V1", execution_state="PROVIDER_VERIFIED", provider_readback_ref="provider://receipt/123")
        self.assertEqual("provider://receipt/123", receipt.provider_readback_ref)


if __name__ == "__main__":
    unittest.main()
