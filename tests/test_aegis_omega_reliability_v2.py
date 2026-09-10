from __future__ import annotations

import asyncio
import concurrent.futures
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AEGIS_SRC = ROOT / "services" / "aegis_omega" / "src"
if str(AEGIS_SRC) not in sys.path:
    sys.path.insert(0, str(AEGIS_SRC))

from aegis_omega.schemas import Assessment
from aegis_omega.storage import (
    InMemoryCaseStore,
    _legacy_request_id_safe,
    _request_doc_key,
)
from services.fuse_mobile_gateway.aegis_edge_bridge import submit_posture


def _assessment(case_id: str = "case-reliability-1") -> Assessment:
    return Assessment(
        case_id=case_id,
        risk_score=0.2,
        confidence=0.9,
        disposition="observe",
        signals=[],
    )


def _healthy_posture() -> dict:
    return {
        "schema": "AEGIS_EDGE_POSTURE_V1",
        "sample_id": "healthy-001",
        "collected_at": "2026-09-10T13:50:00+02:00",
        "consent": True,
        "platform": "android",
        "os_major": "16",
        "security_patch_month": "2026-09",
        "app_version_major_minor": "1.0",
        "screen_lock_configured": True,
        "developer_mode": False,
        "adb_enabled": False,
        "app_debuggable": False,
        "secure_store_available": True,
        "gateway_https": True,
        "session_present": True,
    }


class AegisOmegaReliabilityV2Tests(unittest.TestCase):
    def test_healthy_posture_is_local_no_change_and_never_calls_provider_sink(self):
        calls = []

        async def sink(request_id, events):
            calls.append((request_id, events))
            raise AssertionError("healthy posture must not call provider")

        receipt = asyncio.run(
            submit_posture(
                subject="owner",
                device_hash="a" * 64,
                posture=_healthy_posture(),
                sink=sink,
                allow_provider_effect=True,
            )
        )
        self.assertEqual("NO_CHANGE", receipt.status)
        self.assertEqual(0, receipt.event_count)
        self.assertIsNone(receipt.case_id)
        self.assertFalse(receipt.provider_state_verified)
        self.assertFalse(receipt.provider_effect_performed)
        self.assertEqual([], calls)

    def test_request_document_key_is_deterministic_provider_safe_and_non_reversible_shape(self):
        key = _request_doc_key("event:device/path/../__bad__")
        self.assertEqual(key, _request_doc_key("event:device/path/../__bad__"))
        self.assertTrue(key.startswith("r_"))
        self.assertEqual(66, len(key))
        self.assertNotIn("/", key)
        self.assertNotIn(key, {".", ".."})
        self.assertFalse(key.startswith("__") and key.endswith("__"))
        self.assertNotEqual(key, _request_doc_key("event:other"))

    def test_legacy_request_key_probe_is_fail_closed(self):
        cases = [
            ("request-safe", True),
            ("event:colon-is-safe", True),
            ("contains/slash", False),
            (".", False),
            ("..", False),
            ("__reserved__", False),
            ("", False),
        ]
        for request_id, expected in cases:
            with self.subTest(request_id=request_id):
                self.assertIs(expected, _legacy_request_id_safe(request_id))

    def test_in_memory_outbox_claim_has_exactly_one_concurrent_winner(self):
        store = InMemoryCaseStore()
        store.put(_assessment(), [], request_id="request-claim", request_hash="hash-claim")

        def claim(i: int) -> bool:
            result = store.claim_outbox_delivery(
                "case-reliability-1", f"worker-{i}", lease_seconds=30
            )
            return bool(result["claimed"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(claim, range(8)))
        self.assertEqual(1, sum(outcomes))
        state = store.outbox_state("case-reliability-1")
        self.assertIsNotNone(state)
        self.assertFalse(state["delivered"])
        self.assertTrue(state["claim_owner"].startswith("worker-"))

    def test_outbox_claim_release_allows_retry_and_owner_mismatch_fails_closed(self):
        store = InMemoryCaseStore()
        store.put(_assessment(), [], request_id="request-release", request_hash="hash-release")
        first = store.claim_outbox_delivery(
            "case-reliability-1", "worker-a", lease_seconds=30
        )
        self.assertTrue(first["claimed"])
        with self.assertRaisesRegex(
            RuntimeError, "AEGIS_OUTBOX_CLAIM_OWNERSHIP_MISMATCH"
        ):
            store.mark_outbox_delivered(
                "case-reliability-1", "provider-1", claimant_id="worker-b"
            )
        store.release_outbox_claim("case-reliability-1", "worker-a")
        second = store.claim_outbox_delivery(
            "case-reliability-1", "worker-b", lease_seconds=30
        )
        self.assertTrue(second["claimed"])
        store.mark_outbox_delivered(
            "case-reliability-1", "provider-1", claimant_id="worker-b"
        )
        final = store.outbox_state("case-reliability-1")
        self.assertTrue(final["delivered"])
        self.assertEqual("provider-1", final["provider_ref"])
        self.assertEqual("", final["claim_owner"])


if __name__ == "__main__":
    unittest.main()
