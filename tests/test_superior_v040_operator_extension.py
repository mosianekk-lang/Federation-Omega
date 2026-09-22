import tempfile
import unittest
from pathlib import Path

from operator_extensions.superior_v040 import ACTION, ARTIFACT_SHA256, CanaryFailure, CanaryRequest, LockedCanaryAction, ReceiptStore, install_into


class Backend:
    def __init__(self): self.deploys=0; self.rollbacks=0; self.bad=False
    def snapshot(self, service): return {"exists":False}
    def deploy_canary(self, service, artifact_sha256, config, idempotency_key): self.deploys+=1; return {"revision":"rev-canary-1"}
    def readback(self, service, revision):
        d={"ready":True,"version":"0.4.0","artifact_sha256":ARTIFACT_SHA256,"traffic_percent":0,"min_instances":0,"max_instances":1,"cost_policy":"ZERO_NEW_RECURRING_COST","heartbeat_state":"PROVEN","heartbeat_proof":"proof:heartbeat"}
        if self.bad: d["ready"]=False
        return d
    def rollback(self, service, snapshot): self.rollbacks+=1; return {"state":"ROLLED_BACK"}


class KDV:
    def __init__(self, good=True): self.good=good
    def append(self, record): return {"proof_ref":"kdv:receipt" if self.good else "","readback_match":self.good}


def watchman(producer, verifier, claim, fruit):
    return {"state":"PROVEN" if producer != verifier and all(fruit.get(k)==v for k,v in claim.items()) else "REJECTED", "proof_ref":"watchman:proof"}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.backend=Backend(); self.store=ReceiptStore(Path(self.tmp.name)/"r.db")
    def tearDown(self): self.tmp.cleanup()
    def req(self, **changes):
        d={"action":"DEPLOY_SUPERIOR_V040_CANARY","artifact_sha256":ARTIFACT_SHA256,"service":"superior-doctrine-v040-canary","idempotency_key":"one","formation_permit_receipt":"permit:consumed"}; d.update(changes); return CanaryRequest(**d)
    def test_happy_path_and_idempotent_replay(self):
        action=LockedCanaryAction(self.backend,KDV(),self.store,watchman); self.assertEqual(action.execute(self.req()).state,"CANARY_PROVEN_ZERO_TRAFFIC"); action.execute(self.req()); self.assertEqual(self.backend.deploys,1)
    def test_hash_mismatch_never_mutates(self):
        with self.assertRaisesRegex(CanaryFailure,"ARTIFACT_HASH_MISMATCH"): LockedCanaryAction(self.backend,KDV(),self.store,watchman).execute(self.req(artifact_sha256="0"*64))
        self.assertEqual(self.backend.deploys,0)
    def test_zero_cost_policy_is_locked(self):
        with self.assertRaisesRegex(CanaryFailure,"ZERO_COST_CANARY_POLICY_VIOLATION"): LockedCanaryAction(self.backend,KDV(),self.store,watchman).execute(self.req(max_instances=2))
    def test_semantic_mismatch_rolls_back(self):
        self.backend.bad=True
        with self.assertRaisesRegex(CanaryFailure,"SEMANTIC_READBACK_MISMATCH"): LockedCanaryAction(self.backend,KDV(),self.store,watchman).execute(self.req())
        self.assertEqual(self.backend.rollbacks,1)
    def test_kdv_failure_rolls_back(self):
        with self.assertRaisesRegex(CanaryFailure,"KDV_READBACK_UNPROVEN"): LockedCanaryAction(self.backend,KDV(False),self.store,watchman).execute(self.req())
        self.assertEqual(self.backend.rollbacks,1)
    def test_watchman_rejection_rolls_back(self):
        bad=lambda *args:{"state":"REJECTED","proof_ref":""}
        with self.assertRaisesRegex(CanaryFailure,"WATCHMAN_REJECTED"): LockedCanaryAction(self.backend,KDV(),self.store,bad).execute(self.req())
        self.assertEqual(self.backend.rollbacks,1)
    def test_idempotency_conflict_fails_closed(self):
        action=LockedCanaryAction(self.backend,KDV(),self.store,watchman); action.execute(self.req())
        with self.assertRaisesRegex(CanaryFailure,"IDEMPOTENCY_CONFLICT"): action.execute(self.req(formation_permit_receipt="other"))

    def test_exact_a2_allowlist_registration_and_dispatch(self):
        locked=LockedCanaryAction(self.backend,KDV(),self.store,watchman)
        registry=install_into({"STATUS": object()},locked)
        self.assertEqual(set(registry),{"STATUS",ACTION})
        self.assertEqual(registry[ACTION].authority_class,"A2")
        result=registry[ACTION].handler(self.req().__dict__)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"],ACTION)
        self.assertEqual(self.backend.deploys,1)

    def test_allowlist_collision_fails_closed(self):
        locked=LockedCanaryAction(self.backend,KDV(),self.store,watchman)
        with self.assertRaisesRegex(CanaryFailure,"ALLOWLIST_BINDING_ALREADY_EXISTS"):
            install_into({ACTION: object()},locked)


if __name__ == "__main__": unittest.main()
