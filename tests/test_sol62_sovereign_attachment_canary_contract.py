from __future__ import annotations

import asyncio
import json
import tempfile
import unittest

import httpx
from pathlib import Path

from fuse_genesis.currentness import SourceEpoch
from fuse_genesis.resident_host import HostState, ResidentHost
from services.sol62_client_runtime.browser_carrier_resilience import (
    BrowserCarrierSupervisor,
    CarrierRegistration,
)
from services.sol62_client_runtime.sovereign_entry import app
from sol_61_runtime.sol_62 import GatewayPolicy, MissionSpec, Sol62Runtime, WorkloadIdentityPolicy
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime
from sol_61_runtime.sol_62_genesis_client_bridge import Sol62GenesisWakeBridge
from sol_61_runtime.sol_62_sovereign_plane_binding import Sol62SovereignPlaneBinding


class Sol62SovereignAttachmentCanaryContractTests(unittest.TestCase):
    def _runtime(self, root: Path) -> Sol62Runtime:
        return Sol62Runtime(
            root,
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"issuer"},
                audience="aud",
                subject_prefix="sub:",
                max_ttl_seconds=600,
            ),
        )

    def test_status_exposes_subordinate_transactional_contract_without_authority_widening(self):
        async def read_status():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://sol62.test",
            ) as client:
                health = await client.get("/health")
                status = await client.get("/api/status")
                return health, status

        health, status = asyncio.run(read_status())
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        self.assertEqual(status.status_code, 200)
        body = status.json()
        self.assertEqual(body["service_id"], "runtime.transactional")
        self.assertEqual(body["capability_id"], "CAP-SOL62-TRANSACTIONAL-RUNTIME-V1")
        self.assertEqual(body["ecp_id"], "ECP-SOL62-SOVEREIGN-PLANE-START438-001")
        self.assertEqual(body["sol_role"], "transactional_execution_state_spine")
        self.assertEqual(body["orchestration_plane"], "FUSE_SOVEREIGN_PLANE_R59")
        self.assertEqual(body["truth_root"], "SOL_6_2")
        self.assertEqual(body["source_arbiter"], "FDOF")
        self.assertEqual(body["state_integrity"], "SICF")
        self.assertEqual(body["proof_plane"], "PROOFOS_REALITY_JUDGE")
        self.assertEqual(body["resident_executor"], "FUSE_GENESIS_RESIDENT_EXECUTOR_V2")
        self.assertFalse(body["authority_expansion"])
        self.assertFalse(body["provider_effect_authorized"])
        self.assertFalse(body["scheduler_ownership"])
        self.assertFalse(body["independent_finality"])
        self.assertEqual(body["capability_registry"]["schema"], "SOL62_CAPABILITY_REGISTRY_V1")

    def test_genesis_packet_executes_once_resumes_after_reload_and_stale_fence_cannot_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            runtime = self._runtime(base / "sol")
            try:
                client = Sol62CompleteClientRuntime(runtime, sovereign_plane=Sol62SovereignPlaneBinding())
                runtime.register_mission(
                    MissionSpec("mission-canary", "durable sovereign continuation", {"state": "OPEN"}, {"state": "DONE"})
                )
                client.bind_mission("mission-canary", owner_subject="owner")
                packet = client.resume_packet("mission-canary", reason="CANARY_RESTART_WAKE")
                self.assertEqual(packet["orchestration_plane"], "FUSE_SOVEREIGN_PLANE_R59")
                self.assertTrue(packet["replay_guard_verified"])

                resident_root = base / "genesis"
                bridge = Sol62GenesisWakeBridge(resident_root)
                queued = bridge.enqueue(packet, now_epoch=1000)
                epoch = SourceEpoch("a" * 40, "F345", 345, "MISSION-FUSE-WORKSPACE-20260923-001")
                host = ResidentHost(resident_root, epoch, interval=0)
                receipt = host.run(
                    handler=lambda payload: {
                        "mission_id": payload["mission_id"],
                        "same_sol_mission": payload["mission_id"] == "mission-canary",
                        "replay_guard_verified": bool(payload["replay_guard_verified"]),
                    },
                    max_ticks=1,
                    now_fn=lambda: 1001,
                    sleep_fn=lambda _: None,
                )
                host.close()
                self.assertEqual(receipt["processed"], 1)

                reloaded = HostState(resident_root)
                task = reloaded.task(queued["task_id"])
                self.assertEqual(task["state"], "COMPLETE")
                result = json.loads(task["result_json"])
                self.assertTrue(result["same_sol_mission"])
                self.assertIsNone(reloaded.next_task())
                reloaded.close()

                duplicate = bridge.enqueue(packet, now_epoch=1002)
                self.assertEqual(duplicate["task_id"], queued["task_id"])
                reloaded = HostState(resident_root)
                self.assertIsNone(reloaded.next_task())
                reloaded.close()

                current = ResidentHost(
                    resident_root,
                    SourceEpoch("a" * 40, "F345", 346, "MISSION-FUSE-WORKSPACE-20260923-001"),
                    interval=0,
                )
                current.start(now=1003)
                stale = ResidentHost(resident_root, epoch, interval=0)
                with self.assertRaisesRegex(RuntimeError, "STALE_SOURCE_EPOCH|STALE_OR_DUPLICATE_HOST_FENCE"):
                    stale.start(now=1004)
                stale.close()
                current.state.release(current.instance_id, current.fence, 1005)
                current.close()
            finally:
                runtime.close()

    def test_stream_loss_re_elects_independent_carrier_without_effect_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(Path(tmp) / "sol")
            try:
                client = Sol62CompleteClientRuntime(runtime, sovereign_plane=Sol62SovereignPlaneBinding())
                runtime.register_mission(
                    MissionSpec("m1", "survive chat stream loss", {"state": "OPEN"}, {"state": "DONE"})
                )
                client.bind_mission("m1", owner_subject="owner")
                supervisor = BrowserCarrierSupervisor(client, heartbeat_ttl_seconds=45)
                supervisor.register(
                    CarrierRegistration(
                        carrier_id="chatgpt-tab",
                        owner_subject="owner",
                        session_id="s-chat",
                        client_kind="CHATGPT_BROWSER",
                        priority=100,
                        failure_domain="CHATGPT_BROWSER",
                    ),
                    now_epoch=2000,
                )
                supervisor.register(
                    CarrierRegistration(
                        carrier_id="fuse-web",
                        owner_subject="owner",
                        session_id="s-fuse",
                        client_kind="FUSE_WEB",
                        priority=10,
                        failure_domain="FUSE_OWNED_WEB",
                    ),
                    now_epoch=2000,
                )
                supervisor.attach_mission("m1", owner_subject="owner", carrier_id="chatgpt-tab", now_epoch=2000)
                result = supervisor.failover(
                    "m1",
                    owner_subject="owner",
                    failed_carrier_id="chatgpt-tab",
                    failure_code="STREAM_CACHE_EXPIRED",
                    event_id="stream-expired-canary",
                    now_epoch=2001,
                )
                self.assertEqual(result["state"], "HYDRATE_REPLACEMENT")
                self.assertEqual(result["replacement_carrier_id"], "fuse-web")
                self.assertEqual(result["hydration"]["mission_id"], "m1")
                self.assertFalse(result["effect_replay_allowed"])
                self.assertTrue(result["effect_readback_before_retry"])
                self.assertFalse(result["mission_terminal"])
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
