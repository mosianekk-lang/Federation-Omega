from __future__ import annotations

import unittest

from .assurance_gate import AssuranceContext, PreOwnerAssuranceGate


class PreOwnerAssuranceGateTests(unittest.TestCase):
    def test_major_redesign_of_inherited_estate_holds_until_discovery_complete(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="kdv-productionisation",
                consequential=True,
                major_redesign=True,
                inherited_estate=True,
                realityguard_checked=True,
                fklm_checked=True,
                strongest_countercase_tested=True,
                authority_boundary_checked=True,
                reversibility_checked=True,
                owner_burden_checked=True,
            )
        )
        self.assertEqual(result["gate_state"], "HOLD_FOR_DISCOVERY")
        self.assertFalse(result["release_allowed"])
        self.assertIn("estate_inventory_verified", result["blocking_items"])
        self.assertIn("duplication_lineage_checked", result["blocking_items"])

    def test_available_assurance_not_invoked_blocks_consequential_recommendation(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="consequential-recommendation",
                consequential=True,
                proof_state_reconciled=True,
                strongest_countercase_tested=True,
                authority_boundary_checked=True,
                reversibility_checked=True,
                owner_burden_checked=True,
                realityguard_checked=False,
                fklm_checked=False,
            )
        )
        self.assertEqual(result["gate_state"], "REPAIR_REQUIRED")
        self.assertFalse(result["release_allowed"])
        self.assertIn("realityguard_checked", result["blocking_items"])
        self.assertIn("fklm_checked", result["blocking_items"])

    def test_material_unknowns_hold_even_when_named_checks_pass(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="unknown-boundary",
                consequential=True,
                proof_state_reconciled=True,
                realityguard_checked=True,
                fklm_checked=True,
                strongest_countercase_tested=True,
                authority_boundary_checked=True,
                reversibility_checked=True,
                owner_burden_checked=True,
                unresolved_material_unknowns=("provider authority unresolved",),
            )
        )
        self.assertEqual(result["gate_state"], "HOLD_FOR_DISCOVERY")
        self.assertFalse(result["release_allowed"])
        self.assertIn("provider authority unresolved", result["blocking_items"])

    def test_owner_only_decision_is_not_misclassified_as_system_defect(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="owner-choice",
                consequential=True,
                proof_state_reconciled=True,
                realityguard_checked=True,
                fklm_checked=True,
                strongest_countercase_tested=True,
                authority_boundary_checked=True,
                reversibility_checked=True,
                owner_burden_checked=True,
                owner_only_decision=True,
            )
        )
        self.assertEqual(result["gate_state"], "OWNER_DECISION_REQUIRED")
        self.assertFalse(result["release_allowed"])
        self.assertTrue(result["owner_action_required"])
        self.assertEqual(result["blocking_items"], [])

    def test_fully_assured_major_redesign_can_pass(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="verified-redesign",
                consequential=True,
                major_redesign=True,
                inherited_estate=True,
                estate_inventory_verified=True,
                proof_state_reconciled=True,
                duplication_lineage_checked=True,
                maturity_gap_checked=True,
                prior_failure_scan_checked=True,
                realityguard_checked=True,
                fklm_checked=True,
                strongest_countercase_tested=True,
                authority_boundary_checked=True,
                reversibility_checked=True,
                owner_burden_checked=True,
            )
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])
        self.assertFalse(result["owner_action_required"])

    def test_low_risk_nonconsequential_recommendation_is_not_overblocked(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(recommendation_id="low-risk-tip")
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])


if __name__ == "__main__":
    unittest.main()
