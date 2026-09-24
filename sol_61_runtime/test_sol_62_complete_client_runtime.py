from __future__ import annotations

import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, TransitionSpec, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import (
    ClientRuntimePolicy,
    ExecutionResponse,
    HarvestOutcome,
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
        self.assertEqual(self.client.mission_status("m1", now_epoch=self.now)["closure"]["state"], "VERIFIED_REALITY")

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


if __name__ == "__main__":
    unittest.main()
