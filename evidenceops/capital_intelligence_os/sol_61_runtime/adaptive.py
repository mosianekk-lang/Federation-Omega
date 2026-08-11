from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderRoute:
    provider: str
    capability: str
    unit_cost: float
    latency_ms: float
    success_rate: float
    quota_remaining: int
    concurrency_limit: int
    active: int = 0
    breaker_state: str = "CLOSED"
    cooldown_until: int = 0


class AdaptiveExecutionFabric:
    """Deterministic reference controller for capacity, routing and failover."""

    def __init__(
        self,
        *,
        min_workers: int = 1,
        max_workers: int = 32,
        target_jobs_per_worker: int = 4,
        scale_down_hysteresis: int = 2,
    ) -> None:
        if not (1 <= min_workers <= max_workers):
            raise ValueError("invalid worker bounds")
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.target_jobs_per_worker = max(1, target_jobs_per_worker)
        self.scale_down_hysteresis = max(1, scale_down_hysteresis)
        self._low_load_cycles = 0
        self.routes: dict[str, ProviderRoute] = {}
        self.failures: dict[str, list[bool]] = {}

    def register_route(self, route: ProviderRoute) -> None:
        if not 0 <= route.success_rate <= 1:
            raise ValueError("success_rate outside range")
        if route.unit_cost < 0 or route.latency_ms < 0:
            raise ValueError("negative route metric")
        self.routes[route.provider] = route
        self.failures.setdefault(route.provider, [])

    @staticmethod
    def forecast_queue(samples: list[int], horizon: int = 1) -> int:
        if not samples:
            return 0
        if len(samples) == 1:
            return max(0, samples[0])
        deltas = [right - left for left, right in zip(samples, samples[1:])]
        weighted = sum((index + 1) * value for index, value in enumerate(deltas)) / sum(range(1, len(deltas) + 1))
        return max(0, round(samples[-1] + weighted * max(1, horizon)))

    def desired_workers(self, *, queued: int, running: int, current_workers: int, forecast: int) -> dict[str, Any]:
        demand = max(queued + running, forecast + running)
        desired = math.ceil(demand / self.target_jobs_per_worker) if demand else self.min_workers
        desired = min(self.max_workers, max(self.min_workers, desired))
        if desired < current_workers:
            self._low_load_cycles += 1
            if self._low_load_cycles < self.scale_down_hysteresis:
                desired = current_workers
        else:
            self._low_load_cycles = 0
        return {
            "current": current_workers,
            "desired": desired,
            "action": "SCALE_OUT" if desired > current_workers else "SCALE_IN" if desired < current_workers else "HOLD",
            "forecast": forecast,
            "demand": demand,
        }

    def record_outcome(self, provider: str, success: bool, *, window: int = 8, failure_threshold: float = 0.5) -> str:
        history = self.failures.setdefault(provider, [])
        history.append(bool(success))
        del history[:-window]
        failures = sum(not item for item in history)
        state = "OPEN" if len(history) >= 4 and failures / len(history) >= failure_threshold else "CLOSED"
        route = self.routes[provider]
        self.routes[provider] = ProviderRoute(**(asdict(route) | {"breaker_state": state}))
        return state

    def half_open(self, provider: str) -> None:
        route = self.routes[provider]
        self.routes[provider] = ProviderRoute(**(asdict(route) | {"breaker_state": "HALF_OPEN"}))

    def route(
        self,
        *,
        capability: str,
        now_epoch: int,
        max_unit_cost: float,
        max_latency_ms: float,
        min_success_rate: float,
    ) -> dict[str, Any]:
        eligible = []
        rejected: dict[str, str] = {}
        for route in self.routes.values():
            if route.capability != capability:
                continue
            if route.breaker_state == "OPEN" and now_epoch < route.cooldown_until:
                rejected[route.provider] = "CIRCUIT_OPEN"
                continue
            if route.quota_remaining <= 0:
                rejected[route.provider] = "RATE_LIMITED"
                continue
            if route.active >= route.concurrency_limit:
                rejected[route.provider] = "SATURATED"
                continue
            if route.unit_cost > max_unit_cost:
                rejected[route.provider] = "COST_LIMIT"
                continue
            if route.latency_ms > max_latency_ms:
                rejected[route.provider] = "LATENCY_LIMIT"
                continue
            if route.success_rate < min_success_rate:
                rejected[route.provider] = "RELIABILITY_LIMIT"
                continue
            score = (
                route.success_rate * 100
                - route.unit_cost * 12
                - route.latency_ms / 50
                + min(route.quota_remaining, 100) / 20
                - route.active * 2
                + (2 if route.breaker_state == "CLOSED" else -5)
            )
            eligible.append((score, route))
        if not eligible:
            return {"selected": None, "state": "NO_ELIGIBLE_ROUTE", "rejected": rejected}
        eligible.sort(key=lambda item: (-item[0], item[1].provider))
        score, selected = eligible[0]
        return {
            "selected": selected.provider,
            "state": "ROUTED",
            "score": round(score, 4),
            "rejected": rejected,
        }

    @staticmethod
    def rate_limit_decision(*, quota_remaining: int, reset_seconds: int, queue_depth: int) -> dict[str, Any]:
        if quota_remaining <= 0:
            return {"action": "PAUSE_PROVIDER", "retry_after": max(1, reset_seconds)}
        if queue_depth > quota_remaining:
            return {"action": "THROTTLE_AND_FAILOVER", "safe_batch": max(1, quota_remaining)}
        if quota_remaining < 5:
            return {"action": "THROTTLE", "safe_batch": 1}
        return {"action": "CONTINUE", "safe_batch": min(queue_depth, quota_remaining)}
