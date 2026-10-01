import unittest

from federation.fcoa.intelligence_v1.fcoa_intelligence import FCOAIntelligenceBinding
from federation.formation_power_inheritance_v2 import WorkflowClass, WorkflowFormationSpec
from federation.formation_surface_load_balancer_v1 import (
    FormationWorkPackage,
    SurfaceRuntimeState,
    WorkKind,
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
