import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from jarvis.core import CapabilityFabric, FormationKernel, LearningLedger, CircuitBreaker
from jarvis.orchestrator import Jarvis
from jarvis.principles import catalogue

class JarvisTests(unittest.TestCase):
    def test_health_and_offline_chat(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {}, clear=True):
            app=Jarvis(td); self.assertTrue(app.health()["ok"]); self.assertEqual(app.chat("map")["route"],"offline-deterministic"); self.assertTrue(app.ledger.verify())
    def test_effectful_action_fails_closed_without_permit(self):
        f,k=CapabilityFabric(),FormationKernel(); d=k.decide("M1","deploy candidate",f.get("github")); self.assertEqual(d.status,"DENY"); self.assertIn("SINGLE_USE_PERMIT_REQUIRED",d.reasons)
    def test_unknown_and_unbound_capability_denied(self):
        f,k=CapabilityFabric(),FormationKernel(); self.assertEqual(k.decide("M1","read",None).status,"DENY"); self.assertEqual(k.decide("M1","read",f.get("drive")).status,"DENY")
    def test_principle_truth_labels(self):
        rows=catalogue(); self.assertGreaterEqual(len(rows),10); self.assertTrue(all(x["kind"] and x["limit"] for x in rows))
    def test_circuit_breaker(self):
        b=CircuitBreaker(2); b.record("bad",False); self.assertNotIn("bad",b.quarantined); b.record("bad",False); self.assertIn("bad",b.quarantined)
    def test_hash_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            l=LearningLedger(Path(td)/"events.jsonl"); l.append("x","SUCCESS",1,"proof"); self.assertTrue(l.verify()); v=json.loads(l.path.read_text()); v["outcome"]="FAILURE"; l.path.write_text(json.dumps(v)+"\n"); self.assertFalse(l.verify())

if __name__ == "__main__": unittest.main()
