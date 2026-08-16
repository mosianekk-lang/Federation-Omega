import unittest

from ao_harmonic_v3.cost_governor import (
    CostAction,
    CostClass,
    CostEnvelope,
    PreRevenueCostGovernor,
    WorkloadCostProfile,
)


class PreRevenueCostGovernorTests(unittest.TestCase):
    def setUp(self):
        self.governor = PreRevenueCostGovernor()

    def test_c0_included_is_allowed(self):
        decision = self.governor.evaluate(WorkloadCostProfile(
            workload_id="included",
            cost_class=CostClass.C0_INCLUDED_FREE,
            estimated_monthly_cost=0.0,
            already_paid_or_included=True,
        ))
        self.assertEqual(decision.action, CostAction.ALLOW)
        self.assertFalse(decision.owner_interrupt_required)

    def test_unknown_incremental_cost_fails_closed(self):
        decision = self.governor.evaluate(WorkloadCostProfile(
            workload_id="unknown",
            cost_class=CostClass.C1_MICRO_SERVERLESS,
            estimated_monthly_cost=None,
        ))
        self.assertEqual(decision.action, CostAction.DENY_UNKNOWN_COST)
        self.assertEqual(decision.permitted_incremental_cost, 0.0)

    def test_paid_micro_workload_requires_approved_envelope_by_default(self):
        decision = self.governor.evaluate(WorkloadCostProfile(
            workload_id="micro",
            cost_class=CostClass.C1_MICRO_SERVERLESS,
            estimated_monthly_cost=10.0,
        ))
        self.assertEqual(decision.action, CostAction.HOLD_OWNER_APPROVAL)
        self.assertTrue(decision.owner_interrupt_required)

    def test_expensive_compute_is_owner_reserved(self):
        decision = self.governor.evaluate(WorkloadCostProfile(
            workload_id="gpu",
            cost_class=CostClass.C3_EXPENSIVE_COMPUTE,
            estimated_monthly_cost=500.0,
        ), CostEnvelope(incremental_monthly_budget=1000.0, owner_approved=True))
        self.assertEqual(decision.action, CostAction.HOLD_OWNER_APPROVAL)

    def test_degrades_before_approved_budget_is_exhausted(self):
        decision = self.governor.evaluate(WorkloadCostProfile(
            workload_id="near-limit",
            cost_class=CostClass.C1_MICRO_SERVERLESS,
            estimated_monthly_cost=20.0,
            current_month_spend=70.0,
            event_driven=False,
            scale_to_zero=True,
        ), CostEnvelope(incremental_monthly_budget=100.0, owner_approved=True))
        self.assertEqual(decision.action, CostAction.DEGRADE)
        self.assertIn("EVENT_DRIVEN_MIGRATION_PREFERRED", decision.required_controls)

    def test_cheapest_included_route_wins(self):
        route = self.governor.rank_routes([
            {"name": "paid", "available": True, "authorised": True, "included_or_free": False,
             "estimated_incremental_cost": 1.0, "proof_strength": 1.0, "information_gain": 1.0},
            {"name": "included", "available": True, "authorised": True, "included_or_free": True,
             "estimated_incremental_cost": 0.0, "proof_strength": 0.9, "information_gain": 0.8},
        ])
        self.assertEqual(route["name"], "included")


if __name__ == "__main__":
    unittest.main()
