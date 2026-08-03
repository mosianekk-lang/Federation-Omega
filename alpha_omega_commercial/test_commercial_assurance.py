from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from commercial_assurance import CommercialAssuranceControlPlane, EvidenceReference


def evidence(reference_id: str, evidence_class: str = "REFERENCE_PROVIDER") -> EvidenceReference:
    body = f"{reference_id}:{evidence_class}".encode()
    return EvidenceReference(
        reference_id=reference_id,
        provider="github-actions-reference",
        locator=f"artifact://{reference_id}",
        sha256=hashlib.sha256(body).hexdigest(),
        observed_at="2026-08-03T13:30:00Z",
        evidence_class=evidence_class,
    )


class CommercialAssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.plane = CommercialAssuranceControlPlane(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _complete_assurance(self) -> dict:
        for family in ("ACCESS", "AUDIT", "PRIVACY", "RETENTION", "RECOVERY"):
            self.plane.register_control(
                f"CTRL-{family}", family, f"Reference {family.lower()} control", "service-owner", [evidence(f"ev-{family.lower()}")]
            )
        self.plane.set_retention_policy("RET-OPS", "operational-metadata", 365, "ARCHIVE")
        request = self.plane.open_privacy_request("PRIV-1", "tenant-001", "subject-opaque-001", "ACCESS")
        self.assertEqual(request["status"], "OPEN")
        completed = self.plane.complete_privacy_request("PRIV-1", [evidence("privacy-completion")], "FULFILLED")
        self.assertEqual(completed["status"], "FULFILLED")
        drill = self.plane.run_disaster_recovery_drill(
            "DR-1", {"tenant": "tenant-001", "revision": 7}, {"tenant": "tenant-001", "revision": 7}, 8.0, 30.0
        )
        self.assertTrue(drill["pass"])
        return self.plane.assurance_pack()

    def test_c10_reference_assurance_pack(self) -> None:
        pack = self._complete_assurance()
        self.assertTrue(pack["control_coverage_pass"])
        self.assertEqual(pack["status"], "REFERENCE_ASSURANCE_VERIFIED_ENTERPRISE_ATTESTATION_REQUIRED")
        self.assertIn("no certification", pack["truth_boundary"])

    def test_secret_shaped_material_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.plane.submit_service_request(
                "REQ-SECRET", "tenant-001", "support.request", {"api_key": "must-not-persist"}, "subject-1"
            )

    def test_c11_owner_reserved_request_is_held(self) -> None:
        request = self.plane.submit_service_request(
            "REQ-SUB", "tenant-001", "subscription.change", {"offer_id": "AO-DEPARTMENT"}, "subject-1"
        )
        self.assertEqual(request["status"], "OWNER_APPROVAL_REQUIRED")
        with self.assertRaises(PermissionError):
            self.plane.execute_reference_service_request("REQ-SUB", lambda payload: {}, lambda execution: {})

    def test_c11_reference_service_execution_and_rollback(self) -> None:
        target = self.root / "reference-service-object.json"
        request = self.plane.submit_service_request(
            "REQ-PROVISION", "tenant-001", "workspace.provision", {"workspace_id": "ws-001"}, "operator-1"
        )
        self.assertEqual(request["status"], "ACCEPTED_REFERENCE_EXECUTION_PENDING")

        def handler(payload: dict) -> dict:
            target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            readback = json.loads(target.read_text(encoding="utf-8"))
            return {
                "target": str(target),
                "payload_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "readback_pass": readback == payload,
                "health_pass": target.is_file(),
            }

        def rollback(execution: dict) -> dict:
            target.unlink(missing_ok=True)
            return {"rollback_pass": not target.exists(), "target": execution["target"]}

        result = self.plane.execute_reference_service_request("REQ-PROVISION", handler, rollback)
        self.assertEqual(result["status"], "REFERENCE_EXECUTION_VERIFIED_AND_ROLLED_BACK")
        self.assertFalse(target.exists())

    def test_c12_internal_evidence_cannot_be_published_as_customer_proof(self) -> None:
        study = self.plane.register_outcome_study(
            "STUDY-1", "tenant-001", "cycle_time", 100.0, 55.0, "minutes", True,
            [evidence("study-reference")], "REFERENCE_PROVIDER_SYNTHETIC"
        )
        self.assertEqual(study["status"], "MARKET_PROOF_REQUIRED")
        report = self.plane.case_study_report("STUDY-1")
        self.assertFalse(report["publication_allowed"])
        self.assertAlmostEqual(report["result"]["improvement_ratio"], 0.45)

    def test_c13_owner_approval_and_payment_evidence_boundaries(self) -> None:
        lead = self.plane.create_lead("LEAD-1", "organisation-ref-001", "internal-reference", "manual process delay")
        self.assertEqual(lead["stage"], "NEW")
        self.plane.advance_lead("LEAD-1", "QUALIFIED", "reference://qualification")
        quote = self.plane.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12)
        self.assertEqual(quote["status"], "DRAFT_OWNER_APPROVAL_REQUIRED")
        with self.assertRaises(PermissionError):
            self.plane.register_contract_draft("CONTRACT-1", "QUOTE-1", "NOT_REVIEWED")
        self.plane.approve_quote("QUOTE-1", "owner-approval-reference-001")
        contract = self.plane.register_contract_draft("CONTRACT-1", "QUOTE-1", "LEGAL_REVIEW_REQUIRED")
        self.assertFalse(contract["binding"])
        with self.assertRaises(PermissionError):
            self.plane.register_verified_revenue_event(
                "REV-1", "CONTRACT-1", 1000.0, "ZAR", evidence("payment", "PAYMENT_PROVIDER_VERIFIED"), False
            )
        with self.assertRaises(ValueError):
            self.plane.register_verified_revenue_event(
                "REV-2", "CONTRACT-1", 1000.0, "ZAR", evidence("internal-payment"), True
            )
        dashboard = self.plane.revenue_operations_dashboard()
        self.assertEqual(dashboard["verified_revenue_events"], 0)
        self.assertEqual(dashboard["verified_revenue_by_currency"], {})

    def test_c14_reference_scale_evaluation(self) -> None:
        run = self.plane.run_scale_evaluation(
            "SCALE-1",
            "service.request.submit",
            [30, 35, 40, 42, 45, 47, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 110, 120, 130],
            request_count=1000,
            failure_count=2,
            concurrency=25,
            recovery_seconds=18.0,
            monthly_revenue_zar=75000.0,
            monthly_delivery_cost_zar=28000.0,
            support_hours=24.0,
            targets={
                "max_p95_latency_ms": 130.0,
                "max_error_rate": 0.005,
                "max_recovery_seconds": 30.0,
                "min_gross_margin": 0.55,
                "max_support_hours": 30.0,
            },
        )
        self.assertEqual(run["status"], "REFERENCE_SCALE_VERIFIED_PRODUCTION_LOAD_REQUIRED")
        self.assertTrue(all(run["gates"].values()))

    def test_c15_succession_package_and_maturity_truth_boundary(self) -> None:
        self._complete_assurance()
        target = self.root / "service-canary.json"
        self.plane.submit_service_request(
            "REQ-1", "tenant-001", "workspace.provision", {"workspace_id": "ws-1"}, "operator"
        )

        def handler(payload: dict) -> dict:
            target.write_text(json.dumps(payload), encoding="utf-8")
            return {"target": str(target), "readback_pass": json.loads(target.read_text()) == payload, "health_pass": True}

        def rollback(execution: dict) -> dict:
            target.unlink(missing_ok=True)
            return {"rollback_pass": not target.exists()}

        self.plane.execute_reference_service_request("REQ-1", handler, rollback)
        self.plane.register_outcome_study(
            "STUDY-1", "tenant-001", "cycle_time", 100, 60, "minutes", True,
            [evidence("study-1")], "REFERENCE_PROVIDER_SYNTHETIC"
        )
        self.plane.create_lead("LEAD-1", "organisation-ref", "reference", "workflow delay")
        self.plane.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000, 12)
        self.plane.run_scale_evaluation(
            "SCALE-1", "service.request", [20, 25, 30, 35, 40], 100, 0, 10, 5,
            30000, 10000, 5,
            {"max_p95_latency_ms": 50, "max_error_rate": 0.01, "max_recovery_seconds": 10, "min_gross_margin": 0.55, "max_support_hours": 10},
        )
        export = self.plane.export_succession_package(
            "PKG-1",
            {"restore": "Verify package hash, restore state, verify ledger chain.", "incident": "Fail closed and preserve evidence."},
            {"financial_commitments": "OWNER_RESERVED", "external_communications": "OWNER_RESERVED", "provider_mutation": "PROVIDER_AUTHORITY_REQUIRED"},
        )
        self.assertTrue(export["readback_pass"])
        maturity = self.plane.maturity_snapshot()
        self.assertTrue(maturity["technical_reference_ready"])
        self.assertFalse(maturity["full_commercial_maturity"])
        self.assertEqual(maturity["canonical_status"], "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN")
        self.assertFalse(maturity["external_gates"]["payment_provider_revenue"])

    def test_hash_chained_ledger_detects_tampering(self) -> None:
        self.plane.set_retention_policy("RET-1", "metadata", 30, "DELETE")
        self.assertTrue(self.plane.verify_ledger()["pass"])
        rows = self.plane.ledger_file.read_text(encoding="utf-8").splitlines()
        row = json.loads(rows[0])
        row["action"] = "tampered"
        self.plane.ledger_file.write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.assertFalse(self.plane.verify_ledger()["pass"])


if __name__ == "__main__":
    unittest.main()
