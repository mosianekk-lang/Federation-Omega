import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from jarvis.core import CapabilityFabric, FormationKernel, LearningLedger, CircuitBreaker
from jarvis.execution import TwentyMinuteGovernor
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

class TwentyMinuteGovernorTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000.0
        self.governor = TwentyMinuteGovernor(clock=lambda: self.now)

    def test_plan_is_bounded_and_multi_path_multi_stream(self):
        plan = self.governor.build_plan("M1", "Finish the build")
        self.assertEqual(plan["deadlineAt"] - plan["startedAt"], 1200)
        self.assertEqual(sum(p["max_seconds"] for p in plan["phases"]), 1200)
        self.assertLessEqual(len(plan["paths"]), 3)
        self.assertLessEqual(len(plan["streams"]), 6)
        self.assertEqual({p["path_class"] for p in plan["paths"]}, {"PRIMARY", "PROTECTIVE", "FAILURE_RECOVERY"})

    def test_time_controls_force_split_convergence_and_release(self):
        started = self.now
        self.assertEqual(self.governor.control_state(started, started + 719)["state"], "GREEN")
        self.assertEqual(self.governor.control_state(started, started + 720)["state"], "SPLIT_REQUIRED")
        self.assertEqual(self.governor.control_state(started, started + 900)["state"], "CONVERGENCE_ONLY")
        self.assertEqual(self.governor.control_state(started, started + 1080)["state"], "RELEASE_ONLY")
        self.assertEqual(self.governor.control_state(started, started + 1200)["state"], "DEADLINE_REACHED")

    def test_speed_gain_is_only_shadow_promoted_after_quality_pass(self):
        gates = {gate: True for gate in self.governor.policy.quality_gates}
        review = self.governor.review_cycle(600, gates)
        self.assertTrue(review["cyclePass"])
        self.assertEqual(review["omegaScientist"]["promotionState"], "SHADOW_CANDIDATE")
        self.assertLess(review["omegaScientist"]["candidateNextTargetSeconds"], 600)

    def test_quality_failure_blocks_speed_optimisation(self):
        gates = {gate: True for gate in self.governor.policy.quality_gates}
        gates["SEMANTIC_READBACK"] = False
        review = self.governor.review_cycle(500, gates)
        self.assertFalse(review["cyclePass"])
        self.assertEqual(review["omegaScientist"]["promotionState"], "REJECTED")
        self.assertEqual(review["omegaScientist"]["candidateNextTargetSeconds"], 1200)

    def test_orchestrator_persists_cycle_review(self):
        with tempfile.TemporaryDirectory() as td:
            app = Jarvis(td)
            gates = {gate: True for gate in app.execution.policy.quality_gates}
            result = app.review_cycle(700, gates)
            self.assertTrue(result["cyclePass"])
            self.assertTrue(result["learningHash"])
            self.assertTrue(app.ledger.verify())

if __name__ == "__main__": unittest.main()
