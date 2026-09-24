from __future__ import annotations

import asyncio
import unittest

from services.fuse_mobile_gateway.runtime import ExecutionResult, GatewayRuntime, RuntimeBindingError, VerifiedIdentity
from services.sol62_client_runtime.gateway_adapter import GatewayChatAdapter
from sol_61_runtime.sol_62_complete_client_runtime import ExecutionRequest, RouteCandidate, TransitionBinding


class Executor:
    async def execute(self, *, request, decision, identity):
        return ExecutionResult(
            text="done",
            trace_id="trace-1",
            status="COMPLETE",
            provider="LOCAL_FUSE",
            model="local",
            source_refs=("r1",),
        )


class Health:
    async def capabilities(self, identity):
        return ()


class Session:
    async def verify(self, token):
        return VerifiedIdentity("owner")

    async def issue(self, identity):
        return ("session", 9999999999)


class GatewayAdapterTests(unittest.TestCase):
    def request(self):
        return ExecutionRequest(
            mission_id="m",
            transition_id="t",
            effect_id="e",
            route=RouteCandidate("fuse", "FUSE_GATEWAY"),
            binding=TransitionBinding("t", {"intent": "finish"}, {"status": "COMPLETE"}),
            objective="finish",
        )

    def test_gateway_success_becomes_gateway_readback_proof(self):
        gateway = GatewayRuntime(
            session_manager=Session(),
            chat_executor=Executor(),
            health_provider=Health(),
        )
        result = asyncio.run(GatewayChatAdapter(gateway, VerifiedIdentity("owner")).execute(self.request()))
        self.assertTrue(result.success)
        self.assertEqual(result.provider_ref, "trace-1")
        self.assertEqual(result.evidence_class, "GATEWAY_READBACK")
        self.assertEqual(result.readback, {"status": "COMPLETE"})

    def test_unbound_executor_is_pre_dispatch_failure(self):
        gateway = GatewayRuntime(session_manager=Session(), health_provider=Health())
        result = asyncio.run(GatewayChatAdapter(gateway, VerifiedIdentity("owner")).execute(self.request()))
        self.assertFalse(result.success)
        self.assertFalse(result.dispatch_started)
        self.assertEqual(result.constraint_code, "FEDERATION_EXECUTOR_UNBOUND")


if __name__ == "__main__":
    unittest.main()
