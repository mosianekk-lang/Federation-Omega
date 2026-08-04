from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prove_provider_reconciliation_challenge_release import prove, validate


class ProviderReconciliationChallengeReleaseTests(unittest.TestCase):
    def test_repository_release_evidence_passes_all_checks(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checks, evidence = validate(root)
        self.assertEqual(len(checks), 22)
        self.assertTrue(all(checks.values()), [name for name, ok in checks.items() if not ok])
        self.assertEqual(evidence["provider_proof"]["checks_failed"], 0)
        self.assertTrue(evidence["google_drive_release"]["readback_verified"])
        self.assertFalse(evidence["google_drive_release"]["shared"])

    def test_proof_is_deterministic_and_preserves_truth_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = prove(root, Path(first))
            two = prove(root, Path(second))
        self.assertEqual(one, two)
        self.assertEqual(one["checks_required"], 22)
        self.assertEqual(one["checks_failed"], 0)
        self.assertEqual(one["commercial_truth"]["verified_live_revenue_events"], 0)
        self.assertFalse(one["commercial_truth"]["provider_native_reconciliation_proven"])
        self.assertFalse(one["commercial_truth"]["cloud_run_operation_proven"])

    def test_changed_drive_hash_fails_closed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        receipt_path = root / "alpha_omega_commercial" / "provider_reconciliation_challenge_release_receipt.json"
        original = json.loads(receipt_path.read_text(encoding="utf-8"))
        altered = json.loads(json.dumps(original))
        altered["google_drive_release"]["export_sha256"] = "0" * 64
        real_load = json.loads

        def selective_load(path: Path):
            if path.name == receipt_path.name:
                return altered
            return real_load(path.read_text(encoding="utf-8"))

        with patch("prove_provider_reconciliation_challenge_release.load", side_effect=selective_load):
            checks, _ = validate(root)
        self.assertFalse(checks["drive_export_hash"])
        self.assertFalse(checks["release_receipt_digest"])


if __name__ == "__main__":
    unittest.main()
