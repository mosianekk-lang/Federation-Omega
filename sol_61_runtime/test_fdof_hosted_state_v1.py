from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

try:
    from .fdof_hosted_state_v1 import GENERATION_ANCHOR, export_capsule, restore_capsule, verify_capsule
    from .sol_62_frontier_primitives import AuthorityLease, ConstraintError, FenceError, IdempotencyCollision
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_hosted_state_v1 import GENERATION_ANCHOR, export_capsule, restore_capsule, verify_capsule
    from sol_62_frontier_primitives import AuthorityLease, ConstraintError, FenceError, IdempotencyCollision
    from sol_62_runtime import Sol62Runtime


class FdofHostedStateV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def runtime(self, name: str) -> Sol62Runtime:
        return Sol62Runtime(self.root / name)

    @staticmethod
    def seed(rt: Sol62Runtime) -> None:
        rt.control.cas_put("fdof.test", "state", {"ready": True}, expected_version=0)
        rt.control.append_event("mission-capsule", "FDOF_CAPSULE_SEEDED", {"ready": True})
        rt.control.reserve_idempotency(
            "idem-capsule-1", {"operation": "READ", "target": "repo:test"}, "AT_MOST_ONCE"
        )
        rt.acquire_execution_fence("transition-capsule", "worker-a", ttl_seconds=60, now_epoch=1000)

    def test_lease_fencing_survives_fresh_runtime_restore(self) -> None:
        first = self.runtime("first")
        second = self.runtime("second")
        try:
            self.seed(first)
            before = first.control.db.execute(
                "SELECT fencing_token FROM leases WHERE resource_id='transition:transition-capsule'"
            ).fetchone()
            capsule = export_capsule(first, source_version="sha-a")
            restore_capsule(second, capsule)
            with self.assertRaises(FenceError):
                second.acquire_execution_fence(
                    "transition-capsule", "worker-b", ttl_seconds=60, now_epoch=1001
                )
            replacement = second.acquire_execution_fence(
                "transition-capsule", "worker-b", ttl_seconds=60, now_epoch=1061
            )
            self.assertGreater(int(replacement["fencing_token"]), int(before["fencing_token"]))
            self.assertTrue(second.control.verify_event_chain())
        finally:
            first.close()
            second.close()

    def test_idempotency_survives_restore_and_collision_stays_blocked(self) -> None:
        first = self.runtime("idem-first")
        second = self.runtime("idem-second")
        try:
            self.seed(first)
            capsule = export_capsule(first, source_version="sha-a")
            restore_capsule(second, capsule)
            replay = second.control.reserve_idempotency(
                "idem-capsule-1", {"operation": "READ", "target": "repo:test"}, "AT_MOST_ONCE"
            )
            self.assertEqual(
                replay["request_sha256"],
                capsule["tables"]["idempotency"]["rows"][0]["request_sha256"],
            )
            with self.assertRaises(IdempotencyCollision):
                second.control.reserve_idempotency(
                    "idem-capsule-1", {"operation": "WRITE", "target": "repo:test"}, "AT_MOST_ONCE"
                )
        finally:
            first.close()
            second.close()

    def test_authority_lease_is_deliberately_not_transferred(self) -> None:
        first = self.runtime("authority-first")
        second = self.runtime("authority-second")
        try:
            first.create_authority_lease(
                AuthorityLease(
                    lease_id="authority-hosted-1",
                    action="publish",
                    target="repo/main",
                    actor="worker-a",
                    source_version="sha-a",
                    issued_at_epoch=900,
                    expires_at_epoch=1200,
                    nonce="nonce-1",
                )
            )
            capsule = export_capsule(first, source_version="sha-a")
            self.assertNotIn("authority_leases", capsule["tables"])
            self.assertEqual(capsule["excluded"]["authority_leases"]["row_count_at_export"], 1)
            restore_capsule(second, capsule)
            count = second.control.db.execute("SELECT COUNT(*) AS n FROM authority_leases").fetchone()["n"]
            self.assertEqual(int(count), 0)
        finally:
            first.close()
            second.close()

    def test_corrupt_digest_and_wrong_generation_fail_closed(self) -> None:
        rt = self.runtime("integrity")
        try:
            self.seed(rt)
            capsule = export_capsule(rt, source_version="sha-a")
            corrupt = copy.deepcopy(capsule)
            corrupt["source_version"] = "tampered"
            with self.assertRaises(ConstraintError):
                verify_capsule(corrupt)
            with self.assertRaises(ConstraintError):
                verify_capsule(capsule, expected_generation_anchor="GEN17/not-authorized")
        finally:
            rt.close()

    def test_secret_material_blocks_capsule_export(self) -> None:
        rt = self.runtime("secret")
        try:
            synthetic_header = "".join(("Bear", "er", " ", "should-never-persist"))
            rt.control.cas_put(
                "fdof.test", "unsafe", {"authorization": synthetic_header}, expected_version=0
            )
            with self.assertRaises(ConstraintError):
                export_capsule(rt, source_version="sha-a")
        finally:
            rt.close()

    def test_capsule_has_expected_generation_and_valid_chain(self) -> None:
        first = self.runtime("status-first")
        second = self.runtime("status-second")
        try:
            self.seed(first)
            capsule = export_capsule(first, source_version="sha-a")
            status = verify_capsule(capsule)
            self.assertEqual(status.generation_anchor, GENERATION_ANCHOR)
            self.assertNotIn("authority_leases", status.persisted_tables)
            restored = restore_capsule(second, capsule)
            self.assertEqual(restored.capsule_sha256, capsule["capsule_sha256"])
            self.assertTrue(second.control.verify_event_chain())
        finally:
            first.close()
            second.close()


if __name__ == "__main__":
    unittest.main()
