import json
import tempfile
import unittest
from pathlib import Path

from runtime import (
    CompletionContract,
    Mission,
    ProviderCapability,
    SolRuntime,
    Workstream,
    utc_now,
)


class SolRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runtime = SolRuntime(self.root)
        self.runtime.register_mission(Mission("m1", "Deliver verified system", ("tests", "readback")))
        self.runtime.register_workstream(Workstream("w1", "m1", "Build kernel", (), 90))

    def tearDown(self):
        self.tmp.cleanup()

    def test_event_chain_and_resume(self):
        self.assertTrue(self.runtime.verify_event_chain())
        before = self.runtime.checkpoint("m1")
        resumed = SolRuntime(self.root)
        self.assertTrue(resumed.verify_event_chain())
        self.assertIn(before["checkpoint_id"], resumed.state.checkpoints)
        self.assertIn("m1", resumed.state.missions)

    def test_completion_requires_all_receipts(self):
        contract = CompletionContract(("build", "test", "readback", "rollback"))
        self.runtime.record_receipt("w1", "build", "github", {"pass": True})
        partial = self.runtime.evaluate_completion("w1", contract)
        self.assertEqual(partial["state"], "PARTIALLY_VERIFIED")
        for kind in ("test", "readback", "rollback"):
            self.runtime.record_receipt("w1", kind, "github", {"pass": True})
        complete = self.runtime.evaluate_completion("w1", contract)
        self.assertEqual(complete["state"], "VERIFIED")

    def test_provider_admission_and_owner_boundary(self):
        cap = ProviderCapability("github", "merge", True, True, True, True, False, "VERIFIED", utc_now())
        self.runtime.register_provider(cap)
        self.assertTrue(self.runtime.admit_action("github", "merge")["admitted"])
        held = self.runtime.admit_action("github", "merge", consequential=True)
        self.assertFalse(held["admitted"])
        self.assertEqual(held["state"], "OWNER_APPROVAL_REQUIRED")

    def test_dependency_scheduler(self):
        self.runtime.register_workstream(Workstream("w2", "m1", "Deploy", ("w1",), 80))
        ready = [x["workstream_id"] for x in self.runtime.ready_workstreams()]
        self.assertEqual(ready, ["w1"])
        self.runtime.record_receipt("w1", "done", "local", {"pass": True})
        self.runtime.evaluate_completion("w1", CompletionContract(("done",)))
        ready = [x["workstream_id"] for x in self.runtime.ready_workstreams()]
        self.assertEqual(ready, ["w2"])

    def test_context_compiler_filters_unverified(self):
        facts = [
            {"id": "f1", "missions": ["m1"], "verified": True, "priority": 10},
            {"id": "f2", "missions": ["m1"], "verified": False, "priority": 20},
            {"id": "f3", "missions": ["other"], "verified": True, "priority": 99},
        ]
        context = self.runtime.compile_context("w1", facts)
        self.assertEqual(context["verified_facts"][0]["id"], "f1")
        self.assertEqual(context["unknowns"][0]["id"], "f2")

    def test_reasoning_budget_and_repair(self):
        self.assertEqual(self.runtime.reasoning_budget(complexity=1, consequence=1, uncertainty=1, dependency_depth=1, contradiction_risk=1)["lane"], "FAST")
        self.assertEqual(self.runtime.reasoning_budget(complexity=3, consequence=3, uncertainty=2, dependency_depth=2, contradiction_risk=2)["lane"], "ESCALATED")
        self.assertEqual(self.runtime.classify_failure({"class": "authority"})["class"], "AUTHORITY")

    def test_lessons_compile_to_policy(self):
        self.runtime.record_lesson("registry-only-claim", "Require fresh provider receipt", "receipt://1")
        policy = self.runtime.compile_lesson_to_policy(0, "PREFLIGHT_CHECK")
        self.assertEqual(policy["status"], "ACTIVE")
        self.assertEqual(len(self.runtime.state.policies), 1)

    def test_reliability_and_cybernetics(self):
        for _ in range(50):
            reliability = self.runtime.update_reliability("safe_read", True)
        self.assertEqual(reliability["autonomy"], "AUTOMATIC")
        decision = self.runtime.cybernetic_decision(error_rate=0.3, queue_age_seconds=10, proof_age_seconds=10, retries=4)
        self.assertEqual(decision["action"], "ULTRASTABLE_RECONFIGURE")


if __name__ == "__main__":
    unittest.main()
