import unittest

from federation.formation_infinity_production_v1 import (
    FormationInfinityProductionCompiler,
    LOGICAL_AGENT_BUDGET,
    PredicateState,
    ProductionPredicate,
)
from federation.fuse_ecosystem_v1 import FUSE_ECOSYSTEM_SERVICES


class FormationInfinityProductionTests(unittest.TestCase):
    def setUp(self):
        self.compiler=FormationInfinityProductionCompiler()

    def test_all_current_families_and_resources_are_bound_without_authority(self):
        plan=self.compiler.compile(
            mission_id="MISSION-PRODUCTION-CLOSURE",
            services=FUSE_ECOSYSTEM_SERVICES,
            predicates=[
                ProductionPredicate("SOURCE_ADMITTED",PredicateState.CLOSED,("proof:source",)),
                ProductionPredicate("PROOF_EXECUTION_SCALABLE",PredicateState.ACTIVE,priority=100),
            ],
        )
        self.assertGreater(len(plan.family_bindings),1)
        self.assertGreater(len(plan.resource_bindings),1)
        self.assertTrue(all(x.formation_propagated for x in plan.family_bindings))
        self.assertTrue(all(not x.authority_minted for x in plan.resource_bindings))
        self.assertFalse(plan.provider_execution_proven)
        self.assertFalse(plan.external_effect_authorized)
        self.assertLessEqual(plan.active_logical_agent_slots,LOGICAL_AGENT_BUDGET)
        self.assertIn("PROOF_EXECUTION_SCALABLE",plan.next_predicate_ids)

    def test_default_missing_predicates_keep_production_nonterminal(self):
        plan=self.compiler.compile(
            mission_id="MISSION-PRODUCTION-CLOSURE",
            services=FUSE_ECOSYSTEM_SERVICES,
            predicates=[
                ProductionPredicate("SOURCE_ADMITTED",PredicateState.CLOSED,("proof:source",)),
            ],
        )
        self.assertFalse(plan.production_ready)
        self.assertFalse(plan.commercial_ready)
        self.assertFalse(plan.all_applicable_predicates_closed)

    def test_all_applicable_closed_can_reach_production_and_commercial_ready(self):
        from federation.formation_infinity_production_v1 import PRODUCT_PREDICATE_IDS
        rows=[
            ProductionPredicate(pid,PredicateState.CLOSED,(f"proof:{pid}",))
            for pid in PRODUCT_PREDICATE_IDS
        ]
        plan=self.compiler.compile(
            mission_id="MISSION-PRODUCTION-CLOSURE",
            services=FUSE_ECOSYSTEM_SERVICES,
            predicates=rows,
        )
        self.assertTrue(plan.production_ready)
        self.assertTrue(plan.commercial_ready)
        self.assertEqual(plan.active_logical_agent_slots,0)

    def test_held_predicate_requires_exact_blocker(self):
        with self.assertRaises(ValueError):
            self.compiler.compile(
                mission_id="M",
                services=FUSE_ECOSYSTEM_SERVICES,
                predicates=[ProductionPredicate("SOURCE_ADMITTED",PredicateState.HELD)],
            )


if __name__=="__main__":
    unittest.main()
