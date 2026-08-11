from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from authority_snapshot import digest
from prove_authority_action_idempotency_release import load, run


class AuthorityActionIdempotencyReleaseTests(unittest.TestCase):
    def test_release_reconciliation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "release-proof.json"
            result = run(output)
        self.assertEqual(result["checks_failed"], 0)
        self.assertTrue(all(result["checks"].values()))
        self.assertTrue(result["google_drive_readback_verified"])
        self.assertFalse(result["google_drive_shared"])
        self.assertEqual(result["verified_live_revenue_events"], 0)
        self.assertFalse(result["full_commercial_maturity"])

    def test_release_receipt_hash_detects_mutation(self) -> None:
        release = load("authority_action_idempotency_release_receipt.json")
        recorded = release.pop("receipt_sha256")
        self.assertEqual(digest(release), recorded)
        release["commercial_truth"]["verified_live_revenue_events"] = 1
        self.assertNotEqual(digest(release), recorded)

    def test_external_gates_and_owner_authority_remain_closed(self) -> None:
        release = load("authority_action_idempotency_release_receipt.json")
        self.assertTrue(all(value is False for value in release["external_gates"].values()))
        self.assertEqual(release["commercial_truth"]["verified_live_revenue_events"], 0)
        self.assertFalse(
            release["commercial_truth"]["distributed_provider_exactly_once_proven"]
        )
        self.assertTrue(
            all(
                value.startswith("OWNER_RESERVED")
                for value in release["owner_authority"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
