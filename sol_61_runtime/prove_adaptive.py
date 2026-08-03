from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from adaptive import AdaptiveExecutionFabric, ProviderRoute
from runtime import digest, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    fabric = AdaptiveExecutionFabric(min_workers=1, max_workers=16, target_jobs_per_worker=3, scale_down_hysteresis=2)
    fabric.register_route(ProviderRoute("provider-a", "build", 1.2, 110, 0.995, 30, 4))
    fabric.register_route(ProviderRoute("provider-b", "build", 0.6, 210, 0.975, 60, 8))
    fabric.register_route(ProviderRoute("provider-c", "build", 0.3, 400, 0.90, 0, 2))

    gates = {}
    forecast = fabric.forecast_queue([3, 6, 10], horizon=1)
    scale = fabric.desired_workers(queued=10, running=2, current_workers=2, forecast=forecast)
    gates["workload_prediction"] = forecast > 10
    gates["dynamic_scale_out"] = scale["action"] == "SCALE_OUT" and scale["desired"] > 2

    first = fabric.route(capability="build", now_epoch=1, max_unit_cost=2, max_latency_ms=300, min_success_rate=0.95)
    gates["cost_aware_routing"] = first["selected"] in {"provider-a", "provider-b"}
    failed = first["selected"]
    for _ in range(4):
        fabric.record_outcome(failed, False)
    route = fabric.routes[failed]
    fabric.routes[failed] = ProviderRoute(**({**route.__dict__, "cooldown_until": 100}))
    fallback = fabric.route(capability="build", now_epoch=10, max_unit_cost=2, max_latency_ms=300, min_success_rate=0.95)
    gates["circuit_breaker"] = fabric.routes[failed].breaker_state == "OPEN"
    gates["provider_failover"] = fallback["selected"] not in {None, failed}

    paused = fabric.rate_limit_decision(quota_remaining=0, reset_seconds=45, queue_depth=8)
    throttled = fabric.rate_limit_decision(quota_remaining=3, reset_seconds=45, queue_depth=8)
    gates["rate_limit_pause"] = paused["action"] == "PAUSE_PROVIDER" and paused["retry_after"] == 45
    gates["rate_limit_failover"] = throttled["action"] == "THROTTLE_AND_FAILOVER"

    low1 = fabric.desired_workers(queued=0, running=0, current_workers=5, forecast=0)
    low2 = fabric.desired_workers(queued=0, running=0, current_workers=5, forecast=0)
    gates["scale_down_hysteresis"] = low1["action"] == "HOLD" and low2["action"] == "SCALE_IN"

    receipt = {
        "status": "ADAPTIVE_EXECUTION_VERIFIED" if all(gates.values()) else "ADAPTIVE_EXECUTION_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "evidence": {
            "forecast": forecast,
            "scale_plan": scale,
            "initial_route": first,
            "fallback_route": fallback,
            "paused": paused,
            "throttled": throttled,
        },
        "truth_boundary": {
            "github_actions_execution": True,
            "adaptive_reference_controller": True,
            "live_cloud_autoscaling": False,
            "live_provider_failover": False,
            "continuous_capacity_control": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-adaptive-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
