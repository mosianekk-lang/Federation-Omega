import tempfile
import unittest
from pathlib import Path

from commercial_expansion import ArchiveAdapter, CapabilityMarketplace, FilesystemAdapter, ManagedOps, PartnerProgramme, SQLiteAdapter, prove_adapter


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_three_reference_adapters(self):
        payload = {"tenant_id": "tenant-001", "solution": "case-intake"}
        adapters = [FilesystemAdapter(self.root / "fs"), SQLiteAdapter(self.root / "db.sqlite"), ArchiveAdapter(self.root / "archives")]
        proofs = [prove_adapter(adapter, f"dep-{index}", payload) for index, adapter in enumerate(adapters)]
        self.assertEqual(len(proofs), 3)
        self.assertTrue(all(p["status"] == "REFERENCE_PROVIDER_VERIFIED" for p in proofs))
        self.assertTrue(all(p["gates"]["rollback"] for p in proofs))

    def test_managed_ops_sla_incident_backup_restore(self):
        ops = ManagedOps(self.root / "ops")
        ops.register_service("svc-1", 0.75, 60)
        ops.heartbeat("svc-1", True, 100)
        ops.heartbeat("svc-1", True, 110)
        ops.heartbeat("svc-1", True, 105)
        ops.heartbeat("svc-1", False, 500)
        incident = ops.open_incident("inc-1", "svc-1", "SEV2")
        self.assertEqual(incident["status"], "OPEN")
        ops.resolve_incident("inc-1", "reference recovery")
        backup = ops.backup("svc-1")
        restore = ops.restore(backup["backup_id"])
        self.assertEqual(restore["status"], "RESTORED")
        report = ops.sla_report("svc-1")
        self.assertTrue(report["pass"])
        self.assertEqual(report["open_incidents"], 0)

    def test_marketplace_immutable_release_and_entitlement(self):
        market = CapabilityMarketplace(self.root / "market")
        release = market.publish("cap-intake", "1.0.0", "solution-intake", "v1", "COMMERCIAL", (), {"entry": "run"})
        self.assertEqual(release["version"], "1.0.0")
        market.grant("tenant-001", "cap-intake", "1.0.0", "lic-1")
        self.assertTrue(market.check("tenant-001", "cap-intake", "1.0.0")["entitled"])
        with self.assertRaises(ValueError):
            market.publish("cap-intake", "1.0.0", "solution-other", "v1", "COMMERCIAL", (), {"entry": "different"})

    def test_partner_reference_tenant_and_revenue_share_boundary(self):
        partners = PartnerProgramme(self.root / "partners")
        partner = partners.register("partner-001", "Reference Partner Pty Ltd", "Reference Automation", 1500)
        self.assertEqual(partner["licence"]["status"], "DRAFT_REQUIRES_OWNER_APPROVAL")
        calc = partners.revenue_share_calculation("partner-001", 100_000)
        self.assertEqual(calc["calculated_share_zar"], 15_000)
        self.assertEqual(calc["status"], "CALCULATION_ONLY_NO_REVENUE_RECEIVED")


if __name__ == "__main__":
    unittest.main()
