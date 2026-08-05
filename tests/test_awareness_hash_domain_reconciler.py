from __future__ import annotations

from copy import deepcopy
import unittest

from federation_consolidation.awareness_hash_domain_reconciler import (
    HashDomainError,
    canonical_sha256,
    control_map,
    plan_freshness_reconciliation,
    project_logical_control,
)

OLD = "bba0c434f8f82812e36dc5045e67c3b5d8273f72"
MAIN = "c8789a3401b5ca0367668ba06bee98ce30871b35"
LEGACY = "8961706e5d0e9d1e379ce24b89bb7cf8546cf126adc88e1c93c152d2a979f438"
V2 = "c790d983b08efe3436f88860a97ed4ad1ecbacdde54cfb88bf8b3592a03a7e0e"


def table(main: str = OLD):
    rows = [
        ["Federation Omega + Formation Innovation Engine — Unified Surface Awareness Manifest"],
        ["Private exact-pointer and capability-handle plane"],
        [],
        ["Field", "Value", "Verification"],
        ["Manifest ID", "FEDOMEGA-PRIVATE-SURFACE-AWARENESS-1", "ACTIVE"],
        ["Version", "1.1.0", "VERSIONED_RECONCILIATION"],
        ["Owner / Final Authority", "Kim Kagiso Mosiane", "FOUNDER_FINAL_AUTHORITY"],
        ["Created At", "46238.99792", "ORIGINAL_SWEEP"],
        ["Current GitHub Main", main, "PROVIDER_READBACK_CURRENT_HEAD"],
        ["Reconciler Source Merge", "62de4489c7ec7e2f1a278da1296412390258fbef", "VERIFIED"],
        ["Public Contract Alias", "FEDERATION_SURFACE_AWARENESS_PUBLIC_V1", "PUBLIC_SAFE"],
        ["Private Manifest Alias", "FEDERATION_AWARENESS_PRIVATE_V1", "PRIVATE_POINTER"],
        ["Private Manifest Logical SHA-256", LEGACY, "CANONICAL_PAYLOAD_HASH"],
        ["Credential Value Recorded", "FALSE", "ENFORCED_FALSE"],
        ["Provider Authority Inferred from Storage", "FALSE", "ENFORCED_FALSE"],
        ["Hidden Cross-Chat Access Claimed", "FALSE", "ENFORCED_FALSE"],
        ["Runtime Readback Required", "TRUE", "ENFORCED_TRUE"],
        ["Registered Surface Count", "27", "COUNTED"],
        ["Credential Handle Count", "10", "COUNTED"],
        ["Automation Asset Count", "17", "COUNTED"],
        ["Read-Proven Provider Count", "5", "READ_ONLY_VERIFIED"],
        ["Effectful Successor Build Count", "5", "AUTHORITY_SEPARATED"],
        ["Current Bootstrap Block", "NCB-002", "FOUNDRY_AND_RECONCILER_BOUND"],
        ["Current State", "RUNTIME_STALE", "OLD"],
        ["Final Reconciliation SHA-256", "2" * 64, "OLD_TRANSACTION"],
    ]
    return rows


class AwarenessHashDomainTests(unittest.TestCase):
    def execute(self, **overrides):
        values = dict(
            control_table=table(),
            observed_main=MAIN,
            expected_legacy_logical_sha256=LEGACY,
            expected_logical_sha256_v2=V2,
        )
        values.update(overrides)
        return plan_freshness_reconciliation(**values)

    def test_live_projection_hash_matches_contract(self):
        logical = project_logical_control(control_map(table()))
        self.assertEqual(V2, canonical_sha256(logical))

    def test_stale_head_yields_apply_eligible_with_rollback(self):
        result = self.execute()
        self.assertEqual("APPLY_ELIGIBLE", result["status"])
        self.assertTrue(result["stale_runtime_head"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(
            result["runtime_before_sha256"], result["rollback_runtime_sha256"]
        )
        self.assertEqual(MAIN, result["patch_plan"]["Current GitHub Main"]["value"])

    def test_fresh_head_is_no_change(self):
        result = self.execute(control_table=table(MAIN))
        self.assertEqual("NO_CHANGE_VERIFIED", result["status"])
        self.assertEqual({}, result["patch_plan"])

    def test_logical_field_change_blocks(self):
        changed = table()
        changed[6][1] = "Different Owner"
        with self.assertRaisesRegex(HashDomainError, "v2 logical projection"):
            self.execute(control_table=changed)

    def test_legacy_hash_mismatch_blocks(self):
        changed = table()
        changed[12][1] = "3" * 64
        with self.assertRaisesRegex(HashDomainError, "legacy logical hash"):
            self.execute(control_table=changed)

    def test_duplicate_control_field_blocks(self):
        changed = table() + [["Current GitHub Main", OLD, "DUPLICATE"]]
        with self.assertRaisesRegex(HashDomainError, "duplicate CONTROL field"):
            self.execute(control_table=changed)

    def test_secret_shaped_value_blocks(self):
        changed = table()
        changed[7][1] = "github_pat_" + "A" * 30
        with self.assertRaises(HashDomainError):
            self.execute(control_table=changed)

    def test_receipt_is_deterministic(self):
        self.assertEqual(self.execute()["receipt_sha256"], self.execute()["receipt_sha256"])

    def test_receipt_detects_tampering(self):
        result = self.execute()
        tampered = deepcopy(result)
        tampered["observed_main"] = OLD
        claimed = tampered.pop("receipt_sha256")
        self.assertNotEqual(claimed, canonical_sha256(tampered))


if __name__ == "__main__":
    unittest.main()
