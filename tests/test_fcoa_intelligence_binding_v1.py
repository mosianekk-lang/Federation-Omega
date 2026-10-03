import unittest

from federation.fcoa.intelligence_v1.fcoa_intelligence import FCOAIntelligenceBinding
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


class FCOAIntelligenceBindingTests(unittest.TestCase):
    def test_binding_reuses_formation_and_requires_hipb_and_improvement(self):
        binding=FCOAIntelligenceBinding()
        spec=WorkflowFormationSpec(
            workflow_id="fcoa-test",
            objective="improve FCOA creative/device work",
            workflow_class=WorkflowClass.CREATIVE,
            domains=frozenset({"CREATIVE","DEVICE","ROUTING"}),
        )
        packages=(FormationWorkPackage("p1",WorkKind.COGNITION,("reasoning",)),)
        states=(runtime("OPENAI-GPT6-ASTRA","openai"),)
        plan=binding.compile(spec=spec,packages=packages,runtime_states=states)
        self.assertEqual(plan.hipb_contract_id,"FUSE-HIPB-001")
        self.assertEqual(plan.autonomous_improvement_iterations,10)
        self.assertEqual(plan.sovereign_hook_phases,("PRE_COMPILE","PRE_EFFECT","POST_EFFECT"))
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.builder_self_certification_allowed)
        self.assertFalse(plan.creates_new_controller)
        self.assertFalse(plan.creates_new_scheduler)


if __name__=="__main__":
    unittest.main()
