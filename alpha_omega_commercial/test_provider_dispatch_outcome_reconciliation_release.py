from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from prove_provider_dispatch_outcome_reconciliation_release import prove, receipt_valid, validate

ROOT = Path(__file__).resolve().parents[1]


class ProviderDispatchOutcomeReconciliationReleaseTests(unittest.TestCase):
    def test_all_release_checks_pass(self) -> None:
        checks, evidence = validate(ROOT)
        self.assertEqual(len(checks), 20)
        self.assertTrue(all(checks.values()))
        self.assertEqual(evidence["provider_proof"]["checks_failed"], 0)

    def test_release_proof_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = prove(ROOT, Path(temporary))
            self.assertEqual(result["checks_required"], 20)
            self.assertEqual(result["checks_failed"], 0)
            self.assertTrue((Path(temporary) / "provider-dispatch-outcome-reconciliation-release-proof.json").exists())

    def test_modified_receipt_is_rejected(self) -> None:
        receipt = json.loads((ROOT / "alpha_omega_commercial" / "provider_dispatch_outcome_reconciliation_release_receipt.json").read_text(encoding="utf-8"))
        self.assertTrue(receipt_valid(receipt))
        receipt["commercial_truth"]["verified_live_revenue_events"] = 1
        self.assertFalse(receipt_valid(receipt))


if __name__ == "__main__":
    unittest.main()
