from __future__ import annotations

from datetime import datetime, timezone
import unittest

from bubbles.autonomic_recovery_bridge import AutonomicRecoveryBridge, RecoveryProviderBinding
from bubbles.mission_telemetry import MissionTelemetryBridge, TelemetryExportContract
from bubbles.provider_authority_fabric import AuthorityLeaseDecision, AuthorityState
from bubbles.provider_cell_registry import ProviderCellRegistry, RegistryProjection, default_federation_bindings
from federation.mission_ir import MissionIR
from federation.sentinel_omega.autonomic_immune_system import (
    AuthorityTier,
    AutonomicImmuneController,
    DependencyGraph,
    FailureFingerprint,
    RemediationDisposition,
    RepairRunbook,
)
from ops.sovara_provider_execution_fabric import CellState, ProviderCell, Substrate


SOURCE = "ca2a60a2f0280bfe9eb73541a9a7f9da53a2fdec"


def mission(**overrides) -> MissionIR:
    values = dict(
        mission_id="BUB-T2-MISSION-001",
        objective="Recover one bounded mission route without owner interruption when safely possible.",
        domain="BUBBLES_RECOVERY",
        outcome_contract="One proof-bounded recovery decision.",
        source_frontier=f"main@{SOURCE}",
        privacy_class="PUBLIC",
        rights_state="NOT_APPLICABLE",
        proof_requirements=("SOURCE", "SEMANTIC_READBACK"),
        value_metrics=("owner_interruption_minutes",),
    )
    values.update(overrides)
    return MissionIR(**values)


class ProviderRegistryTests(unittest.TestCase):
    def test_source_ready_or_metadata_only_never_becomes_live(self):
        registry = ProviderCellRegistry(default_federation_bindings())
        cell = ProviderCell(
            provider="OpenRouter",
            state=CellState.METADATA_VERIFIED,
            authority_scope="openrouter-only",
            substrate=Substrate.PRIVATE_RUNTIME,
            credential_reference_ready=True,
            runtime_authorised=True,
            health_ok=True,
            funding_or_quota_ready=True,
            provider_call_proven=False,
            semantic_readback_proven=False,
        )
        projection = registry.project([cell], observed_at="2026-09-03T01:50:00Z")
        health = next(item for item in projection.health if item.cell_id == "openrouter-private-runtime")
        self.assertFalse(health.provider_native)
        self.assertFalse(health.provider_live)
        self.assertFalse(health.semantic_readback_ready)

    def test_proven_sovara_cell_projects_into_selectable_bubbles_health(self):
        registry = ProviderCellRegistry(default_federation_bindings())
        cell = ProviderCell(
            provider="Google Cloud",
            state=CellState.PROVEN,
            authority_scope="google-cloud-only",
            substrate=Substrate.CLOUD_RUN,
            credential_reference_ready=True,
            runtime_authorised=True,
            health_ok=True,
            funding_or_quota_ready=True,
            provider_call_proven=True,
            semantic_readback_proven=True,
        )
        projection = registry.project(
            [cell],
            proof_refs={"google-cloud-cloud-run": ("provider:google:semantic-readback",)},
        )
        health = next(item for item in projection.health if item.cell_id == "google-cloud-cloud-run")
        self.assertTrue(health.provider_native)
        self.assertTrue(health.provider_live)
        self.assertTrue(health.semantic_readback_ready)
        self.assertTrue(health.credential_bound)


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.bridge = MissionTelemetryBridge()
        self.envelope = self.bridge.envelope(
            mission_id="BUB-T2-TRACE-001",
            step="provider recovery",
            kind="recovery",
            status="OK",
            started_at_epoch_ms=1,
            attributes={"safe": "yes", "api_token": "must-not-appear"},
        )
        self.contract = TelemetryExportContract(
            capability_id="OTEL_EXPORT",
            provider="Observability Cloud",
            connector="otel.exporter",
        )

    def decision(self, *, resolved: bool) -> AuthorityLeaseDecision:
        return AuthorityLeaseDecision(
            schema="BUBBLES-OMEGA-PROVIDER-AUTHORITY-FABRIC-V1",
            mission_id="BUB-T2-TRACE-001",
            capability_id="OTEL_EXPORT",
            contract_sha256="a" * 64,
            state=AuthorityState.RESOLVED.value if resolved else AuthorityState.PROVIDER_GATED.value,
            grant_id="GRANT-1" if resolved else "",
            provider="Observability Cloud",
            connector="otel.exporter",
            action="export_otel_trace",
            proof_refs=("authority:otel",) if resolved else (),
            provider_effect_authorized=resolved,
        )

    def test_local_trace_is_secret_key_filtered(self):
        receipt = self.bridge.local_receipt("BUB-T2-TRACE-001", self.envelope)
        self.assertEqual("LOCAL_TRACE_VERIFIED", receipt.state)
        self.assertEqual("yes", receipt.otel_attributes["safe"])
        self.assertNotIn("api_token", receipt.otel_attributes)

    def test_exporter_is_never_called_without_exact_authority(self):
        called = {"count": 0}
        def exporter(_attrs, _key):
            called["count"] += 1
            return {}
        receipt = self.bridge.export(
            "BUB-T2-TRACE-001",
            self.envelope,
            contract=self.contract,
            authority=self.decision(resolved=False),
            exporter=exporter,
        )
        self.assertEqual("EXPORT_AUTHORITY_GATED", receipt.state)
        self.assertEqual(0, called["count"])

    def test_transport_without_semantic_readback_holds(self):
        receipt = self.bridge.export(
            "BUB-T2-TRACE-001",
            self.envelope,
            contract=self.contract,
            authority=self.decision(resolved=True),
            exporter=lambda _attrs, _key: {
                "transport_ok": True,
                "provider_native": True,
                "semantic_readback_verified": False,
                "operation_id": "op-1",
            },
        )
        self.assertEqual("HOLD_READBACK", receipt.state)
        self.assertFalse(receipt.semantic_readback_verified)

    def test_provider_native_export_with_semantic_readback_verifies(self):
        receipt = self.bridge.export(
            "BUB-T2-TRACE-001",
            self.envelope,
            contract=self.contract,
            authority=self.decision(resolved=True),
            exporter=lambda _attrs, _key: {
                "transport_ok": True,
                "provider_native": True,
                "semantic_readback_verified": True,
                "operation_id": "op-2",
                "readback_ref": "otel:trace:readback:2",
                "proof_refs": ("otel:provider-native",),
            },
        )
        self.assertEqual("OTEL_EXPORT_READBACK_VERIFIED", receipt.state)
        self.assertTrue(receipt.semantic_readback_verified)
        self.assertEqual("otel:trace:readback:2", receipt.readback_ref)


