from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, TransitionSpec, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import (
    ClientRuntimePolicy,
    DurabilityMode,
    ExecutionResponse,
    HarvestOutcome,
    InterruptionKind,
    RouteCandidate,
    Sol62CompleteClientRuntime,
    TransitionBinding,
    classify_provider_constraint,
)
from sol_61_runtime.sol_62_genesis_client_bridge import Sol62GenesisWakeBridge
from sol_61_runtime.sol_62_sovereign_plane_binding import Sol62SovereignPlaneBinding
from sol_61_runtime.sol_62 import Sol62Runtime


class FakeAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.routes = []

    async def execute(self, request):
        self.routes.append(request.route.route_id)
        value = self.responses.pop(0)
        if callable(value):
            return value(request)
        return value


class SlowAdapter:
    def __init__(self, delay_seconds, response):
        self.delay_seconds = float(delay_seconds)
        self.response = response
        self.routes = []

    async def execute(self, request):
        self.routes.append(request.route.route_id)
        await asyncio.sleep(self.delay_seconds)
        return self.response


class FakeHarvester:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    async def harvest(self, **kwargs):
        self.calls += 1
        return self.outcome


class Sol62CompleteClientRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = int(time.time())
        self.rt = Sol62Runtime(
            Path(self.tmp.name) / "sol",
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )
        self.client = Sol62CompleteClientRuntime(
            self.rt,
            policy=ClientRuntimePolicy(
                max_attempts_per_wake=8,
                max_total_attempts=32,
                negative_cache_seconds=300,
                retry_delay_seconds=30,
            ),
        )
        self.claims = {
            "iss": "https://token.actions.githubusercontent.com",
            "aud": "sol-runtime",
            "sub": "repo:mosianekk-lang/Federation-Omega:ref:refs/heads/main",
            "iat": self.now - 10,
            "exp": self.now + 300,
            "credential_type": "oidc",
        }
        self.gateway = {
            "runtime_id": "sol-6.2",
            "via_gateway": "sol-gateway",
            "authenticated_principal": "spiffe://sol/client-worker",
            "policy_version": "6.2",
        }

    def tearDown(self):
        self.rt.close()
        self.tmp.cleanup()

    def register(self, *, route=True):
        proof = {
            "proof_id": "p1",
            "subject": "transition:t1",
            "target": "fuse/result",
            "operation": "chat",
            "source_version": "src1",
            "accepted_evidence_classes": ["GATEWAY_READBACK"],
        }
        self.rt.register_mission(
            MissionSpec(
                "m1",
                "complete mission independently of any single provider",
                {"state": "OPEN"},
                {"state": "DONE"},
                success_proofs=(proof,),
            )
        )
        self.rt.register_transition(
            TransitionSpec(
                "t1",
                "m1",
                "chat",
                "fuse/result",
                {"state": "OPEN"},
                {"state": "DONE"},
                required_proofs=(proof,),
                source_version="src1",
            )
        )
        self.client.bind_mission("m1", owner_subject="owner")
        self.client.bind_transition(
            TransitionBinding(
                "t1",
                {"intent": "finish"},
                {"status": "COMPLETE"},
                proof_id="p1",
            )
        )
        if route:
            self.client.register_route(
                RouteCandidate("fuse-auto", "FUSE_GATEWAY", operations=("chat",), priority=100)
            )

    def success(self, route="fuse-auto"):
        return ExecutionResponse(
            True,
            dispatch_started=True,
            provider_ref="trace-" + route,
            readback={"status": "COMPLETE"},
            proof_evidence={"status": "COMPLETE", "route": route},
            evidence_class="GATEWAY_READBACK",
            proof_issuer="FUSE_GATEWAY",
        )

    def test_sovereign_plane_is_attached_without_replacing_sol_truth(self):
        self.register()
        status = self.client.mission_status("m1", now_epoch=self.now)
        self.assertEqual(status["sovereign_plane"]["plane_id"], "FUSE_SOVEREIGN_PLANE_R59")
        mission = self.client._get("sol62.client.mission", "m1")["value"]
        self.assertEqual(mission["sovereign_plane"]["truth_root"], "SOL_6_2")
        self.assertEqual(
            mission["sovereign_plane"]["resident_executor"],
            "FUSE_GENESIS_RESIDENT_EXECUTOR_V2",
        )
        self.assertFalse(mission["sovereign_plane"]["authority_expansion"])

    def test_sovereign_resolver_reorders_only_prequalified_routes(self):
        def resolver(payload):
            return ["local", "chatgpt"]

        self.client = Sol62CompleteClientRuntime(
            self.rt,
            sovereign_plane=Sol62SovereignPlaneBinding(resolver=resolver),
        )
        self.register(route=False)
        self.client.register_route(RouteCandidate("chatgpt", "OPENAI", operations=("chat",), priority=100))
        self.client.register_route(RouteCandidate("local", "LOCAL_FUSE", operations=("chat",), priority=90))
        routes = self.client.eligible_routes("m1", "t1", now_epoch=self.now)
        self.assertEqual([route.route_id for route in routes], ["local", "chatgpt"])
        receipt = self.client._get("sol62.client.route_election", "m1|t1")["value"]
        self.assertEqual(receipt["mode"], "EXTERNAL_SOVEREIGN_RESOLVER")
        self.assertFalse(receipt["authority_expansion"])

    def test_sovereign_resolver_cannot_inject_unqualified_route(self):
        def resolver(payload):
            return ["route-not-in-sol-eligible-set"]

        self.client = Sol62CompleteClientRuntime(
            self.rt,
            sovereign_plane=Sol62SovereignPlaneBinding(resolver=resolver),
        )
        self.register(route=False)
        self.client.register_route(RouteCandidate("local", "LOCAL_FUSE", operations=("chat",), priority=90))
        routes = self.client.eligible_routes("m1", "t1", now_epoch=self.now)
        self.assertEqual([route.route_id for route in routes], ["local"])
        receipt = self.client._get("sol62.client.route_election", "m1|t1")["value"]
        self.assertEqual(receipt["mode"], "SOVEREIGN_RESOLVER_DEGRADED_LOCAL_FALLBACK")

    def test_resume_packet_preserves_sovereign_plane_attachment(self):
        self.register(route=False)
        packet = self.client.resume_packet("m1", reason="WAITING_ROUTE")
        self.assertEqual(packet["orchestration_plane"], "FUSE_SOVEREIGN_PLANE_R59")
        self.assertEqual(packet["truth_root"], "SOL_6_2")
        self.assertEqual(packet["resident_executor"], "FUSE_GENESIS_RESIDENT_EXECUTOR_V2")
        self.assertEqual(packet["five_minute_contract"]["total_slo_seconds"], 300.0)
        self.assertEqual(
            packet["five_minute_contract"]["active_execution_budget_seconds"],
            240.0,
        )
        self.assertFalse(packet["five_minute_contract"]["external_wait_guaranteed"])

    def test_provider_capacity_is_route_local_and_never_mutates_goal(self):
        result = classify_provider_constraint("MAX_WEIGHTED_TOKENS")
        self.assertEqual(result.disposition.value, "ROUTE_LOCAL")
        self.assertFalse(result.mission_terminal)
        self.assertFalse(result.goal_mutation_allowed)
        self.assertTrue(result.retry_requires_changed_route)

    def test_verified_reality_via_fuse_owned_client_runtime(self):
        self.register()
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=FakeAdapter([self.success()]),
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-a",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "VERIFIED_REALITY")
        self.assertEqual(
            result["five_minute_slo"]["state"],
            "FIVE_MINUTE_SLO_VERIFIED",
        )
        self.assertTrue(result["five_minute_slo"]["within_slo"])
        self.assertTrue(result["five_minute_slo"]["acceptance_complete"])
        self.assertTrue(result["five_minute_slo"]["proof_complete"])
        self.assertEqual(self.client.mission_status("m1", now_epoch=self.now)["closure"]["state"], "VERIFIED_REALITY")

    def test_omega_scientia_active_deadline_times_out_to_readback(self):
        self.client = Sol62CompleteClientRuntime(
            self.rt,
            policy=ClientRuntimePolicy(
                max_attempts_per_wake=8,
                max_total_attempts=32,
                negative_cache_seconds=300,
                retry_delay_seconds=30,
                max_active_wake_seconds=0.02,
            ),
        )
        self.register()
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=SlowAdapter(0.05, self.success()),
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-deadline",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "WAITING_READBACK")
        self.assertEqual(
            result["reason"],
            "OMEGA_SCIENTIA_ACTIVE_DEADLINE_EFFECT_STATE_UNKNOWN",
        )
        self.assertTrue(result["active_deadline_timeout"])
        inflight = self.rt.recover_inflight_effects()
        self.assertEqual(len(inflight), 1)
        self.assertIn(
            inflight[0]["action"],
            {"SAFE_RETRY_WITH_SAME_IDEMPOTENCY_KEY", "PROBE_PROVIDER_BEFORE_RETRY", "PROBE_THEN_RETRY_IF_ABSENT"},
        )

    def test_five_minute_receipt_includes_full_mission_elapsed_not_only_current_wake(self):
        self.register()
        self.client._update_client_mission(
            "m1",
            mission_started_epoch=time.time() - 301.0,
        )
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=FakeAdapter([self.success()]),
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-old-mission",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "VERIFIED_REALITY")
        slo = result["five_minute_slo"]
        self.assertEqual(slo["state"], "FIVE_MINUTE_SLO_VIOLATED")
        self.assertFalse(slo["within_slo"])
        self.assertGreater(slo["observed_wall_seconds"], 300.0)
        self.assertTrue(slo["acceptance_complete"])
        self.assertTrue(slo["proof_complete"])

    def test_context_limit_auto_reroutes_without_goal_mutation(self):
        self.register(route=False)
        self.client.register_route(RouteCandidate("chatgpt", "OPENAI", operations=("chat",), priority=100))
        self.client.register_route(RouteCandidate("local", "LOCAL_FUSE", operations=("chat",), priority=90))
        adapter = FakeAdapter(
            [
                ExecutionResponse(False, dispatch_started=False, constraint_code="MAX_WEIGHTED_TOKENS", message="context limit"),
                self.success("local"),
            ]
        )
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=adapter,
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-a",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "VERIFIED_REALITY")
        self.assertEqual(adapter.routes, ["chatgpt", "local"])
        client = self.client._get("sol62.client.mission", "m1")["value"]
        self.assertTrue(client["goal_mutation_by_provider_forbidden"])

    def test_route_local_requeue_rejects_non_cancelled_effect(self):
        self.register(route=False)
        transition = self.client._get("sol62.transition", "t1")["value"]
        from sol_61_runtime.sol_62 import ExecutionIntent
        from sol_61_runtime.sol_62_frontier_primitives import FenceError

        effect_id = "manual-effect"
        intent = ExecutionIntent(
            effect_id,
            "t1",
            "OPENAI",
            {"intent": "finish"},
            "AT_MOST_ONCE",
            "manual-idem",
            "owner",
            transition["source_version"],
            {"status": "COMPLETE"},
            False,
        )
        self.rt.prepare_execution(
            intent,
            gateway_request=self.gateway,
            identity_claims=self.claims,
            now_epoch=self.now,
        )
        fence = self.rt.acquire_execution_fence(
            "t1", "worker-a", ttl_seconds=60, now_epoch=self.now
        )
        self.rt.authorize_dispatch(
            effect_id,
            authority_lease_id=None,
            actor="owner",
            source_version=transition["source_version"],
            now_epoch=self.now,
            worker="worker-a",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )
        self.rt.mark_dispatched(effect_id, provider_ref="provider-ref")
        with self.assertRaisesRegex(
            FenceError, "ROUTE_LOCAL_REQUEUE_REQUIRES_CANCELLED_EFFECT"
        ):
            self.rt.requeue_after_pre_dispatch_cancel(
                effect_id=effect_id,
                transition_id="t1",
                mission_id="m1",
                worker="worker-a",
                lease_epoch=fence["epoch"],
                fencing_token=fence["fencing_token"],
                now_epoch=self.now,
            )

    def test_route_local_requeue_rejects_stale_fence(self):
        self.register(route=False)
        transition = self.client._get("sol62.transition", "t1")["value"]
        from sol_61_runtime.sol_62 import ExecutionIntent
        from sol_61_runtime.sol_62_frontier_primitives import FenceError

        effect_id = "cancelled-effect"
        intent = ExecutionIntent(
            effect_id,
            "t1",
            "OPENAI",
            {"intent": "finish"},
            "AT_MOST_ONCE",
            "cancelled-idem",
            "owner",
            transition["source_version"],
            {"status": "COMPLETE"},
            False,
        )
        self.rt.prepare_execution(
            intent,
            gateway_request=self.gateway,
            identity_claims=self.claims,
            now_epoch=self.now,
        )
        fence = self.rt.acquire_execution_fence(
            "t1", "worker-a", ttl_seconds=60, now_epoch=self.now
        )
        self.rt.authorize_dispatch(
            effect_id,
            authority_lease_id=None,
            actor="owner",
            source_version=transition["source_version"],
            now_epoch=self.now,
            worker="worker-a",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )
        self.rt.control.transition_effect(
            effect_id,
            expected_state="DISPATCHING",
            next_state="CANCELLED",
        )
        with self.assertRaisesRegex(FenceError, "STALE_FENCE"):
            self.rt.requeue_after_pre_dispatch_cancel(
                effect_id=effect_id,
                transition_id="t1",
                mission_id="m1",
                worker="worker-a",
                lease_epoch=fence["epoch"],
                fencing_token=fence["fencing_token"] + 1,
                now_epoch=self.now,
            )

    def test_route_local_requeue_changes_running_back_to_queued_once(self):
        self.register(route=False)
        transition = self.client._get("sol62.transition", "t1")["value"]
        from sol_61_runtime.sol_62 import ExecutionIntent
        from sol_61_runtime.sol_62_frontier_primitives import FenceError

        effect_id = "cancelled-effect-ok"
        intent = ExecutionIntent(
            effect_id,
            "t1",
            "OPENAI",
            {"intent": "finish"},
            "AT_MOST_ONCE",
            "cancelled-idem-ok",
            "owner",
            transition["source_version"],
            {"status": "COMPLETE"},
            False,
        )
        self.rt.prepare_execution(
            intent,
            gateway_request=self.gateway,
            identity_claims=self.claims,
            now_epoch=self.now,
        )
        fence = self.rt.acquire_execution_fence(
            "t1", "worker-a", ttl_seconds=60, now_epoch=self.now
        )
        self.rt.authorize_dispatch(
            effect_id,
            authority_lease_id=None,
            actor="owner",
            source_version=transition["source_version"],
            now_epoch=self.now,
            worker="worker-a",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
        )
        self.rt.control.transition_effect(
            effect_id,
            expected_state="DISPATCHING",
            next_state="CANCELLED",
        )
        receipt = self.rt.requeue_after_pre_dispatch_cancel(
            effect_id=effect_id,
            transition_id="t1",
            mission_id="m1",
            worker="worker-a",
            lease_epoch=fence["epoch"],
            fencing_token=fence["fencing_token"],
            now_epoch=self.now,
        )
        self.assertEqual(receipt["state"], "QUEUED")
        self.assertEqual(self.rt.transition_status("t1")["value"]["status"], "QUEUED")
        with self.assertRaisesRegex(
            FenceError, "ROUTE_LOCAL_REQUEUE_REQUIRES_RUNNING_TRANSITION"
        ):
            self.rt.requeue_after_pre_dispatch_cancel(
                effect_id=effect_id,
                transition_id="t1",
                mission_id="m1",
                worker="worker-a",
                lease_epoch=fence["epoch"],
                fencing_token=fence["fencing_token"],
                now_epoch=self.now,
            )

    def test_safety_or_authority_gate_does_not_get_bypassed(self):
        self.register(route=False)
        self.client.register_route(RouteCandidate("provider-a", "A", operations=("chat",), priority=100))
        self.client.register_route(RouteCandidate("provider-b", "B", operations=("chat",), priority=90))
        adapter = FakeAdapter(
            [ExecutionResponse(False, dispatch_started=False, constraint_code="SAFETY_BOUNDARY")]
        )
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=adapter,
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-a",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "HELD_GATE")
        self.assertEqual(adapter.routes, ["provider-a"])

    def test_auto_harvest_adds_missing_route_then_completes(self):
        self.register(route=False)
        harvester = FakeHarvester(
            HarvestOutcome(routes=(RouteCandidate("harvested", "LOCAL_FUSE", operations=("chat",), priority=100),))
        )
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=FakeAdapter([self.success("harvested")]),
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-a",
                now_epoch=self.now,
                harvester=harvester,
            )
        )
        self.assertEqual(result["state"], "VERIFIED_REALITY")
        self.assertGreaterEqual(harvester.calls, 1)

    def test_missing_harvest_route_persists_resume_packet(self):
        self.register(route=False)
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=FakeAdapter([]),
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="worker-a",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "WAITING_ROUTE")
        self.assertEqual(result["resume_packet"]["task_type"], "SOL62_CLIENT_WAKE")
        self.assertFalse(result["resume_packet"]["goal_mutation_allowed"])

    def test_client_state_survives_runtime_restart(self):
        self.register()
        self.client.create_client_session("s1", owner_subject="owner", now_epoch=self.now)
        root = Path(self.tmp.name) / "sol"
        self.rt.close()
        self.rt = Sol62Runtime(
            root,
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )
        self.client = Sol62CompleteClientRuntime(self.rt)
        row = self.client._get("sol62.client.session", "s1")
        self.assertEqual(row["value"]["owner_subject"], "owner")
        self.assertIsNotNone(self.client._get("sol62.client.mission", "m1"))

    def test_genesis_wake_handoff_is_idempotent(self):
        self.register(route=False)
        packet = self.client.resume_packet("m1", reason="WAITING_ROUTE")
        bridge = Sol62GenesisWakeBridge(Path(self.tmp.name) / "resident")
        first = bridge.enqueue(packet, now_epoch=self.now)
        second = bridge.enqueue(packet, now_epoch=self.now + 1)
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(first["executor"], "FUSE_GENESIS_RESIDENT_EXECUTOR_V2")


    def test_durable_resume_packet_binds_checkpoint_and_canonical_history(self):
        self.register()
        status = self.client.durability_status("m1")
        self.assertEqual(status["policy"]["mode"], DurabilityMode.EFFECT_BOUNDARY.value)
        self.assertEqual(status["event_truth_root"], "SOL62_CONTROL_EVENTS")
        self.assertEqual(status["effect_truth_root"], "SOL62_EFFECT_INTENT")
        self.assertFalse(status["history"]["payloads_included"])
        self.assertGreaterEqual(status["history"]["event_count_total"], 1)

        packet = self.client.resume_packet("m1", reason="TEST_DURABLE_HANDOFF")
        self.assertEqual(packet["schema"], "SOL62_CLIENT_RESUME_PACKET_V1")
        self.assertEqual(packet["schema_version"], 2)
        self.assertTrue(packet["durability_checkpoint_key"].startswith("m1|"))
        self.assertEqual(len(packet["durability_checkpoint_sha256"]), 64)
        latest = self.client._get("sol62.durable.checkpoint_latest", "m1")
        self.assertEqual(latest["value"]["checkpoint_key"], packet["durability_checkpoint_key"])

    def test_durable_interrupt_pauses_wake_and_resume_packet_binds_checkpoint(self):
        self.register()
        opened = self.client.interrupt_mission(
            "m1",
            interruption_id="int-approval-1",
            kind=InterruptionKind.APPROVAL,
            reason="bounded approval required",
            transition_id="t1",
            payload={"scope": "review"},
            now_epoch=self.now,
        )
        self.assertEqual(opened["value"]["state"], "OPEN")
        self.assertFalse(opened["value"]["effect_authorized_by_decision"])

        class NeverExecute:
            calls = 0
            async def execute(inner_self, request):
                inner_self.calls += 1
                raise AssertionError("execution must remain paused while interruption is open")

        adapter = NeverExecute()
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=adapter,
                gateway_request={},
                identity_claims={},
                worker="test",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "WAITING_INTERRUPT")
        self.assertEqual(adapter.calls, 0)
        self.assertIn("int-approval-1", result["resume_packet"]["open_interruption_ids"])

        resolved = self.client.resolve_interruption(
            "m1",
            interruption_id="int-approval-1",
            decision="APPROVE",
            actor="owner-authenticated-client",
            proof_refs=("approval-receipt-1",),
            now_epoch=self.now + 1,
        )
        self.assertEqual(resolved["value"]["state"], "RESOLVED")
        self.assertFalse(resolved["value"]["effect_authorized_by_decision"])
        self.assertEqual(self.client.open_interruptions("m1"), [])

    def test_durable_interruption_is_idempotent_and_collision_fails_closed(self):
        self.register()
        first = self.client.interrupt_mission(
            "m1",
            interruption_id="int-input-1",
            kind=InterruptionKind.EXTERNAL_INPUT,
            reason="need external input",
            payload={"field": "x"},
            now_epoch=self.now,
        )
        second = self.client.interrupt_mission(
            "m1",
            interruption_id="int-input-1",
            kind=InterruptionKind.EXTERNAL_INPUT,
            reason="need external input",
            payload={"field": "x"},
            now_epoch=self.now + 3,
        )
        self.assertEqual(first["value"]["identity_sha256"], second["value"]["identity_sha256"])
        with self.assertRaisesRegex(Exception, "INTERRUPTION_ID_COLLISION"):
            self.client.interrupt_mission(
                "m1",
                interruption_id="int-input-1",
                kind=InterruptionKind.EXTERNAL_INPUT,
                reason="different input request",
                payload={"field": "y"},
                now_epoch=self.now + 4,
            )

    def test_event_history_manifest_is_hash_only_and_detects_change(self):
        self.register()
        before = self.client.event_history_manifest("m1")
        self.client.interrupt_mission(
            "m1",
            interruption_id="int-history-1",
            kind=InterruptionKind.MANUAL_PAUSE,
            reason="history-change",
            now_epoch=self.now,
        )
        after = self.client.event_history_manifest("m1")
        self.assertNotEqual(before["history_sha256"], after["history_sha256"])
        self.assertGreater(after["event_count_total"], before["event_count_total"])
        self.assertNotIn("payload", after["events"][0])


    def test_durability_checkpoint_replay_guard_verifies_exact_history_prefix(self):
        self.register()
        packet = self.client.resume_packet("m1", reason="REPLAY_GUARD_TEST")
        guard = self.client.verify_durability_checkpoint(packet["durability_checkpoint_key"])
        self.assertTrue(guard["verified"])
        self.assertTrue(packet["replay_guard_verified"])
        self.assertEqual(
            packet["replay_guard_history_sha256"],
            guard["history_sha256_observed"],
        )
        self.assertEqual(
            guard["history_sha256_observed"],
            guard["history_sha256_expected"],
        )
        self.assertEqual(
            guard["event_head_observed"],
            guard["event_head_expected"],
        )


    def test_provider_attempt_emits_safe_trace_lineage(self):
        self.register()
        result = asyncio.run(
            self.client.wake_until_terminal(
                "m1",
                adapter=FakeAdapter([self.success()]),
                gateway_request=self.gateway,
                identity_claims=self.claims,
                worker="test",
                now_epoch=self.now,
            )
        )
        self.assertEqual(result["state"], "VERIFIED_REALITY")
        rows = self.rt.control.db.execute(
            "SELECT payload_json FROM events WHERE kind='SOL62_TRACE_EMITTED' ORDER BY seq"
        ).fetchall()
        self.assertGreaterEqual(len(rows), 1)
        payload = rows[-1]["payload_json"]
        self.assertIn("sol.provider", payload)
        self.assertIn("sol.effect.id_hash", payload)
        self.assertNotIn("complete mission independently", payload)
        self.assertNotIn("authorization", payload.lower())


if __name__ == "__main__":
    unittest.main()
