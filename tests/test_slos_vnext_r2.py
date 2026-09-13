import unittest

from superior_logic.acceptance_integrity import AcceptanceDomain, AcceptanceIntegrityCourt, AcceptanceWitness
from superior_logic.engineering_operator import SLOSEngineeringOperator
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
    def _witness(self, witness_id, domain, actor, passed=True, relation="INDEPENDENT", trust_domain=None):
        return AcceptanceWitness(
            witness_id=witness_id,
            domain=domain,
            actor_id=actor,
            trust_domain=trust_domain or f"trust-{actor}",
            passed=passed,
            evidence_refs=(f"proof:{witness_id}",) if passed else (),
            relation_to_implementation=relation,
        )

    def test_implementation_lane_cannot_self_accept(self):
        verdict = AcceptanceIntegrityCourt().evaluate(
            implementation_actor_id="impl",
            implementation_trust_domain="trust-impl",
            witnesses=(
                self._witness("t", AcceptanceDomain.TEST, "impl"),
                self._witness("p", AcceptanceDomain.PROOF, "proof"),
                self._witness("r", AcceptanceDomain.READBACK, "readback"),
            ),
        )
        self.assertFalse(verdict.accepted)
        self.assertIn("TEST", verdict.missing_domains)
        self.assertIn("t", verdict.non_independent_witnesses)
        self.assertFalse(verdict.effect_authority_granted)

    def test_same_trust_domain_aliases_cannot_self_accept(self):
        verdict = AcceptanceIntegrityCourt().evaluate(
            implementation_actor_id="impl",
            implementation_trust_domain="lane-a",
            witnesses=(
                self._witness("t", AcceptanceDomain.TEST, "tester-alias", trust_domain="lane-a"),
                self._witness("p", AcceptanceDomain.PROOF, "proof-alias", trust_domain="lane-a"),
                self._witness("r", AcceptanceDomain.READBACK, "readback-alias", trust_domain="lane-a"),
            ),
        )
        self.assertFalse(verdict.accepted)
        self.assertEqual(set(verdict.missing_domains), {"TEST", "PROOF", "READBACK"})
        self.assertEqual(set(verdict.non_independent_witnesses), {"t", "p", "r"})
        self.assertEqual(verdict.independent_trust_domains, ())

    def test_implementation_trust_domain_is_required(self):
        with self.assertRaisesRegex(ValueError, "IMPLEMENTATION_TRUST_DOMAIN_REQUIRED"):
            AcceptanceIntegrityCourt().evaluate(
                implementation_actor_id="impl",
                implementation_trust_domain="",
                witnesses=(),
            )

    def test_independent_domains_pass(self):
        verdict = AcceptanceIntegrityCourt().evaluate(
            implementation_actor_id="impl",
            implementation_trust_domain="trust-impl",
            witnesses=(
                self._witness("t", AcceptanceDomain.TEST, "tester"),
                self._witness("p", AcceptanceDomain.PROOF, "proof"),
                self._witness("r", AcceptanceDomain.READBACK, "readback"),
            ),
        )
        self.assertTrue(verdict.accepted)
        self.assertEqual(verdict.status, "ACCEPTANCE_INTEGRITY_PASSED")
        self.assertEqual(
            set(verdict.independent_trust_domains),
            {"trust-tester", "trust-proof", "trust-readback"},
        )
        self.assertFalse(verdict.effect_authority_granted)

    def test_operator_binds_implementation_trust_domain(self):
        request = {
            "implementation_actor_id": "impl",
            "implementation_trust_domain": "lane-impl",
            "witnesses": [
                {
                    "witness_id": "t",
                    "domain": "TEST",
                    "actor_id": "tester",
                    "trust_domain": "lane-test",
                    "passed": True,
                    "evidence_refs": ["proof:t"],
                },
                {
                    "witness_id": "p",
                    "domain": "PROOF",
                    "actor_id": "proof",
                    "trust_domain": "lane-proof",
                    "passed": True,
                    "evidence_refs": ["proof:p"],
                },
                {
                    "witness_id": "r",
                    "domain": "READBACK",
                    "actor_id": "readback",
                    "trust_domain": "lane-readback",
                    "passed": True,
                    "evidence_refs": ["proof:r"],
                },
            ],
        }
        receipt = SLOSEngineeringOperator().assess_acceptance(request)
        self.assertEqual(receipt.status, "ACCEPTANCE_INTEGRITY_PASSED")
        self.assertFalse(receipt.payload["effect_authority_granted"])


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
