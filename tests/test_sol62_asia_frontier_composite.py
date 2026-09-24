from __future__ import annotations

import unittest

from services.sol62_client_runtime.asia_frontier_composite import (
    ASIA_FRONTIER_COHORT,
    BENCHMARK_SCHEMA,
    REQUIRED_BENCHMARK_DIMENSIONS,
    SCHEMA,
    MatchedDimension,
    cohort_summary,
    compile_residual_plan,
    matched_frontier_verdict,
    priority_waves,
)


class Sol62AsiaFrontierCompositeTests(unittest.TestCase):
    def test_cohort_is_unique_bilateral_and_provenance_bound(self):
        ids = [row.gene_id for row in ASIA_FRONTIER_COHORT]
        self.assertEqual(len(ids), 24)
        self.assertEqual(len(set(ids)), 24)
        self.assertEqual({row.country for row in ASIA_FRONTIER_COHORT}, {"China", "Japan"})
        self.assertTrue(all(row.evidence_url.startswith("https://") for row in ASIA_FRONTIER_COHORT))
        self.assertTrue(all(row.evidence_date.startswith("2026-") for row in ASIA_FRONTIER_COHORT))
        self.assertTrue(all(row.target_organs for row in ASIA_FRONTIER_COHORT))

    def test_summary_keeps_market_claim_separate_from_harvest(self):
        summary = cohort_summary()
        self.assertEqual(summary["schema"], SCHEMA)
        self.assertEqual(summary["count"], 24)
        self.assertEqual(len(summary["dimensions"]), 32)
        self.assertIn("NE_MARKET_SUPERIORITY", summary["truth_boundary"])

    def test_residual_plan_never_grants_authority_or_self_certifies(self):
        rows = compile_residual_plan()
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(row["authority_granted"] is False for row in rows))
        self.assertTrue(all(row["market_superiority_proven"] is False for row in rows))

    def test_overlap_is_collapsed_to_reuse(self):
        mechanism = ASIA_FRONTIER_COHORT[0].mechanism
        rows = compile_residual_plan(already_covered_mechanisms=(mechanism,))
        row = next(item for item in rows if item["gene_id"] == ASIA_FRONTIER_COHORT[0].gene_id)
        self.assertEqual(row["effective_disposition"], "REUSE")
        self.assertEqual(row["status"], "OVERLAP_COLLAPSED")

    def test_empty_benchmark_never_claims_superiority(self):
        verdict = matched_frontier_verdict(())
        self.assertEqual(verdict["schema"], BENCHMARK_SCHEMA)
        self.assertEqual(verdict["status"], "UNPROVEN")
        self.assertFalse(verdict["market_superiority_proven"])
        self.assertEqual(set(verdict["missing_dimensions"]), set(REQUIRED_BENCHMARK_DIMENSIONS))

    def test_full_noninferior_court_with_significant_wins_can_prove_frozen_composite(self):
        results = tuple(
            MatchedDimension(
                dimension=dimension,
                matched_samples=12,
                candidate_noninferior=True,
                candidate_significant_wins=1 if index < 8 else 0,
                critical_regressions=0,
            )
            for index, dimension in enumerate(REQUIRED_BENCHMARK_DIMENSIONS)
        )
        verdict = matched_frontier_verdict(results)
        self.assertEqual(verdict["status"], "PROVEN_AGAINST_FROZEN_ASIA_FRONTIER_COMPOSITE")
        self.assertTrue(verdict["market_superiority_proven"])
        self.assertEqual(verdict["significant_wins"], 8)

    def test_any_critical_regression_blocks_promotion(self):
        results = [
            MatchedDimension(
                dimension=dimension,
                matched_samples=12,
                candidate_noninferior=True,
                candidate_significant_wins=1 if index < 8 else 0,
                critical_regressions=0,
            )
            for index, dimension in enumerate(REQUIRED_BENCHMARK_DIMENSIONS)
        ]
        results[0] = MatchedDimension(
            dimension=results[0].dimension,
            matched_samples=12,
            candidate_noninferior=False,
            candidate_significant_wins=1,
            critical_regressions=1,
        )
        verdict = matched_frontier_verdict(tuple(results))
        self.assertFalse(verdict["market_superiority_proven"])
        self.assertIn(results[0].dimension, verdict["regression_dimensions"])

    def test_priority_waves_cover_every_gene_once(self):
        waves = priority_waves()
        flattened = [gene_id for wave in waves.values() for gene_id in wave]
        self.assertEqual(len(flattened), 24)
        self.assertEqual(len(set(flattened)), 24)
        self.assertEqual(set(flattened), {row.gene_id for row in ASIA_FRONTIER_COHORT})


if __name__ == "__main__":
    unittest.main()
