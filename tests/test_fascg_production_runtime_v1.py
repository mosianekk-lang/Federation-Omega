from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import GeneDomain
from benchmarking.cfbe_omega.fascg_production_runtime_v1 import *
from federation.fascg_provider_fabric_v1 import CURRENT_PROVIDER_BRIDGES, ProviderRouteSelector, provider_fabric_manifest


class ProductionRuntimeCourt(unittest.TestCase):
    def test_truth_flags_fail_closed(self):
        self.assertFalse(PROVIDER_EFFECT_AUTHORIZED)
        self.assertFalse(AUTHORITY_MINTING_AUTHORIZED)
        self.assertFalse(MODEL_TRAINING_AUTHORIZED)
        self.assertFalse(PRODUCTION_SELF_MUTATION_AUTHORIZED)
        self.assertFalse(TEN_X_VERIFIED)

    def test_state_version_chain(self):
        g = CognitiveStateVersionGraph()
        g = g.append(mission_id="m", state_kind="A", source_sha="s1", payload={"x":1}, proof_refs=("p1",))
        g = g.append(mission_id="m", state_kind="B", source_sha="s1", payload={"x":2}, proof_refs=("p2",))
        self.assertTrue(g.validate_chain())
        self.assertEqual(g.versions[1].previous_version_id, g.versions[0].version_id)

    def test_resume_rejects_source_drift(self):
        g = CognitiveStateVersionGraph().append(mission_id="m", state_kind="A", source_sha="s1", payload={"x":1}, proof_refs=("p",))
        cp = RuntimeCheckpoint("cp","m","s1","t1",g.versions[0].version_id,("a",),("b",),("p",))
        r = RuntimeResumeCourt.evaluate(cp, current_source_sha="s2", current_topology_sha256="t1", state_graph=g)
        self.assertEqual(r.status, "RESUME_HELD")
        self.assertIn("SOURCE_DRIFT", r.blockers)

    def test_resume_accepts_exact_checkpoint(self):
        g = CognitiveStateVersionGraph().append(mission_id="m", state_kind="A", source_sha="s1", payload={"x":1}, proof_refs=("p",))
        cp = RuntimeCheckpoint("cp","m","s1","t1",g.versions[0].version_id,("a",),("b",),("p",))
        r = RuntimeResumeCourt.evaluate(cp, current_source_sha="s1", current_topology_sha256="t1", state_graph=g)
        self.assertEqual(r.status, "RESUME_ALLOWED")

    def test_failure_eval_factory_clusters(self):
        rows = (
            FailureObservation("f1","tool","fp","i1","NO_UNSAFE_CALL","unsafe","p1",.8),
            FailureObservation("f2","tool","fp","i2","NO_UNSAFE_CALL","unsafe2","p2",.7),
        )
        cases = FailureEvalFactory.synthesize(rows)
        self.assertEqual(len(cases), 1)
        self.assertTrue(cases[0].held_out)
        self.assertEqual(set(cases[0].source_failure_ids), {"f1","f2"})

    def test_evolution_never_self_promotes_production(self):
        c = EvolutionCandidate("c","p","n","mut",("m",),("e",),("v1","v2"),
                               {"alt_model":.9,"adjacent":.85},{"cap1":.98,"cap2":.96},"rb",True)
        r = EvolutionPromotionCourt().evaluate(c)
        self.assertEqual(r.status, "SHADOW_ELIGIBLE")

    def test_forgetting_blocks_evolution(self):
        c = EvolutionCandidate("c","p","n","mut",("m",),("e",),("v1","v2"),
                               {"alt_model":.9},{"cap1":.90},"rb",True)
        r = EvolutionPromotionCourt().evaluate(c)
        self.assertEqual(r.status, "SANDBOX_REJECTED")
        self.assertIn("CATASTROPHIC_FORGETTING_RISK", r.blockers)

    def test_provider_stage_requires_native_readback(self):
        row = PromotionEvidence(ProductionStage.PROVIDER_BOUND,"sha",("p",),("v",),False,True,.99,.99,.8)
        r = ProductionPromotionCourt().evaluate((row,))
        self.assertEqual(r.achieved_stage, ProductionStage.SOURCE_READY)
        self.assertIn("PROVIDER_READBACK_REQUIRED:PROVIDER_BOUND", r.blockers)

    def test_sustained_value_requires_windows(self):
        row = PromotionEvidence(ProductionStage.SUSTAINED_VALUE,"sha",("p",),("v",),True,True,.99,.99,.9,2)
        r = ProductionPromotionCourt().evaluate((row,))
        self.assertIn("SUSTAINED_WINDOWS_REQUIRED", r.blockers)

    def test_cold_slate_provider_compiler(self):
        passports = tuple(b.passport() for b in CURRENT_PROVIDER_BRIDGES)
        spec = ColdSlateDeploymentSpec("d","m",(GeneDomain.DURABILITY_INTEROP,),
                                       ("hosted_shadow","google_cloud_readback"),
                                       (ProviderSurface.GITHUB_HOSTED,ProviderSurface.GOOGLE_CLOUD),"A1")
        p = ColdSlateDeploymentCompiler().compile(spec, passports)
        self.assertFalse(p.external_effect_authorized)
        self.assertFalse(p.uncovered_capabilities)

    def test_provider_route_selector_reuses_existing_bridges(self):
        rows = ProviderRouteSelector().choose(("google_cloud_readback","cloud_run_state"), preferred_surfaces=(ProviderSurface.GOOGLE_CLOUD,))
        self.assertTrue(rows)
        self.assertEqual(rows[0].bridge_id, "GOOGLE-CLOUD-CURRENTNESS")
        self.assertTrue(rows[0].provider_native_readback)

    def test_provider_fabric_is_effect_none(self):
        m = provider_fabric_manifest()
        self.assertFalse(m["external_effects"])
        self.assertFalse(m["authority_minting"])
        self.assertGreaterEqual(len(m["bridges"]), 5)


if __name__ == "__main__":
    unittest.main()
