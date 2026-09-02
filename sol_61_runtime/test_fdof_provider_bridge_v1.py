from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from .fdof_provider_bridge_v1 import (
        DispatchReceipt,
        FederationProviderBridge,
        ProviderAdapter,
        ProviderExecutionRequest,
        ReadbackReceipt,
    )
    from .fdof_v1 import ExecutorSpec, FederationDistributedOperatingFabric, HealthObservation, RouteRequest
    from .sol_62_frontier_primitives import ConstraintError, FenceError
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_provider_bridge_v1 import (
        DispatchReceipt,
        FederationProviderBridge,
        ProviderAdapter,
        ProviderExecutionRequest,
        ReadbackReceipt,
    )
    from fdof_v1 import ExecutorSpec, FederationDistributedOperatingFabric, HealthObservation, RouteRequest
    from sol_62_frontier_primitives import ConstraintError, FenceError
    from sol_62_runtime import Sol62Runtime


class ProviderBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = int(time.time())
        self.runtime = Sol62Runtime(self.root)
        self.fdof = FederationDistributedOperatingFabric(self.runtime)
        self.bridge = FederationProviderBridge(self.fdof)
        self.calls = {"dispatch": 0, "readback": 0, "rollback": 0}
        self.fdof.register_executor(
            ExecutorSpec(
                executor_id="exec-github",
                provider="github",
                capabilities=("WRITE",),
                target_prefixes=("repo:",),
                authority_ceiling="A1_INTERNAL",
                cost_class="C0_INCLUDED_FREE",
                readback_modes=("PROVIDER_NATIVE",),
                rollback_modes=("REVERT",),
                max_parallel=1,
                version=1,
            )
        )
        self.fdof.record_health(
            HealthObservation(
                observation_id="health-github",
                executor_id="exec-github",
                observed_at_epoch=self.now,
                ttl_seconds=300,
                process="HEALTHY",
                authentication="HEALTHY",
                target_access="HEALTHY",
                semantic_capability="HEALTHY",
                readback="HEALTHY",
                capacity_available=1,
                provider_state="AVAILABLE",
                proof_id="proof-health",
                evidence_class="PROVIDER_NATIVE",
            )
        )
        self.route = self.fdof.route(
            RouteRequest(
                route_id="route-1",
                mission_id="mission-1",
                transition_id="transition-1",
                operation="WRITE",
                target="repo:mosianekk-lang/Federation-Omega",
                required_capabilities=("WRITE",),
                authority_ceiling="A1_INTERNAL",
                allowed_cost_classes=("C0_INCLUDED_FREE",),
                require_readback=True,
                require_rollback=True,
                consequential=True,
            ),
            now_epoch=self.now,
        )
        self.lease = self.fdof.acquire_transition_lease(
            "transition-1", "exec-github", ttl_seconds=120, now_epoch=self.now
        )

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def request(self, execution_id="exec-1", payload=None):
        return ProviderExecutionRequest(
            execution_id=execution_id,
            mission_id="mission-1",
            transition_id="transition-1",
            route_id="route-1",
            executor_id="exec-github",
            provider="github",
            operation="WRITE",
            target="repo:mosianekk-lang/Federation-Omega",
            payload={} if payload is None else payload,
            idempotency_key="idem-1",
            semantics="IDEMPOTENT",
            consequential=True,
            expected_readback={"state": "APPLIED"},
        )

    def adapter(self, *, uncertain=False, verified=True):
        def dispatch(req):
            self.calls["dispatch"] += 1
            return DispatchReceipt(
                execution_id=req.execution_id,
                provider=req.provider,
                provider_request_id="provider-req-1",
                accepted=True,
                effect_uncertain=uncertain,
                summary={"accepted": True},
            )

        def readback(req, receipt):
            self.calls["readback"] += 1
            return ReadbackReceipt(
                execution_id=req.execution_id,
                provider=req.provider,
                semantic_state="APPLIED" if verified else "UNKNOWN",
                verified=verified,
                provider_correlation_id=receipt.provider_request_id,
                evidence={"provider_native": True},
            )

        def rollback(req, dispatch_receipt, readback_receipt):
            self.calls["rollback"] += 1
            return {"rolled_back": True, "correlation": dispatch_receipt.provider_request_id}

        return ProviderAdapter(
            adapter_id="adapter-github-v1",
            provider="github",
            dispatch=dispatch,
            readback=readback,
            rollback=rollback,
            version=1,
        )

    def test_dispatch_is_not_verification(self):
        self.bridge.register_adapter(self.adapter())
        result = self.bridge.execute(
            self.request(),
            lease_epoch=self.lease["epoch"],
            fencing_token=self.lease["fencing_token"],
            now_epoch=self.now + 1,
        )
        self.assertEqual(result["state"], "DISPATCH_REPORTED")
        self.assertEqual(self.calls["dispatch"], 1)

    def test_provider_native_readback_required_for_verified(self):
        adapter = self.adapter()
        self.bridge.register_adapter(adapter)
        request = self.request()
        self.bridge.execute(
            request,
            lease_epoch=self.lease["epoch"],
            fencing_token=self.lease["fencing_token"],
            now_epoch=self.now + 1,
        )
        verified = self.bridge.verify(
            request,
            dispatch_receipt=DispatchReceipt(
                execution_id="exec-1",
                provider="github",
                provider_request_id="provider-req-1",
                accepted=True,
            ),
            now_epoch=self.now + 2,
        )
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertEqual(verified["semantic_state"], "APPLIED")
        self.assertEqual(self.calls["readback"], 1)

    def test_uncertain_effect_stays_unknown_until_readback(self):
        self.bridge.register_adapter(self.adapter(uncertain=True, verified=False))
        request = self.request()
        dispatched = self.bridge.execute(
            request,
            lease_epoch=self.lease["epoch"],
            fencing_token=self.lease["fencing_token"],
            now_epoch=self.now + 1,
        )
        self.assertEqual(dispatched["state"], "EFFECT_UNKNOWN")
        unresolved = self.bridge.verify(
            request,
            dispatch_receipt=DispatchReceipt(
                execution_id="exec-1",
                provider="github",
                provider_request_id="provider-req-1",
                accepted=True,
                effect_uncertain=True,
            ),
            now_epoch=self.now + 2,
        )
        self.assertEqual(unresolved["state"], "EFFECT_UNKNOWN")
        self.assertEqual(self.calls["dispatch"], 1)

    def test_same_execution_is_not_blindly_dispatched_twice(self):
        self.bridge.register_adapter(self.adapter())
        request = self.request()
        first = self.bridge.execute(
            request,
            lease_epoch=self.lease["epoch"],
            fencing_token=self.lease["fencing_token"],
            now_epoch=self.now + 1,
        )
        second = self.bridge.execute(
            request,
            lease_epoch=self.lease["epoch"],
            fencing_token=self.lease["fencing_token"],
            now_epoch=self.now + 2,
        )
        self.assertEqual(first["request_sha256"], second["request_sha256"])
        self.assertEqual(self.calls["dispatch"], 1)

    def test_execution_id_collision_fails_closed(self):
        self.bridge.register_adapter(self.adapter())
        request = self.request()
        self.bridge.execute(
            request,
            lease_epoch=self.lease["epoch"],
            fencing_token=self.lease["fencing_token"],
            now_epoch=self.now + 1,
        )
        with self.assertRaises(ConstraintError):
            self.bridge.execute(
                self.request(payload={"different": True}),
                lease_epoch=self.lease["epoch"],
                fencing_token=self.lease["fencing_token"],
                now_epoch=self.now + 2,
            )

    def test_stale_fence_fails_closed(self):
        self.bridge.register_adapter(self.adapter())
        with self.assertRaises(FenceError):
            self.bridge.execute(
                self.request(),
                lease_epoch=self.lease["epoch"],
                fencing_token=self.lease["fencing_token"] + 1,
                now_epoch=self.now + 1,
            )

    def test_unhealthy_executor_cannot_dispatch(self):
        self.bridge.register_adapter(self.adapter())
        with self.assertRaises(ConstraintError):
            self.bridge.execute(
                self.request(),
                lease_epoch=self.lease["epoch"],
                fencing_token=self.lease["fencing_token"],
                now_epoch=self.now + 301,
            )

    def test_consequential_rollback_is_explicit(self):
        adapter = self.adapter()
        self.bridge.register_adapter(adapter)
        result = self.bridge.rollback(
            self.request(),
            dispatch_receipt=DispatchReceipt(
                execution_id="exec-1",
                provider="github",
                provider_request_id="provider-req-1",
                accepted=True,
            ),
            readback_receipt=ReadbackReceipt(
                execution_id="exec-1",
                provider="github",
                semantic_state="APPLIED",
                verified=True,
            ),
        )
        self.assertTrue(result["rolled_back"])
        self.assertEqual(self.calls["rollback"], 1)


if __name__ == "__main__":
    unittest.main()
