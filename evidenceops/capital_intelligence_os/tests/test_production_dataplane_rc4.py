import unittest
from datetime import datetime,timezone,timedelta
from evidenceops.capital_intelligence_os.production_dataplane import *
NOW=datetime(2026,8,11,21,tzinfo=timezone.utc)
def claims(tenant="t",mfa=True): return IdentityClaims("u",tenant,("admin",),"idp",mfa,NOW.isoformat())
def probe(a,controls,healthy=True,days=0): return AdapterProbe(a,"provider",healthy,tuple(controls),f"provider-receipt:{a}",(NOW-timedelta(days=days)).isoformat())
def complete(intent):
 g=ProductionDataPlanePreflight(); return [probe(f"a{i}",[c]) for i,c in enumerate(g.required_controls(intent))]
class ProductionDataPlaneRC4Tests(unittest.TestCase):
 def test_empty_fails(self):
  i=ProductionBindingIntent("t"); self.assertFalse(ProductionDataPlanePreflight().evaluate(i,claims(),[],now=NOW).ready)
 def test_complete_passes(self):
  i=ProductionBindingIntent("t"); r=ProductionDataPlanePreflight().evaluate(i,claims(),complete(i),now=NOW); self.assertTrue(r.ready); self.assertEqual(len(r.missing_controls),0)
 def test_market_optional(self):
  i=ProductionBindingIntent("t",market_intelligence_enabled=False); self.assertNotIn(ProductionDataPlanePreflight.MARKET_CONTROL,ProductionDataPlanePreflight().required_controls(i))
 def test_market_required(self):
  i=ProductionBindingIntent("t",market_intelligence_enabled=True); self.assertIn(ProductionDataPlanePreflight.MARKET_CONTROL,ProductionDataPlanePreflight().required_controls(i))
 def test_private_optional(self):
  i=ProductionBindingIntent("t",private_mna_enabled=False); self.assertNotIn(ProductionDataPlanePreflight.PRIVATE_CONTROL,ProductionDataPlanePreflight().required_controls(i))
 def test_mfa_required(self):
  with self.assertRaises(PermissionError): ProductionDataPlanePreflight().evaluate(ProductionBindingIntent("t"),claims(mfa=False),[],now=NOW)
 def test_tenant_mismatch_denied(self):
  with self.assertRaises(PermissionError): ProductionDataPlanePreflight().evaluate(ProductionBindingIntent("t"),claims("other"),[],now=NOW)
 def test_stale_probe_fails(self):
  i=ProductionBindingIntent("t",False,False); ps=complete(i); ps[0]=probe("stale",ps[0].control_ids,days=31); r=ProductionDataPlanePreflight().evaluate(i,claims(),ps,now=NOW); self.assertFalse(r.ready); self.assertIn("stale",r.failed_adapters)
 def test_unhealthy_probe_fails(self):
  i=ProductionBindingIntent("t",False,False); ps=complete(i); ps[0]=probe("bad",ps[0].control_ids,healthy=False); self.assertFalse(ProductionDataPlanePreflight().evaluate(i,claims(),ps,now=NOW).ready)
 def test_secret_shaped_evidence_is_rejected(self):
  i=ProductionBindingIntent("t",False,False); ps=complete(i); p=ps[0]; ps[0]=AdapterProbe(p.adapter_id,p.provider,True,p.control_ids,"s"+"k-"+("x"*24),p.observed_at); self.assertFalse(ProductionDataPlanePreflight().evaluate(i,claims(),ps,now=NOW).ready)
 def test_compiles_provider_evidence(self):
  i=ProductionBindingIntent("t",False,False); r=ProductionDataPlanePreflight().evaluate(i,claims(),complete(i),now=NOW); self.assertTrue(all(e.state==EvidenceState.VERIFIED for e in r.provider_evidence))
