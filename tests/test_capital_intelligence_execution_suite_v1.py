import unittest
from decimal import Decimal

from evidenceops.capital_intelligence_os.capital_intent import CapitalIntentEngine, QuantResearchEvidence
from evidenceops.capital_intelligence_os.portfolio_intelligence import PortfolioCandidate, PortfolioIntelligenceEngine
from federation.capital_execution.capital_constitution import CapitalConstitution, CapitalGateState
from federation.capital_execution.digital_twin import ExecutionDigitalTwin
from federation.capital_execution.models import BookLevel, MarketSnapshot, ShadowOrderRequest
from federation.capital_execution.reconciliation import ShadowReconciler
from federation.capital_execution.risk_governor import CapitalRiskGovernor, RiskContext, RiskLimits
from federation.capital_execution.venues.luno_public import LunoPublicRESTClient


class CapitalIntelligenceExecutionSuiteV1Tests(unittest.TestCase):
    def admitted_evidence(self, *, expected=20.0, benchmark=10.0, strategy="s1"):
        return QuantResearchEvidence(
            strategy_id=strategy,
            instrument_id="XBTZAR",
            evidence_ref=f"evidence:{strategy}",
            research_state="RESEARCH_ADMITTED",
            expected_return_pct=expected,
            benchmark_return_pct=benchmark,
            maximum_drawdown_pct=12.0,
            sharpe_ratio=1.2,
            sample_trades=24,
            robustness_score=0.82,
            regime_fit=0.75,
            liquidity_quality=0.80,
            uncertainty=0.10,
        )

    def snapshot(self):
        return MarketSnapshot(
            venue="LUNO",
            pair="XBTZAR",
            bids=(BookLevel(Decimal("999"), Decimal("2")), BookLevel(Decimal("998"), Decimal("5"))),
            asks=(BookLevel(Decimal("1001"), Decimal("2")), BookLevel(Decimal("1002"), Decimal("5"))),
            timestamp_ms=1_800_000_000_000,
            source_ref="fixture:luno-orderbook-top",
        )

    def test_current_g1_style_underperformer_is_rejected_for_capital(self):
        evidence = self.admitted_evidence(expected=7.35, benchmark=63.51, strategy="g1-openrouter")
        decision = PortfolioIntelligenceEngine().allocate(
            portfolio_id="p1",
            candidates=[PortfolioCandidate(evidence)],
        )
        self.assertEqual(decision.allocations, ())
        self.assertIn("NO_POSITIVE_EXCESS_RETURN", decision.rejected["g1-openrouter"])
        self.assertEqual(decision.cash_weight, 1.0)

    def test_non_admitted_research_cannot_become_capital_intent(self):
        evidence = self.admitted_evidence()
        evidence = QuantResearchEvidence(**{**evidence.__dict__, "research_state": "EVIDENCE_VERIFIED"})
        with self.assertRaises(PermissionError):
            CapitalIntentEngine().prepare(
                portfolio_id="p1",
                evidence=evidence,
                target_weight=0.04,
                maximum_weight=0.06,
                confidence=0.8,
                expires_at="2026-08-28T20:00:00+00:00",
            )

    def test_admitted_candidate_produces_non_executable_capital_intent(self):
        evidence = self.admitted_evidence()
        decision = PortfolioIntelligenceEngine().allocate(
            portfolio_id="p1",
            candidates=[PortfolioCandidate(evidence)],
            maximum_invested_weight=0.10,
            maximum_single_weight=0.06,
        )
        self.assertEqual(len(decision.allocations), 1)
        allocation = decision.allocations[0]
        intent = CapitalIntentEngine().prepare(
            portfolio_id="p1",
            evidence=evidence,
            target_weight=allocation.target_weight,
            maximum_weight=0.06,
            confidence=0.8,
            expires_at="2026-08-28T20:00:00+00:00",
            constraints={"maximum_slippage_bps": 25},
        )
        self.assertFalse(intent.executable)
        self.assertFalse(intent.financial_effect)
        self.assertEqual(intent.strategy_id, evidence.strategy_id)

    def test_capital_intent_rejects_exchange_order_fields(self):
        evidence = self.admitted_evidence()
        with self.assertRaises(PermissionError):
            CapitalIntentEngine().prepare(
                portfolio_id="p1",
                evidence=evidence,
                target_weight=0.04,
                maximum_weight=0.06,
                confidence=0.8,
                expires_at="2026-08-28T20:00:00+00:00",
                constraints={"limit_price": 1000},
            )

    def test_digital_twin_walks_depth_without_provider_effect(self):
        request = ShadowOrderRequest("intent", "XBTZAR", "BUY", Decimal("3"), Decimal("20"))
        fill = ExecutionDigitalTwin().simulate(request, self.snapshot())
        self.assertEqual(fill.status, "FILLED")
        self.assertEqual(fill.filled_base_volume, Decimal("3"))
        self.assertFalse(fill.external_effect)
        self.assertFalse(fill.financial_effect)
        self.assertEqual(fill.depth_levels_used, 2)

    def test_risk_governor_is_independent_fail_closed(self):
        context = RiskContext(
            desired_position_weight=0.04,
            order_notional=1000,
            spread_bps=15,
            simulated_slippage_bps=5,
            depth_ratio=3.0,
            daily_loss_pct=0.1,
            drawdown_pct=1.0,
            market_age_seconds=2.0,
            venue_healthy=True,
            reconciliation_healthy=True,
        )
        self.assertTrue(CapitalRiskGovernor().evaluate(context, RiskLimits()).allowed)
        blocked = CapitalRiskGovernor().evaluate(RiskContext(**{**context.__dict__, "mode": "LIVE"}), RiskLimits())
        self.assertFalse(blocked.allowed)
        self.assertIn("V1_SHADOW_MODE_ONLY", blocked.reason_codes)

    def test_luno_adapter_is_public_read_only(self):
        def fake_transport(path, params):
            self.assertEqual(path, "/api/1/orderbook_top")
            self.assertEqual(params["pair"], "XBTZAR")
            return {
                "timestamp": 1_800_000_000_000,
                "bids": [{"price": "999", "volume": "2"}],
                "asks": [{"price": "1001", "volume": "2"}],
            }

        client = LunoPublicRESTClient(fake_transport)
        snapshot = client.snapshot("XBTZAR")
        self.assertEqual(snapshot.venue, "LUNO")
        with self.assertRaises(PermissionError):
            client.create_order(pair="XBTZAR")
        with self.assertRaises(PermissionError):
            client.cancel_order(order_id="x")
        with self.assertRaises(PermissionError):
            client.convert(from_currency="ZAR", to_currency="XBT")

    def test_reconciliation_binds_request_snapshot_and_fill(self):
        request = ShadowOrderRequest("intent", "XBTZAR", "BUY", Decimal("1"), Decimal("20"))
        snapshot = self.snapshot()
        fill = ExecutionDigitalTwin().simulate(request, snapshot)
        receipt = ShadowReconciler().reconcile(request=request, snapshot=snapshot, fill=fill)
        self.assertEqual(receipt.status, "MATCH")
        self.assertFalse(receipt.provider_effect_verified)
        self.assertFalse(receipt.financial_effect)

    def test_capital_constitution_allows_shadow_but_hard_blocks_live(self):
        base = CapitalGateState(True, True, True, True, True, True)
        self.assertTrue(CapitalConstitution().evaluate(base).allowed)
        live = CapitalGateState(True, True, True, True, True, True, True, True, "LIVE")
        decision = CapitalConstitution().evaluate(live)
        self.assertFalse(decision.allowed)
        self.assertIn("LIVE_CAPITAL_HARD_DISABLED_V1", decision.reason_codes)

    def test_end_to_end_shadow_chain(self):
        evidence = self.admitted_evidence()
        allocation = PortfolioIntelligenceEngine().allocate(
            portfolio_id="p1",
            candidates=[PortfolioCandidate(evidence)],
            maximum_invested_weight=0.05,
            maximum_single_weight=0.05,
        ).allocations[0]
        intent = CapitalIntentEngine().prepare(
            portfolio_id="p1",
            evidence=evidence,
            target_weight=allocation.target_weight,
            maximum_weight=0.05,
            confidence=0.8,
            expires_at="2026-08-28T20:00:00+00:00",
        )
        snapshot = self.snapshot()
        request = ShadowOrderRequest(intent.intent_id, "XBTZAR", "BUY", Decimal("1"), Decimal("20"))
        fill = ExecutionDigitalTwin().simulate(request, snapshot)
        reconciliation = ShadowReconciler().reconcile(request=request, snapshot=snapshot, fill=fill)
        risk = CapitalRiskGovernor().evaluate(
            RiskContext(
                desired_position_weight=intent.target_weight,
                order_notional=float(fill.gross_counter_value),
                spread_bps=float(snapshot.spread_bps),
                simulated_slippage_bps=float(fill.slippage_bps or 0),
                depth_ratio=2.0,
                daily_loss_pct=0.0,
                drawdown_pct=0.0,
                market_age_seconds=1.0,
                venue_healthy=True,
                reconciliation_healthy=reconciliation.status == "MATCH",
            )
        )
        gate = CapitalConstitution().evaluate(
            CapitalGateState(True, True, risk.allowed, True, reconciliation.status == "MATCH", True)
        )
        self.assertTrue(gate.allowed)
        self.assertEqual(reconciliation.status, "MATCH")
        self.assertFalse(fill.financial_effect)


if __name__ == "__main__":
    unittest.main()
