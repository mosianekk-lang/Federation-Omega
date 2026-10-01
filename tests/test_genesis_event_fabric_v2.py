import unittest,tempfile,shutil,pathlib
from fuse_genesis.event_fabric_v2 import *

class T(unittest.TestCase):
 def setUp(self):
  self.d=pathlib.Path(tempfile.mkdtemp()); self.f=EventFabric(self.d/"e.db",max_attempts=3); self.f.set_fence("t",10)
 def tearDown(self): self.f.close(); shutil.rmtree(self.d,ignore_errors=True)
 def e(self,i=1,key=None,payload=None,producer="p",pseq=None,fence=10,topic="t"):
  return EventEnvelope(f"e{i}",topic,key or f"k{i}","m",producer,pseq or i,fence,payload or {"i":i},"r")
 def test_01_publish(self): self.assertEqual(self.f.publish(self.e()),1)
 def test_02_idem(self): a=self.f.publish(self.e()); b=self.f.publish(self.e()); self.assertEqual(a,b)
 def test_03_idem_collision(self):
  self.f.publish(self.e())
  with self.assertRaises(IdempotencyCollision): self.f.publish(self.e(payload={"x":2}))
 def test_04_stale_fence(self):
  with self.assertRaises(StaleFence): self.f.publish(self.e(fence=9))
 def test_05_fence_advance(self): self.assertEqual(self.f.set_fence("t",11),11)
 def test_06_fence_regression(self):
  self.f.set_fence("t",11)
  with self.assertRaises(StaleFence): self.f.set_fence("t",10)
 def test_07_producer_order(self):
  self.f.publish(self.e(i=1,pseq=2))
  with self.assertRaises(ProducerOrderError): self.f.publish(self.e(i=2,pseq=1))
 def test_08_poll(self): self.f.publish(self.e()); self.assertEqual(len(self.f.poll("c")),1)
 def test_09_ack(self): self.f.publish(self.e()); r=self.f.poll("c")[0]; self.assertEqual(len(self.f.ack("c",r)),64)
 def test_10_ack_removes(self): self.f.publish(self.e()); r=self.f.poll("c")[0]; self.f.ack("c",r); self.assertEqual(self.f.poll("c"),[])
 def test_11_offset(self): self.f.publish(self.e()); r=self.f.poll("c")[0]; self.f.ack("c",r); self.assertEqual(self.f.offset("c"),1)
 def test_12_pause(self): self.f.publish(self.e()); self.f.pause("c"); self.assertEqual(self.f.poll("c"),[])
 def test_13_resume(self): self.f.publish(self.e()); self.f.pause("c"); self.f.resume("c"); self.assertEqual(len(self.f.poll("c")),1)
 def test_14_unacked_redelivery(self): self.f.publish(self.e()); a=self.f.poll("c")[0]; b=self.f.poll("c")[0]; self.assertEqual(a["event_id"],b["event_id"])
 def test_15_fail_retry(self): self.f.publish(self.e()); r=self.f.poll("c")[0]; self.assertEqual(self.f.fail("c",r,"x"),"RETRY")
 def test_16_poison_dlq(self):
  self.f.publish(self.e()); r=self.f.poll("c")[0]; self.f.fail("c",r,"x"); self.f.fail("c",r,"x"); self.assertEqual(self.f.fail("c",r,"x"),"DLQ")
 def test_17_dlq_removed_from_poll(self):
  self.f.publish(self.e()); r=self.f.poll("c")[0]
  for _ in range(3): self.f.fail("c",r,"x")
  self.assertEqual(self.f.poll("c"),[])
 def test_18_dlq_row(self):
  self.f.publish(self.e()); r=self.f.poll("c")[0]
  for _ in range(3): self.f.fail("c",r,"x")
  self.assertEqual(len(self.f.dlq_rows("c")),1)
 def test_19_replay(self): self.f.publish(self.e()); self.assertEqual(len(self.f.replay()),1)
 def test_20_replay_range(self):
  self.f.publish(self.e(1)); self.f.publish(self.e(2)); self.assertEqual([x["seq"] for x in self.f.replay(2,2)],[2])
 def test_21_topic_filter(self):
  self.f.publish(self.e(1,topic="t")); self.f.set_fence("u",1); self.f.publish(self.e(2,producer="q",pseq=1,topic="u",fence=1)); self.assertEqual(len(self.f.poll("c",topic="u")),1)
 def test_22_consumer_independent(self):
  self.f.publish(self.e()); a=self.f.poll("a")[0]; self.f.ack("a",a); self.assertEqual(len(self.f.poll("b")),1)
 def test_23_restart_unacked(self):
  p=self.d/"e.db"; self.f.publish(self.e()); self.f.close(); self.f=EventFabric(p); self.assertEqual(len(self.f.poll("c")),1)
 def test_24_restart_acked(self):
  p=self.d/"e.db"; self.f.publish(self.e()); r=self.f.poll("c")[0]; self.f.ack("c",r); self.f.close(); self.f=EventFabric(p); self.assertEqual(self.f.poll("c"),[])
 def test_25_restart_fence(self):
  p=self.d/"e.db"; self.f.set_fence("t",12); self.f.close(); self.f=EventFabric(p)
  with self.assertRaises(StaleFence): self.f.publish(self.e(fence=11))
 def test_26_duplicate_event_id(self):
  self.f.publish(self.e())
  with self.assertRaises(Exception): self.f.publish(EventEnvelope("e1","t","other","m","q",1,10,{"x":1},"r"))
 def test_27_digest(self): self.f.publish(self.e()); self.assertEqual(len(self.f.state_digest()),64)
 def test_28_digest_stable(self): self.f.publish(self.e()); self.assertEqual(self.f.state_digest(),self.f.state_digest())
 def test_29_digest_changes(self): a=self.f.state_digest(); self.f.publish(self.e()); self.assertNotEqual(a,self.f.state_digest())
 def test_30_ack_idempotent(self): self.f.publish(self.e()); r=self.f.poll("c")[0]; a=self.f.ack("c",r); b=self.f.ack("c",r); self.assertEqual(a,b)
 def test_31_offset_no_regress(self):
  self.f.publish(self.e(1)); self.f.publish(self.e(2)); rows=self.f.poll("c"); self.f.ack("c",rows[1])
  with self.assertRaises(EventError): self.f._advance_offset("c",1)
 def test_32_partition_resume_preserves(self):
  self.f.publish(self.e()); self.f.pause("c"); self.f.resume("c"); self.assertEqual(self.f.poll("c")[0]["event_id"],"e1")
 def test_33_producer_two(self):
  self.f.publish(self.e(1,producer="a",pseq=1)); self.f.publish(self.e(2,producer="b",pseq=1)); self.assertEqual(len(self.f.replay()),2)
 def test_34_same_producer_monotonic(self):
  self.f.publish(self.e(1,pseq=1)); self.f.publish(self.e(2,pseq=2)); self.assertEqual(len(self.f.replay()),2)
 def test_35_same_producer_equal_reject(self):
  self.f.publish(self.e(1,pseq=1))
  with self.assertRaises(ProducerOrderError): self.f.publish(self.e(2,pseq=1))
 def test_36_dlq_advances_offset(self):
  self.f.publish(self.e()); r=self.f.poll("c")[0]
  for _ in range(3): self.f.fail("c",r,"x")
  self.assertEqual(self.f.offset("c"),1)
 def test_37_retry_does_not_advance(self):
  self.f.publish(self.e()); r=self.f.poll("c")[0]; self.f.fail("c",r,"x"); self.assertEqual(self.f.offset("c"),0)
 def test_38_event_hash_payload(self):
  self.f.publish(self.e(payload={"x":1})); self.assertEqual(len(self.f.replay()[0]["payload_sha256"]),64)
 def test_39_new_topic_initial_fence(self):
  self.f.publish(self.e(topic="x",fence=5)); self.assertEqual(self.f.db.execute("select token from stream_fences where topic='x'").fetchone()[0],5)
 def test_40_no_events(self): self.assertEqual(self.f.poll("c"),[])
if __name__=="__main__": unittest.main(verbosity=2)
