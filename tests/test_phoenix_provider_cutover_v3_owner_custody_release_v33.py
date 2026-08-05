from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_custody_ceremony_checkpoint_v33.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v33.json"
RECEIPT = ROOT / "alpha_omega_commercial" / "phoenix_owner_custody_ceremony_release_receipt_v33.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_hash(test: unittest.TestCase, payload: dict, field: str) -> None:
    body = dict(payload)
    claimed = body.pop(field)
    calculated = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    test.assertEqual(claimed, calculated)


class OwnerCustodyReleaseV33Tests(unittest.TestCase):
    def test_release_records_exact_provider_native_evidence(self):
        receipt = load(RECEIPT)
        self.assertEqual(276, receipt["implementation"]["pull_request"])
        self.assertEqual(
            "4b3e9d8f4b3385b806ccc68a1bda458cbcc43f54",
            receipt["implementation"]["head_sha"],
        )
        self.assertEqual(
            "b75b5a74d445425dc45bb381f3f34ee2f1866057",
            receipt["implementation"]["merged_main_sha"],
        )
        self.assertEqual(30977255475, receipt["admission"]["airlock_run"])
        self.assertEqual(30977300852, receipt["current_main_proof"]["phoenix_run"])
        self.assertEqual("SUCCESS", receipt["current_main_proof"]["status"])
        self.assertEqual(191, receipt["admission"]["provider_v3_family_tests_passed"])
        self.assertEqual(4, receipt["admission"]["v33_tests_passed"])
        self.assertEqual(0, receipt["admission"]["airlock_findings"])
        self.assertEqual(0, receipt["admission"]["changed_workflows"])
        self.assertEqual(0, receipt["admission"]["unadmitted_commits"])

    def test_export_and_drive_readback_are_exact(self):
        receipt = load(RECEIPT)
        proof = receipt["current_main_proof"]
        self.assertEqual(0, proof["core_active_workflows"])
        self.assertEqual(0, proof["ops_active_workflows"])
        self.assertEqual(0, proof["runtime_bytecode"])
        self.assertTrue(proof["custody_engine_included"])
        self.assertTrue(proof["custody_contract_included"])
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        drive = receipt["drive_release"]
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(4410, drive["export_size"])
        self.assertEqual(
            "70b183e10a003b2be363431996a58d81b4a93062cd65118b5daca6e3c1c42e93",
            drive["export_sha256"],
        )

    def test_checkpoint_projection_and_receipt_are_hash_bound(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        receipt = load(RECEIPT)
        assert_hash(self, checkpoint, "checkpoint_sha256")
        assert_hash(self, projection, "projection_sha256")
        assert_hash(self, receipt, "receipt_sha256")
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], projection["dependency_order"])
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])

    def test_owner_market_provider_and_revenue_boundaries_remain_closed(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        receipt = load(RECEIPT)
        self.assertEqual(
            "OWNER_CUSTODY_CEREMONY_PROVIDER_PROOF_VERIFIED_OWNER_EXECUTION_AND_ATTESTATION_REQUIRED",
            checkpoint["status"],
        )
        self.assertTrue(checkpoint["custody_truth"]["provider_native_readback_present"])
        self.assertFalse(checkpoint["custody_truth"]["owner_controlled_custody_proven"])
        self.assertFalse(checkpoint["custody_truth"]["owner_attestation_present"])
        self.assertFalse(checkpoint["custody_truth"]["owner_authorization_present"])
        truth = receipt["truth_boundary"]
        self.assertFalse(truth["provider_authority_created"])
        self.assertFalse(truth["provider_apply_performed"])
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["signed_customer_contract"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])


if __name__ == "__main__":
    unittest.main()
