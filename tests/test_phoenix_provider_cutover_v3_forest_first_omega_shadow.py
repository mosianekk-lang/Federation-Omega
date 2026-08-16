import unittest

from ao_harmonic_v3.forest_omega_shadow import run_forest_omega_shadow


class ForestFirstOmegaShadowTests(unittest.TestCase):
    def setUp(self):
        self.report = run_forest_omega_shadow()

    def test_shadow_passes_all_bounded_acceptance_checks(self):
        self.assertTrue(self.report["pass"], self.report["acceptance"])
        self.assertTrue(all(self.report["acceptance"].values()))

    def test_shadow_is_no_effect_and_a1_internal(self):
        self.assertFalse(self.report["external_effect"])
        self.assertEqual(self.report["authority_ceiling"], "A1_INTERNAL")
        self.assertEqual(
            self.report["truth_boundary"],
            "REAL_MISSION_DERIVED_REDACTED_CONTROL_STATE_NO_PRIVATE_PAYLOAD_NO_EXTERNAL_EFFECT",
        )

    def test_horizon_extends_and_roots_are_falsifiable(self):
        integrated = self.report["integrated"]
        reference = self.report["reference"]
        self.assertGreater(integrated["adaptive_horizon_depth"], reference["adaptive_horizon_depth"])
        self.assertGreaterEqual(integrated["root_hypotheses_challenged"], 2)
        self.assertGreaterEqual(integrated["falsifier_questions_available"], 2)

    def test_route_failure_is_recovered_without_owner_blocker(self):
        integrated = self.report["integrated"]
        self.assertTrue(integrated["route_recovered"])
        self.assertFalse(integrated["route_failure_surface_to_owner"])
        self.assertEqual(self.report["route_recovery"]["rerouted_to"]["route_id"], "RECOVER-PRIMARY")

    def test_creator_mode_absorbs_system_work(self):
        integrated = self.report["integrated"]
        self.assertGreaterEqual(integrated["system_absorbed_work_items"], 2)
        self.assertEqual(integrated["owner_required_work_items"], 0)
        self.assertFalse(integrated["owner_interrupt_required"])

    def test_high_information_reversible_path_wins(self):
        self.assertEqual(self.report["selected_path"], "RECOVER-PRIMARY")

    def test_reference_is_explicit_fixture_not_runtime_claim(self):
        self.assertEqual(
            self.report["reference_boundary"],
            "FRAGMENTED_REFERENCE_POLICY_IS_ARCHITECTURAL_FIXTURE_NOT_HISTORICAL_RUNTIME_MEASUREMENT",
        )
        self.assertEqual(
            self.report["formal_scope"],
            "FOREST_FIRST_OMEGA_SYSTEM_SPECIFIC_REAL_MISSION_DERIVED_NO_EFFECT_SHADOW",
        )


if __name__ == "__main__":
    unittest.main()
