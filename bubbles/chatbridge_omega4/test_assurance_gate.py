from __future__ import annotations

import unittest

from .assurance_gate import AssuranceContext, PreOwnerAssuranceGate


class PreOwnerAssuranceGateTests(unittest.TestCase):
    def _consequential_base(self, **overrides):
        data = {
            "recommendation_id": "assured",
            "consequential": True,
            "proof_state_reconciled": True,
            "realityguard_checked": True,
            "fklm_checked": True,
            "strongest_countercase_tested": True,
            "authority_boundary_checked": True,
            "reversibility_checked": True,
            "owner_burden_checked": True,
        }
        data.update(overrides)
        return AssuranceContext(**data)

    def test_major_redesign_of_inherited_estate_holds_until_discovery_complete(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            self._consequential_base(
                recommendation_id="kdv-productionisation",
                major_redesign=True,
                inherited_estate=True,
            )
        )
        self.assertEqual(result["gate_state"], "HOLD_FOR_DISCOVERY")
        self.assertFalse(result["release_allowed"])
        self.assertIn("estate_inventory_verified", result["blocking_items"])
        self.assertIn("duplication_lineage_checked", result["blocking_items"])

    def test_available_assurance_not_invoked_blocks_consequential_recommendation(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            self._consequential_base(
                recommendation_id="consequential-recommendation",
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
            self._consequential_base(
                recommendation_id="unknown-boundary",
                unresolved_material_unknowns=("provider authority unresolved",),
            )
        )
        self.assertEqual(result["gate_state"], "HOLD_FOR_DISCOVERY")
        self.assertFalse(result["release_allowed"])
        self.assertIn("provider authority unresolved", result["blocking_items"])

    def test_owner_only_decision_is_not_misclassified_as_system_defect(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            self._consequential_base(
                recommendation_id="owner-choice",
                owner_only_decision=True,
            )
        )
        self.assertEqual(result["gate_state"], "OWNER_DECISION_REQUIRED")
        self.assertFalse(result["release_allowed"])
        self.assertTrue(result["owner_action_required"])
        self.assertEqual(result["blocking_items"], [])

    def test_fully_assured_major_redesign_can_pass(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            self._consequential_base(
                recommendation_id="verified-redesign",
                major_redesign=True,
                inherited_estate=True,
                estate_inventory_verified=True,
                duplication_lineage_checked=True,
                maturity_gap_checked=True,
                prior_failure_scan_checked=True,
            )
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])
        self.assertFalse(result["owner_action_required"])
        self.assertTrue(result["assurance_receipt_required_before_release"])

    def test_low_risk_nonconsequential_recommendation_is_not_overblocked(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(recommendation_id="low-risk-tip")
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])
        self.assertFalse(result["assurance_receipt_required_before_release"])

    def test_source_mutation_without_isolation_is_blocked(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="unsafe-main-write",
                source_mutation=True,
                change_isolation_verified=False,
            )
        )
        self.assertEqual(result["gate_state"], "REPAIR_REQUIRED")
        self.assertFalse(result["release_allowed"])
        self.assertIn("change_isolation_verified", result["hardening_missing"])

    def test_source_mutation_with_isolation_can_pass_low_risk_gate(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="branch-write",
                source_mutation=True,
                change_isolation_verified=True,
            )
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])

    def test_provider_claim_without_readback_is_blocked(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="provider-claim",
                provider_claim=True,
                provider_readback_verified=False,
            )
        )
        self.assertEqual(result["gate_state"], "REPAIR_REQUIRED")
        self.assertFalse(result["release_allowed"])
        self.assertIn("provider_readback_verified", result["hardening_missing"])

    def test_provider_claim_with_readback_can_pass_low_risk_gate(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="provider-readback",
                provider_claim=True,
                provider_readback_verified=True,
            )
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])

    def test_sophisticated_output_with_incomplete_evidence_holds_for_challenge(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="coherent-but-underobserved",
                false_confidence_risk=True,
                false_confidence_challenge=False,
            )
        )
        self.assertEqual(result["gate_state"], "HOLD_FOR_DISCOVERY")
        self.assertFalse(result["release_allowed"])
        self.assertIn("false_confidence_challenge", result["hardening_missing"])

    def test_false_confidence_challenge_clears_when_no_other_blocker_exists(self) -> None:
        result = PreOwnerAssuranceGate.assess(
            AssuranceContext(
                recommendation_id="challenged-output",
                false_confidence_risk=True,
                false_confidence_challenge=True,
            )
        )
        self.assertEqual(result["gate_state"], "PASS")
        self.assertTrue(result["release_allowed"])

    def test_contract_explicitly_separates_assessment_from_receipt_persistence(self) -> None:
        contract = PreOwnerAssuranceGate.contract()
        self.assertEqual(contract["version"], "POA-1.1")
        self.assertEqual(
            contract["receipt_rule"],
            "PERSIST_ASSESSMENT_BEFORE_CONSEQUENTIAL_RELEASE",
        )
        self.assertEqual(contract["source_mutation_rule"], "ISOLATE_BEFORE_MUTATION")
        self.assertEqual(
            contract["provider_claim_rule"],
            "PROVIDER_READBACK_BEFORE_TERMINAL_CLAIM",
        )


if __name__ == "__main__":
    unittest.main()
