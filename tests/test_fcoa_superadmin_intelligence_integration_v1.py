import unittest

from federation.fcoa.admin_v1.fcoa_admin import FCOAAdminRegistry, FCOASuperAdmin
from federation.formation_power_inheritance_v2 import WorkflowClass, WorkflowFormationSpec
from federation.formation_surface_load_balancer_v1 import FormationWorkPackage, SurfaceRuntimeState, WorkKind


class FCOASuperAdminIntelligenceIntegrationTests(unittest.TestCase):
    def test_superadmin_consumes_existing_intelligence_binding(self):
        admin=FCOASuperAdmin(FCOAAdminRegistry())
        spec=WorkflowFormationSpec(
            workflow_id="fcoa-admin-intelligence",
            objective="compose FCOA intelligence without expanding authority",
            workflow_class=WorkflowClass.AUTOMATION,
            domains=frozenset({"FCOA","AUTOMATION","ROUTING"}),
        )
        packages=(FormationWorkPackage(
            package_id="p1",
            kind=WorkKind.COGNITION,
            required_capabilities=frozenset({"reasoning"}),
        ),)
        states=(SurfaceRuntimeState(
            surface_id="local",
            current=True,
            healthy=True,
            callable=True,
            authority=True,
            privacy=True,
            cost_ok=True,
            supported_kinds=frozenset({WorkKind.COGNITION}),
            capabilities=frozenset({"reasoning"}),
            failure_domain="local",
        ),)
        plan=admin.compile_intelligence(spec=spec,packages=packages,runtime_states=states)
        self.assertEqual(plan.contract_id,"FCOA-INTELLIGENCE-001")
        self.assertEqual(plan.hipb_contract_id,"FUSE-HIPB-001")
        self.assertEqual(plan.autonomous_improvement_iterations,10)
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.creates_new_controller)
        self.assertFalse(plan.creates_new_scheduler)


if __name__=="__main__":
    unittest.main()
