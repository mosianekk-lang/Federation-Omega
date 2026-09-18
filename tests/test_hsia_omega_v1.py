import unittest
from benchmarking.cfbe_omega.hsia_omega_v1 import *

def item(i,mechanism="adaptive semantic route selection with proof gating",required=("routing","proof"),rights=Rights.CLEAR,vendor=(),corpus="ALGORITHM"):
    return IntelligenceItem(i,corpus,i,mechanism,"current evidence selects and verifies the mechanism",(f"src:{i}",),("routing","proof"),vendor,required,rights,.9)

class TestHSIA(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(100,DAILY_TARGET); self.assertEqual(4,len(CORPORA)); self.assertEqual(5,len(FIVE_D))
    def test_delta(self):
        x=item("A"); self.assertEqual((),changed((x,),{"A":fingerprint(x)}))
    def test_clean_room(self):
        h=harvest(item("B","VendorX adaptive route proof",vendor=("VendorX",))); self.assertNotIn("VendorX",h["mechanism"]); self.assertIn("provider",h["mechanism"])
    def test_reuse(self):
        h=harvest(item("C")); e=(EstateCapability("CAP",("adaptive","semantic","route","selection","proof","gating","routing"),("routing","proof")),); self.assertEqual(Disposition.REUSE,classify(h,e).disposition)
    def test_partial_before_build(self):
        h=harvest(item("D","durable routing proof recovery",("routing","proof","recovery"))); e=(EstateCapability("A",("durable","routing"),("routing",)),EstateCapability("B",("proof","recovery"),("proof","recovery"))); self.assertNotEqual(Disposition.BUILD_RESIDUAL,classify(h,e).disposition)
    def test_residual(self):
        h=harvest(item("E","quantum harmonization lattice",("quantum_lattice","harmonizer"))); e=(EstateCapability("X",("routing","proof"),("routing",)),); self.assertEqual(Disposition.BUILD_RESIDUAL,classify(h,e).disposition)
    def test_rights(self):
        self.assertEqual(Disposition.REJECT,classify(harvest(item("F",rights=Rights.RESTRICTED)),()).disposition)
    def test_gap_mission_and_no_effect(self):
        r=compile_daily(items=(item("G","novel recovery mesh",("recovery_mesh","fencing")),),estate=(),target=1); self.assertEqual(1,len(r.missions)); self.assertFalse(r.external_effect_authorized); self.assertTrue(r.missions[0]["source_serialized_by_fdof"])
    def test_propagation_gate(self):
        d=classify(harvest(item("H")),()); self.assertEqual((),propagation_targets(decision=d,proof=Proof.SHADOW,rights=Rights.CLEAR)); self.assertTrue(propagation_targets(decision=d,proof=Proof.RECEIVER,rights=Rights.CLEAR))
    def test_deterministic(self):
        x=item("I"); self.assertEqual(compile_daily(items=(x,),estate=(),target=1).receipt_sha256,compile_daily(items=(x,),estate=(),target=1).receipt_sha256)

if __name__=="__main__": unittest.main()
