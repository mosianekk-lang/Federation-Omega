import unittest,tempfile,shutil,pathlib,time
from fuse_genesis.resident_host import HostState,ResidentHost
from fuse_genesis.currentness import SourceEpoch

E=SourceEpoch("a"*40,"F323",323,"GENESIS")
class T(unittest.TestCase):
 def setUp(self): self.d=pathlib.Path(tempfile.mkdtemp())
 def tearDown(self): shutil.rmtree(self.d,ignore_errors=True)
 def test_01_claim(self):
  s=HostState(self.d); s.claim_host("a",1,1); self.assertEqual(s.snapshot()["host"]["fence"],1); s.close()
 def test_02_equal_fence_blocked(self):
  s=HostState(self.d); s.claim_host("a",1,1)
  with self.assertRaises(RuntimeError): s.claim_host("b",1,2)
  s.close()
 def test_03_lower_fence_blocked(self):
  s=HostState(self.d); s.claim_host("a",2,1)
  with self.assertRaises(RuntimeError): s.claim_host("b",1,2)
  s.close()
 def test_04_higher_fence_takeover(self):
  s=HostState(self.d); s.claim_host("a",1,1); s.claim_host("b",2,2); self.assertEqual(s.snapshot()["host"]["instance_id"],"b"); s.close()
 def test_05_heartbeat(self):
  s=HostState(self.d); s.claim_host("a",1,1); self.assertTrue(s.heartbeat("a",1,2)); s.close()
 def test_06_stale_heartbeat(self):
  s=HostState(self.d); s.claim_host("a",1,1)
  with self.assertRaises(RuntimeError): s.heartbeat("b",1,2)
  s.close()
 def test_07_release(self):
  s=HostState(self.d); s.claim_host("a",1,1); s.release("a",1,2); self.assertEqual(s.snapshot()["host"]["state"],"RELEASED"); s.close()
 def test_08_reclaim_after_release(self):
  s=HostState(self.d); s.claim_host("a",1,1); s.release("a",1,2); s.claim_host("b",2,3); self.assertEqual(s.snapshot()["host"]["state"],"ACTIVE"); s.close()
 def test_09_enqueue(self):
  s=HostState(self.d); self.assertEqual(s.enqueue("t","k",{"x":1},1),"t"); s.close()
 def test_10_enqueue_idempotent(self):
  s=HostState(self.d); s.enqueue("t","k",{"x":1},1); self.assertEqual(s.enqueue("z","k",{"x":1},2),"t"); s.close()
 def test_11_collision(self):
  s=HostState(self.d); s.enqueue("t","k",{"x":1},1)
  with self.assertRaises(RuntimeError): s.enqueue("z","k",{"x":2},2)
  s.close()
 def test_12_next(self):
  s=HostState(self.d); s.enqueue("t","k",{"x":1},1); self.assertEqual(s.next_task()["task_id"],"t"); s.close()
 def test_13_checkpoint(self):
  s=HostState(self.d); s.enqueue("t","k",{"x":1},1); s.checkpoint("t",{"n":1},2); self.assertEqual(s.task("t")["state"],"RUNNING"); s.close()
 def test_14_complete(self):
  s=HostState(self.d); s.enqueue("t","k",{},1); s.complete("t",{"ok":1},2); self.assertEqual(s.task("t")["state"],"COMPLETE"); s.close()
 def test_15_restart_task(self):
  s=HostState(self.d); s.enqueue("t","k",{},1); s.checkpoint("t",{"n":1},2); s.close(); s=HostState(self.d); self.assertEqual(s.next_task()["task_id"],"t"); s.close()
 def test_16_restart_host(self):
  s=HostState(self.d); s.claim_host("a",1,1); s.release("a",1,2); s.close(); s=HostState(self.d); self.assertEqual(s.snapshot()["host"]["state"],"RELEASED"); s.close()
 def test_17_tick_persist(self):
  s=HostState(self.d); s.claim_host("a",1,1); s.heartbeat("a",1,2); self.assertEqual(len(s.snapshot()["ticks"]),1); s.close()
 def test_18_multiple_ticks(self):
  s=HostState(self.d); s.claim_host("a",1,1)
  for x in range(2,7): s.heartbeat("a",1,x)
  self.assertEqual(len(s.snapshot()["ticks"]),5); s.close()
 def test_19_epoch_bind(self):
  s=HostState(self.d); s.bind_epoch(E,1); self.assertEqual(s.epoch()["digest"],E.digest); s.close()
 def test_20_epoch_collision(self):
  s=HostState(self.d); s.bind_epoch(E,1)
  with self.assertRaises(RuntimeError): s.bind_epoch(SourceEpoch("b"*40,"F323",323,"GENESIS"),2)
  s.close()
 def test_21_stale_epoch(self):
  s=HostState(self.d); s.bind_epoch(E,1)
  with self.assertRaises(RuntimeError): s.bind_epoch(SourceEpoch("b"*40,"F322",322,"GENESIS"),2)
  s.close()
 def test_22_resident_direct(self):
  h=ResidentHost(self.d,E,interval=0); h.start(1); h.tick(2); h.state.release(h.instance_id,323,3); self.assertEqual(h.state.snapshot()["host"]["state"],"RELEASED"); h.close()
 def test_23_run_three_ticks(self):
  times=iter(range(1,20)); h=ResidentHost(self.d,E,interval=0); r=h.run(max_ticks=3,now_fn=lambda:next(times),sleep_fn=lambda _:None); self.assertEqual(r["ticks"],3); self.assertEqual(len(h.state.snapshot()["ticks"]),3); self.assertEqual(r["host_state"],"RELEASED"); h.close()
 def test_24_process_external_task(self):
  times=iter(range(1,30)); h=ResidentHost(self.d,E,interval=0); h.state.enqueue("t","k",{"x":2},0); r=h.run(handler=lambda p:{"y":p["x"]+1},max_ticks=1,now_fn=lambda:next(times),sleep_fn=lambda _:None); self.assertEqual(r["processed"],1); self.assertEqual(h.state.task("t")["state"],"COMPLETE"); h.close()
 def test_25_no_handler_no_self_execution(self):
  times=iter(range(1,30)); h=ResidentHost(self.d,E,interval=0); h.state.enqueue("t","k",{"x":2},0); r=h.run(max_ticks=1,now_fn=lambda:next(times),sleep_fn=lambda _:None); self.assertEqual(r["processed"],0); self.assertEqual(h.state.task("t")["state"],"PENDING"); h.close()
 def test_26_epoch_persisted_with_ticks(self):
  times=iter(range(1,30)); h=ResidentHost(self.d,E,interval=0); h.run(max_ticks=2,now_fn=lambda:next(times),sleep_fn=lambda _:None); self.assertEqual(h.state.snapshot()["source_epoch"]["digest"],E.digest); h.close()
 def test_27_no_release_on_exit_option(self):
  times=iter(range(1,30)); h=ResidentHost(self.d,E,interval=0); h.run(max_ticks=1,now_fn=lambda:next(times),sleep_fn=lambda _:None,release_on_exit=False); self.assertEqual(h.state.snapshot()["host"]["state"],"ACTIVE"); h.state.release(h.instance_id,323,next(times)); h.close()
 def test_28_negative_interval(self):
  with self.assertRaises(ValueError): ResidentHost(self.d,E,interval=-1)
 def test_29_invalid_max_ticks(self):
  h=ResidentHost(self.d,E,interval=0)
  with self.assertRaises(ValueError): h.run(max_ticks=0,now_fn=lambda:1,sleep_fn=lambda _:None)
  h.close()
 def test_30_source_fence_equals_host_fence(self):
  h=ResidentHost(self.d,E,interval=0); self.assertEqual(h.fence,E.fence); h.close()
 def test_31_long_task_keeps_heartbeat_alive(self):
  h=ResidentHost(self.d,E,interval=0,task_heartbeat_interval=0.01); h.state.enqueue("t","k",{"x":1},0)
  h.start()
  before=len(h.state.snapshot()["ticks"])
  h.process_next(lambda p:(time.sleep(0.06) or {"ok":p["x"]}))
  after=len(h.state.snapshot()["ticks"])
  self.assertGreaterEqual(after-before,3)
  self.assertEqual(h.state.task("t")["state"],"COMPLETE")
  h.state.release(h.instance_id,h.fence,time.time()); h.close()
if __name__=="__main__": unittest.main(verbosity=2)
