import unittest
from decimal import Decimal

from evidenceops.capital_intelligence_os.capital_intent import CapitalIntentEngine, QuantResearchEvidence
from evidenceops.capital_intelligence_os.portfolio_intelligence import PortfolioCandidate, PortfolioIntelligenceEngine
from federation.capital_execution.capital_constitution import CapitalConstitution, CapitalGateState
from federation.capital_execution.digital_twin import ExecutionDigitalTwin
from federation.capital_execution.models import BookLevel, MarketSnapshot, ShadowOrderRequest
from federation.capital_execution.reconciliation import ShadowReconciler
from federation.capital_execution.venues.luno_public import LunoPublicRESTClient


class CapitalExecutionSuiteAirlockBridgeTests(unittest.TestCase):
    def test_benchmark_failure_cannot_become_capital_allocation(self):
        evidence = QuantResearchEvidence(
            strategy_id="g1-openrouter",
            instrument_id="XBTZAR",
            evidence_ref="lona:g1-openrouter",
            research_state="RESEARCH_ADMITTED",
            expected_return_pct=7.35,
            benchmark_return_pct=63.51,
            maximum_drawdown_pct=10.0,
            sharpe_ratio=1.0,
            sample_trades=20,
            robustness_score=0.8,
            regime_fit=0.8,
            liquidity_quality=0.8,
        )
        decision = PortfolioIntelligenceEngine().allocate(
            portfolio_id="airlock",
            candidates=[PortfolioCandidate(evidence)],
        )
        self.assertEqual(decision.allocations, ())
        self.assertIn("NO_POSITIVE_EXCESS_RETURN", decision.rejected["g1-openrouter"])

    def test_cios_intent_never_becomes_exchange_order(self):
        evidence = QuantResearchEvidence(
            strategy_id="candidate",
            instrument_id="XBTZAR",
            evidence_ref="receipt:candidate",
            research_state="RESEARCH_ADMITTED",
            expected_return_pct=20.0,
            benchmark_return_pct=10.0,
            maximum_drawdown_pct=10.0,
            sharpe_ratio=1.2,
            sample_trades=20,
            robustness_score=0.8,
            regime_fit=0.8,
            liquidity_quality=0.8,
        )
        intent = CapitalIntentEngine().prepare(
            portfolio_id="airlock",
            evidence=evidence,
            target_weight=0.02,
            maximum_weight=0.04,
            confidence=0.8,
            expires_at="2026-08-28T20:00:00+00:00",
        )
        self.assertFalse(intent.executable)
        self.assertFalse(intent.financial_effect)

    def test_shadow_execution_reconciles_without_provider_effect(self):
        snapshot = MarketSnapshot(
            venue="LUNO",
            pair="XBTZAR",
            bids=(BookLevel(Decimal("999"), Decimal("2")),),
            asks=(BookLevel(Decimal("1001"), Decimal("2")),),
            timestamp_ms=1_800_000_000_000,
            source_ref="fixture:luno",
        )
        request = ShadowOrderRequest("intent", "XBTZAR", "BUY", Decimal("1"), Decimal("20"))
        fill = ExecutionDigitalTwin().simulate(request, snapshot)
        receipt = ShadowReconciler().reconcile(request=request, snapshot=snapshot, fill=fill)
        self.assertEqual(receipt.status, "MATCH")
        self.assertFalse(fill.financial_effect)
        self.assertFalse(receipt.provider_effect_verified)

    def test_luno_write_and_live_capital_are_both_fail_closed(self):
        client = LunoPublicRESTClient(lambda path, params: {})
        with self.assertRaises(PermissionError):
            client.create_order(pair="XBTZAR")
        decision = CapitalConstitution().evaluate(
            CapitalGateState(True, True, True, True, True, True, True, True, "LIVE")
        )
        self.assertFalse(decision.allowed)
        self.assertIn("LIVE_CAPITAL_HARD_DISABLED_V1", decision.reason_codes)


if __name__ == "__main__":
    unittest.main()
