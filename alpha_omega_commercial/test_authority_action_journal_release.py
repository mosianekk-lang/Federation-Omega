from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from authority_snapshot import digest
from prove_authority_action_journal_release import ROOT, run


class AuthorityActionJournalReleaseTests(unittest.TestCase):
    def test_release_reconciliation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            proof = run(output)
            self.assertEqual(
                proof["status"],
                "AUTHORITY_ACTION_JOURNAL_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
            )
            self.assertEqual(proof["checks_failed"], 0)
            self.assertTrue(all(proof["checks"].values()))
            self.assertTrue(output.exists())

    def test_release_receipt_is_hash_bound(self) -> None:
        release = json.loads(
            (ROOT / "authority_action_journal_release_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        recorded = release.pop("receipt_sha256")
        self.assertEqual(digest(release), recorded)

    def test_external_claims_remain_closed(self) -> None:
        release = json.loads(
            (ROOT / "authority_action_journal_release_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(
            all(value is False for value in release["external_gates"].values())
        )
        self.assertEqual(
            release["commercial_truth"]["verified_live_revenue_events"], 0
        )
        self.assertFalse(
            release["commercial_truth"]["cloud_run_operation_proven"]
        )
        self.assertFalse(
            release["commercial_truth"]["payment_provider_operation_proven"]
        )
        self.assertFalse(
            release["commercial_truth"]["full_commercial_maturity"]
        )
        self.assertTrue(
            all(
                value.startswith("OWNER_RESERVED")
                for value in release["owner_authority"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
