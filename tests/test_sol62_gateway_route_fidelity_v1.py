from __future__ import annotations

import asyncio
import unittest

from federation.mobile_gateway.fuse_mobile_v1 import Capability
from services.fuse_mobile_gateway.runtime import ExecutionResult, GatewayRuntime, VerifiedIdentity
from services.sol62_client_runtime.gateway_adapter import GatewayChatAdapter
from sol_61_runtime.sol_62_complete_client_runtime import (
    ExecutionRequest,
    RouteCandidate,
    TransitionBinding,
)


class StaticHealth:
    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]:
        del identity
        return ()


class RoutedExecutor:
    route_id = "ROUTE-A"
    provider = "PROVIDER-A"

    def __init__(self, *, returned_provider: str = "PROVIDER-A") -> None:
        self.returned_provider = returned_provider
        self.calls = 0

    async def execute(self, *, request, decision, identity) -> ExecutionResult:
        del request, decision, identity
        self.calls += 1
        return ExecutionResult(
            text="ok",
            trace_id="trace-route-fidelity",
            provider=self.returned_provider,
            model="model-a",
            source_refs=("proof:route-fidelity",),
        )


def request(route_id: str) -> ExecutionRequest:
    return ExecutionRequest(
        mission_id="mission-1",
        transition_id="transition-1",
        effect_id="effect-1",
        route=RouteCandidate(route_id, "PROVIDER-A", operations=("chat",)),
        binding=TransitionBinding(
            "transition-1",
            {"intent": "prove route fidelity"},
            {"status": "OK"},
            effect_class="READ_ONLY",
        ),
        objective="prove route fidelity",
    )


class Sol62GatewayRouteFidelityV1Tests(unittest.TestCase):
    def adapter(self, executor: RoutedExecutor) -> GatewayChatAdapter:
        gateway = GatewayRuntime(
            health_provider=StaticHealth(),
            chat_executor=executor,
        )
        return GatewayChatAdapter(gateway, VerifiedIdentity("owner:kim"))

    def test_selected_route_mismatch_blocks_before_provider_dispatch(self) -> None:
        executor = RoutedExecutor()
        response = asyncio.run(self.adapter(executor).execute(request("ROUTE-B")))
        self.assertFalse(response.success)
        self.assertFalse(response.dispatch_started)
        self.assertEqual(response.constraint_code, "EXECUTOR_ROUTE_MISMATCH")
        self.assertEqual(executor.calls, 0)

    def test_selected_route_matches_bound_executor_and_emits_fidelity_evidence(self) -> None:
        executor = RoutedExecutor()
        response = asyncio.run(self.adapter(executor).execute(request("ROUTE-A")))
        self.assertTrue(response.success)
        self.assertTrue(response.dispatch_started)
        self.assertEqual(executor.calls, 1)
        evidence = response.proof_evidence
        self.assertTrue(evidence["route_fidelity_verified"])
        self.assertEqual(evidence["selected_route_id"], "ROUTE-A")
        self.assertEqual(evidence["bound_executor_route_id"], "ROUTE-A")
        self.assertEqual(evidence["bound_executor_provider"], "PROVIDER-A")

    def test_provider_readback_mismatch_is_not_silently_promoted(self) -> None:
        executor = RoutedExecutor(returned_provider="PROVIDER-B")
        response = asyncio.run(self.adapter(executor).execute(request("ROUTE-A")))
        self.assertFalse(response.success)
        self.assertTrue(response.dispatch_started)
        self.assertEqual(response.constraint_code, "EXECUTOR_PROVIDER_READBACK_MISMATCH")
        self.assertEqual(response.readback["provider"], "PROVIDER-B")
        self.assertEqual(executor.calls, 1)


if __name__ == "__main__":
    unittest.main()
