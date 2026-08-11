
import copy, json, unittest
from pathlib import Path
from evidenceops.capital_intelligence_os.mvp_journey import MVPJourneyOrchestrator, DecisionCompletenessIndex
BASE=json.loads((Path(__file__).parents[1]/"fixtures"/"synthetic_mvp_deal_v1.json").read_text())
class Recorder:
 def __init__(self): self.rows=[]
 def record(self,**kw): self.rows.append(kw)
class JourneyTests(unittest.TestCase):
 def test_full_journey_passes_with_human_gate(self):
  r=Recorder(); out=MVPJourneyOrchestrator(outcome_recorder=r).run(copy.deepcopy(BASE))
  self.assertTrue(out.passed); self.assertEqual(out.final_recommendation_disposition,"REQUIRE_HUMAN")
  self.assertEqual(out.live_order_disposition,"DENY"); self.assertEqual(out.private_to_market_disposition,"DENY")
  self.assertGreaterEqual(out.contradiction_count,1); self.assertTrue(out.outcome_recorded); self.assertEqual(len(r.rows),1)
 def test_missing_evidence_lowers_diligence(self):
  full=MVPJourneyOrchestrator(outcome_recorder=Recorder()).run(copy.deepcopy(BASE))
  p=copy.deepcopy(BASE); p["documents"]=p["documents"][:1]
  partial=MVPJourneyOrchestrator(outcome_recorder=Recorder()).run(p)
  self.assertLess(partial.diligence_score,full.diligence_score)
  self.assertLess(partial.transaction_readiness,full.transaction_readiness)
 def test_strategy_gate_fails_closed(self):
  p=copy.deepcopy(BASE); p["target"]["sector"]="mining"
  out=MVPJourneyOrchestrator(outcome_recorder=Recorder()).run(p)
  self.assertFalse(out.passed); self.assertFalse(out.target_eligible)
 def test_outcome_expected_without_recorder_fails(self):
  out=MVPJourneyOrchestrator().run(copy.deepcopy(BASE))
  self.assertFalse(out.passed); self.assertFalse(out.checks["outcome_learning_respects_configuration"])
 def test_no_outcome_config_does_not_require_recorder(self):
  p=copy.deepcopy(BASE); p.pop("outcome")
  out=MVPJourneyOrchestrator().run(p)
  self.assertTrue(out.checks["outcome_learning_respects_configuration"])
 def test_completeness_bounds(self):
  with self.assertRaises(ValueError): DecisionCompletenessIndex().score(target_fit=1.1,diligence=.5,passport=.5,evidence_confidence=.5)
