from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from evidenceops.capital_intelligence_os.market_algorithms import AnnouncementMoveDecomposer, DealFragilitySurface, LiquidityStressPenalty, PortfolioConcentrationRadar, SignalDivergenceIndex, SpreadPersistenceMonitor, TransactionWindowRadar
from evidenceops.capital_intelligence_os.market_intelligence import DealCompletionProbabilityEngine, ExposureImpactBridge, FinancingMarketRadar, FundamentalSignal, MarketDealTerms, MarketTruthGate, MarketTwin, PublicMarketObservation, PublicTradingIntelligenceBridge, RegimeAwareValuationEngine, RegimeScenario
from evidenceops.capital_intelligence_os.market_service import MarketIntelligenceService
from evidenceops.capital_intelligence_os.models import Claim, Domain, EvidenceRef, EvidenceStatus, InformationClass

class StaticAdapter:
    def __init__(self, values): self.values=values
    def observations(self): return list(self.values)

def obs(value=100, info=InformationClass.PUBLIC, observed_at=None):
    return PublicMarketObservation("provider-public","ABC","price",value,observed_at or datetime.now(timezone.utc).isoformat(),"provider:ABC",currency="ZAR",information_class=info)

class MarketTruthTests(unittest.TestCase):
    def test_public_observation_converts_to_verified_claim(self):
        c=MarketTruthGate().to_claim(obs()); self.assertEqual(c.status,EvidenceStatus.VERIFIED); self.assertEqual(c.domain,Domain.PUBLIC_MARKETS); self.assertEqual(c.information_class,InformationClass.PUBLIC); self.assertTrue(c.evidence)
    def test_non_public_observation_is_rejected(self):
        with self.assertRaises(PermissionError): MarketTruthGate().accept(obs(info=InformationClass.CONFIDENTIAL))
    def test_market_event_is_public_only(self):
        e=MarketTruthGate().to_event(obs(),.8); self.assertEqual(e.domain,Domain.PUBLIC_MARKETS); self.assertEqual(e.information_class,InformationClass.PUBLIC); self.assertEqual(e.materiality,.8)
    def test_market_twin_deduplicates_and_keeps_latest(self):
        t=MarketTwin(); now=datetime.now(timezone.utc); old=obs(90,InformationClass.PUBLIC,(now-timedelta(days=1)).isoformat()); new=obs(100,InformationClass.PUBLIC,now.isoformat()); self.assertEqual(t.ingest([old,new,new]),2); self.assertEqual(t.latest("ABC","price").value,100)
    def test_market_twin_freshness(self):
        t=MarketTwin(); now=datetime.now(timezone.utc); t.ingest([obs(100,observed_at=(now-timedelta(days=2)).isoformat())]); self.assertAlmostEqual(t.freshness_days("ABC","price",now),2,places=4)
    def test_public_bridge_rejects_private_input(self):
        bridge=PublicTradingIntelligenceBridge(StaticAdapter([obs()])); c=Claim("co","x",1,EvidenceStatus.VERIFIED,[EvidenceRef("s","d","l")],InformationClass.CONFIDENTIAL,Domain.PRIVATE_MNA,.9)
        with self.assertRaises(PermissionError): bridge.private_claim_to_market(c)
    def test_public_bridge_accepts_public_adapter(self): self.assertEqual(len(PublicTradingIntelligenceBridge(StaticAdapter([obs()])).read_public_evidence()),1)
    def test_bridge_rejects_adapter_returning_private_data(self):
        with self.assertRaises(PermissionError): PublicTradingIntelligenceBridge(StaticAdapter([obs(info=InformationClass.CONFIDENTIAL)])).read_public_evidence()
    def test_bridge_has_no_order_interface(self):
        bridge=PublicTradingIntelligenceBridge(StaticAdapter([obs()])); self.assertFalse(hasattr(bridge,"place_order")); self.assertFalse(hasattr(bridge,"transfer"))

