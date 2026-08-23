import unittest

from ao_harmonic_v3 import AOHarmonicV3, ForestOmegaContext
from evidenceops.lex_omega.forest_first_creator_mode import WorkClass, WorkItem


class ForestFirstOmegaIntegrationTests(unittest.TestCase):
    def base_context(self, **overrides):
        data = dict(
            matter_id="FOREST-OMEGA-TEST",
            objective="Protect the objective while discovering the decision-changing truth",
            desired_outcome="Strongest lawful reversible path selected with proof preserved",
            high_stakes=True,
            consequential_action_planned=False,
            consequence=0.9,
            uncertainty=0.8,
            dependency_density=0.8,
            adversarial_complexity=0.8,
            root_hypotheses=("The immediate event may be part of a larger strategic pattern",),
            tree_facts=("primary fact A", "primary fact B"),
            evidence_dependencies=("primary record", "decision chain"),
            cross_lane_risks=("waiver", "forum contamination"),
            route_alternatives=(
                {
                    "route_id": "REUSE-PRIMARY", "route_type": "REUSE", "available": True, "authorised": True,
                    "feasibility": 0.9, "proof_strength": 0.95, "reversibility": 1.0, "speed": 0.8,
                    "strategic_value": 0.95, "owner_burden": 0.0, "privacy_cost": 0.1,
                    "maintenance_cost": 0.1, "information_gain": 0.9,
                },
                {
                    "route_id": "NEW-BUILD", "route_type": "NEW_BUILD", "available": True, "authorised": True,
                    "feasibility": 0.5, "proof_strength": 0.6, "reversibility": 0.7, "speed": 0.3,
                    "strategic_value": 0.6, "owner_burden": 0.4, "privacy_cost": 0.2,
                    "maintenance_cost": 0.7, "information_gain": 0.5,
                },
            ),
        )
        data.update(overrides)
        return ForestOmegaContext(**data)

    def test_runtime_exposes_forest_first_omega(self):
        runtime = AOHarmonicV3()
        self.assertEqual(runtime.VERSION, "3.3.0")
        self.assertEqual(runtime.forest.ENGINE_ID, "FOREST-FIRST-OMEGA-V1")
        self.assertEqual(runtime.horizon.ENGINE_ID, "HORIZON-OMEGA-V1")

    def test_integrated_cycle_and_adaptive_horizon(self):
        result = AOHarmonicV3().forest.run(self.base_context())
        self.assertEqual(result.architecture_cycle, (
            "ROOTS", "FOREST", "HORIZON", "TREES", "PATHS", "DECISION", "OMEGA", "READBACK", "LEARNING"
        ))
        self.assertGreater(result.horizon["adaptive_depth"], 10)
        self.assertEqual(result.horizon["profile"], "FOREST_FIRST_OMEGA")
        self.assertEqual(result.paths[0]["route_id"], "REUSE-PRIMARY")
        self.assertFalse(result.external_effect)
        self.assertEqual(result.truth_class, "STRATEGIC_SIMULATION_AND_CONTROL_STATE_NOT_FACT")

    def test_route_failure_auto_reroutes_without_owner_surface(self):
        context = self.base_context(route_failure_detected=True, objective_exhausted=False, owner_only_dependency=False, material_strategy_change=False)
        result = AOHarmonicV3().forest.run(context)
        self.assertEqual(result.route_recovery["rerouted_to"]["route_id"], "REUSE-PRIMARY")
        self.assertFalse(result.route_recovery["surface_to_owner"])
        self.assertEqual(result.route_recovery["rule"], "ROUTE_FAILURE_IS_NOT_OBJECTIVE_FAILURE")

    def test_creator_mode_absorbs_system_debugging(self):
        context = self.base_context(work_items=(
            WorkItem("repair connector route", WorkClass.SYSTEM_DEBUG),
            WorkItem("recover primary record", WorkClass.RESEARCH_RETRIEVAL),
        ))
        result = AOHarmonicV3().forest.run(context)
        self.assertEqual(result.creator_mode["system_absorbed_count"], 2)
        self.assertEqual(result.creator_mode["user_required_count"], 0)
        self.assertTrue(result.creator_mode["creator_focus_protected"])

    def test_anticipatory_controls_act_before_owner_prompt(self):
        context = self.base_context(
            credible_risk_signal_present=True,
            deadline_state_verified=False,
            evidence_preservation_current=False,
            continuity_checkpoint_current=False,
        )
        result = AOHarmonicV3().forest.run(context)
        need_classes = {cue["need_class"] for cue in result.anticipatory["cues"]}
        self.assertTrue({"RISK", "DEADLINE", "EVIDENCE", "CONTINUITY"}.issubset(need_classes))
        self.assertTrue(result.anticipatory["automatic_actions"])

    def test_consequential_action_holds_for_human_authority_and_teachback(self):
        context = self.base_context(consequential_action_planned=True, teach_back_complete=False)
        result = AOHarmonicV3().forest.run(context)
        self.assertTrue(result.user_interrupt_required)
        self.assertTrue(result.decision["owner_hold"])
        self.assertTrue(result.anticipatory["owner_decisions"])

    def test_learning_pipeline_activates_on_correction_or_repeat_failure(self):
        context = self.base_context(repeated_failure_detected=True, material_user_correction_received=True)
        result = AOHarmonicV3().forest.run(context)
        self.assertTrue(result.learning["candidate_required"])
        self.assertEqual(result.learning["backcast_success_claims"], "PROHIBITED")
        self.assertTrue(result.learning["misses_preserved"])


if __name__ == "__main__":
    unittest.main()