class RecoveryBridgeTests(unittest.TestCase):
    def fingerprint(self) -> FailureFingerprint:
        return FailureFingerprint(
            target="provider-route",
            failure_class="PROVIDER_TRANSIENT",
            error_signature="HTTP 503 same route",
            provider_epoch="p1",
            source_epoch=SOURCE,
        )

    def test_a1_internal_repair_is_ready_without_provider_effect(self):
        controller = AutonomicImmuneController(
            runbooks=(
                RepairRunbook(
                    runbook_id="RB-INTERNAL",
                    failure_classes=("PROVIDER_TRANSIENT",),
                    max_authority=AuthorityTier.A1_INTERNAL,
                    reversible=True,
                    route_family="internal-reconcile",
                ),
            ),
            dependency_graph=DependencyGraph({"provider-route": ("mission",)}),
        )
        bridge = AutonomicRecoveryBridge(controller)
        plan = bridge.plan(
            mission(),
            self.fingerprint(),
            authority_ceiling=AuthorityTier.A1_INTERNAL,
            state_epoch="state-1",
            registry=RegistryProjection("BUBBLES-OMEGA-PROVIDER-CELL-REGISTRY-V1", (), (), (), ()),
        )
        self.assertEqual("READY_INTERNAL", plan.state)
        self.assertEqual(RemediationDisposition.AUTO_REPAIR.value, plan.disposition)
        self.assertFalse(plan.owner_interrupt_required)
        self.assertEqual(("mission",), plan.affected_nodes)

    def test_a2_provider_repair_selects_live_cell_but_stops_before_effect(self):
        controller = AutonomicImmuneController(
            runbooks=(
                RepairRunbook(
                    runbook_id="RB-GCP",
                    failure_classes=("PROVIDER_TRANSIENT",),
                    max_authority=AuthorityTier.A2_REVERSIBLE_PROVIDER,
                    reversible=True,
                    rollback_ref="rollback:gcp",
                    route_family="gcp-cloud-run",
                ),
            )
        )
        registry = ProviderCellRegistry(default_federation_bindings()).project(
            [
                ProviderCell(
                    provider="Google Cloud",
                    state=CellState.PROVEN,
                    authority_scope="google-cloud-only",
                    substrate=Substrate.CLOUD_RUN,
                    credential_reference_ready=True,
                    runtime_authorised=True,
                    health_ok=True,
                    funding_or_quota_ready=True,
                    provider_call_proven=True,
                    semantic_readback_proven=True,
                )
            ]
        )
        bridge = AutonomicRecoveryBridge(
            controller,
            provider_bindings=(RecoveryProviderBinding("RB-GCP", "GOOGLE_CLOUD_EFFECTS"),),
        )
        bounded = mission(
            effect_class="BOUNDED_EFFECT",
            authority_requirements=("A2",),
            rollback_required=True,
        )
        plan = bridge.plan(
            bounded,
            self.fingerprint(),
            authority_ceiling=AuthorityTier.A2_REVERSIBLE_PROVIDER,
            state_epoch="state-1",
            registry=registry,
        )
        self.assertEqual("PROVIDER_AUTHORITY_PREFLIGHT_REQUIRED", plan.state)
        self.assertEqual("google-cloud-cloud-run", plan.selected_cell_id)
        self.assertEqual("Google Cloud", plan.selected_provider)
        self.assertIn("ROLLBACK:rollback:gcp", plan.proof_requirements)

    def test_unchanged_failed_route_is_not_retried_and_reroutes(self):
        controller = AutonomicImmuneController(
            runbooks=(
                RepairRunbook(
                    runbook_id="RB-RETRY",
                    failure_classes=("PROVIDER_TRANSIENT",),
                    max_authority=AuthorityTier.A1_INTERNAL,
                    reversible=True,
                    route_family="same-route",
                ),
            )
        )
        bridge = AutonomicRecoveryBridge(controller)
        fp = self.fingerprint()
        first = bridge.plan(
            mission(), fp,
            authority_ceiling=AuthorityTier.A1_INTERNAL,
            state_epoch="state-1",
            registry=RegistryProjection("BUBBLES-OMEGA-PROVIDER-CELL-REGISTRY-V1", (), (), (), ()),
        )
        bridge.record_attempt(
            first,
            route_family="same-route",
            result="FAILED",
            attempted_at=datetime(2026, 9, 3, 1, 50, tzinfo=timezone.utc),
            state_epoch="state-1",
        )
        second = bridge.plan(
            mission(), fp,
            authority_ceiling=AuthorityTier.A1_INTERNAL,
            state_epoch="state-1",
            registry=RegistryProjection("BUBBLES-OMEGA-PROVIDER-CELL-REGISTRY-V1", (), (), (), ()),
            safe_alternate_routes=("different-route",),
        )
        self.assertEqual("READY_REROUTE", second.state)
        self.assertEqual(RemediationDisposition.REROUTE.value, second.disposition)
        self.assertIn("different-route", second.reason)

    def test_higher_authority_repair_escalates_owner_without_execution(self):
        controller = AutonomicImmuneController(
            runbooks=(
                RepairRunbook(
                    runbook_id="RB-A3",
                    failure_classes=("PROVIDER_TRANSIENT",),
                    max_authority=AuthorityTier.A3_OWNER_RESERVED,
                    reversible=False,
                    route_family="owner-reserved",
                ),
            )
        )
        plan = AutonomicRecoveryBridge(controller).plan(
            mission(),
            self.fingerprint(),
            authority_ceiling=AuthorityTier.A1_INTERNAL,
            state_epoch="state-1",
            registry=RegistryProjection("BUBBLES-OMEGA-PROVIDER-CELL-REGISTRY-V1", (), (), (), ()),
        )
        self.assertEqual("OWNER_ACTION_REQUIRED", plan.state)
        self.assertEqual(RemediationDisposition.ESCALATE_OWNER.value, plan.disposition)
        self.assertTrue(plan.owner_interrupt_required)


if __name__ == "__main__":
    unittest.main()
