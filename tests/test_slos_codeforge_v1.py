from __future__ import annotations
import unittest
from superior_logic.codeforge import CapabilityAcquirer,CapabilityCandidate,CapabilityGap,EngineeringMetrics,EngineeringRisk,EngineeringSpecCompiler,RepositoryIntelligence,TenXEngineeringCourt,VerificationCourt,VerificationObservation

class RepoTests(unittest.TestCase):
 def setUp(self):
  self.e=RepositoryIntelligence(); self.i=self.e.index({'app/service.py':"import json\nclass UserService:\n def create_user(self,name): return {'name':name}\n",'tests/test_service.py':'def test_create_user():\n assert True\n','README.md':'User service architecture notes'})
 def test_index_search_deterministic(self):
  j=self.e.index({'README.md':'User service architecture notes','tests/test_service.py':'def test_create_user():\n assert True\n','app/service.py':"import json\nclass UserService:\n def create_user(self,name): return {'name':name}\n"})
  self.assertEqual(self.i.merkle_root,j.merkle_root); self.assertEqual(self.e.search(self.i,'create_user UserService')[0].path,'app/service.py')
 def test_update_delta(self):
  j=self.e.update(self.i,changed_files={'app/service.py':'def create_user(name): return name\n'},removed_paths=('README.md',)); d=self.e.delta(self.i,j); self.assertEqual(d['changed'],('app/service.py',)); self.assertEqual(d['removed'],('README.md',))
 def test_context_bounded(self): self.assertLessEqual(len(self.e.context_pack(self.i,'user service',max_chars=300)),300)

class SpecTests(unittest.TestCase):
 def test_high_risk(self):
  repo=RepositoryIntelligence().index({'svc/auth.py':'def authorize(token): return bool(token)\n'}); s=EngineeringSpecCompiler().compile(mission_id='M',objective='harden authorization',success_condition='tests pass',repository=repo,risk=EngineeringRisk.HIGH); ids=[x.task_id for x in s.tasks]; self.assertIn('security',ids); self.assertEqual(ids[-1],'terminal_verify'); self.assertIn('SECURITY',s.required_checks); self.assertEqual(len(s.compiled_digest),64)

class VerifyTests(unittest.TestCase):
 def test_missing_proof(self):
  v=VerificationCourt().evaluate(required_checks=('UNIT','SECURITY'),observations=(VerificationObservation('UNIT',True,'proof://unit'),VerificationObservation('SECURITY',True,''))); self.assertEqual(v.status,'INCOMPLETE'); self.assertEqual(v.missing_checks,('SECURITY',))
 def test_failure(self): self.assertEqual(VerificationCourt().evaluate(required_checks=('UNIT',),observations=(VerificationObservation('UNIT',False,'proof://fail'),)).status,'FAILED')

class AcquireTests(unittest.TestCase):
 def test_internal_first(self):
  g=CapabilityGap('G','SANDBOX',('isolated','readback')); i=CapabilityCandidate('AO','INTERNAL',('isolated','readback'),'TESTED','repo://ao'); x=CapabilityCandidate('V','VENDOR_DOC',('isolated','readback'),'DOC','web://v'); p=CapabilityAcquirer().plan(g,internal_candidates=(i,),external_candidates=(x,)); self.assertEqual((p.action,p.candidate_id),('REUSE_INTERNAL','AO'))
 def test_graft_gated(self):
  g=CapabilityGap('G','PARSER',('ast','incremental')); c=CapabilityCandidate('oss','OPEN_SOURCE',('ast','incremental'),'REL','git://sha','Apache-2.0',True,True,True); p=CapabilityAcquirer().plan(g,external_candidates=(c,)); self.assertEqual(p.action,'CODE_GRAFT_CANDIDATE'); self.assertTrue(p.direct_code_allowed); self.assertIn('SUPPLY_CHAIN',p.proof_gates)
 def test_unreviewed_mechanism_only(self):
  g=CapabilityGap('G','INDEX',('semantic_search',)); c=CapabilityCandidate('oss','OPEN_SOURCE',('semantic_search',),'REL','git://sha','MIT',True,True,False); p=CapabilityAcquirer().plan(g,external_candidates=(c,)); self.assertEqual(p.action,'HARVEST_MECHANISM'); self.assertFalse(p.direct_code_allowed)

class TenXTests(unittest.TestCase):
 def test_tenx(self):
  b=EngineeringMetrics('suite','accept',.8,3600,2,20,.05,.9,30,1); c=EngineeringMetrics('suite','accept',.9,120,0,4,.01,.98,30,.5); v=TenXEngineeringCourt().compare(b,c); self.assertGreater(v.multiplier,10); self.assertTrue(v.target_met)
 def test_small_sample_held(self):
  b=EngineeringMetrics('suite','accept',.8,3600,2,20,.05,.9,5,1); c=EngineeringMetrics('suite','accept',.95,30,0,2,0,1,5,.1); v=TenXEngineeringCourt().compare(b,c); self.assertFalse(v.target_met); self.assertEqual(v.reason,'INSUFFICIENT_PAIRED_SAMPLE')
 def test_identity_mismatch(self):
  b=EngineeringMetrics('a','accept',.8,100,0,1,0,.9,30); c=EngineeringMetrics('b','accept',.9,10,0,1,0,.9,30)
  with self.assertRaises(ValueError): TenXEngineeringCourt().compare(b,c)

if __name__=='__main__': unittest.main()
