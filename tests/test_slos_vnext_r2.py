import unittest

from superior_logic.acceptance_integrity import AcceptanceDomain, AcceptanceIntegrityCourt, AcceptanceWitness
from superior_logic.evolution_lab import EvolutionLab
from superior_logic.finalization_kernel import FinalizationDirective, SLOSFinalizationKernel
from superior_logic.harness_tournament import HarnessGenome
from superior_logic.opportunity_adapter import EngineeringOpportunityAdapter, EngineeringShape, MissionProfile


class OpportunityAdapterTests(unittest.TestCase):
    def test_small_known_change_is_direct(self):
        verdict = EngineeringOpportunityAdapter().choose_shape(
            MissionProfile(
                mission_id="m-direct",
                changed_paths=("superior_logic/x.py",),
                subsystems=("SUPERIOR_LOGIC",),
                risk="LOW",
                unknown_count=0,
                estimated_tasks=1,
                external_effects=False,
            )
        )
        self.assertEqual(verdict.shape, EngineeringShape.DIRECT)
        self.assertTrue(verdict.mutation_allowed_by_shape)

    def test_missing_external_authority_holds(self):
        verdict = EngineeringOpportunityAdapter().choose_shape(
            MissionProfile(
                mission_id="m-hold",
                changed_paths=("x.py",),
                risk="HIGH",
                external_effects=True,
                authority_ready=False,
            )
        )
        self.assertEqual(verdict.shape, EngineeringShape.HOLD)
        self.assertFalse(verdict.mutation_allowed_by_shape)

    def test_wide_mission_uses_fleet(self):
        verdict = EngineeringOpportunityAdapter().choose_shape(
            MissionProfile(
                mission_id="m-fleet",
                changed_paths=tuple(f"pkg/f{i}.py" for i in range(12)),
                subsystems=("A", "B", "C"),
                risk="HIGH",
                estimated_tasks=7,
            )
        )
        self.assertEqual(verdict.shape, EngineeringShape.FLEET)


class AcceptanceIntegrityTests(unittest.TestCase):
    def _witness(self, witness_id, domain, actor, passed=True, relation="INDEPENDENT"):
        return AcceptanceWitness(
            witness_id=witness_id,
            domain=domain,
            actor_id=actor,
            trust_domain=f"trust-{actor}",
            passed=passed,
            evidence_refs=(f"proof:{witness_id}",) if passed else (),
            relation_to_implementation=relation,
        )

    def test_implementation_lane_cannot_self_accept(self):
        verdict = AcceptanceIntegrityCourt().evaluate(
            implementation_actor_id="impl",
            witnesses=(
                self._witness("t", AcceptanceDomain.TEST, "impl"),
                self._witness("p", AcceptanceDomain.PROOF, "proof"),
                self._witness("r", AcceptanceDomain.READBACK, "readback"),
            ),
        )
        self.assertFalse(verdict.accepted)
        self.assertIn("TEST", verdict.missing_domains)
        self.assertIn("t", verdict.non_independent_witnesses)

    def test_independent_domains_pass(self):
        verdict = AcceptanceIntegrityCourt().evaluate(
            implementation_actor_id="impl",
            witnesses=(
                self._witness("t", AcceptanceDomain.TEST, "tester"),
                self._witness("p", AcceptanceDomain.PROOF, "proof"),
                self._witness("r", AcceptanceDomain.READBACK, "readback"),
            ),
        )
        self.assertTrue(verdict.accepted)
        self.assertEqual(verdict.status, "ACCEPTANCE_INTEGRITY_PASSED")


class EvolutionLabTests(unittest.TestCase):
    def baseline(self):
        return HarnessGenome.create(
            model_ref="model-a",
            aci_profile="aci-a",
            context_policy="context-a",
            skills=("skill-a",),
            tools=("tool-a",),
            workspace_policy="prepared",
            fleet_shape="PLAN_ACT",
            verifier_profile="independent",
        )

    def test_generation_is_bounded_and_excludes_baseline(self):
        baseline = self.baseline()
        variants = EvolutionLab().generate(
            baseline,
            substitutions={
                "model_ref": ("model-a", "model-b"),
                "context_policy": ("context-b",),
                "fleet_shape": ("FLEET",),
            },
            max_variants=4,
            max_changed_dimensions=2,
        )
        self.assertLessEqual(len(variants), 4)
        self.assertTrue(variants)
        self.assertTrue(all(row.genome.genome_id != baseline.genome_id for row in variants))
        batch = EvolutionLab().plan(baseline, variants)
        self.assertEqual(batch.parent_genome_id, baseline.genome_id)
        self.assertIn("INDEPENDENT_ACCEPTANCE", batch.proof_obligations)


class FinalizationShapeIntegrationTests(unittest.TestCase):
    def test_blueprint_carries_engineering_shape_without_effect(self):
        directive = FinalizationDirective(
            mission_id="shape-final",
            base_revision="abc",
            objective="improve repository intelligence",
            required_capabilities=("repository_intelligence",),
            risk="LOW",
            estimated_tasks=1,
        )
        blueprint = SLOSFinalizationKernel().compile(
            directive,
            repository_files={"superior_logic/x.py": "def repository_intelligence():\n    pass\n"},
            toolchain={"python": "3.12"},
            dependencies={},
        )
        self.assertIn(blueprint.engineering_shape, {"DIRECT", "PLAN_ACT", "FLEET", "HOLD"})
        self.assertTrue(blueprint.blueprint_sha256)


if __name__ == "__main__":
    unittest.main()
