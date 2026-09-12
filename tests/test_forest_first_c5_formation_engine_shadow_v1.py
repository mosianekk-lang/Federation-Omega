import unittest

from ao_harmonic_v3.formation_engine_shadow import run_c5_formation_engine_shadow


class ForestFirstC5FormationEngineShadowV1Tests(unittest.TestCase):
    def setUp(self):
        self.report = run_c5_formation_engine_shadow()
        self.rows = {row["scenario_id"]: row for row in self.report["scenarios"]}

    def test_all_ten_required_scenarios_pass(self):
        self.assertEqual(self.report["scenario_count"], 10)
        self.assertEqual(self.report["semantic_axis_count"], 10)
        self.assertEqual(len(self.report["required_scenarios"]), 10)
        self.assertTrue(self.report["pass"])
        self.assertTrue(all(row["pass_state"] for row in self.report["scenarios"]))

    def test_public_api_and_mission_convergence_are_preserved(self):
        self.assertTrue(self.rows["C5-PUBLIC-API-FREEZE"]["checks"]["public_api_preserved"])
        self.assertTrue(self.rows["C5-MISSION-CONVERGENCE"]["checks"]["independent_lane_parallelized"])
        self.assertTrue(self.rows["C5-MISSION-CONVERGENCE"]["checks"]["shared_state_serialized"])
        self.assertTrue(self.rows["C5-PROOF-CLOSURE"]["checks"]["closure_initially_fail_closed"])
        self.assertTrue(self.rows["C5-PROOF-CLOSURE"]["checks"]["closure_opens_after_required_proof"])

    def test_autonomic_and_assurance_boundaries_remain_fail_closed(self):
        self.assertTrue(
            self.rows["C5-AUTONOMIC-AUTHORITY"]["checks"][
                "external_effect_held_without_authority"
            ]
        )
        self.assertTrue(
            self.rows["C5-INDEPENDENT-WITNESS"]["checks"][
                "self_certification_prohibited"
            ]
        )
        self.assertTrue(
            self.rows["C5-MONOTONIC-CLOSURE"]["checks"][
                "safety_regression_rejected"
            ]
        )

    def test_source_reconciliation_and_strategic_ecology_are_preserved(self):
        self.assertTrue(
            self.rows["C5-SOURCE-CONVERGENCE"]["checks"]["safe_reanchor_allowed"]
        )
        self.assertTrue(
            self.rows["C5-RECONCILIATION"]["checks"]["rollback_gap_preserved"]
        )
        self.assertTrue(
            self.rows["C5-STRATEGIC-ECOLOGY"]["checks"][
                "external_mission_not_selected"
            ]
        )

    def test_formation_remains_engine_not_sovereign_brain(self):
        checks = self.rows["C5-AUTHORITY-IDENTITY"]["checks"]
        self.assertTrue(checks["formation_kept_as_engine"])
        self.assertTrue(checks["mission_execution_layer_preserved"])
        self.assertTrue(checks["sovereign_cognitive_takeover_prohibited"])
        self.assertTrue(checks["proof_not_inherited"])
        self.assertTrue(checks["authority_not_inherited"])
        self.assertTrue(checks["maturity_not_inherited"])

    def test_shadow_remains_source_scoped_and_non_migratory(self):
        self.assertEqual(self.report["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(self.report["external_effect"])
        self.assertFalse(self.report["provider_runtime_proved"])
        self.assertFalse(self.report["physical_migration_executed"])
        self.assertFalse(self.report["system_retirement_allowed"])
        self.assertFalse(self.report["formation_runtime_rewired"])
        self.assertFalse(self.report["public_api_superseded"])
        self.assertFalse(self.report["formation_authority_expanded"])
        self.assertFalse(self.report["cognitive_sovereignty_claimed"])
        self.assertFalse(self.report["maturity_inheritance"])
        self.assertEqual(self.report["independent_assurance_review"], "PENDING")


if __name__ == "__main__":
    unittest.main()
