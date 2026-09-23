import unittest,tempfile,shutil,pathlib
from fuse_genesis.resident_host import HostState,ResidentHost

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
 def test_19_resident_direct(self):
  h=ResidentHost(self.d,1); h.start(1); h.tick(2); h.state.release(h.instance_id,1,3); self.assertEqual(h.state.snapshot()["host"]["state"],"RELEASED"); h.close()
 def test_20_fence_advance_restart(self):
  s=HostState(self.d); s.claim_host("a",1,1); s.release("a",1,2); s.close(); s=HostState(self.d); s.claim_host("b",2,3); self.assertEqual(s.snapshot()["host"]["fence"],2); s.close()

if __name__=="__main__": unittest.main(verbosity=2)