class ProbabilityTests(unittest.TestCase):
    def setUp(self): self.e=DealCompletionProbabilityEngine()
    def test_fundamental_is_reliability_weighted(self): self.assertAlmostEqual(self.e.fundamental([FundamentalSignal("reg",.8,1),FundamentalSignal("fin",.4,.5)]),2/3)
    def test_fundamental_zero_reliability_rejected(self):
        with self.assertRaises(ValueError): self.e.fundamental([FundamentalSignal("x",.5,0)])
    def test_market_proxy_is_bounded(self): self.assertAlmostEqual(self.e.market_implied_proxy(MarketDealTerms(95,100,70,0,0)),(95-70)/(100-70))
    def test_market_proxy_invalid_downside_rejected(self):
        with self.assertRaises(ValueError): self.e.market_implied_proxy(MarketDealTerms(100,90,95,0,0))
    def test_expectation_gap_keeps_direction(self): self.assertAlmostEqual(self.e.expectation_gap(.8,.6),.2)

class RegimeAndExposureTests(unittest.TestCase):
    def test_regime_wacc_and_multiple(self):
        r=RegimeAwareValuationEngine().scenario(base_wacc=.10,base_terminal_multiple=8,scenario=RegimeScenario("tight",.01,.02,.01,-.1,.4)); self.assertAlmostEqual(r["wacc"],.14); self.assertAlmostEqual(r["terminal_multiple"],7.2)
    def test_expected_regime_parameters(self):
        e=RegimeAwareValuationEngine(); a=e.scenario(base_wacc=.1,base_terminal_multiple=8,scenario=RegimeScenario("a",0,0,0,0,.5)); b=e.scenario(base_wacc=.1,base_terminal_multiple=8,scenario=RegimeScenario("b",.02,0,0,-.25,.5)); x=e.expected_parameters([a,b]); self.assertAlmostEqual(x["expected_wacc"],.11); self.assertAlmostEqual(x["expected_terminal_multiple"],7)
    def test_exposure_bridge(self): self.assertAlmostEqual(ExposureImpactBridge().impact({"fx":10,"oil":-4},{"fx":.2,"oil":.5})["TOTAL"],0)
    def test_financing_radar(self): self.assertEqual(FinancingMarketRadar().annual_cost_delta(100_000_000,.02,.01,.005),2_500_000)

class MarketAlgorithmTests(unittest.TestCase):
    def test_signal_divergence(self): self.assertAlmostEqual(SignalDivergenceIndex().score(.9,.5,.8),.32)
    def test_fragility_interaction(self): self.assertGreater(DealFragilitySurface().score(financing_stress=1,regulatory_uncertainty=1,market_volatility=.5,synergy_dependence=1,leverage=1),.9)
    def test_transaction_window_is_bounded(self): self.assertEqual(TransactionWindowRadar().score(valuation_attractiveness=1,financing_availability=1,volatility_inverse=1,buyer_activity=1,strategic_urgency=1),1)
    def test_abnormal_move_is_math_not_causation(self): self.assertAlmostEqual(AnnouncementMoveDecomposer().abnormal_return(.1,.03,1.2),.064)
    def test_portfolio_concentration(self): self.assertAlmostEqual(PortfolioConcentrationRadar().herfindahl([50,50]),.5)
    def test_spread_persistence(self): self.assertEqual(SpreadPersistenceMonitor().persistence([.1,.2,.3])["sign_persistence"],1)
    def test_liquidity_penalty_rises_with_stress(self): self.assertGreater(LiquidityStressPenalty().penalty(spread_pct=.05,turnover_ratio=.1,volatility=.8),.8)

class MarketServiceTests(unittest.TestCase):
    def test_assessment_keeps_fundamental_and_market_views_separate(self):
        a=MarketIntelligenceService().assess_deal([FundamentalSignal("reg",.9,1)],MarketDealTerms(95,100,70,0,0),financing_stress=.2,regulatory_uncertainty=.2,market_volatility=.2,synergy_dependence=.2,leverage=.2,evidence_confidence=.9)
        self.assertAlmostEqual(a.fundamental_probability,.9); self.assertNotEqual(a.expectation_gap,0); self.assertTrue(a.caveats)

if __name__ == "__main__": unittest.main()
