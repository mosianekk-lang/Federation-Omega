from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.fascg_shadow_benchmark_v1 import (
    HostedShadowHarness,
    MeasuredResilienceRun,
    default_shadow_scenarios,
    eligible_10x_runs,
)
from benchmarking.cfbe_omega.autopilot_sentinel_frontier_court_v1 import ResilienceRun


class FASCGShadowBenchmarkTests(unittest.TestCase):
    def test_default_shadow_suite_passes_all_scenarios(self) -> None:
        receipt = HostedShadowHarness().run_suite(default_shadow_scenarios())
        self.assertEqual(8, receipt["scenario_count"])
        self.assertEqual(8, receipt["passed"])
        self.assertEqual(0, receipt["failed"])
        self.assertFalse(receipt["external_effects"])
        self.assertFalse(receipt["ten_x_verified"])

    def test_evidence_gap_prefers_provider_readback(self) -> None:
        scenario = default_shadow_scenarios()[1]
        receipt = HostedShadowHarness().run(scenario)
        self.assertEqual("sense-provider-readback", receipt.best_sensing_id)
        self.assertEqual("ACTIVE_SENSE", receipt.homeostasis_action)

    def test_blast_radius_uses_simulation_and_no_effect(self) -> None:
        scenario = default_shadow_scenarios()[2]
        receipt = HostedShadowHarness().run(scenario)
        self.assertEqual("SIMULATE_INTERVENTION", receipt.homeostasis_action)
        self.assertEqual("sim-reroute", receipt.intervention_id)
        self.assertFalse(receipt.external_effect_authorized)

    def test_security_scenario_forms_specialist_cells(self) -> None:
        receipt = HostedShadowHarness().run(default_shadow_scenarios()[3])
        for domain in ("SECURITY", "IDENTITY", "DATA_PRIVACY", "AGENT_RUNTIME"):
            self.assertIn(domain, receipt.cell_domains)
        self.assertEqual("QUARANTINE", receipt.homeostasis_action)

    def test_owner_only_decision_holds_owner(self) -> None:
        receipt = HostedShadowHarness().run(default_shadow_scenarios()[5])
        self.assertEqual("HOLD_OWNER", receipt.homeostasis_action)
        self.assertEqual("HOLD_OWNER", receipt.autonomy_level)

    def test_synthetic_measurement_cannot_feed_10x_court(self) -> None:
        metrics = ResilienceRun(.9,.9,.9,.9,.9,.98,.98,.9,.1,.1,0,.1)
        row = MeasuredResilienceRun("r1","reliability","REAL_HOSTED_SHADOW","abc","env",("proof",),metrics,synthetic=True)
        with self.assertRaisesRegex(ValueError, "SYNTHETIC"):
            eligible_10x_runs((row,))

    def test_local_or_unknown_measurement_class_rejected(self) -> None:
        metrics = ResilienceRun(.9,.9,.9,.9,.9,.98,.98,.9,.1,.1,0,.1)
        row = MeasuredResilienceRun("r2","reliability","LOCAL_SYNTHETIC","abc","env",("proof",),metrics)
        with self.assertRaisesRegex(ValueError, "CLASS_NOT_ELIGIBLE"):
            eligible_10x_runs((row,))

    def test_real_shadow_measurement_requires_proof(self) -> None:
        metrics = ResilienceRun(.9,.9,.9,.9,.9,.98,.98,.9,.1,.1,0,.1)
        row = MeasuredResilienceRun("r3","reliability","REAL_HOSTED_SHADOW","abc","env",(),metrics)
        with self.assertRaisesRegex(ValueError, "PROOF_REQUIRED"):
            eligible_10x_runs((row,))

    def test_real_shadow_measurement_can_be_eligible(self) -> None:
        metrics = ResilienceRun(.9,.9,.9,.9,.9,.98,.98,.9,.1,.1,0,.1)
        row = MeasuredResilienceRun("r4","reliability","REAL_HOSTED_SHADOW","abc","env",("proof",),metrics)
        rows = eligible_10x_runs((row,))
        self.assertEqual(1, len(rows))
        self.assertGreater(rows[0].ary(), 0)


if __name__ == "__main__":
    unittest.main()
