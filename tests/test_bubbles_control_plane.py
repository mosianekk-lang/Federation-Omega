import unittest

from ao_harmonic_v3.failure_win_manifest import compile_receiver_manifest
from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinState,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from bubbles.control_plane import (
    ActionRequest,
    BubblesControlPlane,
    EffectClass,
    RouteKind,
)
from federation.bubbles_hyperperformance import (
    CurrentStateLease,
    CurrentStateLeaseError,
    IdempotencyEnvelope,
    IdempotencyLedger,
    TraceEvent,
    TraceSpine,
)
from governance.external_action_firewall import LEASE_PROOF
from tests.test_external_action_firewall import ExternalActionFirewallTests  # noqa: F401
from tests.test_failure_win_manifest import FailureWinReceiverManifestTests  # noqa: F401


class BubblesControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.control = BubblesControlPlane()

    def test_native_drive_write_requires_connector_and_execution_lease_proof(self) -> None:
        request = ActionRequest(
            adapter_id="google_drive",
            action="update_document",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GOOGLE_WORKSPACE_CANONICAL_STORE",
            payload={"document_alias": "TEST_ONLY"},
        )
        blocked = self.control.decide(request)
        self.assertEqual(blocked.state, "CONSTRAINT")
        self.assertIn("connector_permission_verified", blocked.missing_proofs)
        self.assertIn(LEASE_PROOF, blocked.missing_proofs)

        still_blocked = self.control.decide(
            request,
            frozenset({"connector_permission_verified"}),
        )
        self.assertEqual(still_blocked.state, "CONSTRAINT")
        self.assertEqual(still_blocked.missing_proofs, (LEASE_PROOF,))

        ready = self.control.decide(
            request,
            frozenset({"connector_permission_verified", LEASE_PROOF}),
        )
        self.assertEqual(ready.state, "READY")
        self.assertEqual(ready.route_kind, RouteKind.CHATGPT_NATIVE)

    def test_cloud_write_fails_closed_without_provider_readback_contract(self) -> None:
        request = ActionRequest(
            adapter_id="google_cloud",
            action="run_harmless_canary",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GOOGLE_CLOUD_EXECUTION_PLANE",
        )
        decision = self.control.decide(
            request,
            frozenset(
                {
                    "provider_identity_verified",
                    "target_verified",
                    "action_scope_verified",
                    LEASE_PROOF,
                }
            ),
        )
        self.assertEqual(decision.state, "CONSTRAINT")
        self.assertEqual(decision.missing_proofs, ("provider_readback_contract",))

    def test_cloud_write_can_route_through_command_bus_when_all_gates_pass(self) -> None:
        request = ActionRequest(
            adapter_id="google_cloud",
            action="run_harmless_canary",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GOOGLE_CLOUD_EXECUTION_PLANE",
        )
        decision = self.control.decide(
            request,
            frozenset(
                {
                    "provider_identity_verified",
                    "target_verified",
                    "action_scope_verified",
                    "provider_readback_contract",
                    LEASE_PROOF,
                }
            ),
        )
        self.assertEqual(decision.state, "READY")
        self.assertEqual(decision.route_kind, RouteKind.GITHUB_COMMAND_BUS)

    def test_mcp_route_never_allows_write_on_current_surface(self) -> None:
        request = ActionRequest(
            adapter_id="bubbles_mcp",
            action="mutate_provider",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="ANY_PROVIDER",
        )
        decision = self.control.decide(request)
        self.assertEqual(decision.state, "CONSTRAINT")
        self.assertEqual(decision.route_kind, RouteKind.MCP_READ_ONLY)

    def test_secret_bearing_command_payload_is_rejected(self) -> None:
        request = ActionRequest(
            adapter_id="github",
            action="enqueue",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GITHUB_ACTIONS_A0_A1",
            payload={"api_key": "must-never-enter-command-bus"},
        )
        decision = self.control.decide(
            request,
            frozenset({"connector_permission_verified", LEASE_PROOF}),
        )
        self.assertEqual(decision.state, "CONSTRAINT")
        with self.assertRaises(ValueError):
            self.control.command_envelope(request)

    def test_command_envelope_is_deterministic_and_proof_safe(self) -> None:
        request = ActionRequest(
            adapter_id="apps_script",
            action="inspect_project",
            effect=EffectClass.READ,
            target_alias="GOOGLE_APPS_SCRIPT_AUTOMATION",
            payload={"project_alias": "CANARY_ONLY"},
        )
        first = self.control.command_envelope(request)
        second = self.control.command_envelope(request)
        self.assertEqual(first["command_sha256"], second["command_sha256"])
        self.assertIn("provider execution", first["truth_boundary"])

    def test_current_state_lease_expires_and_preserves_authority_boundary(self) -> None:
        lease = CurrentStateLease(
            entity_id="SURFACE-GITHUB",
            field_id="current_sha",
            value="9a7e83c",
            authority_source="GITHUB_MAIN",
            observed_at="2026-08-30T20:00:00+02:00",
            fresh_until="2026-08-30T20:10:00+02:00",
            proof_refs=("github:main:9a7e83c",),
            source_event_id="GEN2-EVT-LEASE-001",
        )
        lease.require_fresh(
            now="2026-08-30T20:05:00+02:00",
            expected_authority="GITHUB_MAIN",
        )
        with self.assertRaisesRegex(CurrentStateLeaseError, "AUTHORITY_MISMATCH"):
            lease.require_fresh(
                now="2026-08-30T20:05:00+02:00",
                expected_authority="PROJECT_HEARTBEAT",
            )
        with self.assertRaisesRegex(CurrentStateLeaseError, "EXPIRED"):
            lease.require_fresh(now="2026-08-30T20:10:00+02:00")

    def test_trace_spine_is_append_only_idempotent_and_payload_safe(self) -> None:
        trace = TraceSpine()
        root = TraceEvent(
            trace_id="trace-1",
            span_id="span-root",
            mission_id="mission-1",
            stage="MISSION",
            state="STARTED",
            occurred_at="2026-08-30T20:00:00+02:00",
            proof_refs=("mission:capsule",),
        )
        child = TraceEvent(
            trace_id="trace-1",
            span_id="span-provider",
            parent_span_id="span-root",
            mission_id="mission-1",
            stage="PROVIDER_READ",
            state="PASS",
            occurred_at="2026-08-30T20:01:00+02:00",
            provider="GITHUB",
            proof_refs=("github:readback",),
        )
        self.assertEqual("APPENDED", trace.append(root).state)
        appended = trace.append(child)
        self.assertEqual(2, appended.event_count)
        self.assertEqual("IDEMPOTENT_REPLAY", trace.append(child).state)
        with self.assertRaisesRegex(ValueError, "TRACE_SPAN_CONFLICT"):
            trace.append(
                TraceEvent(
                    **{**child.__dict__, "state": "FAIL"}
                )
            )
        with self.assertRaisesRegex(ValueError, "SENSITIVE_PAYLOAD"):
            trace.append(
                TraceEvent(
                    trace_id="trace-1",
                    span_id="span-secret",
                    parent_span_id="span-root",
                    mission_id="mission-1",
                    stage="PROVIDER_READ",
                    state="HELD",
                    occurred_at="2026-08-30T20:02:00+02:00",
                    sensitive_payload_present=True,
                )
            )

    def test_universal_idempotency_reuses_existing_command_hash_without_granting_authority(self) -> None:
        request = ActionRequest(
            adapter_id="google_drive",
            action="update_document",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="DOC-EXACT-1",
            payload={"document_alias": "TEST_ONLY"},
        )
        command = self.control.command_envelope(request)
        envelope = IdempotencyEnvelope(
            operation_id="op-1",
            command_sha256=str(command["command_sha256"]),
            target_alias=request.target_alias,
            action_scope=request.action,
            effect_class=request.effect.value,
            expires_at="2026-08-30T20:10:00+02:00",
        )
        ledger = IdempotencyLedger()
        first = ledger.admit(envelope, now="2026-08-30T20:00:00+02:00")
        self.assertTrue(first.execute)
        self.assertEqual("ACCEPT_FIRST", first.state)
        duplicate = ledger.admit(envelope, now="2026-08-30T20:01:00+02:00")
        self.assertFalse(duplicate.execute)
        self.assertEqual("HOLD_DUPLICATE_IN_FLIGHT", duplicate.state)
        ledger.record_result("op-1", "provider-readback:receipt-1")
        replay = ledger.admit(envelope, now="2026-08-30T20:02:00+02:00")
        self.assertEqual("REPLAY_SAME_RESULT", replay.state)
        self.assertEqual("provider-readback:receipt-1", replay.result_ref)
        conflict = ledger.admit(
            IdempotencyEnvelope(
                operation_id="op-1",
                command_sha256=str(command["command_sha256"]),
                target_alias="DOC-DIFFERENT",
                action_scope=request.action,
                effect_class=request.effect.value,
                expires_at="2026-08-30T20:10:00+02:00",
            ),
            now="2026-08-30T20:03:00+02:00",
        )
        self.assertEqual("REJECT_CONFLICT", conflict.state)
        self.assertFalse(conflict.execute)

    def test_failure_win_v2_manifest_compiler_separates_structure_from_behavior(self) -> None:
        result = compile_receiver_manifest(
            [
                {
                    "receiver_id": "Bubbles",
                    "canonical_control": "Bubbles control",
                    "primary_id": "bubbles-id",
                    "active": True,
                },
                {
                    "receiver_id": "CFBE-Ω",
                    "canonical_control": "CFBE control",
                    "primary_id": "cfbe-id",
                    "active": True,
                },
            ],
            [
                {
                    "event_id": "V1-CFBE",
                    "timestamp": "2026-08-23T00:00:00Z",
                    "receiver_id": "CFBE-Ω",
                    "kernel_version": "1.0.0",
                    "kernel_invoked": True,
                    "behavior_proven": True,
                    "independent_readback": True,
                    "current": True,
                    "evidence_refs": ["R1"],
                }
            ],
            generated_from="bubbles-host-fixture",
            generated_at="2026-08-27T00:00:00Z",
            source_complete=True,
        )
        self.assertTrue(result.complete)
        self.assertFalse(result.behavior_complete)
        by_id = {item.receiver_id: item for item in result.receivers}
        self.assertEqual("REGISTERED_V2_BEHAVIOR_PENDING", by_id["Bubbles"].receiver_state)
        self.assertEqual("V1_BEHAVIOR_PROVEN_V2_PENDING", by_id["CFBE-Ω"].receiver_state)

    def test_failure_win_v2_bubbles_precursor_canary_invokes_prevention_path(self) -> None:
        incumbent = PerformanceVector(quality=5, reliability=5, proof=5, speed=1)
        candidate = PerformanceVector(
            quality=5,
            reliability=5,
            proof=5,
            speed=4,
            owner_time_recovered=2,
            recovery_gain=2,
        )
        result = FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=FailureObservation(
                    event_id="FWV2-BUBBLES-PRECURSOR-CANARY",
                    event_type=FailureEventType.PRECURSOR_RISK,
                    system_id="Bubbles",
                    objective="preempt a synthetic no-effect route risk",
                    claim="current route may become slow",
                    observed_fruit="precursor only; no provider effect",
                    desired_outcome="prewarm a stronger reversible route",
                    failure_code="SYNTHETIC_PRECURSOR_CANARY",
                    material=False,
                    precursor_signals=("latency-drift-fixture",),
                ),
                incumbent=incumbent,
                routes=(
                    RecoveryRoute(
                        route_id="bubbles-prewarm-fixture",
                        route_type="REROUTE",
                        performance=candidate,
                        proof_strength=1.0,
                        reversibility=1.0,
                        strategic_value=1.0,
                    ),
                ),
            )
        )
        self.assertEqual(FailureWinState.PREEMPTION_READY, result.state)
        self.assertEqual(("bubbles-prewarm-fixture",), result.prewarm_route_ids)
        self.assertFalse(result.proof_graph.complete)


if __name__ == "__main__":
    unittest.main()
