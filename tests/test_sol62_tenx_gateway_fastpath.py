from __future__ import annotations

import asyncio
import unittest

from federation.mobile_gateway.fuse_mobile_v1 import Capability
from services.fuse_mobile_gateway.runtime import GatewayRuntime, VerifiedIdentity


class CountingHealth:
    def __init__(self, *, ttl_seconds: int, delay_seconds: float = 0.01) -> None:
        self.ttl_seconds = ttl_seconds
        self.delay_seconds = delay_seconds
        self.calls = 0

    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]:
        del identity
        self.calls += 1
        await asyncio.sleep(self.delay_seconds)
        return (
            Capability(
                "TEST-CAP",
                "MODEL_PROVIDER",
                "test://capability",
                health="HEALTHY",
                authority="SERVER_SIDE_ONLY",
                freshness_ttl_seconds=self.ttl_seconds,
            ),
        )


class Sol62TenXFastPathTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_identical_manifest_reads_are_singleflight(self) -> None:
        provider = CountingHealth(ttl_seconds=0)
        runtime = GatewayRuntime(health_provider=provider)
        identity = VerifiedIdentity("owner-1", {"tenant": "fuse"})

        results = await asyncio.gather(*(runtime.manifest(identity) for _ in range(24)))

        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(results), 24)
        metrics = runtime.performance_snapshot()
        self.assertEqual(metrics["capability_provider_reads"], 1)
        self.assertEqual(metrics["capability_singleflight_joins"], 23)
        self.assertEqual(metrics["capability_cache_hits"], 0)

    async def test_provider_advertised_freshness_enables_sequential_cache(self) -> None:
        provider = CountingHealth(ttl_seconds=2, delay_seconds=0)
        runtime = GatewayRuntime(health_provider=provider)
        identity = VerifiedIdentity("owner-1", {"tenant": "fuse"})

        await runtime.manifest(identity)
        await runtime.manifest(identity)

        self.assertEqual(provider.calls, 1)
        self.assertEqual(runtime.performance_snapshot()["capability_cache_hits"], 1)

    async def test_zero_ttl_never_reuses_sequential_snapshot(self) -> None:
        provider = CountingHealth(ttl_seconds=0, delay_seconds=0)
        runtime = GatewayRuntime(health_provider=provider)
        identity = VerifiedIdentity("owner-1", {"tenant": "fuse"})

        await runtime.manifest(identity)
        await runtime.manifest(identity)

        self.assertEqual(provider.calls, 2)
        self.assertEqual(runtime.performance_snapshot()["capability_cache_hits"], 0)

    async def test_claims_are_part_of_singleflight_and_cache_identity(self) -> None:
        provider = CountingHealth(ttl_seconds=2, delay_seconds=0)
        runtime = GatewayRuntime(health_provider=provider)

        await runtime.manifest(VerifiedIdentity("owner-1", {"role": "a"}))
        await runtime.manifest(VerifiedIdentity("owner-1", {"role": "b"}))

        self.assertEqual(provider.calls, 2)

    async def test_metrics_are_redacted(self) -> None:
        provider = CountingHealth(ttl_seconds=2, delay_seconds=0)
        runtime = GatewayRuntime(health_provider=provider)
        identity = VerifiedIdentity("secret-owner", {"sensitive": "value"})
        await runtime.manifest(identity)

        rendered = repr(runtime.performance_snapshot())
        self.assertNotIn("secret-owner", rendered)
        self.assertNotIn("sensitive", rendered)
        self.assertNotIn("value", rendered)


if __name__ == "__main__":
    unittest.main()
