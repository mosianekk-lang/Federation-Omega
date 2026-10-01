import unittest

from federation.capability_truth_v1 import CapabilityCurrentnessFabric
from federation.formation_infinity_production_v1 import PredicateState, ProductionPredicate
from federation.fuse_ecosystem_v1 import FuseEcosystemKernel


class FuseEcosystemFormationInfinityTests(unittest.TestCase):
    def test_ecosystem_kernel_exposes_production_infinity_over_registered_families(self):
        kernel=FuseEcosystemKernel(CapabilityCurrentnessFabric())
        plan=kernel.compile_production_infinity(
            mission_id="MISSION-FUSE-PRODUCTION-CLOSURE",
            predicates=[
                ProductionPredicate(
                    "SOURCE_ADMITTED",
                    PredicateState.CLOSED,
                    ("proof:source",),
                    priority=100,
                ),
                ProductionPredicate(
                    "PROOF_EXECUTION_SCALABLE",
                    PredicateState.ACTIVE,
                    priority=99,
                ),
            ],
        )
        self.assertEqual(plan.contract_id,"FUSE-FORMATION-INFINITY-PRODUCTION-001")
        self.assertTrue(plan.family_bindings)
        self.assertTrue(all(x.formation_propagated for x in plan.family_bindings))
        self.assertTrue(plan.resource_bindings)
        self.assertLessEqual(plan.active_logical_agent_slots,99)
        self.assertFalse(plan.external_effect_authorized)
        self.assertFalse(plan.provider_execution_proven)
        self.assertFalse(plan.production_ready)
        self.assertEqual(plan.next_predicate_ids[0],"PROOF_EXECUTION_SCALABLE")

    def test_future_registered_service_family_is_inherited_automatically(self):
        from federation.fuse_ecosystem_v1 import EcosystemPlane, EcosystemServiceSpec
        services={
            "future.service": EcosystemServiceSpec(
                "future.service",
                EcosystemPlane.INTELLIGENCE,
                ("future.capability",),
            )
        }
        kernel=FuseEcosystemKernel(CapabilityCurrentnessFabric(),services=services)
        plan=kernel.compile_production_infinity(
            mission_id="M",
            predicates=[ProductionPredicate("SOURCE_ADMITTED",PredicateState.ACTIVE)],
        )
        self.assertEqual(len(plan.family_bindings),1)
        self.assertEqual(plan.family_bindings[0].family_id,"INTELLIGENCE")
        self.assertEqual(plan.family_bindings[0].service_ids,("future.service",))


if __name__=="__main__":
    unittest.main()
