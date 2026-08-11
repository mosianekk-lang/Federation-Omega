from __future__ import annotations
import unittest
from evidenceops.capital_intelligence_os.valuation import DCFEngine,ForecastCashFlow,EquityBridge,ComparableValuationEngine,ReturnEngine,PurchasePriceBridge
from evidenceops.capital_intelligence_os.qoe import EBITDAAdjustment,QualityOfEarningsEngine,WorkingCapitalNormalizer,DebtLikeItem,DebtLikeEngine
from evidenceops.capital_intelligence_os.diligence import DiligenceEngine,DiligenceRequirement,AnswerSufficiencyScorer,DiligenceMaterialityRouter
from evidenceops.capital_intelligence_os.integration import SynergyCommitment,SynergyLedger,IntegrationMilestone,DayOneReadiness,ValueLeakageDetector
from evidenceops.capital_intelligence_os.workspace import ReadinessDimension,SaleReadinessEngine,NextAction,NextBestActionEngine,DecisionBriefBuilder
class ValuationTests(unittest.TestCase):
    def test_dcf_known_case(self):
        r=DCFEngine().value([ForecastCashFlow(1,100),ForecastCashFlow(2,110)],.10,.03); self.assertGreater(r.enterprise_value,1000); self.assertAlmostEqual(r.enterprise_value,r.pv_explicit_cash_flows+r.pv_terminal_value)
    def test_dcf_rejects_growth_at_or_above_wacc(self):
        with self.assertRaises(ValueError): DCFEngine().value([ForecastCashFlow(1,100)],.05,.05)
    def test_sensitivity_invalid_cell_is_none(self): self.assertIsNone(DCFEngine().sensitivity([ForecastCashFlow(1,100)],[.05],[.06])[(.05,.06)])
    def test_equity_bridge(self): self.assertEqual(EquityBridge(1000,cash=100,debt=300,debt_like=50,non_operating_assets=20).equity_value(),770)
    def test_comparable_median(self): self.assertEqual(ComparableValuationEngine().implied_enterprise_value(10,[5,7,9])['implied_enterprise_value'],70)
    def test_moic(self): self.assertEqual(ReturnEngine().moic(100,250),2.5)
    def test_irr(self): self.assertAlmostEqual(ReturnEngine().irr([-100,0,121]),.1,places=5)
    def test_purchase_price_bridge(self): self.assertEqual(PurchasePriceBridge().equity_purchase_price(1000,100,300,50,20),770)
class QoETests(unittest.TestCase):
    def test_normalized_ebitda_confidence_gate(self):
        r=QualityOfEarningsEngine().normalize_ebitda(100,[EBITDAAdjustment('a','owner cost',20,False,.9),EBITDAAdjustment('b','weak',50,False,.2)]); self.assertEqual(r['normalized_ebitda'],120); self.assertEqual(r['excluded_low_confidence_ids'],['b'])
    def test_recurring_quality_ratio_bounded(self): self.assertEqual(QualityOfEarningsEngine().recurring_quality_ratio(120,100),1)
    def test_working_capital_median(self): self.assertEqual(WorkingCapitalNormalizer().target([10,100,20]),20)
    def test_working_capital_adjustment(self): self.assertEqual(WorkingCapitalNormalizer().adjustment(30,20),10)
    def test_debt_like_confidence_gate(self): self.assertEqual(DebtLikeEngine().total([DebtLikeItem('a',10,.9),DebtLikeItem('b',20,.2)])['total_debt_like'],10)
class DiligenceTests(unittest.TestCase):
    def test_standard_profile_missing_is_materiality_sorted(self):
        e=DiligenceEngine(); gaps=e.missing(e.standard_profile(),['management accounts']); self.assertGreaterEqual(gaps[0].materiality,gaps[-1].materiality)
    def test_completeness_improves_with_documents(self):
        e=DiligenceEngine(); p=e.standard_profile(); self.assertGreater(e.completeness(p,['audited financial statements','management accounts']),e.completeness(p,[]))
    def test_question_is_generated(self): self.assertIn('contract',DiligenceEngine().missing([DiligenceRequirement('x','LEGAL','contract',1,'obligations')],[])[0].question.lower())
    def test_answer_sufficiency(self): self.assertTrue(AnswerSufficiencyScorer().score('Revenue is 10 and margin is 20',['revenue','margin'])['sufficient'])
    def test_materiality_router(self): self.assertEqual(DiligenceMaterialityRouter().lane(1,1),'CRITICAL')
class IntegrationTests(unittest.TestCase):
    def test_synergy_realization(self): self.assertEqual(SynergyLedger().realization([SynergyCommitment('a','cost',100,60),SynergyCommitment('b','revenue',100,40)])['realization_ratio'],.5)
    def test_day_one_weights_critical(self): self.assertAlmostEqual(DayOneReadiness().score([IntegrationMilestone('a',1,True,True),IntegrationMilestone('b',1,False,False)]),2/3)
    def test_value_leakage(self): self.assertEqual(ValueLeakageDetector().detect(100,80,10)['leakage'],30)
class WorkspaceTests(unittest.TestCase):
    def test_readiness_owner_summary_and_issues(self):
        r=SaleReadinessEngine().assess([ReadinessDimension('financials',.9,2,'good'),ReadinessDimension('customer concentration',.3,2,'weak'),ReadinessDimension('ip',.7,1,'ok')]); self.assertIn('transaction-ready',r.owner_summary); self.assertEqual(r.top_issues[0],'customer concentration')
    def test_next_action_prefers_high_impact_low_effort(self): self.assertEqual(NextBestActionEngine().rank([NextAction('a','Fix contracts',1,.9,.2,.8),NextAction('b','Cosmetic',.2,.9,.1,.2)])[0][0].action_id,'a')
    def test_irreversible_action_is_penalized(self): self.assertEqual(NextBestActionEngine().rank([NextAction('a','rev',.8,.8,.2,.5,True),NextAction('b','irrev',.8,.8,.2,.5,False)])[0][0].action_id,'a')
    def test_decision_brief_preserves_fact_assumption_separation(self):
        b=DecisionBriefBuilder().build(title='Acquire',verified_facts=['Revenue 10'],assumptions=['Growth 5%'],risks=['Customer concentration'],alternatives=['No deal'],recommendation='Review'); self.assertEqual(b['verified_facts'],['Revenue 10']); self.assertEqual(b['assumptions'],['Growth 5%']); self.assertTrue(b['requires_human_decision'])
if __name__=='__main__': unittest.main()
