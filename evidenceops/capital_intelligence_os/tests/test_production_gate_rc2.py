import unittest
from datetime import datetime,timezone,timedelta
from evidenceops.capital_intelligence_os.production_gate import *
NOW=datetime(2026,8,11,21,0,tzinfo=timezone.utc)
def ev(c,state=EvidenceState.VERIFIED,days=0):return ProviderEvidence(c,state,"provider",f"receipt:{c}",(NOW-timedelta(days=days)).isoformat())
class GateTests(unittest.TestCase):
 def setUp(self):self.intent=DeploymentIntent("PRODUCTION","africa-south1")
 def test_empty_fails(self):self.assertFalse(ProductionQualificationGate().evaluate(self.intent,[],now=NOW).qualified)
 def test_all_verified_passes(self):
  g=ProductionQualificationGate();d=g.evaluate(self.intent,[ev(c) for c in g.required_controls(self.intent)],now=NOW);self.assertTrue(d.qualified);self.assertEqual(d.maturity,"PRODUCTION_VERIFIED")
 def test_failed_blocks(self):
  g=ProductionQualificationGate();e=[ev(c) for c in g.required_controls(self.intent)];e[-1]=ev(e[-1].control_id,EvidenceState.FAILED);self.assertFalse(g.evaluate(self.intent,e,now=NOW).qualified)
 def test_expired_blocks(self):
  g=ProductionQualificationGate();e=[ev(c) for c in g.required_controls(self.intent)];e[0]=ev(e[0].control_id,days=31);self.assertIn("SOURCE_ADMISSION",g.evaluate(self.intent,e,now=NOW).expired_controls)
 def test_market_optional(self):
  i=DeploymentIntent("STAGING","africa-south1",market_intelligence_enabled=False);self.assertNotIn(ProductionQualificationGate.MARKET_CONTROL,ProductionQualificationGate().required_controls(i))
 def test_live_effects_forbidden(self):
  with self.assertRaises(PermissionError):DeploymentIntent("PRODUCTION","africa-south1",live_financial_effects_enabled=True).validate()
 def test_destructive_forbidden(self):
  with self.assertRaises(PermissionError):DeploymentIntent("PRODUCTION","africa-south1",destructive_actions_enabled=True).validate()
 def test_secret_ref_rejected(self):
  with self.assertRaises(ValueError):ProviderEvidence("X",EvidenceState.VERIFIED,"p","sk-abcdefghijklmnopqrstuvwxyz","2026-08-11T00:00:00+00:00").validate()
 def test_unverified_missing(self):
  g=ProductionQualificationGate();r=g.required_controls(self.intent);self.assertIn(r[0],g.evaluate(self.intent,[ev(r[0],EvidenceState.UNVERIFIED)],now=NOW).missing_controls)
