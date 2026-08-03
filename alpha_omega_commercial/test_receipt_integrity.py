from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from commercial_assurance import digest
from prove_c10_c15 import execute
from receipt_integrity import CommercialReceiptIntegrityReconciler, verify_ledger


class CommercialReceiptIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "proof"
        execute(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _read(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_detects_and_repairs_embedded_c15_maturity_drift(self) -> None:
        package_path = self.root / "reference-state" / "receipts" / "succession-AO-COMMERCIAL-C10-C15-001.json"
        original = self._read(package_path)
        final_maturity = self._read(self.root / "commercial-maturity.json")
        self.assertFalse(original["maturity"]["technical_gates"]["C15_succession_ready"])
        self.assertTrue(final_maturity["technical_gates"]["C15_succession_ready"])

        result = CommercialReceiptIntegrityReconciler(self.root).reconcile()
        repaired = self._read(package_path)
        receipt = self._read(self.root / "commercial-c10-c15-receipt.json")
        state = self._read(self.root / "reference-state" / "commercial_assurance_state.json")

        self.assertEqual(result["status"], "CANONICAL_RECEIPT_INTEGRITY_VERIFIED")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(repaired["maturity"], final_maturity)
        self.assertTrue(repaired["maturity"]["technical_gates"]["C15_succession_ready"])
        package_body = {key: value for key, value in repaired.items() if key != "package_sha256"}
        self.assertEqual(repaired["package_sha256"], digest(package_body))
        self.assertEqual(
            state["succession_exports"]["AO-COMMERCIAL-C10-C15-001"]["package_sha256"],
            repaired["package_sha256"],
        )
        self.assertEqual(receipt["stages"]["C15"]["maturity"], final_maturity)
        self.assertEqual(receipt["canonical_receipt_integrity"]["status"], "CANONICAL_RECEIPT_INTEGRITY_VERIFIED")
        self.assertTrue(verify_ledger(self.root / "reference-state" / "commercial_assurance_ledger.jsonl")["pass"])

    def test_reconciliation_is_idempotent(self) -> None:
        reconciler = CommercialReceiptIntegrityReconciler(self.root)
        first = reconciler.reconcile()
        first_ledger = verify_ledger(self.root / "reference-state" / "commercial_assurance_ledger.jsonl")
        second = reconciler.reconcile()
        second_ledger = verify_ledger(self.root / "reference-state" / "commercial_assurance_ledger.jsonl")
        self.assertEqual(first["package_sha256"], second["package_sha256"])
        self.assertEqual(first_ledger["entries"], second_ledger["entries"])
        self.assertTrue(second_ledger["pass"])

    def test_transactional_rollback_restores_original_artifact_hashes(self) -> None:
        canary = Path(self.temporary.name) / "rollback-canary"
        shutil.copytree(self.root, canary)
        reconciler = CommercialReceiptIntegrityReconciler(canary)
        reconciler.reconcile()
        rollback = reconciler.rollback()
        self.assertEqual(rollback["status"], "CANONICAL_RECEIPT_ROLLBACK_VERIFIED")
        self.assertTrue(all(rollback["restored"].values()))
        package = self._read(canary / "reference-state" / "receipts" / "succession-AO-COMMERCIAL-C10-C15-001.json")
        self.assertFalse(package["maturity"]["technical_gates"]["C15_succession_ready"])

    def test_external_maturity_boundaries_remain_unchanged(self) -> None:
        result = CommercialReceiptIntegrityReconciler(self.root).reconcile()
        maturity = self._read(self.root / "commercial-maturity.json")
        self.assertEqual(result["status"], "CANONICAL_RECEIPT_INTEGRITY_VERIFIED")
        self.assertFalse(maturity["full_commercial_maturity"])
        self.assertFalse(any(maturity["external_gates"].values()))
        self.assertIn("No customer", result["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
