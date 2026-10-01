from __future__ import annotations

import argparse
import asyncio
import json
import time

from federation.mobile_gateway.fuse_mobile_v1 import Capability
from services.fuse_mobile_gateway.runtime import GatewayRuntime, VerifiedIdentity


class SerializedProvider:
    def __init__(self, delay_seconds: float, ttl_seconds: int = 0) -> None:
        self.delay_seconds = delay_seconds
        self.ttl_seconds = ttl_seconds
        self.calls = 0
        self._gate = asyncio.Semaphore(1)

    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]:
        del identity
        async with self._gate:
            self.calls += 1
            await asyncio.sleep(self.delay_seconds)
            return (
                Capability(
                    "BENCH-CAP",
                    "MODEL_PROVIDER",
                    "bench://capability",
                    health="HEALTHY",
                    authority="SERVER_SIDE_ONLY",
                    freshness_ttl_seconds=self.ttl_seconds,
                ),
            )


async def run_baseline(concurrency: int, delay_seconds: float) -> tuple[float, int]:
    provider = SerializedProvider(delay_seconds)
    identity = VerifiedIdentity("bench-owner")
    started = time.perf_counter()
    await asyncio.gather(*(provider.capabilities(identity) for _ in range(concurrency)))
    return time.perf_counter() - started, provider.calls


async def run_accelerated(concurrency: int, delay_seconds: float) -> tuple[float, int, dict]:
    provider = SerializedProvider(delay_seconds)
    runtime = GatewayRuntime(health_provider=provider)
    identity = VerifiedIdentity("bench-owner")
    started = time.perf_counter()
    await asyncio.gather(*(runtime.manifest(identity) for _ in range(concurrency)))
    return time.perf_counter() - started, provider.calls, runtime.performance_snapshot()


async def main(concurrency: int, delay_seconds: float, target: float) -> int:
    baseline_s, baseline_calls = await run_baseline(concurrency, delay_seconds)
    accelerated_s, accelerated_calls, metrics = await run_accelerated(concurrency, delay_seconds)
    speedup = baseline_s / accelerated_s if accelerated_s > 0 else float("inf")
    receipt = {
        "schema": "SOL62_TENX_SYNTHETIC_BENCHMARK_V1",
        "scope": "CONCURRENT_IDENTICAL_CAPABILITY_CURRENTNESS_READS",
        "evidence_class": "SYNTHETIC_LOCAL_ONLY",
        "baseline_seconds": baseline_s,
        "accelerated_seconds": accelerated_s,
        "baseline_provider_reads": baseline_calls,
        "accelerated_provider_reads": accelerated_calls,
        "speedup": speedup,
        "target_speedup": target,
        "target_met": speedup >= target,
        "live_provider_verified": False,
        "owner_value_10x_verified": False,
        "metrics": metrics,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if speedup >= target else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--delay-ms", type=float, default=20.0)
    parser.add_argument("--target", type=float, default=10.0)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.concurrency, args.delay_ms / 1000.0, args.target)))
