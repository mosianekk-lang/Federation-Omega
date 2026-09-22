import unittest

from ao_harmonic_v3.recovery_formation_shadow import run_c3_recovery_formation_shadow


class ForestFirstC3RecoveryFormationShadowV1Tests(unittest.TestCase):
    def setUp(self):
        self.report = run_c3_recovery_formation_shadow()
        self.rows = {row["scenario_id"]: row for row in self.report["scenarios"]}

    def test_all_five_required_scenarios_pass(self):
        self.assertEqual(self.report["scenario_count"], 5)
        self.assertTrue(self.report["pass"])
        self.assertTrue(all(row["pass_state"] for row in self.report["scenarios"]))

    def test_portable_failure_identity_is_shared_without_erasing_receiver_identity(self):
        row = self.rows["C3-SHARED-PORTABLE-FINGERPRINT"]
        self.assertTrue(row["checks"]["portable_fingerprint_shared"])
        self.assertTrue(row["checks"]["receiver_local_fingerprints_distinct"])

    def test_recovery_receipt_is_equivalent_without_operational_overclaim(self):
        row = self.rows["C3-RECOVERY-RECEIPT-EQUIVALENCE"]
        self.assertTrue(row["checks"]["normalized_receipts_equivalent"])
        self.assertTrue(row["checks"]["alternate_route_selected"])
        self.assertTrue(row["checks"]["proof_graph_remains_incomplete"])
        self.assertTrue(row["checks"]["no_false_operational_win"])

    def test_unchanged_retry_is_still_prohibited(self):
        row = self.rows["C3-UNCHANGED-RETRY-PROHIBITED"]
        self.assertTrue(row["checks"]["unchanged_route_not_selected"])
        self.assertTrue(row["checks"]["repair_cycle_remains_open"])
        self.assertTrue(row["checks"]["alternate_route_search_required"])

    def test_route_failure_does_not_become_objective_failure(self):
        row = self.rows["C3-ROUTE-FAILURE-NOT-OBJECTIVE-FAILURE"]
        self.assertTrue(row["checks"]["failed_incumbent_route_does_not_end_objective"])
        self.assertTrue(row["checks"]["materially_different_route_available"])
        self.assertTrue(row["checks"]["state_not_quarantined_by_single_route_failure"])

    def test_rollback_and_semantic_readback_are_mandatory(self):
        row = self.rows["C3-ROLLBACK-AND-FORMATION-RELEASE"]
        self.assertTrue(row["checks"]["nonrollback_route_not_selected"])
        self.assertTrue(row["checks"]["rollback_route_selected"])
        self.assertTrue(row["checks"]["formation_release_denied_without_rollback"])
        self.assertTrue(row["checks"]["formation_release_allowed_with_semantic_readback_and_rollback"])
        self.assertTrue(row["checks"]["semantic_mismatch_still_blocks_release"])

    def test_shadow_remains_non_effectful_and_non_migratory(self):
        self.assertEqual(self.report["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(self.report["external_effect"])
        self.assertFalse(self.report["provider_runtime_proved"])
        self.assertFalse(self.report["canonical_docs_modified"])
        self.assertFalse(self.report["physical_migration_executed"])
        self.assertFalse(self.report["system_retirement_allowed"])
        self.assertFalse(self.report["failure_win_operational_maturity_inherited"])
        self.assertEqual(self.report["independent_assurance_review"], "PENDING")


if __name__ == "__main__":
    unittest.main()
