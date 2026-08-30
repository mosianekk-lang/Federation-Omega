import unittest
from dataclasses import replace

from ao_harmonic_v3.forest_integrity_equivalence import (
    admitted_reference_context,
    fully_admissible,
)
from ao_harmonic_v3.forest_integrity_mode import (
    DEFAULT_INTEGRITY_MODE,
    ForestIntegrityModeController,
    IntegrityMode,
)


class ForestIntegrityModeTests(unittest.TestCase):
    def setUp(self):
        self.context = admitted_reference_context()

    def test_default_is_shadow_not_enforced(self):
        self.assertEqual(DEFAULT_INTEGRITY_MODE, IntegrityMode.SHADOW)
        controller = ForestIntegrityModeController()
        self.assertEqual(controller.mode, IntegrityMode.SHADOW)

    def test_shadow_attaches_typed_state_without_changing_legacy_selection(self):
        result = ForestIntegrityModeController().run(self.context)
        self.assertEqual(result.mode, "SHADOW")
        self.assertEqual(result.selected_path, "REUSE-PRIMARY")
        self.assertEqual(result.legacy_selected_path, "REUSE-PRIMARY")
        self.assertIsNone(result.typed_selected_path)
        self.assertTrue(result.shadow_attached)
        self.assertFalse(result.runtime_default_changed)
        self.assertFalse(result.execution_authorized)
        self.assertFalse(result.external_effect)

    def test_enforced_holds_when_legacy_routes_lack_typed_admissibility(self):
        result = ForestIntegrityModeController(mode=IntegrityMode.ENFORCED).run(self.context)
        self.assertTrue(result.held)
        self.assertIn("NO_ADMISSIBLE_TYPED_PATH", result.hold_reasons)
        self.assertIsNone(result.selected_path)
        self.assertFalse(result.execution_authorized)

    def test_enforced_selects_explicitly_admissible_path_internally(self):
        routes = tuple(fully_admissible(dict(route)) for route in self.context.route_alternatives)
        context = replace(self.context, route_alternatives=routes)
        result = ForestIntegrityModeController(mode=IntegrityMode.ENFORCED).run(context)
        self.assertFalse(result.held)
        self.assertEqual(result.selected_path, "REUSE-PRIMARY")
        self.assertEqual(result.typed_selected_path, "REUSE-PRIMARY")
        self.assertFalse(result.execution_authorized)
        self.assertFalse(result.provider_effect_proved)

    def test_enforced_excludes_unauthorised_high_score_route(self):
        high = fully_admissible(
            dict(self.context.route_alternatives[0]),
            route_id="UNAUTHORISED-HIGH",
            authorised=False,
            strategic_value=1.0,
            proof_strength=1.0,
        )
        safe = fully_admissible(
            dict(self.context.route_alternatives[1]),
            route_id="AUTHORISED-LOWER",
            strategic_value=0.7,
            proof_strength=0.8,
        )
        result = ForestIntegrityModeController(mode=IntegrityMode.ENFORCED).run(
            replace(self.context, route_alternatives=(high, safe))
        )
        self.assertEqual(result.legacy_selected_path, "UNAUTHORISED-HIGH")
        self.assertEqual(result.selected_path, "AUTHORISED-LOWER")
        self.assertFalse(result.held)

    def test_consequential_action_remains_held_even_with_admissible_route(self):
        routes = tuple(fully_admissible(dict(route)) for route in self.context.route_alternatives)
        context = replace(
            self.context,
            consequential_action_planned=True,
            route_alternatives=routes,
        )
        result = ForestIntegrityModeController(mode=IntegrityMode.ENFORCED).run(context)
        self.assertTrue(result.held)
        self.assertEqual(result.selected_path, "REUSE-PRIMARY")
        self.assertIn("OWNER_AUTHORITY_REQUIRED_FOR_CONSEQUENTIAL_ACTION", result.hold_reasons)
        self.assertFalse(result.execution_authorized)

    def test_legacy_mode_remains_available_for_rollback(self):
        result = ForestIntegrityModeController(mode=IntegrityMode.LEGACY).run(self.context)
        self.assertEqual(result.decision_source, "LEGACY_FOREST_OMEGA")
        self.assertEqual(result.selected_path, "REUSE-PRIMARY")
        self.assertFalse(result.shadow_attached)
        self.assertFalse(result.execution_authorized)


if __name__ == "__main__":
    unittest.main()
