from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from authority_snapshot_release import AuthoritySnapshotReleaseVerifier, digest


FILES = (
    "authority_snapshot_release_receipt.json",
    "authority_snapshot_checkpoint.json",
    "canonical_commercial_api.json",
    "programme.json",
    "effective_programme_state.json",
)


class AuthoritySnapshotReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(__file__).resolve().parent
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in FILES:
            (self.root / name).write_text(
                (self.source / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _read(self, name: str) -> dict:
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def _write(self, name: str, value: dict, *, rehash: bool = False) -> None:
        if rehash and name == "authority_snapshot_release_receipt.json":
            unsigned = copy.deepcopy(value)
            unsigned.pop("receipt_sha256", None)
            value["receipt_sha256"] = digest(unsigned)
        (self.root / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_verified_release(self) -> None:
        checks = AuthoritySnapshotReleaseVerifier(self.root).require_verified()
        self.assertEqual(len(checks), 16)
        self.assertTrue(all(checks.values()))

    def test_receipt_tampering_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["google_drive_release"]["shared"] = True
        self._write("authority_snapshot_release_receipt.json", receipt)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertFalse(checks["receipt_hash_valid"])
        self.assertFalse(checks["drive_release_complete"])

    def test_rehashed_external_gate_promotion_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["external_gates"]["customer_demand"] = True
        self._write("authority_snapshot_release_receipt.json", receipt, rehash=True)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertTrue(checks["receipt_hash_valid"])
        self.assertFalse(checks["external_gates_unchanged"])

    def test_rehashed_revenue_claim_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["commercial_truth"]["verified_live_revenue_events"] = 1
        self._write("authority_snapshot_release_receipt.json", receipt, rehash=True)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertFalse(checks["zero_revenue_truth_preserved"])

    def test_rehashed_cloud_claim_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["commercial_truth"]["cloud_run_operation_proven"] = True
        self._write("authority_snapshot_release_receipt.json", receipt, rehash=True)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertFalse(checks["cloud_and_maturity_not_claimed"])

    def test_rehashed_provider_artifact_drift_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["final_head_provider_proof"]["artifact_id"] = 1
        self._write("authority_snapshot_release_receipt.json", receipt, rehash=True)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertFalse(checks["final_head_provider_proof_exact"])

    def test_rehashed_drive_hash_drift_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["google_drive_release"]["export_sha256"] = "0" * 64
        self._write("authority_snapshot_release_receipt.json", receipt, rehash=True)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertFalse(checks["drive_release_complete"])

    def test_owner_authority_drift_is_rejected(self) -> None:
        receipt = self._read("authority_snapshot_release_receipt.json")
        receipt["owner_authority"]["contracts"] = "AUTOMATED"
        self._write("authority_snapshot_release_receipt.json", receipt, rehash=True)
        checks = AuthoritySnapshotReleaseVerifier(self.root).verify()
        self.assertFalse(checks["owner_authority_preserved"])


if __name__ == "__main__":
    unittest.main()
