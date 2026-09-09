from __future__ import annotations
import unittest
from benchmarking.cfbe_omega.fuse_autopilot_sentinel_bridge_v1 import CURRENT_BINDINGS, FuseAutopilotSentinelBridge, integration_manifest
from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import AutonomyContext, InterventionCandidate, MissionHomeostasisState, SensingCandidate

class A:
    def mission_state(self,mission_id): return {"objective":"keep mission healthy","authority_ceiling":"A1_INTERNAL","data_boundary":"PRIVATE"}
class S:
    def observations(self,mission_id): return ({"id":"o1","severity":.3},)
class E:
    def evolution_state(self,mission_id): return {"generation":1,"state":"OPEN"}
class P:
    def proof_refs(self,mission_id): return ("proof-1","proof-2")
class EmptyA:
    def mission_state(self,mission_id): return {}


def state(): return MissionHomeostasisState(.95,.97,.96,.9,.1,.2,.2,.1,.2,.1,.8,.9)
def autonomy(): return AutonomyContext("NO_EFFECT",True,True,.9,.1,.1,.1,True)

class BridgeTests(unittest.TestCase):
    def test_eight_bindings(self): self.assertEqual(8,len(CURRENT_BINDINGS))
    def test_manifest_hash(self): self.assertEqual(64,len(integration_manifest()["sha256"]))
    def test_manifest_effect_false(self): self.assertFalse(integration_manifest()["external_effects"])
    def test_manifest_authority_false(self): self.assertFalse(integration_manifest()["authority_minting"])
    def test_autopilot_binding(self): self.assertTrue(any("federation_autopilot_metacognition_v1" in b.module_path for b in CURRENT_BINDINGS))
    def test_sentinel_binding(self): self.assertTrue(any("sentinel_omega.observability_causal_fabric" in b.module_path for b in CURRENT_BINDINGS))
    def test_aocef_binding(self): self.assertTrue(any("cognitive_evolution_v1" in b.module_path for b in CURRENT_BINDINGS))
    def test_multistream_binding(self): self.assertTrue(any("multistream" in b.module_path for b in CURRENT_BINDINGS))
    def test_internal_cycle(self):
        b=FuseAutopilotSentinelBridge(A(),S(),E(),P())
        r=b.run_internal_cycle("m",state=state(),signal_texts=["agent threat identity cloud"],sensing_candidates=[SensingCandidate("sense","h",.7,.1,.1,0,0)],intervention_candidates=[InterventionCandidate("sim","svc",.7,.1,.1,.2,True,True,("proof-1",))],autonomy_context=autonomy())
        self.assertEqual("m",r.mission_id); self.assertFalse(r.external_effect_authorized); self.assertTrue(r.sentinel_cells); self.assertEqual("sense",r.best_sensing_id); self.assertEqual("sim",r.intervention_simulation_id)
    def test_current_receiver_state_required(self):
        b=FuseAutopilotSentinelBridge(EmptyA(),S(),E(),P())
        with self.assertRaises(ValueError): b.run_internal_cycle("m",state=state(),signal_texts=["threat"],sensing_candidates=[],intervention_candidates=[],autonomy_context=autonomy())
    def test_receipt_hash(self):
        b=FuseAutopilotSentinelBridge(A(),S(),E(),P()); r=b.run_internal_cycle("m",state=state(),signal_texts=["threat"],sensing_candidates=[],intervention_candidates=[],autonomy_context=autonomy()); self.assertEqual(64,len(r.receipt_sha256))
