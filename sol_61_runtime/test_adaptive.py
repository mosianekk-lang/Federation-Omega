from __future__ import annotations

import unittest

from adaptive import AdaptiveExecutionFabric, ProviderRoute


class AdaptiveExecutionFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = AdaptiveExecutionFabric(min_workers=1, max_workers=10, target_jobs_per_worker=2, scale_down_hysteresis=2)
        self.fabric.register_route(ProviderRoute("primary", "build", 1.0, 120, 0.99, 20, 4))
        self.fabric.register_route(ProviderRoute("secondary", "build", 0.5, 220, 0.97, 50, 8))

    def test_forecast_and_scaling_with_hysteresis(self) -> None:
        forecast = self.fabric.forecast_queue([2, 4, 7])
        self.assertGreaterEqual(forecast, 9)
        plan = self.fabric.desired_workers(queued=7, running=1, current_workers=2, forecast=forecast)
        self.assertEqual(plan["action"], "SCALE_OUT")
        hold = self.fabric.desired_workers(queued=0, running=0, current_workers=5, forecast=0)
        self.assertEqual(hold["action"], "HOLD")
        scale_in = self.fabric.desired_workers(queued=0, running=0, current_workers=5, forecast=0)
        self.assertEqual(scale_in["action"], "SCALE_IN")

    def test_cost_aware_routing_and_failover(self) -> None:
        chosen = self.fabric.route(capability="build", now_epoch=1, max_unit_cost=2, max_latency_ms=300, min_success_rate=0.95)
        self.assertIn(chosen["selected"], {"primary", "secondary"})
        for _ in range(4):
            self.fabric.record_outcome(chosen["selected"], False)
        failed = chosen["selected"]
        route = self.fabric.routes[failed]
        self.fabric.routes[failed] = ProviderRoute(**({**route.__dict__, "cooldown_until": 100}))
        fallback = self.fabric.route(capability="build", now_epoch=10, max_unit_cost=2, max_latency_ms=300, min_success_rate=0.95)
        self.assertNotEqual(fallback["selected"], failed)

    def test_rate_limit_governance(self) -> None:
        self.assertEqual(self.fabric.rate_limit_decision(quota_remaining=0, reset_seconds=30, queue_depth=10)["action"], "PAUSE_PROVIDER")
        self.assertEqual(self.fabric.rate_limit_decision(quota_remaining=3, reset_seconds=30, queue_depth=10)["action"], "THROTTLE_AND_FAILOVER")
        self.assertEqual(self.fabric.rate_limit_decision(quota_remaining=10, reset_seconds=30, queue_depth=4)["action"], "CONTINUE")


if __name__ == "__main__":
    unittest.main()
