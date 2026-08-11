import unittest
from evidenceops.capital_intelligence_os.strategy import *
from evidenceops.capital_intelligence_os.evolution import *
class StrategyV07Tests(unittest.TestCase):
 def setUp(self):self.t=ThesisCompiler().compile({'sectors':['saas'],'geographies':['south africa'],'min_revenue':50,'max_revenue':500,'min_ebitda_margin':.15,'max_leverage':3,'required_recurring_revenue':.6,'strategic_priorities':['ai','payments']})
 def test_compile(self):self.assertEqual(self.t.sectors,('saas',))
 def test_bad_range(self):
  with self.assertRaises(ValueError):ThesisCompiler().compile({'min_revenue':100,'max_revenue':10})
 def test_hard_gate(self):self.assertFalse(TargetScreenEngine().assess(self.t,TargetCandidate('1','Bad','mining','south africa',100,.2,1,.8,('ai',))).eligible)
 def test_rank(self):
  a=TargetCandidate('1','A','saas','south africa',100,.25,1,.85,('ai','payments'));b=TargetCandidate('2','B','saas','south africa',100,.16,2.8,.61,('ai',));self.assertEqual(TargetScreenEngine().rank(self.t,[b,a])[0].target_id,'1')
 def test_build_buy_partner(self):self.assertEqual(len(BuildBuyPartnerEngine().rank([StrategicRoute('BUILD',70,20,18,.9,.3),StrategicRoute('BUY',100,80,4,1,.4),StrategicRoute('PARTNER',60,10,2,.4,.2)])),3)
 def test_scarcity(self):self.assertGreater(StrategicScarcityEngine().score(qualified_targets=1,buyer_competition=.9,capability_uniqueness=.9),70)
 def test_whitespace(self):self.assertEqual(WhiteSpaceDetector().gaps(['AI','Payments','Cyber'],['AI']),('cyber','payments'))
class EvolutionV07Tests(unittest.TestCase):
 def test_court_promotes(self):self.assertTrue(ExperimentCourt().decide(ExperimentEvidence('e',.6,.7,.68,100,.001,2,False)).promoted)
 def test_safety_veto(self):self.assertIn('SAFETY_REGRESSION_VETO',ExperimentCourt().decide(ExperimentEvidence('e',.6,.9,.9,100,.001,1,True)).reasons)
 def test_multiple_testing(self):self.assertFalse(ExperimentCourt().decide(ExperimentEvidence('e',.6,.7,.68,100,.02,10,False)).promoted)
 def test_mortality(self):self.assertEqual(CapabilityMortality().state(CapabilityRecord('c',.1,.1,.1,.1,100)),'RETIRE_CANDIDATE')
 def test_evidence_weighted_council(self):self.assertEqual(EvidenceWeightedCouncil().synthesize([CouncilOpinion('weak1','BUY',1,.1),CouncilOpinion('weak2','BUY',1,.1),CouncilOpinion('strong','PASS',.9,.9)]).recommendation,'PASS')
 def test_empty_council(self):
  with self.assertRaises(ValueError):EvidenceWeightedCouncil().synthesize([])
 def test_failure_compiler(self):self.assertEqual(FailureInnovationCompiler().compile([{'fingerprint':'DNS','alternative_route':'CONNECTOR'}]*3)[0].lifecycle_state,'EXPERIMENTAL_REQUIRES_COURT')
