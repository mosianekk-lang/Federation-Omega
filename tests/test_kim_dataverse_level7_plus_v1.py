from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import (
    AutonomyDebt,
    EventClass,
    MaintenanceEvent,
    MaturityState,
    Objective,
    OwnerBoundary,
    allocate_resources,
    architecture_entropy_recommendation,
    assess_levels,
    institutional_receipt,
    objective_ecology,
    owner_attention_leverage,
    owner_interruption_firewall,
)


class KimDataverseLevel7PlusTests(unittest.TestCase):
    def test_owner_interruption_firewall_autoresolves_internal_maintenance(self) -> None:
        decision = owner_interruption_firewall(
            MaintenanceEvent(
                event_id="phoenix-regression",
                event_class=EventClass.MAINTENANCE,
                self_resolvable=True,
                reversible=True,
            )
        )
        self.assertFalse(decision.interrupt_owner)
        self.assertEqual("AUTONOMIC_REPAIR", decision.reason)
        self.assertTrue(decision.continue_independent_lanes)

    def test_owner_authority_boundary_is_never_autopiloted(self) -> None:
        decision = owner_interruption_firewall(
            MaintenanceEvent(
                event_id="wif-mutation",
                event_class=EventClass.MAINTENANCE,
                self_resolvable=False,
                reversible=True,
                owner_boundary=OwnerBoundary.AUTHORITY,
            )
        )
        self.assertTrue(decision.interrupt_owner)
        self.assertEqual("OWNER_BOUNDARY:AUTHORITY", decision.reason)
        self.assertTrue(decision.continue_independent_lanes)

    def test_external_effect_without_exact_boundary_fails_to_owner(self) -> None:
        decision = owner_interruption_firewall(
            MaintenanceEvent(
                event_id="unknown-effect",
                event_class=EventClass.RECOVERY,
                self_resolvable=True,
                reversible=True,
                external_effect=True,
            )
        )
        self.assertTrue(decision.interrupt_owner)
        self.assertEqual("UNSCOPED_EXTERNAL_EFFECT", decision.reason)

    def test_autonomy_debt_counts_owner_as_scheduler_antipatterns(self) -> None:
        debt = AutonomyDebt(
            owner_continuations=3,
            owner_retries=1,
            owner_repair_prompts=2,
            chat_session_dependencies=4,
            unrelated_gate_stalls=1,
        )
        self.assertEqual(11, debt.score)

    def test_objective_ecology_prioritizes_shared_capability_unlock(self) -> None:
        result = objective_ecology(
            (
                Objective("A", 5, 5, required_capabilities=("provider-readback",)),
                Objective("B", 5, 4, required_capabilities=("provider-readback",)),
                Objective("C", 4, 5, required_capabilities=("isolated-cap",)),
            )
        )
        self.assertEqual(("provider-readback", 2), result.shared_unlocks[0])
        self.assertIn(result.ranked_objectives[0], {"A", "B"})

    def test_objective_ecology_fails_closed_on_unknown_reference(self) -> None:
        with self.assertRaises(ValueError):
            objective_ecology((Objective("A", 1, 1, dependencies=("missing",)),))

    def test_resource_allocation_is_bounded_and_complete(self) -> None:
        allocations = allocate_resources(
            (
                Objective("A", 3, 2),
                Objective("B", 2, 1),
            ),
            10,
            minimum_slice=1,
        )
        self.assertAlmostEqual(10, sum(item.budget for item in allocations), places=5)
        self.assertTrue(all(item.budget >= 1 for item in allocations))

    def test_architecture_entropy_only_recommends_high_overlap(self) -> None:
        result = architecture_entropy_recommendation(
            {
                "alpha": ("schedule", "retry", "state"),
                "beta": ("schedule", "retry", "state"),
                "gamma": ("provider",),
            }
        )
        self.assertEqual(("alpha", "beta", 1.0), result[0])
        self.assertEqual(1, len(result))

    def test_attention_leverage_uses_verified_value_not_activity(self) -> None:
        self.assertEqual(5.0, owner_attention_leverage(50, 10))
        self.assertEqual(50.0, owner_attention_leverage(50, 0))

    def test_level_assessment_is_sequential_and_fail_closed(self) -> None:
        signals = {
            "objective_ecology": True,
            "resource_economy": True,
            "owner_interruption_firewall": True,
            "autonomy_debt": True,
            "dynamic_topology": True,
            "digital_twin": True,
            "measured_gap_evolution": True,
            "historical_replay": True,
            "adversarial_qualification": True,
            "architectural_entropy_controller": True,
            "causal_learning": True,
            "no_self_authority_promotion": True,
            "persistent_no_chat_continuity": False,
        }
        levels = assess_levels(signals)
        self.assertTrue(levels[0].qualified)
        self.assertTrue(levels[1].qualified)
        self.assertFalse(levels[2].qualified)
        self.assertFalse(levels[3].qualified)

    def test_provider_verified_is_distinct_from_value_proven(self) -> None:
        self.assertNotEqual(MaturityState.PROVIDER_VERIFIED, MaturityState.VALUE_PROVEN)

    def test_institutional_receipt_is_deterministic_and_non_authorizing(self) -> None:
        first = institutional_receipt(source_sha="a" * 40, payload={"state": "TESTED"})
        second = institutional_receipt(source_sha="a" * 40, payload={"state": "TESTED"})
        different = institutional_receipt(source_sha="b" * 40, payload={"state": "TESTED"})
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertTrue(first.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
