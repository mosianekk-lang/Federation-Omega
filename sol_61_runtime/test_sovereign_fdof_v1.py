from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from .fdof_v1 import ExecutorSpec, HealthObservation, RouteRequest
    from .sovereign_fdof_v1 import SovereignFederationDistributedOperatingFabric
    from .sol_62_frontier_primitives import ConstraintError
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_v1 import ExecutorSpec, HealthObservation, RouteRequest
    from sovereign_fdof_v1 import SovereignFederationDistributedOperatingFabric
    from sol_62_frontier_primitives import ConstraintError
    from sol_62_runtime import Sol62Runtime


class SovereignFdofV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = int(time.time())
        self.runtime = Sol62Runtime(self.root)
        self.fdof = SovereignFederationDistributedOperatingFabric(self.runtime)

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def request(self, route_id="route-sovereign-1", **metadata):
        return RouteRequest(
            route_id=route_id,
            mission_id="mission-sovereign-1",
            transition_id="transition-sovereign-1",
            operation="WORKFLOW_ADMISSION",
            target="provider:github/actions/airlock",
            required_capabilities=("WORKFLOW_EXECUTION", "PROOF_GATE"),
            authority_ceiling="A1_INTERNAL",
            allowed_cost_classes=("C0_INCLUDED_FREE",),
            require_readback=True,
            require_rollback=False,
            consequential=False,
            metadata=metadata,
        )

    def fuse_executor(self, executor_id="fuse-forge"):
        return ExecutorSpec(
            executor_id=executor_id,
            provider="fuse-native",
            capabilities=("WORKFLOW_EXECUTION", "PROOF_GATE"),
            target_prefixes=("provider:github/",),
            authority_ceiling="A1_INTERNAL",
            cost_class="C0_INCLUDED_FREE",
            readback_modes=("LOCAL_PROOF_LEDGER",),
            rollback_modes=("LKG_ROLLBACK",),
            max_parallel=4,
            version=1,
            metadata={"ownership": "FUSE_OWNED"},
        )

    def health(self, executor_id="fuse-forge"):
        return HealthObservation(
            observation_id=f"health-{executor_id}",
            executor_id=executor_id,
            observed_at_epoch=self.now,
            ttl_seconds=300,
            process="HEALTHY",
            authentication="HEALTHY",
            target_access="HEALTHY",
            semantic_capability="HEALTHY",
            readback="HEALTHY",
            capacity_available=2,
            provider_state="AVAILABLE",
            proof_id="proof-fuse-native",
            evidence_class="DETERMINISTIC",
        )

    def test_no_verified_route_auto_creates_sovereign_signal(self):
        req = self.request(
            failure_class="WORKFLOW_ADMISSION_BLOCKED",
            source_system="github",
            evidence_ref="run-123",
        )
        with self.assertRaises(ConstraintError):
            self.fdof.route(req, now_epoch=self.now)
        signal = self.fdof.replacement_for_route(req.route_id)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["recommended_component"], "FUSE_FORGE_PROOF_GATE")
        self.assertEqual(signal["replacement_action"], "BUILD_MINIMUM_FUSE_NATIVE_REPLACEMENT")
        self.assertEqual(signal["external_adapter_policy"], "OPTIONAL_ONLY_AFTER_FUSE_NATIVE_REPLACEMENT")
        self.assertTrue(signal["no_duplicate_build"])
        self.assertTrue(signal["proof_before_promotion"])

    def test_route_or_replace_returns_replacement_instead_of_dead_end(self):
        result = self.fdof.route_or_replace(
            self.request(failure_class="WORKFLOW_ADMISSION_BLOCKED", source_system="github"),
            now_epoch=self.now,
        )
        self.assertEqual(result["state"], "SOVEREIGN_REPLACEMENT_TRIGGERED")
        self.assertIsNone(result["decision"])
        self.assertEqual(result["replacement"]["recommended_component"], "FUSE_FORGE_PROOF_GATE")

    def test_external_constraint_maps_missing_config_to_fuse_config_vault(self):
        req = RouteRequest(
            route_id="route-config",
            mission_id="mission-config",
            transition_id="transition-config",
            operation="RUNTIME_CONFIG",
            target="provider:github/actions/variables",
            required_capabilities=("CONFIG_READ",),
            authority_ceiling="A1_INTERNAL",
            allowed_cost_classes=("C0_INCLUDED_FREE",),
        )
        signal = self.fdof.record_external_constraint(
            req,
            failure_class="MISSING_RUNTIME_VARIABLE",
            source_system="github",
            evidence_ref="job-log-1",
            now_epoch=self.now,
        )
        self.assertEqual(signal["recommended_component"], "FUSE_CONFIG_VAULT")
        self.assertEqual(signal["status"], "OPEN")

    def test_existing_fuse_owned_candidate_blocks_duplicate_build(self):
        self.fdof.register_executor(self.fuse_executor())
        req = self.request(failure_class="WORKFLOW_ADMISSION_BLOCKED", source_system="github")
        signal = self.fdof.record_external_constraint(
            req,
            failure_class="WORKFLOW_ADMISSION_BLOCKED",
            source_system="github",
            now_epoch=self.now,
        )
        self.assertEqual(signal["replacement_action"], "ACTIVATE_OR_REPAIR_EXISTING_FUSE_NATIVE")
        self.assertEqual(signal["existing_fuse_candidates"], ["fuse-forge"])

    def test_signal_is_idempotent_for_same_constraint(self):
        req = self.request(failure_class="WORKFLOW_ADMISSION_BLOCKED", source_system="github")
        first = self.fdof.record_external_constraint(
            req,
            failure_class="WORKFLOW_ADMISSION_BLOCKED",
            source_system="github",
            evidence_ref="receipt-a",
            now_epoch=self.now,
        )
        second = self.fdof.record_external_constraint(
            req,
            failure_class="WORKFLOW_ADMISSION_BLOCKED",
            source_system="github",
            evidence_ref="receipt-a",
            now_epoch=self.now + 1,
        )
        self.assertEqual(first["signal_id"], second["signal_id"])
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(len(self.fdof.open_replacements()), 1)

    def test_verified_replacement_must_be_fuse_owned_and_healthy(self):
        req = self.request(failure_class="WORKFLOW_ADMISSION_BLOCKED", source_system="github")
        signal = self.fdof.record_external_constraint(
            req,
            failure_class="WORKFLOW_ADMISSION_BLOCKED",
            source_system="github",
            now_epoch=self.now,
        )
        external = ExecutorSpec(
            executor_id="github-exec",
            provider="github",
            capabilities=("WORKFLOW_EXECUTION", "PROOF_GATE"),
            target_prefixes=("provider:github/",),
            authority_ceiling="A1_INTERNAL",
            cost_class="C0_INCLUDED_FREE",
            readback_modes=("PROVIDER_NATIVE",),
            rollback_modes=("REVERT",),
            max_parallel=1,
            version=1,
        )
        self.fdof.register_executor(external)
        self.fdof.record_health(self.health("github-exec"))
        with self.assertRaises(ConstraintError):
            self.fdof.mark_replacement_verified(
                signal["signal_id"],
                executor_id="github-exec",
                proof_id="external-proof",
                now_epoch=self.now,
            )

        self.fdof.register_executor(self.fuse_executor())
        self.fdof.record_health(self.health())
        verified = self.fdof.mark_replacement_verified(
            signal["signal_id"],
            executor_id="fuse-forge",
            proof_id="fuse-proof-1",
            now_epoch=self.now,
        )
        self.assertEqual(verified["status"], "FUSE_NATIVE_REPLACEMENT_VERIFIED")
        self.assertTrue(verified["external_control_dependency_retired"])
        self.assertEqual(verified["external_dependency_role"], "OPTIONAL_ADAPTER")

    def test_healthy_fuse_route_uses_fuse_and_creates_no_replacement(self):
        self.fdof.register_executor(self.fuse_executor())
        self.fdof.record_health(self.health())
        result = self.fdof.route_or_replace(self.request(), now_epoch=self.now)
        self.assertEqual(result["state"], "ROUTED")
        self.assertEqual(result["decision"]["executor_id"], "fuse-forge")
        self.assertEqual(self.fdof.open_replacements(), [])


if __name__ == "__main__":
    unittest.main()
