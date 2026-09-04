import unittest
from federation.kioas_sentinel import *
class SentinelTests(unittest.TestCase):
 def setUp(self): self.s=KioasSentinel()
 def one(self,o): return self.s.evaluate([o])[0]
 def test_public_writer(self):
  f=self.one(Observation('apps_script_permission','smart',{'public_writer_count':1},{'public_writer_count':0},'drive'))
  self.assertEqual(f.disposition,Disposition.OWNER_OR_PROVIDER_TRIGGER_REQUIRED); self.assertFalse(f.provider_effect_allowed)
 def test_generic_high_callee(self):
  f=self.one(Observation('generic_invocation','deploy',{'wrapper_risk':'MEDIUM','callee_risk':'HIGH','action':'RUN_FUNCTION'},{},'policy'))
  self.assertEqual(f.disposition,Disposition.AUTO_REPAIR_FENCED)
 def test_gns3_stale(self):
  f=self.one(Observation('scheduler_liveness','gns3',{'heartbeat_fresh':False},{'trigger_count':1},'scheduler'))
  self.assertEqual(f.disposition,Disposition.WAITING_EXACT_CAPABILITY)
 def test_backup_stale(self):
  f=self.one(Observation('backup_freshness','architron',{'age_hours':30},{'max_age_hours':24},'drive'))
  self.assertEqual(f.disposition,Disposition.AUTO_REPAIR_CANARY)
 def test_repeat_route(self):
  f=self.one(Observation('repeated_route_failure','drive-scripts',{'unchanged_repeat_count':2},{},'route'))
  self.assertEqual(f.disposition,Disposition.QUARANTINE_AND_REROUTE)
 def test_identity_drift(self):
  f=self.one(Observation('source_identity','kioas',{'provider_id':'new'},{'provider_id':'old'},'drive'))
  self.assertEqual(f.disposition,Disposition.AUTO_REPAIR_FENCED)
 def test_healthy_no_findings(self): self.assertEqual(self.s.evaluate([Observation('apps_script_permission','x',{'public_writer_count':0},{'public_writer_count':0},'d')]),[])
 def test_receipt_no_effect(self): self.assertFalse(sentinel_receipt([])['provider_effect'])
if __name__=='__main__': unittest.main()
