from __future__ import annotations
import unittest
from ops.sovara_ao5_full_v2.ao5_full_engine import *

class AO5ZeroDilutionTests(unittest.TestCase):
    def setUp(self): self.a=AO5()
    def test_source_hash(self): self.assertEqual(SOURCE_SHA256,"e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f")
    def test_coverage(self):
        g=coverage_gate(); self.assertTrue(g["complete"]); self.assertEqual((g["sections"],g["roman_parts"]),(55,54))
        for p,m in COVERAGE.items(): self.assertTrue(hasattr(AO5,m),p)
    def test_part0(self): self.assertEqual(len(self.a.registers),19)
    def test_partI(self): self.assertTrue(self.a.partI())
    def test_partII(self):
        with self.assertRaises(ValueError): self.a.partII("S11_EXECUTION")
        self.a.partXV({}); self.a.partII("S11_EXECUTION")
        with self.assertRaises(ValueError): self.a.partII("S21_RELEASE")
        self.a.release_gates={k:True for k in self.a.release_gates}; self.a.partII("S21_RELEASE")
    def test_partIII(self):
        with self.assertRaises(ValueError): self.a.partIII("C2_TOOL_BOUND","C4_PROVIDER_VERIFIED")
    def test_partIV(self): self.assertEqual(self.a.partIV(({"id":"B","date":"2","proof":"VERIFIED"},{"id":"A","date":"1","proof":"VERIFIED"}))["id"],"A")
    def test_partV(self): self.assertIn("O",self.a.partV(({"id":"O","class":"PRIMARY"},)))
    def test_partVI(self): self.assertIn("R",self.a.partVI(set(),{"R"})["gaps"])
    def test_partVII(self): self.assertTrue(self.a.partVII({"A":"SOURCE_NODE","B":"FACT_NODE"},(("A","SUPPORTS","B"),)))
    def test_partVIII(self): self.assertEqual(self.a.partVIII({"A":{"X"},"B":{"X"}})["X"],("A","B"))
    def test_partIX(self): self.assertEqual(len(self.a.partIX(({"id":"P","class":"PRIMARY"},))),1)
    def test_partX(self):
        r=self.a.partX(tuple({"id":f"P{i}","class":"PRIMARY"} for i in range(8))); self.assertEqual((len(r["ACTIVE"]),len(r["SHADOW"]),len(r["ARCHIVED"])),(3,3,2))
    def test_partXI(self): self.assertEqual(self.a.partXI(("ST-01","ST-30")),("ST-01","ST-30"))
    def test_partXII(self): self.assertTrue(self.a.partXII(())["SYNCHRONISATION"])
    def test_partXIII(self): self.assertEqual(self.a.partXIII(({"stream":"ST-01","facts":(),"inferences":("X",)},),("X",)),("ST-01:X",))
    def test_partXIV(self): self.assertEqual(self.a.partXIV({"pages":31})["action"],"LANE_SPLIT")
    def test_partXV(self): self.assertTrue(self.a.partXV({"page_count":51})["auto_decompose"])
    def test_partXVI(self): self.assertEqual(self.a.partXVI({k:True for k in ("sources","propositions","contradictions","adverse","countercase","low_marginal_value")}),"CONVERGED")
    def test_partXVII(self):
        d={k:.8 for k in ("authenticity","proximity","contemporaneity","independence","completeness","specificity","consistency","chain_of_custody","admissibility_or_usability","decision_relevance")}; self.assertEqual(len(self.a.partXVII(**d)),10)
    def test_partXVIII(self):
        d={"source":.9,"fact":.95,"temporal":.8,"actor_knowledge":.4,"authority":.7,"causal":.2,"legal_fit":.8,"policy_fit":.8,"theory":.6,"remedy":.5}; self.assertGreater(self.a.partXVIII(**d)["fact"],d["causal"])
    def test_partXIX(self): self.assertEqual(self.a.partXIX()[-1],"CLASSIFY SOURCE PRECEDENCE")
    def test_partXX(self): self.assertEqual(self.a.partXX(("A","A","B"))["independent_source_count"],2)
    def test_partXXI(self):
        r=({"id":"A","information_gain":1,"decision_value":1,"source_quality":1,"cost":1},{"id":"B","information_gain":.1,"decision_value":1,"source_quality":1,"cost":1}); self.assertEqual(self.a.partXXI(r)[0],"A")
    def test_partXXII(self): self.assertEqual(self.a.partXXII(({"id":"A","documents":("a",)},{"id":"B","documents":("b",)}))["A"],("a",))
    def test_partXXIII(self):
        self.assertEqual(self.a.partXXIII("APPROVED","S")["state"],"APPROVED")
        with self.assertRaises(ValueError): self.a.partXXIII("ACTIVE","")
    def test_partXXIV(self): self.assertEqual(self.a.partXXIV((1,6,2)),6)
    def test_partXXV(self): self.assertEqual(self.a.partXXV({"a":1,"b":1}),"CG-5")
    def test_partXXVI(self): self.assertEqual(self.a.partXXVI({"CH-CAUSATION":False})["CH-CAUSATION"],"REPAIR")
    def test_partXXVII(self): self.assertEqual(self.a.partXXVII({x:.9 for x in COUNCIL}),"Ω-A")
    def test_partXXVIII(self): self.assertTrue(self.a.partXXVIII("S",("f",),("c",),("p",),("w",))["id"].startswith("PREMORTEM"))
    def test_partXXIX(self): self.assertEqual(self.a.partXXIX(result="R")["result"],"R")
    def test_partXXX(self):
        self.a.partXXX({"id":"D","version":1}); self.assertEqual(len(self.a.partXXX({"id":"D","version":2})),2)
        with self.assertRaises(ValueError): self.a.partXXX({"id":"D","version":4})
    def test_partXXXI(self): self.assertEqual(self.a.partXXXI(({"conclusion":"c","theory":"t","element":"e","fact":"f","proposition":"p","source":"s"},)),"DURABLY_VERIFIED")
    def test_partXXXII(self): self.assertIn("NOT_PERSONALITY",self.a.partXXXII({})["rule"])
    def test_partXXXIII(self): self.assertFalse(self.a.partXXXIII("FAST","VERIFIED","x")["final"])
    def test_partXXXIV(self): self.assertEqual(self.a.partXXXIV({"owner_wait_signal":True})[0],"STOP_EXPANSION")
    def test_partXXXV(self): self.assertEqual(self.a.partXXXV({"path_explosion":True})["state"],"YELLOW")
    def test_partXXXVI(self):
        p={k:() for k in ("ALPHA_NODES","OMEGA_PORTFOLIO","ACTIVE_PATHS","SHADOW_PATHS","PRUNED_PATHS","ACTIVE_STREAMS","COMPLETED_LANES","VERIFIED_FACTS","SUPPORTED_INFERENCES","ADVERSE_EVIDENCE","CONTRADICTIONS","GAP_STATE","THEORY_VERSIONS","DECISION_VERSIONS","FAILURE_STATE","METHOD_STATE")}
        p.update({"HANDOFF_ID":"H","PROJECT_ID":"P","WORKSTREAM_ID":"W","CURRENT_STATE_MACHINE_STATE":"S","CURRENT_LANE":"L","SOURCE_STATE":"S","KNOWLEDGE_STATE":"K","LAST_VERIFIED_SOURCE":"S","NEXT_EXACT_ACTION":"N","RESTORE_COMMAND":"R"}); self.assertTrue(self.a.partXXXVI(p)["valid"])
    def test_partXXXVII(self): self.assertEqual(self.a.partXXXVII({"class":"TOOL_ROUTE","repair":"x","regression":True})["promotion"],"CAPABILITY")
    def test_partXXXVIII(self): self.assertTrue(self.a.partXXXVIII(why_owner_detected_first="x",signal_available="s",why_control_failed="f",detector_should_have_fired="d",universal_prevention=True))
    def test_partXXXIX(self): self.assertEqual(self.a.partXXXIX("x","c")["action"],"LEARN_BEFORE_FAILURE")
    def test_partXL(self): self.assertEqual(self.a.partXL(3),"REDESIGN_OR_ROLLBACK")
    def test_partXLI(self): self.assertEqual(self.a.partXLI()["studies"],"METHOD_NOT_CASE_MERITS")
    def test_partXLII(self):
        e={k:1 for k in ("experiment_id","question","existing_method","candidate_method","hypothesis","test","control","accuracy","source_fidelity","decision_value","information_gain","latency","tool_cost","owner_load","failure_rate","context_cost","regression_result","promotion_state")}; self.assertTrue(self.a.partXLII(e))
    def test_partXLIII(self): self.assertTrue(self.a.partXLIII({"accuracy":1},{}))
    def test_partXLIV(self):
        self.assertTrue(self.a.partXLIV("routing"))
        with self.assertRaises(ValueError): self.a.partXLIV("immutable kernel")
    def test_partXLV(self): self.assertIn("MAY->DID",self.a.partXLV((("MAY","DID"),)))
    def test_partXLVI(self): self.assertTrue(self.a.partXLVI("mind-reading").startswith("BLOCK"))
    def test_partXLVII(self): self.assertTrue(self.a.partXLVII({"AUTHORISED":True,"EXECUTED":True,"TARGET":"T","RESULT":"R","READBACK":"RB","FAILURE":""})["COMPLETE"])
    def test_partXLVIII(self): self.assertTrue(self.a.partXLVIII(True,"ALT",True,True,True)["continued"])
    def test_partXLIX(self): self.assertEqual(self.a.partXLIX({x:1 for x in OUTPUT_FIELDS[:-1]}),())
    def test_partL(self): self.assertFalse(self.a.partL()["owner_default_qa"])
    def test_partLI(self): self.assertTrue(self.a.partLI("n").startswith("NEXT_HIGHEST"))
    def test_partLII(self): self.assertGreaterEqual(len(self.a.partLII()),30)
    def test_partLIII(self): self.assertTrue(all(self.a.partLIII().values()))
    def test_partLIV(self): self.assertTrue(self.a.partLIV({x:True for x in PERFORMANCE})["passed"])
    def test_canary(self):
        r=canary(); self.assertEqual(r["status"],"PASS"); self.assertTrue(all(r["checks"].values())); self.assertEqual(r["external_effects"],0)
    def test_zero_dilution_gate(self):
        self.assertTrue(zero_dilution_verdict(True,True)["local_eligible"])
        self.assertFalse(zero_dilution_verdict(True,True)["verified"])
        self.assertTrue(zero_dilution_verdict(True,True,True,True)["verified"])

if __name__=="__main__": unittest.main()
