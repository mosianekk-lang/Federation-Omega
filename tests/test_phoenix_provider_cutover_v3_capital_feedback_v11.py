import unittest

from federation.capital_execution.circuit_breaker import CapitalCircuitBreaker, CircuitSnapshot, CircuitState
from federation.capital_execution.failure_bridge import ExecutionFailureWinBridge
from federation.capital_execution.feedback import BacktestExecutionAssumption, BacktestRealityComparator, RealityCostObservation
from federation.capital_execution.luno_lona_bridge import LunoToLonaDataBridge
from federation.capital_execution.sovara_events import CapitalEventFactory


class CapitalFeedbackV11AirlockTests(unittest.TestCase):
    def test_reality_cost_regression_cannot_self_promote(self):
        delta = BacktestRealityComparator().compare(
            BacktestExecutionAssumption(10, 0),
            RealityCostObservation(20, 10, 10),
        )
        self.assertEqual(delta.status, "MODEL_UNDERESTIMATES_COSTS")
        proposal = ExecutionFailureWinBridge().propose(parent_id="strategy", evidence_ref=delta.digest, reason_codes=("SLIPPAGE_LIMIT",))
        self.assertFalse(proposal.auto_promote)
        self.assertTrue(proposal.material_change_required)

    def test_reconciliation_failure_opens_circuit(self):
        state = CapitalCircuitBreaker().observe(CircuitSnapshot(), ("RECONCILIATION_UNHEALTHY",))
        self.assertEqual(state.state, CircuitState.OPEN)

    def test_sovara_surface_is_envelope_only(self):
        factory = CapitalEventFactory()
        event = factory.build(event_type="FAILURE.WIN.TRIGGERED", source="capital-feedback", subject="strategy", data={"mutation":"execution_cost_model"})
        self.assertFalse(event.external_effect)
        self.assertFalse(event.financial_effect)
        self.assertFalse(hasattr(factory, "publish"))

    def test_luno_to_lona_bridge_does_not_claim_upload(self):
        payload = {"candles": [{"timestamp": 1800000000000 + i * 60000, "open":"100", "high":"102", "low":"99", "close":"101", "volume":"10"} for i in range(10)]}
        dataset = LunoToLonaDataBridge().normalize_candles(pair="XBTZAR", duration_seconds=60, payload=payload, source_ref="fixture:luno")
        self.assertTrue(dataset.lona_upload_eligible)
        self.assertFalse(dataset.external_effect)
        self.assertFalse(dataset.financial_effect)
        self.assertFalse(hasattr(LunoToLonaDataBridge(), "upload"))


if __name__ == "__main__":
    unittest.main()
