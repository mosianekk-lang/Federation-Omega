import os,tempfile,unittest
from bubbles.federation_cognitive_runtime_omega5 import AdaptiveCognitiveRuntime,NodeState

class Omega5Tests(unittest.TestCase):
    def setUp(self): self.t=tempfile.TemporaryDirectory(); self.r=AdaptiveCognitiveRuntime(os.path.join(self.t.name,"g.sqlite3"),os.path.join(self.t.name,"l.sqlite3"))
    def tearDown(self): self.r.close(); self.t.cleanup()
    def _graph(self):
        g=self.r.graph; g.upsert_node("TUT","S_POLICY","SOURCE","TUT disciplinary policy",NodeState.VERIFIED.value,"v1","drive:policy"); g.upsert_node("TUT","F_STEP","FACT","Step-1 procedural history",NodeState.VERIFIED.value); g.upsert_node("TUT","C_FAIR","CLAIM","Procedural fairness assessment",NodeState.VERIFIED.value); g.add_edge("TUT","S_POLICY","SUPPORTS","F_STEP"); g.add_edge("TUT","F_STEP","SUPPORTS","C_FAIR")
    def test_invalidation_propagates_only_dependency_branch(self):
        self._graph(); x=self.r.graph.invalidate_version("TUT","S_POLICY","v2"); self.assertEqual({"F_STEP","C_FAIR"},set(x["affected"])); self.assertEqual("REVALIDATION_REQUIRED",self.r.graph.node("TUT","C_FAIR")["state"])
    def test_matter_wall_blocks_missing_cross_project_endpoint(self):
        self._graph(); self.r.graph.upsert_node("BUSINESS","B1","FACT","business fact")
        with self.assertRaises(KeyError): self.r.graph.add_edge("TUT","S_POLICY","SUPPORTS","B1")
    def test_predictive_retrieval_is_pointer_only(self):
        self._graph(); p=self.r.retrieval.plan("TUT","disciplinary policy and procedural fairness",["S_POLICY"]); self.assertEqual("drive:policy",p["immediate"][0]["source_pointer"]); self.assertNotIn("content",p["immediate"][0])
    def test_scheduler_and_convergence(self):
        missions=[{"mission_id":"A","project_id":"TUT","objective":"Review grievance step one procedure","urgency":3,"proof_gain":3,"unblock_impact":3,"user_value":3,"reuse_value":2,"latency_cost":1,"risk":1,"dependency_cost":1,"evidence_nodes":["S_POLICY"]},{"mission_id":"B","project_id":"TUT","objective":"Assess grievance step one procedural fairness","urgency":2,"proof_gain":2,"unblock_impact":2,"user_value":2,"reuse_value":2,"latency_cost":1,"risk":1,"dependency_cost":1,"evidence_nodes":["S_POLICY"]},{"mission_id":"C","project_id":"BUSINESS","objective":"Assess business margin","urgency":1,"proof_gain":1,"unblock_impact":1,"user_value":1,"reuse_value":1,"latency_cost":3,"risk":2,"dependency_cost":2,"evidence_nodes":[]}]
        rank=self.r.scheduler.rank(missions); self.assertEqual("A",rank[0]["mission_id"]); conv=self.r.convergence.candidates(missions,threshold=0.4); self.assertTrue(any(x["a"]=="A" and x["b"]=="B" for x in conv)); self.assertFalse(any(set([x["a"],x["b"]])==set(["A","C"]) for x in conv))
    def test_repair_learning_changes_order(self):
        self.r.repairs.record("NO_SEARCH_DELTA","metadata_lookup",True,100); self.r.repairs.record("NO_SEARCH_DELTA","metadata_lookup",True,120); self.assertEqual("metadata_lookup",self.r.repairs.rank("NO_SEARCH_DELTA")[0]["strategy"])
    def test_digital_twin_is_read_only(self):
        self._graph(); x=self.r.twin.simulate_source_stale("TUT","S_POLICY"); self.assertFalse(x["mutation_performed"]); self.assertIn("C_FAIR",x["affected_nodes"]); self.assertEqual("VERIFIED",self.r.graph.node("TUT","C_FAIR")["state"])

if __name__=="__main__": unittest.main()
