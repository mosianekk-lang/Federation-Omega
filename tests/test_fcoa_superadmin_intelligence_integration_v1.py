import unittest

from federation.fcoa.admin_v1.fcoa_admin import FCOAAdminRegistry, FCOASuperAdmin
from federation.formation_power_inheritance_v2 import WorkflowClass, WorkflowFormationSpec
from federation.formation_surface_load_balancer_v1 import FormationWorkPackage, SurfaceRuntimeState, WorkKind


def runtime(surface_id: str, domain: str) -> SurfaceRuntimeState:
    return SurfaceRuntimeState(
        surface_id=surface_id,
        authority_pass=True,
        privacy_pass=True,
        currentness_pass=True,
        proof_pass=True,
        health_pass=True,
        quota_pass=True,
        quality=0.9,
        reliability=0.95,
        proof_strength=0.95,
        latency_ms=100.0,
        estimated_cost=0.01,
        owner_burden=0.01,
        privacy_cost=0.01,
        maintenance_cost=0.01,
        strategic_value=0.7,
        parallel_slots=2,
        correlation_domains=(domain,),
        proof_refs=(f"proof:{surface_id}",),
    )


class FCOASuperAdminIntelligenceIntegrationTests(unittest.TestCase):
    def test_superadmin_consumes_existing_intelligence_binding(self):
        admin=FCOASuperAdmin(FCOAAdminRegistry())
        spec=WorkflowFormationSpec(
            workflow_id="fcoa-admin-intelligence",
            objective="compose FCOA intelligence without expanding authority",
            workflow_class=WorkflowClass.AUTOMATION,
            domains=frozenset({"FCOA","AUTOMATION","ROUTING"}),
        )
        packages=(FormationWorkPackage("p1",WorkKind.COGNITION,("reasoning",)),)
        states=(runtime("OPENAI-GPT6-ASTRA","openai"),)
        plan=admin.compile_intelligence(spec=spec,packages=packages,runtime_states=states)
        self.assertEqual(plan.contract_id,"FCOA-INTELLIGENCE-001")
        self.assertEqual(plan.hipb_contract_id,"FUSE-HIPB-001")
        self.assertEqual(plan.autonomous_improvement_iterations,10)
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.creates_new_controller)
        self.assertFalse(plan.creates_new_scheduler)


if __name__=="__main__":
    unittest.main()
