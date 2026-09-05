import unittest

from ao_harmonic_v3.high_coupling_policy_shadow import run_c4_high_coupling_policy_shadow


class ForestFirstC4HighCouplingPolicyShadowV1Tests(unittest.TestCase):
    def setUp(self):
        self.report = run_c4_high_coupling_policy_shadow()
        self.rows = {row["scenario_id"]: row for row in self.report["scenarios"]}

    def test_all_ten_required_scenarios_pass(self):
        self.assertEqual(self.report["scenario_count"], 10)
        self.assertEqual(len(self.report["required_scenarios"]), 10)
        self.assertTrue(self.report["pass"])
        self.assertTrue(all(row["pass_state"] for row in self.report["scenarios"]))

    def test_superior_logic_remains_policy_identity_not_self_certifier(self):
        row = self.rows["C4-AUTHORITY-NON-TAKEOVER"]
        self.assertTrue(row["checks"]["superior_logic_target_is_policy_library"])
        self.assertTrue(row["checks"]["caseforge_target_is_validation_lab"])
        self.assertTrue(row["checks"]["evidence_truth_stays_outside_both"])
        self.assertTrue(row["checks"]["provider_effect_stays_external"])

    def test_caseforge_scientific_guards_remain_fail_closed(self):
        self.assertTrue(self.rows["C4-SCIENTIFIC-FALSIFICATION"]["checks"]["missing_falsifier_fails_closed"])
        self.assertTrue(self.rows["C4-BLIND-EVALUATION-SEPARATION"]["checks"]["answer_key_leak_is_rejected"])
        self.assertTrue(self.rows["C4-PROVIDER-READBACK-SEPARATION"]["checks"]["provider_verified_without_readback_fails"])
        self.assertTrue(self.rows["C4-INDEPENDENT-REPLICATION"]["checks"]["same_provider_same_model_same_route_is_not_independent"])

    def test_independent_assurance_and_legacy_identities_survive(self):
        self.assertTrue(self.rows["C4-INDEPENDENT-ASSURANCE-NO-SPOF"]["checks"]["independent_assurance_preserved"])
        self.assertTrue(self.rows["C4-LEGACY-IDENTITY-COMPATIBILITY"]["checks"]["superior_legacy_identity_resolves"])
        self.assertTrue(self.rows["C4-LEGACY-IDENTITY-COMPATIBILITY"]["checks"]["caseforge_legacy_identity_resolves"])

    def test_shadow_remains_no_effect_and_non_migratory(self):
        self.assertEqual(self.report["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(self.report["external_effect"])
        self.assertFalse(self.report["provider_runtime_proved"])
        self.assertFalse(self.report["physical_migration_executed"])
        self.assertFalse(self.report["system_retirement_allowed"])
        self.assertFalse(self.report["superior_logic_runtime_rewired"])
        self.assertFalse(self.report["caseforge_authority_expanded"])
        self.assertFalse(self.report["maturity_inheritance"])
        self.assertEqual(self.report["independent_assurance_review"], "PENDING")


if __name__ == "__main__":
    unittest.main()
