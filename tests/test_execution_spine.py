from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from bubbles.control_plane import EffectClass
from federation.execution_spine import Capsule, Mission, State, Task, UltimateExecutionSpine
from governance.external_action_firewall import ExternalActionFirewall, FileLeaseStore, FirewallDecision


class ExecutionSpineTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_reads_and_dependent_fanin(self):
        starts={}; ends={}
        async def reader(task):
            starts[task.task_id]=time.monotonic(); await asyncio.sleep(.05); ends[task.task_id]=time.monotonic(); return {"task":task.task_id}
        async def fanin(task): return {"joined":True}
        mission=Mission("m-par","parallel","a"*40,(
            Task("a","r:a","bubbles_command_bus","canary"),
            Task("b","r:b","bubbles_command_bus","canary"),
            Task("c","r:c","bubbles_command_bus","canary",depends_on=("a","b")),
        ))
        before=time.monotonic()
        cap=await UltimateExecutionSpine().run(mission,executors={"a":reader,"b":reader,"c":fanin},current_anchor=lambda:"a"*40)
        elapsed=time.monotonic()-before
        self.assertEqual("COMPLETE_VERIFIED_LOCAL",cap.state)
        self.assertLess(abs(starts["a"]-starts["b"]),.03)
        self.assertLess(elapsed,.13)
        self.assertGreaterEqual(starts["c"],min(ends["a"],ends["b"]))

    async def test_resume_hit_preserves_successful_work(self):
        calls={"a":0}
        async def run(task): calls["a"]+=1; return "ok"
        mission=Mission("m-resume","resume","b"*40,(Task("a","r:a","bubbles_command_bus","canary"),))
        spine=UltimateExecutionSpine()
        first=await spine.run(mission,executors={"a":run})
        second=await spine.run(mission,executors={"a":run},capsule=first)
        self.assertEqual(1,calls["a"])
        self.assertEqual(State.RESUME_HIT,second.results["a"].state)

    async def test_effect_lane_blocks_without_execution_lease_but_read_lane_continues(self):
        called={"write":0,"read":0}
        async def read(task): called["read"]+=1; return "read"
        async def write(task): called["write"]+=1; return "write"
        mission=Mission("m-gate","gate","c"*40,(
            Task("read","r:read","bubbles_command_bus","canary"),
            Task("write","r:write","google_drive","update_file",EffectClass.LOW_RISK_WRITE,target_alias="DRIVE"),
        ))
        cap=await UltimateExecutionSpine().run(mission,executors={"read":read,"write":write})
        self.assertEqual(State.SUCCESS,cap.results["read"].state)
        self.assertEqual(State.BLOCKED,cap.results["write"].state)
        self.assertEqual(1,called["read"]); self.assertEqual(0,called["write"])

    async def test_low_information_optional_task_is_skipped(self):
        mission=Mission("m-info","info","d"*40,(
            Task("core","r:core","bubbles_command_bus","canary"),
            Task("optional","r:opt","bubbles_command_bus","canary",required=False,info_gain=.01),
        ),info_gain_floor=.1)
        cap=await UltimateExecutionSpine().run(mission,executors={"core":lambda t:"ok","optional":lambda t:"never"})
        self.assertEqual(State.SKIP_LOW_VALUE,cap.results["optional"].state)

    async def test_smart_read_workaround_recovers_tool_failure_and_records_learning(self):
        async def failing(task): raise RuntimeError("connector unavailable")
        async def alternate(task): return {"recovered":True}
        mission=Mission("m-work","workaround","e"*40,(Task("read","route:primary","bubbles_command_bus","canary",retries=0),))
        cap=await UltimateExecutionSpine().run(mission,executors={"read":failing},alternates={"ALTERNATE_READ_ROUTE":alternate})
        result=cap.results["read"]
        self.assertEqual(State.SUCCESS,result.state)
        self.assertEqual("ALTERNATE_READ_ROUTE",result.workaround)
        self.assertTrue(result.failure_fingerprint)
        self.assertTrue(result.learning_receipt)
        self.assertEqual(1,cap.recurrence[result.failure_fingerprint])

    async def test_stale_anchor_holds_before_execution(self):
        called={"a":0}
        async def run(task): called["a"]+=1; return "ok"
        mission=Mission("m-stale","stale","f"*40,(Task("a","r:a","bubbles_command_bus","canary"),))
        cap=await UltimateExecutionSpine().run(mission,executors={"a":run},current_anchor=lambda:"0"*40)
        self.assertEqual("HOLD_STALE_SOURCE",cap.state)
        self.assertEqual(0,called["a"])

    async def test_capsule_roundtrip(self):
        mission=Mission("m-json","json","1"*40,(Task("a","r:a","bubbles_command_bus","canary"),))
        cap=await UltimateExecutionSpine().run(mission,executors={"a":lambda t:"ok"})
        restored=Capsule.from_json(cap.to_json())
        self.assertEqual(cap.capsule_sha256,restored.capsule_sha256)
        self.assertEqual(State.SUCCESS,restored.results["a"].state)


class ExistingFirewallRegression(unittest.TestCase):
    def test_exact_n_cannot_prepare_external_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            firewall=ExternalActionFirewall(secret=b"test-secret",store=FileLeaseStore(Path(td)/"leases.json"),clock=lambda:1_700_000_000)
            receipt=firewall.prepare(user_turn_id="t1",user_text="n",action="send_draft",target={"adapter":"gmail","draft_id":"d1","recipient":"x@example.org"})
            self.assertEqual(FirewallDecision.DENY.value,receipt.decision)
            self.assertIn("No explicit current-turn",receipt.reason)


if __name__=="__main__":
    unittest.main()
