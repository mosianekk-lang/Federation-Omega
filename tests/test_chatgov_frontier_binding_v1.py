from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3 import (
    ConnectorGateway,
    DurableState,
    FrontierControlPlane,
    MissionPlan,
    frontier_binding_receipt,
)


def mission_plan() -> MissionPlan:
    return MissionPlan(
        mission_id="mission-frontier-binding",
        objective="read the same provider state safely",
        mission_type="software_build",
        active_specialists=["Bubbles"],
        active_connectors=["GitHub"],
        excluded_connectors=[],
        retrieval_budget=3,
        tool_result_token_budget=2048,
        max_parallel_lanes=4,
        created_at="2026-09-05T14:00:00+02:00",
    )


class FrontierBindingTests(unittest.TestCase):
    def test_package_exports_load_bearing_frontier_control_plane(self):
        plane = FrontierControlPlane()
        receipt = plane.receipt()
        self.assertEqual("CHATGOV-FRONTIER-BINDING-V1", receipt.schema)
        self.assertIn("FRONTIER_RUNTIME_V2", receipt.bound_layers)
        self.assertIn("FRONTIER_RESILIENCE_V3", receipt.bound_layers)
        self.assertIn("FRONTIER_EVOLUTION_V4", receipt.bound_layers)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.traffic_change_authorized)
        self.assertFalse(receipt.source_promotion_authorized)
        self.assertFalse(receipt.skill_promotion_authorized)
        self.assertEqual(64, len(receipt.receipt_sha256))
        self.assertEqual(receipt, frontier_binding_receipt())

    def test_frontier_directly_rejects_effectful_singleflight(self):
        plane = FrontierControlPlane()
        with self.assertRaisesRegex(
            ValueError, "FRONTIER_SINGLEFLIGHT_EFFECT_CLASS_FORBIDDEN"
        ):
            plane.execute_safe_read(
                key="effectful",
                fn=lambda: {"written": True},
                effect_class="CONSEQUENTIAL_EFFECT",
            )

    def test_connector_gateway_coalesces_concurrent_explicit_safe_reads(self):
        with tempfile.TemporaryDirectory() as td:
            state = DurableState(str(Path(td) / "state.sqlite3"))
            plane = FrontierControlPlane()
            gateway = ConnectorGateway(state, frontier=plane)
            plan = mission_plan()
            started = threading.Event()
            release = threading.Event()
            calls: list[str] = []
            results: list[dict] = []
            errors: list[BaseException] = []
            lock = threading.Lock()

            def work():
                with lock:
                    calls.append("provider-read")
                started.set()
                if not release.wait(2.0):
                    raise TimeoutError("test release not observed")
                return {"semantic": "ok", "provider_effect_performed": False}

            def runner():
                try:
                    result = gateway.execute(
                        plan=plan,
                        connector="GitHub",
                        action="read",
                        target="same-target",
                        fn=work,
                        semantic_check=lambda payload: payload["semantic"] == "ok",
                        source_version="v1",
                        effect_class="READ_ONLY",
                    )
                    with lock:
                        results.append(result)
                except BaseException as exc:
                    with lock:
                        errors.append(exc)

            first = threading.Thread(target=runner)
            second = threading.Thread(target=runner)
            first.start()
            self.assertTrue(started.wait(2.0))
            second.start()
            time.sleep(0.05)
            release.set()
            first.join(2.0)
            second.join(2.0)

            self.assertEqual([], errors)
            self.assertEqual(1, len(calls))
            self.assertEqual(2, len(results))
            self.assertEqual(1, plane.singleflight.executions)
            self.assertEqual(1, plane.singleflight.coalesced_waiters)
            self.assertTrue(all(row["frontier_singleflight"] for row in results))
            self.assertTrue(all(row["payload"]["semantic"] == "ok" for row in results))

    def test_unspecified_or_effectful_gateway_work_never_enters_singleflight(self):
        with tempfile.TemporaryDirectory() as td:
            state = DurableState(str(Path(td) / "state.sqlite3"))
            plane = FrontierControlPlane()
            gateway = ConnectorGateway(state, frontier=plane)
            plan = mission_plan()
            calls: list[int] = []

            for _ in range(2):
                result = gateway.execute(
                    plan=plan,
                    connector="GitHub",
                    action="write-like-test",
                    target="same-target",
                    fn=lambda: calls.append(1) or {"ok": True},
                    source_version="v1",
                    force_revalidation=True,
                    retry_attempts=1,
                    effect_class="BOUNDED_EFFECT",
                )
                self.assertFalse(result["frontier_singleflight"])

            self.assertEqual(2, len(calls))
            self.assertEqual(0, plane.singleflight.executions)


if __name__ == "__main__":
    unittest.main()
