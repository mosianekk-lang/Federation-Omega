from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from .fdof_v1 import (
        ExecutorSpec,
        FactClaim,
        FederationDistributedOperatingFabric,
        HealthObservation,
        RouteRequest,
    )
    from .sol_62_frontier_primitives import ConstraintError, FenceError
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_v1 import (
        ExecutorSpec,
        FactClaim,
        FederationDistributedOperatingFabric,
        HealthObservation,
        RouteRequest,
    )
    from sol_62_frontier_primitives import ConstraintError, FenceError
    from sol_62_runtime import Sol62Runtime


class FdofV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = int(time.time())
        self.runtime = Sol62Runtime(self.root)
        self.fdof = FederationDistributedOperatingFabric(self.runtime)

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def executor(
        self,
        executor_id: str,
        *,
        provider: str = "github",
        capabilities=("READ", "WRITE"),
        target_prefixes=("repo:",),
        authority_ceiling="A1_INTERNAL",
        cost_class="C0_INCLUDED_FREE",
        readback_modes=("PROVIDER_NATIVE",),
        rollback_modes=("REVERT",),
        version=1,
    ) -> ExecutorSpec:
        return ExecutorSpec(
            executor_id=executor_id,
            provider=provider,
            capabilities=tuple(capabilities),
            target_prefixes=tuple(target_prefixes),
            authority_ceiling=authority_ceiling,
            cost_class=cost_class,
            readback_modes=tuple(readback_modes),
            rollback_modes=tuple(rollback_modes),
            max_parallel=2,
            version=version,
        )

    def healthy(self, executor_id: str, *, observed=None, ttl=300, proof_id="proof-health") -> HealthObservation:
        return HealthObservation(
            observation_id=f"health-{executor_id}",
            executor_id=executor_id,
            observed_at_epoch=self.now if observed is None else observed,
            ttl_seconds=ttl,
            process="HEALTHY",
            authentication="HEALTHY",
            target_access="HEALTHY",
            semantic_capability="HEALTHY",
            readback="HEALTHY",
            capacity_available=2,
            provider_state="AVAILABLE",
            proof_id=proof_id,
            evidence_class="PROVIDER_NATIVE",
        )

    def route_request(self, route_id="route-1", *, authority="A1_INTERNAL", costs=("C0_INCLUDED_FREE",), consequential=True):
        return RouteRequest(
            route_id=route_id,
            mission_id="mission-1",
            transition_id="transition-1",
            operation="WRITE",
            target="repo:mosianekk-lang/Federation-Omega",
            required_capabilities=("WRITE",),
            authority_ceiling=authority,
            allowed_cost_classes=tuple(costs),
            require_readback=True,
            require_rollback=consequential,
            consequential=consequential,
        )

    def test_source_registration_does_not_inherit_runtime_health(self):
        self.fdof.register_executor(self.executor("exec-a"))
        state = self.fdof.health_state("exec-a", now_epoch=self.now)
        self.assertEqual(state["state"], "UNKNOWN")
        with self.assertRaises(ConstraintError):
            self.fdof.route(self.route_request(), now_epoch=self.now)

    def test_fresh_health_required_and_stale_executor_is_excluded(self):
        self.fdof.register_executor(self.executor("exec-stale"))
        self.fdof.record_health(self.healthy("exec-stale", observed=self.now - 1000, ttl=60))
        self.assertEqual(self.fdof.health_state("exec-stale", now_epoch=self.now)["state"], "STALE")
        with self.assertRaises(ConstraintError):
            self.fdof.route(self.route_request(), now_epoch=self.now)

    def test_cheapest_fresh_eligible_executor_wins_deterministically(self):
        self.fdof.register_executor(self.executor("exec-free", cost_class="C0_INCLUDED_FREE"))
        self.fdof.register_executor(self.executor("exec-micro", cost_class="C1_MICRO_SERVERLESS"))
        self.fdof.record_health(self.healthy("exec-free"))
        self.fdof.record_health(self.healthy("exec-micro"))
        decision = self.fdof.route(
            self.route_request(costs=("C0_INCLUDED_FREE", "C1_MICRO_SERVERLESS")),
            now_epoch=self.now,
        )
        self.assertEqual(decision["executor_id"], "exec-free")
        self.assertEqual(decision["health_state"], "HEALTHY")

    def test_authority_ceiling_and_cost_policy_fail_closed(self):
        self.fdof.register_executor(self.executor("exec-a1", authority_ceiling="A1_INTERNAL"))
        self.fdof.record_health(self.healthy("exec-a1"))
        with self.assertRaises(ConstraintError):
            self.fdof.route(self.route_request(authority="A2_BOUNDED_PROVIDER"), now_epoch=self.now)
        with self.assertRaises(ConstraintError):
            self.fdof.route(self.route_request(costs=("C2_CONTROLLED_PAID",)), now_epoch=self.now)

    def test_consequential_route_requires_rollback_and_readback(self):
        self.fdof.register_executor(
            self.executor("exec-no-rollback", rollback_modes=(), readback_modes=("PROVIDER_NATIVE",))
        )
        self.fdof.record_health(self.healthy("exec-no-rollback"))
        with self.assertRaises(ConstraintError):
            self.fdof.route(self.route_request(consequential=True), now_epoch=self.now)

    def test_execution_lease_reuses_sol62_fencing(self):
        self.fdof.register_executor(self.executor("exec-a"))
        self.fdof.register_executor(self.executor("exec-b"))
        self.fdof.record_health(self.healthy("exec-a"))
        self.fdof.record_health(self.healthy("exec-b"))
        lease = self.fdof.acquire_transition_lease(
            "transition-1", "exec-a", ttl_seconds=60, now_epoch=self.now
        )
        self.assertEqual(lease["fencing_token"], 1)
        with self.assertRaises(FenceError):
            self.fdof.acquire_transition_lease(
                "transition-1", "exec-b", ttl_seconds=60, now_epoch=self.now + 1
            )
        replacement = self.fdof.acquire_transition_lease(
            "transition-1", "exec-b", ttl_seconds=60, now_epoch=self.now + 61
        )
        self.assertGreater(replacement["fencing_token"], lease["fencing_token"])

    def test_provider_native_runtime_claim_beats_newer_source_claim(self):
        self.fdof.record_claim(
            FactClaim(
                claim_id="source-newer",
                subject="architron",
                dimension="runtime",
                value="OPERATIONAL",
                source_kind="SOURCE",
                observed_at_epoch=self.now,
                source_version="sha-source",
            )
        )
        self.fdof.record_claim(
            FactClaim(
                claim_id="provider-older",
                subject="architron",
                dimension="runtime",
                value="DEGRADED",
                source_kind="PROVIDER_NATIVE",
                observed_at_epoch=self.now - 30,
                source_version="provider-readback",
                proof_id="provider-proof",
            )
        )
        resolved = self.fdof.resolve_claims("architron", "runtime", now_epoch=self.now)
        self.assertTrue(resolved["resolved"])
        self.assertEqual(resolved["winner"]["claim_id"], "provider-older")
        self.assertEqual(resolved["winner"]["value"], "DEGRADED")

    def test_owner_directive_controls_generation_anchor_dimension(self):
        self.fdof.record_claim(
            FactClaim(
                claim_id="owner-anchor",
                subject="federation",
                dimension="generation_anchor",
                value="6fa54e31",
                source_kind="OWNER_DIRECTIVE",
                observed_at_epoch=self.now - 20,
                source_version="GEN16",
            )
        )
        self.fdof.record_claim(
            FactClaim(
                claim_id="new-source",
                subject="federation",
                dimension="generation_anchor",
                value="296ed9c2",
                source_kind="SIGNED_SOURCE",
                observed_at_epoch=self.now,
                source_version="296ed9c2",
            )
        )
        resolved = self.fdof.resolve_claims("federation", "generation_anchor", now_epoch=self.now)
        self.assertEqual(resolved["winner"]["claim_id"], "owner-anchor")
        self.assertEqual(resolved["winner"]["value"], "6fa54e31")

    def test_source_and_runtime_dimensions_coexist_without_flattening(self):
        self.fdof.record_claim(
            FactClaim("source", "system-x", "source", "PRESENT", "SIGNED_SOURCE", self.now, "sha")
        )
        self.fdof.record_claim(
            FactClaim("runtime", "system-x", "runtime", "DOWN", "PROVIDER_NATIVE", self.now, "provider")
        )
        source = self.fdof.resolve_claims("system-x", "source", now_epoch=self.now)
        runtime = self.fdof.resolve_claims("system-x", "runtime", now_epoch=self.now)
        self.assertEqual(source["winner"]["value"], "PRESENT")
        self.assertEqual(runtime["winner"]["value"], "DOWN")

    def test_integrity_status_uses_existing_sol62_chain(self):
        self.fdof.register_executor(self.executor("exec-a"))
        self.fdof.record_health(self.healthy("exec-a"))
        status = self.fdof.status(now_epoch=self.now)
        self.assertEqual(status["fdof_version"], "1.0.0")
        self.assertTrue(status["sol62_integrity"]["event_chain_valid"])
        self.assertEqual(status["healthy_executors"], 1)


if __name__ == "__main__":
    unittest.main()
