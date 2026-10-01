from __future__ import annotations

import tempfile
import unittest

from fuse_genesis.currentness import SourceEpoch
from fuse_genesis.resident_host import HostState
from services.fuse_mobile_gateway.runtime import GatewayRuntime, VerifiedIdentity
from services.sol62_client_runtime.resident_worker import Sol62ResidentProcessor
from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, Sol62Runtime, WorkloadIdentityPolicy


class Session:
    async def verify(self, token):
        return VerifiedIdentity("owner")

    async def issue(self, identity):
        return ("session", 9999999999)


class ResidentWorkerTests(unittest.TestCase):
    def test_persisted_build_packet_survives_without_live_build_executor(self):
        with tempfile.TemporaryDirectory() as td:
            sol = Sol62Runtime(
                td + "/sol",
                gateway_policy=GatewayPolicy("g", "r"),
                identity_policy=WorkloadIdentityPolicy(
                    allowed_issuers={"issuer"},
                    audience="aud",
                    subject_prefix="sub:",
                    max_ttl_seconds=600,
                ),
            )
            gateway = GatewayRuntime(session_manager=Session())
            worker = Sol62ResidentProcessor(
                gateway=gateway,
                sol=sol,
                genesis_root=td + "/genesis",
            )
            try:
                sol.register_mission(MissionSpec("m", "finish", {"state": "OPEN"}, {"state": "DONE"}))
                worker.client.bind_mission("m", owner_subject="owner")
                result = worker.process(
                    {
                        "task_type": "SOL62_CLIENT_BUILD",
                        "mission_id": "m",
                        "transition_id": "t",
                        "source_frontier": "abc",
                        "authority_boundary": {
                            "source_mutation_authority_granted": False,
                            "provider_effect_authority_granted": False,
                        },
                    }
                )
                self.assertEqual(result["state"], "WAITING_BUILD_EXECUTOR")
                rows = worker.client._rows("sol62.client.build_work")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["value"]["state"], "WAITING_BUILD_EXECUTOR")
            finally:
                worker.close()


if __name__ == "__main__":
    unittest.main()
