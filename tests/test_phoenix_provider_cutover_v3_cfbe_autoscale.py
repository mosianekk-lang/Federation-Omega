from __future__ import annotations

import unittest

from sovara_operator_adapter.cfbe_autoscale_governor import (
    POLICIES,
    AutoscaleSignal,
    decide_autoscale,
    rank_admissible_signals,
)


class CFBEAutoscaleGovernorAirlockAdmission(unittest.TestCase):
    def test_all_twenty_one_canonical_policies_are_present(self) -> None:
        self.assertEqual([p.policy_id for p in POLICIES], [f"AS-{i:03d}" for i in range(1, 22)])

    def test_mesh_policy_actions_are_registered(self) -> None:
        index = {p.policy_id: p.action for p in POLICIES}
        self.assertEqual(index["AS-015"], "FORM_LOGICAL_SPECIALIST_CELL")
        self.assertEqual(index["AS-016"], "SPLIT_SPECIALIST_CELL")
        self.assertEqual(index["AS-017"], "MERGE_OR_DEMOTE_LOGICAL_CELL")
        self.assertEqual(index["AS-018"], "PROMOTE_NODE_RING")
        self.assertEqual(index["AS-019"], "DEMOTE_NODE_AND_REROUTE")
        self.assertEqual(index["AS-020"], "CONTINUE_LOCAL_AND_REROUTE")
        self.assertEqual(index["AS-021"], "RIGHTSIZE_LOCAL_NODE_CADENCE")

    def test_safe_source_depth_scale_up_is_admissible(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-SOURCE", "AS-004", 0.8, 0.9))
        self.assertEqual(decision.status, "AUTONOMOUS_ADMISSIBLE")
        self.assertEqual(decision.action, "DEEPEN_OFFICIAL_SOURCE_DISCOVERY")
        self.assertFalse(decision.self_certifies_improvement)

    def test_safe_mesh_formation_is_control_admissible(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-MESH", "AS-015", 0.95, 0.9))
        self.assertEqual(decision.status, "AUTONOMOUS_ADMISSIBLE")
        self.assertEqual(decision.action, "FORM_LOGICAL_SPECIALIST_CELL")
        self.assertFalse(decision.authorizes_authority_expansion)
        self.assertFalse(decision.authorizes_destructive_retirement)

    def test_paid_or_unknown_cost_requires_owner_trigger(self) -> None:
        for cost_class in ("PAID", "UNKNOWN"):
            decision = decide_autoscale(
                AutoscaleSignal("SIG-COST-" + cost_class, "AS-007", 0.9, 0.9, cost_class=cost_class)
            )
            self.assertEqual(decision.status, "OWNER_TRIGGER_REQUIRED")
            self.assertTrue(decision.owner_trigger_required)

    def test_mesh_paid_runtime_still_requires_owner_trigger(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-MESH-PAID", "AS-018", 1.0, 1.0, cost_class="PAID"))
        self.assertEqual(decision.status, "OWNER_TRIGGER_REQUIRED")

    def test_iam_secret_or_external_effect_cannot_autoscale_authority(self) -> None:
        for field in ("iam_or_secret_change", "external_effect", "destructive_change", "consequential"):
            kwargs = {field: True}
            decision = decide_autoscale(
                AutoscaleSignal("SIG-AUTH-" + field, "AS-014", 1.0, 1.0, **kwargs)
            )
            self.assertEqual(decision.status, "OWNER_TRIGGER_REQUIRED")
            self.assertFalse(decision.authorizes_authority_expansion)
            self.assertFalse(decision.authorizes_destructive_retirement)

    def test_stale_proof_holds_without_freezing_unaffected_lanes(self) -> None:
        decision = decide_autoscale(
            AutoscaleSignal("SIG-STALE", "AS-001", 0.9, 0.9, evidence_current=False)
        )
        self.assertEqual(decision.status, "HOLD_STALE_PROOF")
        self.assertTrue(decision.continue_unaffected_lanes)

    def test_evd_hold_overrides_scale_up(self) -> None:
        decision = decide_autoscale(
            AutoscaleSignal(
                "SIG-EVD",
                "AS-014",
                1.0,
                1.0,
                evd_verdict="HOLD_ARCHITECTURE_EXPANSION",
            )
        )
        self.assertEqual(decision.status, "HOLD_ARCHITECTURE_EXPANSION")
        self.assertEqual(decision.direction, "HOLD")

    def test_permanent_anchor_cannot_be_auto_demoted(self) -> None:
        decision = decide_autoscale(
            AutoscaleSignal(
                "SIG-ANCHOR",
                "AS-003",
                0.7,
                0.7,
                permanent_anchor_target=True,
            )
        )
        self.assertEqual(decision.status, "HOLD_PERMANENT_ANCHOR")

    def test_failover_is_lateral_and_does_not_inherit_authority(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-FAILOVER", "AS-011", 1.0, 1.0))
        self.assertEqual(decision.status, "AUTONOMOUS_ADMISSIBLE")
        self.assertEqual(decision.direction, "LATERAL")
        self.assertEqual(decision.action, "REROUTE_EQUIVALENT_ADAPTER")
        self.assertFalse(decision.authorizes_authority_expansion)

    def test_mesh_failover_is_lateral_and_keeps_unaffected_lanes(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-MESH-FAILOVER", "AS-020", 1.0, 1.0))
        self.assertEqual(decision.status, "AUTONOMOUS_ADMISSIBLE")
        self.assertEqual(decision.direction, "LATERAL")
        self.assertEqual(decision.action, "CONTINUE_LOCAL_AND_REROUTE")
        self.assertTrue(decision.continue_unaffected_lanes)

    def test_low_value_activity_does_not_trigger_growth(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-LOW", "AS-006", 0.1, 0.1))
        self.assertEqual(decision.status, "NO_SCALE_LOW_VALUE")
        self.assertEqual(decision.action, "NO_SCALE")

    def test_self_improvement_forms_smallest_missing_capability(self) -> None:
        decision = decide_autoscale(AutoscaleSignal("SIG-SELF", "AS-014", 0.95, 0.8))
        self.assertEqual(decision.action, "FORM_SMALLEST_MISSING_CAPABILITY")
        self.assertFalse(decision.self_certifies_improvement)

    def test_admissible_ranking_is_deterministic_and_value_weighted(self) -> None:
        ranked = rank_admissible_signals(
            [
                AutoscaleSignal("SIG-B", "AS-004", 0.7, 0.8),
                AutoscaleSignal("SIG-A", "AS-012", 0.9, 0.9),
                AutoscaleSignal("SIG-GATED", "AS-007", 1.0, 1.0, cost_class="PAID"),
            ]
        )
        self.assertEqual([d.signal_id for d in ranked], ["SIG-A", "SIG-B"])


if __name__ == "__main__":
    unittest.main()
