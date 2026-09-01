from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from kimmie_seed.workforce.runtime_adapter import KimmieRuntimeAdapter


def packet(packet_id: str = "PACKET-001") -> dict[str, object]:
    return {
        "packet_id": packet_id,
        "bot_id": "KIMMIE-BOT-001",
        "lane_scope": "KIMMIE-IPEP-001",
        "authority": "A0",
        "lease": {"collision_key": "exclusive:one"},
    }


class RuntimeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "runtime.sqlite3"
        self.runtime = KimmieRuntimeAdapter(self.db, max_attempts=3)
        self.runtime.register_packet(packet(), now=1.0)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_stop_and_explicit_start(self) -> None:
        self.assertIsNone(self.runtime.lease_one("worker-a", now=2.0))
        with self.assertRaises(PermissionError):
            self.runtime.start()
        self.runtime.start(explicit=True, now=2.0)
        self.assertIsNotNone(self.runtime.lease_one("worker-a", now=3.0))

    def test_two_workers_cannot_lease_same_lane(self) -> None:
        self.runtime.start(explicit=True, now=2.0)
        results: list[object] = []
        barrier = threading.Barrier(2)

        def lease(worker: str) -> None:
            barrier.wait()
            results.append(self.runtime.lease_one(worker, now=3.0))

        threads = [threading.Thread(target=lease, args=(name,)) for name in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(item is not None for item in results), 1)

    def test_heartbeat_is_fenced(self) -> None:
        self.runtime.start(explicit=True, now=2.0)
        lease = self.runtime.lease_one("worker-a", now=3.0)
        assert lease
        self.runtime.heartbeat(lease, now=4.0, extend_seconds=20.0)
        forged = type(lease)(lease.lane_id, "worker-b", lease.attempt, lease.lease_token, lease.lease_expires_at)
        with self.assertRaises(PermissionError):
            self.runtime.heartbeat(forged, now=5.0)

    def test_three_failures_dead_letter_exactly_once(self) -> None:
        self.runtime.start(explicit=True, now=2.0)
        for attempt in range(1, 4):
            lease = self.runtime.lease_one("worker-a", now=float(attempt * 10))
            assert lease
            verdict = self.runtime.fail(lease, "boom", now=float(attempt * 10 + 1))
        self.assertEqual(verdict, "DEAD_LETTERED")
        receipt = self.runtime.receipt()
        self.assertEqual(len(receipt["dead_letters"]), 1)
        self.assertEqual(receipt["dead_letters"][0]["attempt"], 3)
        self.assertFalse(receipt["provider_model_execution_proven"])

    def test_effect_authority_is_rejected(self) -> None:
        bad = packet("PACKET-002")
        bad["authority"] = "A2"
        with self.assertRaises(PermissionError):
            self.runtime.register_packet(bad)


if __name__ == "__main__":
    unittest.main()
