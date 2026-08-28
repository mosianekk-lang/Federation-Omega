from __future__ import annotations
import unittest
from federation.living_state.future_intelligence import *
from federation.living_state.world_model import *
NOW="2026-08-28T06:00:00+00:00"
def model():
    m=LivingWorldModel(); p=Provenance("s","p",NOW,ProofMaturity.DETERMINISTIC_TESTED,3600,.9)
    for n in (WorldNode("provider:P",NodeKind.PROVIDER,"P","READY",{},p),WorldNode("capability:C",NodeKind.CAPABILITY,"C","ACTIVE",{},p),WorldNode("capability:OLD",NodeKind.CAPABILITY,"OLD","DEPRECATED",{},p),WorldNode("mission:M",NodeKind.MISSION,"M","ACTIVE",{},p)): m.observe_node(n)
    m.observe_edge(WorldEdge("e1","capability:C","provider:P",EdgeKind.DEPENDS_ON,p)); m.observe_edge(WorldEdge("e2","mission:M","capability:C",EdgeKind.DEPENDS_ON,p))
    for i in range(3): m.observe_route_telemetry(RouteTelemetry("R","M",NOW,True,10,.1,.1,.9,.9,.1,("FD",),f"r{i}"))
    return m
class FutureTests(unittest.TestCase):
    def test_scenario_is_topology_simulation(self):
        r=FederationFutureIntelligence(model()).scenario_ensemble((ScenarioShock("S","provider:P","DOWN",.5,.8,"p"),))[0]; self.assertIn("mission:M",r.impacted_missions); self.assertFalse(r.causal_claim)
    def test_missing_scenario_node_fails(self):
        with self.assertRaises(Exception): FederationFutureIntelligence(model()).scenario_ensemble((ScenarioShock("S","missing","DOWN",.5,.8,"p"),))
    def test_stress_ranks_provider(self): self.assertEqual(FederationFutureIntelligence(model()).shared_dependency_stress()[0]["node_id"],"provider:P")
    def test_experiment_rejects_external_effect(self):
        d=FederationFutureIntelligence(model()).design_experiment((ExperimentCandidate("A","h","provider:P",.8,.9,1,.8,.1,.1,"p"),ExperimentCandidate("B","h","provider:P",1,1,.1,.9,.9,.9,"p",True))); self.assertEqual(d.selected_experiment_id,"A"); self.assertIn("B",d.rejected)
    def test_all_effectful_experiments_hold(self):
        d=FederationFutureIntelligence(model()).design_experiment((ExperimentCandidate("B","h","provider:P",1,1,.1,.9,.9,.9,"p",True),)); self.assertEqual(d.disposition,"HOLD_FOR_SEPARATE_EFFECT_ADMISSION")
    def test_state_explanation_contains_lineage(self): self.assertTrue(FederationFutureIntelligence(model()).explain_state("provider:P",now=NOW)["event_lineage"])
    def test_route_explanation_contains_penalties(self): self.assertIn("risk",FederationFutureIntelligence(model()).explain_route("R")["penalties"])
    def test_retirement_is_archive_first(self):
        p=FederationFutureIntelligence(model()).retirement_proposals(now=NOW); old=next(x for x in p if x.node_id=="capability:OLD"); self.assertTrue(old.archive_required); self.assertFalse(old.deletion_permitted)
    def test_active_capability_not_retired(self): self.assertNotIn("capability:C",{x.node_id for x in FederationFutureIntelligence(model()).retirement_proposals(now=NOW)})
    def test_canary(self):
        r=run_future_intelligence_canary(); self.assertEqual(r["status"],"PASS"); self.assertEqual(r["count"],12); self.assertTrue(all(r["checks"].values())); self.assertEqual(r["external_effects"],0)
if __name__=="__main__": unittest.main()
