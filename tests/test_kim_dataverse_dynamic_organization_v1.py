from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_dynamic_organization_v1 import (
    OrganizationContext,
    OrganizationPattern,
    compile_dynamic_organization,
    organization_dissolves_after_mission,
)


class KimDataverseDynamicOrganizationTests(unittest.TestCase):
    def test_provider_failure_forms_provider_recovery_swarm(self) -> None:
        plan = compile_dynamic_organization(OrganizationContext(0.5, 0.5, 0.5, False, True, False, True, 4))
        self.assertEqual(OrganizationPattern.PROVIDER_RECOVERY_SWARM, plan.pattern)
        self.assertIn("semantic-witness", plan.roles)

    def test_architecture_change_uses_council_with_entropy_critic(self) -> None:
        plan = compile_dynamic_organization(OrganizationContext(0.8, 0.6, 0.4, False, False, True, True, 4))
        self.assertEqual(OrganizationPattern.ARCHITECTURE_COUNCIL, plan.pattern)
        self.assertIn("entropy-critic", plan.roles)

    def test_high_uncertainty_forces_scientific_tournament(self) -> None:
        plan = compile_dynamic_organization(OrganizationContext(0.4, 0.9, 0.2, False, False, False, True, 5))
        self.assertEqual(OrganizationPattern.SCIENTIFIC_TOURNAMENT, plan.pattern)
        self.assertIn("challenger", plan.roles)
        self.assertIn("falsifier", plan.roles)

    def test_simple_work_uses_solo_specialist(self) -> None:
        plan = compile_dynamic_organization(OrganizationContext(0.2, 0.2, 0.2, False, False, False, False, 1))
        self.assertEqual(OrganizationPattern.SOLO_SPECIALIST, plan.pattern)
        self.assertEqual(("specialist",), plan.roles)

    def test_high_consequence_caps_parallelism(self) -> None:
        plan = compile_dynamic_organization(OrganizationContext(0.9, 0.9, 0.95, False, False, False, True, 10))
        self.assertLessEqual(plan.max_parallelism, 2)
        self.assertFalse(plan.external_effect_authorized)

    def test_organizations_are_ephemeral_not_permanent_agent_sprawl(self) -> None:
        plan = compile_dynamic_organization(OrganizationContext(0.7, 0.5, 0.3, False, False, False, True, 3))
        self.assertEqual(0, plan.permanent_agents_created)
        self.assertTrue(organization_dissolves_after_mission(plan))


if __name__ == "__main__":
    unittest.main()
