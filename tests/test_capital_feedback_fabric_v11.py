import unittest

from federation.capital_execution.circuit_breaker import CapitalCircuitBreaker, CircuitSnapshot, CircuitState
from federation.capital_execution.failure_bridge import ExecutionFailureWinBridge
from federation.capital_execution.feedback import BacktestExecutionAssumption, BacktestRealityComparator, RealityCostObservation
from federation.capital_execution.luno_lona_bridge import LunoToLonaDataBridge
from federation.capital_execution.sovara_events import CapitalEventFactory
from federation.capital_execution.venues.base import VenueMarketObserver, observer_capabilities
from federation.capital_execution.venues.luno_public import LunoPublicRESTClient


class CapitalFeedbackFabricV11Tests(unittest.TestCase):
    def candles(self, count=10):
        return {"candles": [
            {"timestamp": 1800000000000 + i * 60000, "open": str(100 + i), "high": str(102 + i), "low": str(99 + i), "close": str(101 + i), "volume": str(10 + i)}
            for i in range(count)
        ]}

    def test_luno_normalization_is_deterministic_and_lona_eligibility_is_explicit(self):
        bridge = LunoToLonaDataBridge()
        a = bridge.normalize_candles(pair="XBTZAR", duration_seconds=60, payload=self.candles(10), source_ref="fixture:luno")
        b = bridge.normalize_candles(pair="XBTZAR", duration_seconds=60, payload=self.candles(10), source_ref="fixture:luno")
        self.assertEqual(a.fingerprint(), b.fingerprint())
        self.assertTrue(a.lona_upload_eligible)
        self.assertEqual(a.to_csv_text().splitlines()[0], "timestamp,open,high,low,close,volume")
        self.assertFalse(a.financial_effect)

    def test_less_than_ten_bars_is_normalized_but_not_lona_upload_eligible(self):
        dataset = LunoToLonaDataBridge().normalize_candles(pair="XBTZAR", duration_seconds=60, payload=self.candles(9), source_ref="fixture:luno")
        self.assertFalse(dataset.lona_upload_eligible)

    def test_invalid_ohlc_and_duplicate_timestamp_fail_closed(self):
        bad = self.candles(2)
        bad["candles"][0]["high"] = "50"
        with self.assertRaises(ValueError):
            LunoToLonaDataBridge().normalize_candles(pair="XBTZAR", duration_seconds=60, payload=bad, source_ref="fixture:luno")
        dup = self.candles(2)
        dup["candles"][1]["timestamp"] = dup["candles"][0]["timestamp"]
        with self.assertRaises(ValueError):
            LunoToLonaDataBridge().normalize_candles(pair="XBTZAR", duration_seconds=60, payload=dup, source_ref="fixture:luno")

    def test_backtest_reality_comparator_detects_cost_underestimation(self):
        delta = BacktestRealityComparator().compare(
            BacktestExecutionAssumption(commission_bps=10, slippage_bps=2),
            RealityCostObservation(spread_bps=20, shadow_slippage_bps=8, venue_fee_bps=10),
            tolerance_bps=5,
        )
        self.assertEqual(delta.status, "MODEL_UNDERESTIMATES_COSTS")
        self.assertGreater(delta.error_bps, 0)
        self.assertFalse(delta.financial_effect)

    def test_circuit_opens_on_reconciliation_failure_and_requires_verified_probe(self):
        breaker = CapitalCircuitBreaker()
        opened = breaker.observe(CircuitSnapshot(), ("RECONCILIATION_UNHEALTHY",))
        self.assertEqual(opened.state, CircuitState.OPEN)
        self.assertEqual(breaker.observe(opened, ()), opened)
        half = breaker.prepare_probe(opened)
        closed = breaker.close_after_verified_probe(half, reconciliation_healthy=True, venue_healthy=True)
        self.assertEqual(closed.state, CircuitState.CLOSED)

    def test_no_effect_event_is_deterministic_and_authority_smuggling_is_rejected(self):
        factory = CapitalEventFactory()
        a = factory.build(event_type="CAPITAL.CANDIDATE.REJECTED", source="CIOS", subject="s1", data={"reason":"benchmark"})
        b = factory.build(event_type="CAPITAL.CANDIDATE.REJECTED", source="CIOS", subject="s1", data={"reason":"benchmark"})
        self.assertEqual(a.digest(), b.digest())
        self.assertFalse(a.external_effect)
        self.assertFalse(hasattr(factory, "publish"))
        with self.assertRaises(PermissionError):
            factory.build(event_type="CAPITAL.INTENT.PREPARED", source="CIOS", subject="s1", data={"owner_capital_authority": True})

    def test_execution_failure_becomes_non_authoritative_material_mutation(self):
        proposal = ExecutionFailureWinBridge().propose(parent_id="parent", evidence_ref="receipt", reason_codes=("SLIPPAGE_LIMIT", "DEPTH_LIMIT"))
        self.assertEqual(set(proposal.changed_dimensions), {"execution_cost_model", "liquidity_sizing"})
        self.assertTrue(proposal.material_change_required)
        self.assertFalse(proposal.auto_promote)
        self.assertFalse(proposal.financial_effect)

    def test_luno_public_adapter_satisfies_observation_protocol_only(self):
        client = LunoPublicRESTClient(lambda path, params: {})
        self.assertIsInstance(client, VenueMarketObserver)
        caps = observer_capabilities(client, venue="LUNO")
        self.assertTrue(caps.public_market_data)
        self.assertFalse(caps.order_write)
        self.assertFalse(caps.withdrawal_write)
        self.assertFalse(caps.transfer_write)


if __name__ == "__main__":
    unittest.main()
