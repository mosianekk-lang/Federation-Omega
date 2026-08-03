from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from commercial_platform import CommercialPlatform, SecretReference, UsageEvent


class CommercialPlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.platform = CommercialPlatform(self.root)
        self.owner = "owner:kim"
        self.platform.create_tenant("tenant-001", "Tenant One", "AO-PILOT", self.owner)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_catalogue_quote_and_sales_truth_boundary(self) -> None:
        self.assertEqual(len(self.platform.catalogue()), 3)
        quote = self.platform.quote("AO-PILOT")
        self.assertEqual(quote["contract_value_zar"], 560_000)
        self.assertEqual(quote["status"], "ESTIMATE_REQUIRES_OWNER_APPROVAL")
        self.assertIn("hypotheses", self.platform.sales_asset("AO-PILOT")["truth_boundary"])

    def test_tenant_rbac_and_cross_tenant_default_deny(self) -> None:
        self.platform.assign_role("tenant-001", self.owner, "operator:a", "operator")
        self.assertEqual(self.platform.tenant_readback("tenant-001", "operator:a")["tenant_id"], "tenant-001")
        self.platform.create_tenant("tenant-002", "Tenant Two", "AO-PILOT", "owner:two")
        with self.assertRaises(PermissionError):
            self.platform.tenant_readback("tenant-002", "operator:a")

    def test_audit_hash_chain_is_valid_and_tamper_evident(self) -> None:
        self.platform.assign_role("tenant-001", self.owner, "auditor:a", "auditor")
        self.assertTrue(self.platform.verify_audit_chain())
        rows = self.platform.audit_file.read_text(encoding="utf-8").splitlines()
        row = json.loads(rows[0])
        row["action"] = "tampered"
        rows[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
        self.platform.audit_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
        self.assertFalse(self.platform.verify_audit_chain())

    def test_secret_reference_and_rotation_store_no_material(self) -> None:
        reference = SecretReference("tenant-001", "provider", "mock", "projects/x/secrets/y", ("read",), "1", "2027-01-01T00:00:00Z")
        stored = self.platform.register_secret_reference(self.owner, reference)
        self.assertNotIn("secret", stored)
        rotated = self.platform.rotate_secret_reference("tenant-001", self.owner, "provider", "2", "2027-06-01T00:00:00Z")
        self.assertEqual(rotated["version"], "2")
        with self.assertRaises(ValueError):
            self.platform._reject_secret_material({"token": "do-not-store"})

    def test_workspace_provision_idempotency_rollback_and_restore(self) -> None:
        first = self.platform.provision_workspace("tenant-001", self.owner)
        second = self.platform.provision_workspace("tenant-001", self.owner)
        self.assertEqual(first, second)
        rollback = self.platform.rollback_workspace("tenant-001", self.owner)
        self.assertFalse(rollback["exists_after"])
        restored = self.platform.provision_workspace("tenant-001", self.owner)
        self.assertEqual(restored["status"], "READY")

    def test_metering_plan_budget_and_invoice_export(self) -> None:
        self.platform.append_usage(self.owner, UsageEvent("tenant-001", "e1", "2026-08-03T00:00:00Z", "build", 1, 6000))
        self.platform.append_usage(self.owner, UsageEvent("tenant-001", "e2", "2026-08-03T00:01:00Z", "support_hour", 4, 500))
        metered = self.platform.meter("tenant-001")
        self.assertEqual(metered["cost_zar"], 8000.0)
        self.assertTrue(self.platform.plan_enforcement("tenant-001")["within_plan"])
        self.assertEqual(self.platform.budget_control("tenant-001")["decision"], "ALLOW")
        self.platform.assign_role("tenant-001", self.owner, "billing:a", "billing")
        invoice = self.platform.invoice_ready_export("tenant-001", "billing:a", self.root / "invoice.csv")
        self.assertEqual(invoice["status"], "INVOICE_READY_NOT_ISSUED")
        self.assertTrue((self.root / "invoice.csv").exists())

    def test_duplicate_usage_is_rejected(self) -> None:
        event = UsageEvent("tenant-001", "dup", "2026-08-03T00:00:00Z", "build", 1, 1)
        self.platform.append_usage(self.owner, event)
        with self.assertRaises(ValueError):
            self.platform.append_usage(self.owner, event)

    def test_budget_hold_and_plan_overage(self) -> None:
        self.platform.append_usage(self.owner, UsageEvent("tenant-001", "e1", "2026-08-03T00:00:00Z", "build", 2, 10000))
        self.assertFalse(self.platform.plan_enforcement("tenant-001")["within_plan"])
        self.assertEqual(self.platform.budget_control("tenant-001")["decision"], "HOLD_NEW_COST")

    def test_state_persists_across_process_instances(self) -> None:
        reopened = CommercialPlatform(self.root)
        self.assertEqual(reopened.tenant_readback("tenant-001", self.owner)["name"], "Tenant One")

    def test_invalid_tenant_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.platform.create_tenant("Bad ID", "Bad", "AO-PILOT", self.owner)


if __name__ == "__main__":
    unittest.main()
