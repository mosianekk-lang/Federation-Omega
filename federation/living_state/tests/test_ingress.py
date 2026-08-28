from __future__ import annotations
from pathlib import Path
import tempfile, unittest
from federation.living_state.ingress import *
from federation.living_state.store import LivingStateStore
from federation.living_state.world_model import FabricError, NodeKind, ProofMaturity
NOW="2026-08-28T06:00:00+00:00"
def env(eid="evt:1",state="READY",payload=None,sensitivity="PUBLIC_SAFE"):
    return IngressEnvelope(eid,"NODE_STATE","sensor",NOW,"proof",ProofMaturity.PROVIDER_READBACK,"provider:P",NodeKind.PROVIDER.value,state,payload or {"label":"P"},sensitivity=sensitivity)
class IngressTests(unittest.TestCase):
    def test_apply_and_idempotent_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td)/"s.db") as s:
                i=LivingStateIngress(s); a=i.ingest(env()); b=i.ingest(env()); self.assertEqual(a.disposition,"APPLIED"); self.assertEqual(b.disposition,"DUPLICATE_IDEMPOTENT"); self.assertEqual(s.restore().event_count,1)
    def test_conflicting_event_reuse_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td)/"s.db") as s:
                i=LivingStateIngress(s); i.ingest(env());
                with self.assertRaises(FabricError): i.ingest(env(state="DOWN"))
    def test_public_secret_shape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td)/"s.db") as s:
                with self.assertRaises(FabricError): LivingStateIngress(s).ingest(env(payload={"password":"secret"}))
    def test_private_local_requires_explicit_admission(self):
        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td)/"s.db") as s:
                with self.assertRaises(FabricError): LivingStateIngress(s).ingest(env(sensitivity="PRIVATE_LOCAL"))
    def test_private_local_receipt_never_returns_payload(self):
        with tempfile.TemporaryDirectory() as td:
            with LivingStateStore(Path(td)/"s.db") as s:
                r=LivingStateIngress(s,allow_private_local=True).ingest(env(sensitivity="PRIVATE_LOCAL")); self.assertFalse(r.private_payload_returned)
    def test_canary(self):
        r=run_ingress_canary(); self.assertEqual(r["status"],"PASS"); self.assertEqual(r["count"],7); self.assertTrue(all(r["checks"].values())); self.assertEqual(r["external_effects"],0)
if __name__=="__main__": unittest.main()
