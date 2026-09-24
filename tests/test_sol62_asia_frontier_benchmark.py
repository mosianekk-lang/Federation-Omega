from __future__ import annotations

import unittest

from services.sol62_client_runtime.asia_frontier_benchmark import (
    MatchedSample,
    compile_independent_judge_packet,
    dimension_court,
    freeze_frontier,
    natural_workload_sample,
    run_matched_frontier_court,
)
from services.sol62_client_runtime.asia_frontier_composite import REQUIRED_BENCHMARK_DIMENSIONS


class Sol62AsiaFrontierBenchmarkTests(unittest.TestCase):
    def frontier(self):
        return freeze_frontier(
            frozen_at="2026-09-24",
            source_refs=("official:china", "official:japan"),
            mechanism_gene_ids=tuple(f"gene-{i:02d}" for i in range(24)),
            workload_manifest={"version": 1, "dimensions": list(REQUIRED_BENCHMARK_DIMENSIONS)},
            runtime_epoch="sol62-test",
        )

    def test_freeze_frontier_is_deterministic_and_provenance_bound(self):
        first = self.frontier()
        second = self.frontier()
        self.assertEqual(first, second)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(len(first.workload_manifest_sha256), 64)

    def test_natural_workload_sample_keeps_operational_metrics_visible(self):
        sample = natural_workload_sample(
            dimension=REQUIRED_BENCHMARK_DIMENSIONS[0],
            sample_id="s1",
            workload_id="w1",
            candidate_accepted=True,
            frontier_accepted=False,
            candidate_quality=0.9,
            frontier_quality=0.8,
            candidate_owner_interventions=0,
            frontier_owner_interventions=1,
            candidate_wall_time_ms=1000,
            frontier_wall_time_ms=1500,
            candidate_cost=0.1,
            frontier_cost=0.2,
            candidate_tool_calls=5,
            frontier_tool_calls=8,
            candidate_critical_regression=False,
            evidence_ref="receipt:s1",
        )
        self.assertGreater(sample.candidate_score, sample.frontier_score)
        self.assertEqual(sample.candidate_owner_interventions, 0)
        self.assertEqual(sample.frontier_owner_interventions, 1)
        self.assertFalse(sample.synthetic)

    def test_dimension_court_requires_natural_samples_and_blocks_critical_regression(self):
        dimension = REQUIRED_BENCHMARK_DIMENSIONS[0]
        synthetic = tuple(
            MatchedSample(
                dimension=dimension,
                sample_id=f"s{i}",
                workload_id=f"w{i}",
                candidate_score=0.9,
                frontier_score=0.7,
                synthetic=True,
            )
            for i in range(12)
        )
        court = dimension_court(dimension, synthetic)
        self.assertFalse(court.noninferior)
        self.assertEqual(court.natural_samples, 0)

        natural = list(
            MatchedSample(
                dimension=dimension,
                sample_id=f"n{i}",
                workload_id=f"nw{i}",
                candidate_score=0.9,
                frontier_score=0.7,
                evidence_ref=f"receipt:n{i}",
            )
            for i in range(12)
        )
        natural[0] = MatchedSample(
            dimension=dimension,
            sample_id="n0",
            workload_id="nw0",
            candidate_score=0.9,
            frontier_score=0.7,
            critical_regression=True,
            evidence_ref="receipt:n0",
        )
        court = dimension_court(dimension, tuple(natural))
        self.assertFalse(court.noninferior)
        self.assertEqual(court.critical_regressions, 1)

    def test_sign_test_requires_real_paired_win_signal(self):
        dimension = REQUIRED_BENCHMARK_DIMENSIONS[0]
        wins = tuple(
            MatchedSample(
                dimension=dimension,
                sample_id=f"s{i}",
                workload_id=f"w{i}",
                candidate_score=0.9,
                frontier_score=0.7,
                evidence_ref=f"receipt:{i}",
            )
            for i in range(12)
        )
        court = dimension_court(dimension, wins)
        self.assertTrue(court.noninferior)
        self.assertTrue(court.significant_win)
        self.assertEqual(court.wins, 12)
        self.assertEqual(court.losses, 0)
        self.assertLess(court.one_sided_sign_p, 0.05)

    def test_incomplete_32_dimension_court_cannot_claim_superiority(self):
        dimension = REQUIRED_BENCHMARK_DIMENSIONS[0]
        samples = tuple(
            MatchedSample(
                dimension=dimension,
                sample_id=f"s{i}",
                workload_id=f"w{i}",
                candidate_score=0.9,
                frontier_score=0.7,
                evidence_ref=f"receipt:{i}",
            )
            for i in range(12)
        )
        result = run_matched_frontier_court(frontier=self.frontier(), samples=samples)
        self.assertFalse(result["verdict"]["market_superiority_proven"])
        self.assertGreater(len(result["verdict"]["missing_dimensions"]), 0)
        self.assertFalse(result["builder_self_certification_allowed"])

    def test_full_court_can_only_prove_frozen_composite(self):
        samples = []
        for dimension_index, dimension in enumerate(REQUIRED_BENCHMARK_DIMENSIONS):
            candidate = 0.90 if dimension_index < 8 else 0.82
            frontier = 0.70 if dimension_index < 8 else 0.82
            for sample_index in range(12):
                samples.append(
                    MatchedSample(
                        dimension=dimension,
                        sample_id=f"{dimension_index}-{sample_index}",
                        workload_id=f"w-{dimension_index}-{sample_index}",
                        candidate_score=candidate,
                        frontier_score=frontier,
                        evidence_ref=f"receipt:{dimension_index}:{sample_index}",
                    )
                )
        result = run_matched_frontier_court(
            frontier=self.frontier(),
            samples=tuple(samples),
        )
        self.assertTrue(result["verdict"]["market_superiority_proven"])
        self.assertEqual(
            result["verdict"]["status"],
            "PROVEN_AGAINST_FROZEN_ASIA_FRONTIER_COMPOSITE",
        )
        self.assertIn("NE_UNIVERSAL_MARKET_SUPERIORITY", result["truth_boundary"])
        self.assertEqual(len(result["court_sha256"]), 64)

    def test_independent_judge_packet_never_makes_builder_authoritative(self):
        result = run_matched_frontier_court(frontier=self.frontier(), samples=())
        packet = compile_independent_judge_packet(result)
        self.assertTrue(packet["judge_must_recompute"])
        self.assertTrue(packet["judge_must_verify_sample_custody"])
        self.assertTrue(packet["judge_must_check_critical_regressions"])
        self.assertTrue(packet["judge_must_check_cohort_currentness"])
        self.assertFalse(packet["builder_verdict_authoritative"])
        self.assertFalse(packet["authority_granted"])


if __name__ == "__main__":
    unittest.main()
